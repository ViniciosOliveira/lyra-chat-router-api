import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('release', ROOT / 'release.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class Host:
    def __init__(self):
        self.activations = 0
        self.bad = set()
    def effective(self, spec):
        return 'reviewed-effective-config'
    def activate(self, spec):
        self.activations += int(bool(spec['unit']))
    def health(self, spec, target):
        if target.name in self.bad:
            raise ValueError('injected unhealthy release')
        return {'ok': True, 'release': str(target)}


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.s = json.loads((ROOT / 'release-contract.json').read_text())
        for field in ('current', 'candidates', 'releases', 'state'):
            self.s[field] = str(root / field); Path(self.s[field]).mkdir()
        self.s['legacy'] = None; self.s['unit_template'] = None
        self.s['asset_archive'] = str(root / 'archive'); Path(self.s['asset_archive']).mkdir()
        self.s['lock'] = str(root / 'lock')
        self.sha = 'a' * 40
        self.candidate = Path(self.s['candidates']) / self.sha; self.candidate.mkdir()
        for p in (Path(self.s['current']), self.candidate):
            entry = p / self.s['entry']; entry.parent.mkdir(parents=True, exist_ok=True); entry.write_text('release')
            if self.s['kind'] == 'static':
                (p / 'assets').mkdir(); (p / 'assets/main-hash.js').write_text('asset')
        self.host = Host(); self.e = m.Engine(self.s, self.host, lambda: 1000)
        self.a = {'artifact_digest': m.fingerprint(self.candidate), 'baseline': self.e.snapshot(), 'expires': 2000}
        self.e.admission = lambda commit: self.a
        self.sleep = patch.object(m.time, 'sleep'); self.sleep.start(); self.addCleanup(self.sleep.stop)
    def plan(self):
        return self.e.dry_run(self.sha)['plan_id']
    def receipt(self, plan):
        return json.loads((Path(self.s['state']) / ('receipt-' + plan + '.json')).read_text())
    def test_dry_run_never_changes_live_code_assets_or_unit(self):
        before = self.e.snapshot(); self.plan()
        self.assertEqual(before, self.e.snapshot()); self.assertEqual(self.host.activations, 0)
        self.assertEqual(list(Path(self.s['releases']).iterdir()), [])
        self.assertEqual(list(Path(self.s['asset_archive']).iterdir()), [])
    def test_full_deploy_retains_old_directory_and_refuses_replay(self):
        plan = self.plan(); self.assertEqual(self.e.apply(plan)['status'], 'succeeded')
        self.assertEqual(Path(self.s['current']).resolve(), Path(self.s['releases']) / self.sha)
        self.assertTrue(Path(self.receipt(plan)['exchange']).is_dir())
        with self.assertRaisesRegex(ValueError, 'consumed'):
            self.e.apply(plan)
    def test_automatic_rollback_recovers_first_directory(self):
        plan = self.plan(); self.host.bad.add(self.sha)
        with self.assertRaisesRegex(RuntimeError, 'rolled_back'):
            self.e.apply(plan)
        self.assertFalse(Path(self.s['current']).is_symlink())
        self.assertEqual(self.e.snapshot(), self.a['baseline'])
    def test_explicit_rollback_once(self):
        plan = self.plan(); self.e.apply(plan)
        self.assertEqual(self.e.rollback(plan)['status'], 'rolled_back')
        with self.assertRaisesRegex(ValueError, 'consumed'):
            self.e.rollback(plan)
    def test_previous_sha_rollback(self):
        old = Path(self.s['releases']) / ('b' * 40)
        Path(self.s['current']).rename(old); Path(self.s['current']).symlink_to(old)
        self.a['baseline'] = self.e.snapshot(); plan = self.plan(); self.e.apply(plan); self.e.rollback(plan)
        self.assertEqual(Path(self.s['current']).resolve(), old)
    def test_bad_recovery_fences_even_existing_plan(self):
        plan = self.plan(); self.host.bad.update([self.sha, 'current'])
        with self.assertRaisesRegex(RuntimeError, 'intervention_required'):
            self.e.apply(plan)
        with self.assertRaisesRegex(ValueError, 'fences'):
            self.plan()
    def test_tamper_rejected_before_side_effect(self):
        plan = self.plan(); (self.candidate / self.s['entry']).write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'artifact drift'):
            self.e.apply(plan)
        self.assertEqual(self.host.activations, 0)
    def test_baseline_drift_and_expired_plan(self):
        plan = self.plan(); self.e.clock = lambda: 3000
        with self.assertRaisesRegex(ValueError, 'expired'):
            self.e.apply(plan)
        self.e.clock = lambda: 1000
        (Path(self.s['current']) / self.s['entry']).write_text('changed')
        with self.assertRaisesRegex(ValueError, 'drift'):
            self.e.apply(plan)
    def test_no_overwrite_release(self):
        (Path(self.s['releases']) / self.sha).mkdir()
        with self.assertRaisesRegex(ValueError, 'collision'):
            self.plan()
    def test_excluded_env_and_escaping_link(self):
        p = self.candidate / '.env'; p.touch()
        with self.assertRaisesRegex(ValueError, 'excluded'):
            m.fingerprint(self.candidate)
        p.unlink(); (self.candidate / 'escape').symlink_to('/etc')
        with self.assertRaisesRegex(ValueError, 'escaping'):
            m.fingerprint(self.candidate)
    def test_budget_reserves_recovery_and_counts_failure(self):
        self.e.spend({'deploy': 2}); plan = self.plan()
        with self.assertRaisesRegex(ValueError, 'budget'):
            self.e.apply(plan)
        self.assertEqual(self.host.activations, 0)
    def test_unknown_reference_rejected(self):
        with self.assertRaisesRegex(ValueError, 'invalid plan'):
            self.e.apply('../../PAY2')
    def test_static_assets_append_only_with_collision_refusal(self):
        if self.s['kind'] != 'static':
            self.skipTest('static-only asset contract')
        p = Path(self.s['asset_archive']) / 'main-hash.js'; p.write_text('different')
        with self.assertRaisesRegex(ValueError, 'collision'):
            self.e.archive_assets(self.candidate)
        self.assertEqual(p.read_text(), 'different')
    def test_versioned_unit_projection_matches_contract(self):
        spec = json.loads((ROOT / 'release-contract.json').read_text())
        if spec['unit_template']:
            self.assertEqual((ROOT / spec['unit']).read_text(), spec['unit_template'])
            self.assertNotIn('OPENCLAW_FORWARD_URL', spec['unit_template'])
    def test_new_current_preserves_legacy_env_and_restores_unit(self):
        if not self.s['unit']:
            self.skipTest('service-only bootstrap')
        legacy = Path(self.s['current']).with_name('legacy')
        Path(self.s['current']).rename(legacy)
        self.s['legacy'] = str(legacy)
        env = legacy / '.env'; env.write_text('test-fixture-no-credential')
        unit = legacy.parent / 'unit'; unit.write_text('old-unit')
        self.s['unit_file'] = str(unit); self.s['unit_template'] = 'new-unit'
        self.a['baseline'] = self.e.snapshot(); plan = self.plan(); self.e.apply(plan)
        self.assertEqual(unit.read_text(), 'new-unit')
        self.e.rollback(plan)
        self.assertEqual(unit.read_text(), 'old-unit')
        self.assertEqual(env.read_text(), 'test-fixture-no-credential')
        self.assertFalse(Path(self.s['current']).exists())


if __name__ == '__main__':
    unittest.main()
