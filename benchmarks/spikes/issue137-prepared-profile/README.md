# #137 native prepared profile / #138 paired verification

Authorized 2026-11-08 by the Human via dispatch task_4a5c9791be0c.
Question: remove genuinely legacy-only prepared repair contacts while retaining
embedded-text bootstrap protection and native SQL/prepared/lifecycle semantics,
then distinguish the #128 Close/capture observation race in a paired trial.
Inputs:14c3b38a drain diagnosis and ae1a8465 maintenance map; historical evidence
is immutable. Target13.0.2 source_commit620a4b5624222048fece7fe1789978ae0675cae2,
tag_object_sha308a50778fb4916ddde0d2923feea3d11dcc92c8. Product adoption/public
12.3.3 preflight are separate. No queue/credit/deadline relocation.

Before work budget: active<=2h including tooling<=20min; wall<=4h30; two sequential
fresh guest producers maximum, timeout60min each; two sequential translation/host
builds maximum30min each; suites<=15min/path; CI0/benchmark0/public expansion0.
Stop at first unresolved shared/semantic failure or budget breach, preserve
originals and unknowns; no automatic retry campaign. Known source rebasing before
builds is allowed. All owned downloads/source/SDK/cache/generated/output and
TMPDIR/GOTMPDIR must fall within the counted owned build tree, ceiling12GiB,
whole-filesystem floor12GiB sampled continuously including inside the builder.
Source selection requires complete target files/callers before omission, strict
fuzz0 and exact complete pre/postimages. Full native bindings require new review.

Initial audit: HEAD14c3b38a clean; free22.35GiB; helper dry-run no candidates/debt;
no relevant compiler/issue job in process inventory. Assigned workspace only;
parent protected files and other-worker state untouched. Existing-workspace
branch experiment/issue137-prepared-profile; helper issue137 prepared without
new worktree, floor/ceiling12GiB. Source acquisition uses ordinary pinned
scripts/prepare_guest.py under an outer guard counting the entire build tree.

## Outcome: STOPPED / implementation and acceptance incomplete

Ordinary pinned preparation fetched/verified the full MariaDB13.0.2 archive,
lite4mariadb recipe, Connector/C and wolfSSL and strictly applied the previous
profile/overlays. It then failed at scripts/prepare_guest.py:96 fetching pinned
PCRE2. The request returned HTTP504 Gateway Time-out; whether this originated
at GitHub or an intermediary was not diagnosed. One explicitly bounded manual
retry of that dependency failed with the same504. Both unedited logs are saved:
[initial-preparation.txt](evidence/initial-preparation.txt),
[dependency-retry.txt](evidence/dependency-retry.txt). No third attempt, URL/hash
substitution, dependency weakening or build retry was made. This is the first
unresolved shared acquisition failure and execution stops here.

**No #137 profile candidate was implemented or pinned, and no #138 observer was
applied.** No guest/host build, translation, generated runtime, SQL, runtime suite,
CI or benchmark ran. No fresh-success or binding evidence exists for this slice.
The historical 1c5a6d59 result and14c3b38a diagnosis remain byte-unchanged; no old
PASS is transferred. The target Git tag/commit was not reverified in this run
because build was not reached; it remains a mandatory check before any future
producer, not a claimed completed exit.

[stop.json](evidence/stop.json) records exact verified acquired bytes/digests,
incomplete prepared-file identities and zero execution counts. Preparation did
not produce build/prepared-source.json: patched source is an **incomplete**
ordinary preparation, not canonical success. Guarding counted the whole owned
build tree with12GiB ceiling/free floor throughout acquisition and retry; reused
CLI exports the initial sample but not peak/minimum samples, so no peak/minimum
measurement is invented.

## Partial source facts, not omission approval

The full target files were available for inspection: sql_prepare.cc6755 lines,
libmysql.c5009 and lib_sql.cc1587 after existing native overlays. The source and
caller search confirmed:

- Native setup_set_params chooses insert_params[_with_log]; legacy embedded
  branches choose emb_insert_params[_with_log]. The old MYSQL_BIND routines still
  exist in this source, and **zero contacts have actually been eliminated**.
- Native set_parameters asserts client_params==NULL, uses the wire conversion
  snapshot/restore around setup_conversion_functions/set_params. SQL-prepared
  is_sql_ps instead uses set_params_from_actual_params; this branch and CALL's
  stored-routine interactions must remain in the completed source review.
- lib_sql.cc's embedded_stmt_execute assigns client_params from MYSQL_STMT;
  its parameter-metadata export is called by libmysql.c's C API adapter. These
  are plausible excluded families, not complete native-unreachability proof.
- Embedded Protocol text metadata still needs the null allocation guard before
  strlen; removing the entire prepared.patch remains invalid.

[partial-source-excerpts.txt](evidence/partial-source-excerpts.txt) retains the
relevant source coordinates/hashes. Complete SQL PREPARE/EXECUTE/CALL reachability,
native profile full pre/postimages, TIME/EOF rebasing and bootstrap/source-guard
negative tests remain unfinished. No new source rule or allowlist was introduced.

## Joint #128/#131 maintenance accounting and next cost

Actual shared work: initial pinned acquisition and old-profile preparation,
network-failure triage and preservation. Actual native-specific functional
repairs0; actual removed adapter/export/MYSQL_BIND contacts0; new profile/pin/
binding repairs0 because implementation was not reached. Source review effort
is real investigation cost, not a demonstrated future repair saving. Two-profile
bookkeeping burden and native benefit remain unknown. #128 total update burden
stays INCONCLUSIVE. No basis to adopt or reverse a candidate that was not made;
retain exact old profile and the conditional reversal rules in#137.

Resumption needs the original hash-verified PCRE2 (and remaining libfmt/toolchain)
acquisition available, complete preparation/source review, then actual profile
implementation plus138 observation before either sole producer. The proposed
remaining maximum slots remain two sequential guest builds60min/path, two
translation/hosts30min/path, suites15min/path; however this stopped task does not
authorize a fresh budget or automatic resumption. Active implementation/review
cost after resolving acquisition is unknown within the original2h envelope;
previous successful producer durations are historical, not guaranteed estimates.
No rebuilt observer-only baseline should be added. Archive/capture/restore,
branch hits, exact bindings and final128candidate/public132/134 remain pending.

Verification before preservation: original128report/FAIL and14cdrain report
byte-identical to startingHEAD; evidence JSON parsed, acquired archive hashes
matched lock, failure logs/excerpts checksummed. No runtime tests run because
there is no runtime change/candidate. Estimated active10–15min including
2–4min tooling; network/ordinary preparation command wait is additional wall,
not native build/repair cost. These active buckets are estimates, not stopwatch
measurements. Initialpreparation uses a900s acquisition guard, retry180s; both
returned nonzero before timeout. Measured end snapshot: ownedbuild1.007GiB,
free21.29GiB,2026-11-08T09:37:24Z, not claimed sampled peak/minimum.

Final cleanup: preserved initial evidence commitf342dfa4 was pushed before
removing ownedsource/unpack/downloads (~1.007GiB). Helper issue137 was finalized,
cleanup dry-run inspected and apply completed; its lifecycle JSON is retained
in evidence/lifecycle.json. Helper receipt/bytecode scratch removed, tracked
build/go.mod remains. Checkout~388MiB, free22.32GiB; no retained path>1GiB,
cleanup debt0. Other workspaces/images/caches untouched. Excerpt line-prefix
whitespace was normalized after diff-check identified it; source hash and raw
failure logs are unchanged. Final diff-check passes. Orca/coordinator owns
assigned-workspace removal.
