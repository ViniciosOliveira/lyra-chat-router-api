#!/usr/bin/env python3
"""Fixed-contract release adapter; external admitted controller required."""
import argparse
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.request
import uuid


def check(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(root, baseline=False):
    check(root.is_dir(), 'missing source directory')
    result = []
    for p in sorted(root.rglob('*')):
        parts = p.relative_to(root).parts
        excluded = any(x in {'.git', '.venv', 'venv', '__pycache__', 'data', 'logs', 'uploads', 'backups'}
                       or x.startswith('.env') or x.endswith(('.db', '.sqlite', '.sqlite3', '.pyc')) for x in parts)
        if excluded:
            check(baseline, 'data/credential/dependency artifact excluded')
            continue
        if p.is_symlink():
            check(baseline or (not os.path.isabs(os.readlink(p)) and p.resolve().is_relative_to(root.resolve())),
                  'escaping artifact symlink')
            value = 'link:' + os.readlink(p)
        elif p.is_file():
            check(not p.stat().st_mode & 0o6000, 'setid file')
            value = sha(p.read_bytes())
        elif p.is_dir():
            continue
        else:
            raise ValueError('special file')
        result.append([p.relative_to(root).as_posix(), p.lstat().st_mode & 0o777, value])
    return sha(json.dumps(result, separators=(',', ':')).encode())


def atomic_json(path, value):
    check(not path.is_symlink(), 'state symlink')
    tmp = path.with_name('.' + path.name + uuid.uuid4().hex)
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(value, f, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def exchange(first, second):
    """Linux atomic exchange also handles first deployment from a real directory."""
    libc = ctypes.CDLL(None, use_errno=True)
    fn = libc.renameat2
    fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    fn.restype = ctypes.c_int
    if fn(-100, os.fsencode(first), -100, os.fsencode(second), 2):
        raise OSError(ctypes.get_errno(), 'atomic exchange failed')


class Host:
    def run(self, *cmd):
        return subprocess.run(cmd, capture_output=True, text=True, check=True,
                              timeout=120 if 'restart' in cmd or 'daemon-reload' in cmd else 3).stdout.strip()

    def effective(self, spec):
        if spec['unit']:
            self.run('/usr/bin/systemctl', 'is-active', '--quiet', spec['unit'])
            return sha(self.run('/usr/bin/systemctl', 'cat', spec['unit']).encode())
        # The effective parsed configuration, not a guessed sites-enabled filename.
        self.run('/usr/sbin/nginx', '-t')
        config = self.run('/usr/sbin/nginx', '-T')
        check(spec['current'] in config and spec['asset_archive'] in config,
              'nginx current/assets contract not installed; bootstrap required')
        return sha(config.encode())

    def activate(self, spec):
        if spec.get('unit_template'):
            self.run('/usr/bin/systemctl', 'daemon-reload')
        if spec['unit']:
            self.run('/usr/bin/systemctl', 'restart', spec['unit'])
        # Static current replacement needs no Nginx reload/restart.

    def health(self, spec, target):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args):
                return None
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        req = urllib.request.Request(spec['health'], headers={'Cache-Control': 'no-cache'})
        with op.open(req, timeout=3) as response:
            check(response.status == 200, 'health HTTP')
            raw = response.read(4 * 1024 * 1024)
        if spec['kind'] == 'static':
            check(sha(raw) == sha((target / 'index.html').read_bytes()), 'served index differs from release')
        else:
            data = json.loads(raw)
            for key, expected in spec['health_fields'].items():
                check(data.get(key) == expected, 'health contract')
            if spec.get('required_openapi_paths'):
                check(set(spec['required_openapi_paths']) <= set(data.get('paths', {})), 'OpenAPI regression')
            pid = self.run('/usr/bin/systemctl', 'show', spec['unit'], '-p', 'MainPID', '--value')
            check(pid.isdecimal() and int(pid) > 0, 'main PID')
            check(Path('/proc', pid, 'cwd').resolve() == target.resolve(), 'wrong release process cwd')
        return {'ok': True, 'release': str(target)}


class Engine:
    def __init__(self, spec, host, clock=time.time):
        self.s, self.h, self.clock = spec, host, clock
        self.state = Path(spec['state'])
        self.current = Path(spec['current'])
        self.releases = Path(spec['releases'])

    def previous(self):
        if self.current.is_symlink():
            p = self.current.resolve(strict=True)
            check(p.parent == self.releases and re.fullmatch('[0-9a-f]{40}', p.name), 'invalid current target')
            return p
        if self.current.is_dir():
            return self.current
        check(not self.current.exists() and self.s.get('legacy'), 'current missing; explicit bootstrap required')
        old = Path(self.s['legacy'])
        check(old.is_dir() and not old.is_symlink(), 'legacy baseline missing')
        return old

    def snapshot(self):
        p = self.previous()
        return {'target': str(p), 'code': fingerprint(p, baseline=True), 'effective': self.h.effective(self.s)}

    def unresolved(self):
        for p in self.state.glob('receipt-*.json'):
            check(json.loads(p.read_text())['status'] not in ('started', 'intervention_required'), 'unresolved receipt fences deploy')

    def spend(self, amounts):
        f = self.state / 'budget.json'
        rows = json.loads(f.read_text()) if f.exists() else []
        rows = [r for r in rows if r['time'] > self.clock() - 86400]
        for name, count in amounts.items():
            check(sum(r['used'].get(name, 0) for r in rows) + count <= self.s['budget'][name], 'budget exhausted')
        rows.append({'time': self.clock(), 'used': amounts}); atomic_json(f, rows)

    def admission(self, commit):
        check(re.fullmatch('[0-9a-f]{40}', commit), 'full lowercase SHA required')
        f = self.state / 'admissions' / (commit + '.json')
        check(not f.is_symlink() and f.stat().st_uid == 0 and not f.stat().st_mode & 0o022, 'admission ownership')
        a = json.loads(f.read_text())
        check(a['sha'] == commit and a['expires'] > self.clock(), 'admission expired/mismatched')
        for key in ('merged_ci_verified', 'schema_unchanged', 'dependency_runtime_unchanged',
                    'runtime_data_paths_verified', 'worker_compatibility_verified'):
            check(a[key] is True, 'unverified prerequisite: ' + key)
        check(a['canary']['result'] == 'passed' or
              (a['canary']['result'] == 'unavailable' and a['canary']['evidence']), 'canary not passed or explained')
        for key in ('demand_id', 'approval_source', 'profile_digest', 'journal_head'):
            check(bool(a[key]), 'missing receipt authority evidence')
        check(a['script_digest'] == sha(Path(__file__).read_bytes()), 'script drift')
        check(a['contract_digest'] == sha(json.dumps(self.s, sort_keys=True).encode()), 'contract drift')
        return a

    def dry_run(self, commit):
        self.unresolved()
        check(self.current.parent.is_dir() and not self.current.parent.is_symlink(), 'current parent bootstrap missing')
        if self.s['kind'] == 'static':
            check(Path(self.s['asset_archive']).is_dir() and not Path(self.s['asset_archive']).is_symlink(), 'asset archive bootstrap missing')
        if self.s.get('unit_template'):
            check(not Path(self.s['unit_file']).is_symlink(), 'unit fragment symlink needs review')
        a = self.admission(commit)
        candidate = Path(self.s['candidates']) / commit
        check(candidate.is_dir() and not candidate.is_symlink(), 'candidate must be real directory')
        check(fingerprint(candidate) == a['artifact_digest'], 'candidate not admitted')
        check((candidate / self.s['entry']).is_file(), 'runtime entry missing')
        check(self.snapshot() == a['baseline'], 'baseline drift')
        release = self.releases / commit
        check(not release.exists() and not release.is_symlink(), 'release collision')
        self.spend({'dry_run': 1})
        plan_id = uuid.uuid4().hex
        plan = {'id': plan_id, 'commit': commit, 'admission': a,
                'before': a['baseline'], 'expires': min(a['expires'], self.clock() + 1800),
                'exchange': str(self.current.with_name('.previous-' + plan_id))}
        atomic_json(self.state / ('plan-' + plan_id + '.json'), plan)
        return {'plan_id': plan_id, 'live_mutations': 0}

    def archive_assets(self, candidate):
        if self.s['kind'] != 'static':
            return
        archive = Path(self.s['asset_archive'])
        check(archive.is_dir() and not archive.is_symlink(), 'asset archive must be bootstrapped')
        source = candidate / 'assets'
        check(source.is_dir(), 'static assets absent')
        for p in sorted(source.rglob('*')):
            check(not p.is_symlink(), 'asset symlink forbidden')
            if not p.is_file():
                continue
            destination = archive / p.relative_to(source)
            check(not any(x.is_symlink() for x in [destination, *destination.parents]), 'asset path symlink')
            if destination.exists():
                check(sha(destination.read_bytes()) == sha(p.read_bytes()), 'hashed asset collision')
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as out:
                out.write(p.read_bytes()); out.flush(); os.fsync(out.fileno())
            destination.chmod(0o644)

    def health(self, target):
        for _ in range(6):
            try:
                return self.h.health(self.s, target)
            except Exception:
                time.sleep(2)
        raise RuntimeError('health/release readback failed')

    def install_unit(self, content):
        if not self.s.get('unit_template'):
            return
        dest = Path(self.s['unit_file'])
        temp = dest.with_name('.' + dest.name + uuid.uuid4().hex)
        temp.write_text(content); temp.chmod(0o644); os.replace(temp, dest)

    def restore(self, r):
        previous = Path(r['before']['target'])
        swapped = Path(r['exchange'])
        old = swapped if previous == self.current else previous
        check(fingerprint(old, baseline=True) == r['before']['code'], 'previous source drift before recovery')
        if previous == Path(self.s.get('legacy') or '/') and previous != self.current:
            if self.current.is_symlink():
                self.current.unlink()
        elif previous == self.current:
            check(swapped.is_dir() and not swapped.is_symlink(), 'first-deploy backup absent')
            exchange(self.current, swapped)
        else:
            temp = self.current.with_name('.restore-' + uuid.uuid4().hex)
            temp.symlink_to(previous); os.replace(temp, self.current)
        if self.s.get('unit_template'):
            self.install_unit(r['unit_before'])
        self.h.activate(self.s)
        return self.health(self.previous())

    def apply(self, plan_id):
        check(re.fullmatch('[0-9a-f]{32}', plan_id), 'invalid plan ID')
        self.unresolved()
        p = json.loads((self.state / ('plan-' + plan_id + '.json')).read_text())
        receipt = self.state / ('receipt-' + plan_id + '.json')
        check(not receipt.exists(), 'plan consumed')
        check(p['expires'] > self.clock(), 'dry-run expired')
        check(self.admission(p['commit']) == p['admission'] and self.snapshot() == p['before'], 'drift after dry-run')
        candidate = Path(self.s['candidates']) / p['commit']
        check(fingerprint(candidate) == p['admission']['artifact_digest'], 'artifact drift')
        release = self.releases / p['commit']
        check(not release.exists() and not release.is_symlink(), 'release collision')
        temp = Path(p['exchange'])
        check(not temp.exists() and not temp.is_symlink(), 'backup collision')
        self.spend({'deploy': 1, 'rollback': 1, 'restart': 2 if self.s['unit'] else 0, 'health': 20})
        r = {**p, 'status': 'started', 'rollback': None}
        if self.s.get('unit_template'):
            r['unit_before'] = Path(self.s['unit_file']).read_text()
        atomic_json(receipt, r)
        activated = False
        try:
            shutil.copytree(candidate, release, symlinks=True)
            check(fingerprint(release) == p['admission']['artifact_digest'], 'copied artifact mismatch')
            self.archive_assets(self.previous())
            self.archive_assets(release)
            temp.symlink_to(release)
            # Existing directory or symlink is retained exactly at exchange path.
            if self.current.exists() or self.current.is_symlink():
                exchange(self.current, temp)
            else:
                os.replace(temp, self.current)
            activated = True
            if self.s.get('unit_template'):
                self.install_unit(self.s['unit_template'])
            self.h.activate(self.s)
            r['health'] = self.health(release)
            r['effective_after'] = self.h.effective(self.s)
            r['status'] = 'succeeded'
        except Exception:
            r['status'] = 'failed_before_activation'
            if activated:
                try:
                    r['rollback'] = self.restore(r); r['status'] = 'rolled_back'
                except Exception:
                    r['status'] = 'intervention_required'
            atomic_json(receipt, r)
            raise RuntimeError('deploy failed; ' + r['status']) from None
        atomic_json(receipt, r)
        return {'status': r['status'], 'receipt': str(receipt)}

    def rollback(self, plan_id):
        check(re.fullmatch('[0-9a-f]{32}', plan_id), 'invalid plan ID')
        receipt = self.state / ('receipt-' + plan_id + '.json')
        r = json.loads(receipt.read_text())
        check(r['status'] == 'succeeded' and r['rollback'] is None, 'rollback already consumed')
        check(self.previous() == self.releases / r['commit'], 'current changed')
        check(self.h.effective(self.s) == r['effective_after'], 'effective config changed since deploy')
        old = Path(r['exchange']) if Path(r['before']['target']) == self.current else Path(r['before']['target'])
        check(fingerprint(old, baseline=True) == r['before']['code'], 'previous source drift')
        r['status'] = 'started'; r['rollback'] = {'attempted': True}; atomic_json(receipt, r)
        try:
            r['rollback'] = self.restore(r); r['status'] = 'rolled_back'
        except Exception:
            r['status'] = 'intervention_required'; atomic_json(receipt, r)
            raise RuntimeError('rollback failed; intervention_required') from None
        atomic_json(receipt, r)
        return {'status': r['status']}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('action', choices=['dry-run', 'apply', 'rollback']); ap.add_argument('reference')
    args = ap.parse_args()
    check(os.geteuid() == 0, 'admitted root controller required')
    contract = Path(__file__).with_name('release-contract.json')
    check(contract.stat().st_uid == 0 and not contract.stat().st_mode & 0o022 and not contract.is_symlink(), 'untrusted contract')
    spec = json.loads(contract.read_text())
    for p in [Path(spec['state']), Path(spec['state']) / 'admissions', Path(spec['releases']), Path(spec['candidates'])]:
        check(p.is_dir() and not p.is_symlink() and p.stat().st_uid == 0 and not p.stat().st_mode & 0o022, 'unsafe bootstrap path')
    fd = os.open(spec['lock'], os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        e = Engine(spec, Host())
        print(json.dumps({'dry-run': e.dry_run, 'apply': e.apply, 'rollback': e.rollback}[args.action](args.reference)))


if __name__ == '__main__':
    main()
