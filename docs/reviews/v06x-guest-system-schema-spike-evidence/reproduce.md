# Routine feasibility reproduction

This is a development-unqualified-v1 experiment, not a product recipe. Use
experiment/guest-system-schema, based on 866c17e7c64c7b0bee73b3e5b42a1b83982d4378.
The report pins actual build source and all inputs; later docs/probe commits do
not become tested runtime identities. Protect unrelated main state.

1. Create the experiment branch explicitly at the pinned866c17e commit before
   calling prepare --branch on it (new branches otherwise start at current HEAD).
   Prepare an experiment workspace with 16 GiB free-space floor and 32 GiB budget.
   Inspect the three commits with scripts/git_identity.py (git-input-identities.json).
   Verify the MariaDB source archive SHA256 against release/inputs.lock.json and
   extract the two scripts, VERSION and selected source files to temp/source.
2. From the clean pinned source, seed temp/builder-build/go.mod with build/go.mod,
   create fresh temp/linux-root and temp/linux-work and worktree/build/downloads.
   Under the retained disk guard, run the existing
   benchmarks/spikes/prepared-bridge/guest-command.sh. It uses the pinned builder
   sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f
   and build_generated_guest.py --development-output <TASK>/temp/dev-guest.
   No canonical or experimental guest patch changes are needed for this spike.
3. Use Python 3.14 with PyMySQL==1.2.3 and pytest==8.4.2 in a task-local venv.
   Connector/Python is deliberately not imported by this SQL-only probe. Its
   prepared support remains a separate decision, not repaired or regressed here.
4. Set MARIAMEM_DEV_WORKSPACE to the absolute task root and GOTOOLCHAIN=go1.26.8.
   Under the disk guard invoke scripts/regenerate_release_guest.py --development
   --guest-dir <TASK>/temp/dev-guest --output <TASK>/temp/dev-native. Keep the
   official source, Wasm, translation, installation and development receipts.
5. Start the disposable native reference from
   mariadb@sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1
   with empty local root password, test DB and 127.0.0.1:57019:3306.
   This is Linux arm64 in Docker, not Ubuntu x86_64 qualification.
6. Run probe.py with --source <TASK>/temp/source --mode baseline, proc-only,
   damaged-proc and base-fix, each --output <evidence>/<mode>.json. Guest calls
   additionally supply --host <TASK>/temp/dev-native/mariamem-dev-host and
   PYTHONPATH=<TASK>/temp/dev-native/product/python. Each guest call creates a
   fresh DB. Native controls omit --host and use --port 57019. Native baseline
   starts with installed system schema; native base/fix replays against existing
   tables. Do not call those starting states identical to an empty guest.
7. The probe handles DELIMITER in the fixed upstream scripts, preserves SQL
   statements and records all failures without treating them as successful.
   Official fix is an upgrade script that permits duplicate/old-column errors;
   the new-install script uses a different script set (source-review.json).
8. For diagnostics compile cost.go.txt as a .go file under tests/guest_system_schema_cost/
   in the isolated generated product, after the official route finishes its
   source-inventory checks. This is an authored probe, not generated-Go editing.
   Build with -p 1 -trimpath -buildvcs=false to reuse the same compile inputs. Feed
   cost-sql.json (statement lists derived by the same parser). Run alternating
   modes, then --only control/proc/base-fix in separate processes. Cold means
   first Start in that process, without flushing OS caches; warm means later
   independent empty DBs. This is not a performance acceptance campaign.
9. Keep exact error logs and compare routine results with native, including
   intermediate result rows, terminal OK, 1644 SIGNAL and connection reuse.
   A controlled nullable comment column must produce1728 and an ordinal15
   NOT NULL diagnostic; restoring the official definition must restore cases.
   That does not identify the unprovided historical Web REPL manual DDL.
10. Stop owned processes, preserve compact checksummed evidence and pushed refs,
    finalize and remove recreatable task worktree/build/cache. Do not merge,
    qualify, tag or release. Return to Human Review.

## Verify/materialize compact evidence

The Git evidence bundle uses files.json with stored/original hashes and explicit
original_name. Before replaying assess.py, materialize originals in a fresh task
temp directory (never overwrite source):

```python
import gzip, hashlib, json
from pathlib import Path
bundle = Path("docs/reviews/v06x-guest-system-schema-spike-evidence")
replay = Path("/absolute/owned-task/temp/replay")
replay.mkdir(parents=True, exist_ok=False)
for stored, info in json.loads((bundle / "files.json").read_text()).items():
    data = (bundle / stored).read_bytes()
    assert hashlib.sha256(data).hexdigest() == info["stored_sha256"]
    raw = gzip.decompress(data) if info["encoding"] == "gzip" else data
    assert hashlib.sha256(raw).hexdigest() == info["original_sha256"]
    target = replay / info["original_name"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
```

Run `python <replay>/assess.py <replay>` and retain the full-fix FAIL1193 rather
than turning the overall minimum feasibility PASS into an all-checks PASS.
Raw probe-initial.py belongs to the first native controls; probe-native-final.py
is the six-case native source before adding the separate source-revision query.
probe.py is the final guest source. The added identity query does not alter any
case oracle. The independent-generation comparison reuses the previous paired
52-file inventories; new provenance is kept rather than normalized.
