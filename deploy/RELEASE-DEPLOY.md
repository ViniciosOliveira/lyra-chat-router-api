# lyra-chat-router-api: immutable release adapter

Source-only proposal. No deployment, database operation or credential change.
`release.py` is the only proposed entrypoint for `lyra-chat-router-api` in the production profile.
No manual exception is permitted while this PR or controller binding is pending.

| Contract     | Value                                                |
| ------------ | ---------------------------------------------------- |
| Host         | backends                                             |
| Kind         | python                                               |
| Unit         | lyra-chat-router-api.service                         |
| Current      | `/opt/lyra-chat-router-runtime/current`              |
| SHA releases | `/opt/lyra-chat-router-releases/<sha40>`             |
| Candidates   | `/opt/lyra-chat-router-api-candidates/<sha40>`       |
| Health       | `http://127.0.0.1:3201/googlechat/health`            |
| Lock         | `/run/lock/lyra-chat-router-api-release-deploy.lock` |
| State        | `/var/lib/lyra-chat-router-api-deploy`               |
| Assets       | not applicable                                       |

## Controller admission and mandatory dry-run

Provision merged digest-pinned code at `/opt/lyra-chat-router-api-deploy/repository/deploy/` and
root-owned directories in release-contract.json. State/admissions are 0700;
contract, adapter and tickets must not be writable by non-root identities. No
CLI/environment override of paths, unit, command or HTTP endpoint is accepted.
Replacing lyra-chat-router-api below means the fixed repository name, not a deploy argument.

```text
/usr/bin/python3 /opt/lyra-chat-router-api-deploy/repository/deploy/release.py dry-run <sha40>
/usr/bin/python3 /opt/lyra-chat-router-api-deploy/repository/deploy/release.py apply <plan_id32>
/usr/bin/python3 /opt/lyra-chat-router-api-deploy/repository/deploy/release.py rollback <plan_id32>
```

An external admitted controller provisions a root:root 0600
`state/admissions/<sha40>.json`. Required fields are enforced by `admission()`:
sha, expires (Unix seconds), script_digest, contract_digest (SHA256 of sorted-key
JSON), artifact_digest from fingerprint(candidate), baseline from snapshot(),
merged_ci_verified, schema_unchanged, dependency_runtime_unchanged,
runtime_data_paths_verified, worker_compatibility_verified, demand_id,
approval_source, profile_digest, journal_head and canary result/evidence.
These attestations require real evidence. Creating a JSON ticket does not grant
authority; the profile stays blocked until an enforceable controller is admitted.
No adapter command creates tickets or approves a deployment.

Build the exact merged SHA on an isolated builder with the repository's pinned
runtime/lockfile and green CI; scan before admission. Transfer a clean artifact,
never live data, env, .git, venv or caches. Python uses existing pinned environment:
no pip install, no venv relocation, no dependency replacement in deployment. The
controller must prove dependencies match the source and remain unchanged for
rollback. Static artifacts include index.html and hashed assets from the build.

Migrations: **none are executed**. Compare schema, startup DDL, migration history,
worker compatibility and data paths against the active baseline. Changed schema
or dependency runtime requires a separate reviewed plan and remains blocked here;
never run down migrations during rollback. When an isolated canary is available,
require it green before general; otherwise record concrete unavailable evidence.
No billing, provider send, PAY2, wallet, Router selectors, cron rewrite, environment
mutation, backdoor, shell argument or manual fallback is part of this adapter.

Dry-run records a 30-minute plan and preflight budget only. It does not copy a
release, switch pointers, install units, restart, call application health or run
migrations. Apply rechecks admission, baseline and candidate; plans are single-use.
Exclusive flock surrounds CLI operations. Production health checks and restarts
are fixed in the contract, not supplied by the caller.

## Release, health and recovery

Apply copies an immutable SHA release (collision is refused), verifies its digest,
retains the original current directory/symlink at `.previous-<plan_id>` using Linux
renameat2 atomic exchange, and switches current. No file is deleted or release
pruned. A new-current bootstrap preserves the original legacy directory intact.
Health requires the exact served index for static sites; Python requires declared
JSON/OpenAPI and MainPID cwd at the SHA. No authenticated/payment mutation smoke.

A failed activation recovers the captured previous release with at most one
restart; a failed rollback or crash leaves intervention_required/started and
fences even previously prepared plans. Explicit rollback accepts only its own
successful receipt while its release is current and previous code is unchanged.
The original unit fragment is captured in private state if a template changes it;
existing drop-ins remain installed, and their effective hash is rechecked. No
unit template is installed by this source PR.

Budgets rolling 24h: dry_run24, deploy2, rollback2, restart4, health60. Apply reserves
one deploy, one recovery, two service restarts (zero for static), twenty reserved (at most twelve used) bounded
health attempts before side effects. Failed attempts count. No automatic budget
increase. Local receipts do not replace the controller's canonical hash-chain.

After first proven deployment, inventory old directories, processes and rollback
references before proposing a separate dated archival plan. Do not delete a
`.previous-*` directory while a receipt references it. No automatic cleanup.

## CI dry-run

`python3 -m unittest discover -s deploy/tests -v` exercises real temporary-file
atomic exchanges and fake host activation: dry-run no effects, replay/drift/expiry,
release collision, secret-path rejection, symlink escape, budgets, health failure,
first-directory recovery, previous-SHA recovery and single-use explicit rollback.
CI has no SSH, provider credentials or production network access.

## Existing environment and workers

The old directory stays intact, including its .env (never read/copied by this
adapter). The reviewed unit changes WorkingDirectory only; it preserves the old
EnvironmentFile, interpreter, bind address and port. Existing drop-ins remain.
Worker units are not restarted or silently repointed: controller admission must
prove cross-version compatibility; otherwise a coordinated worker plan is needed.
Router forwarding/hook selectors are not read, rewritten or smoke-dispatched.

Host commands have explicit timeouts: 3s for readback, 120s for restart/reload.
Each health phase attempts at most six probes (3s HTTP, 3s PID readback, 2s delay).
The controller must additionally impose a wall-clock deadline on its entire job;
local receipts fence a timed-out or interrupted operation instead of retrying it.
