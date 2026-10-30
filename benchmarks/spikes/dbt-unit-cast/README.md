# dbt1.8 signed integer fixture CAST experiment

Authorized2026-10-31 after the unmodified native1064/42000 result. Question:
can a project-local `mariadb__safe_cast` override make the exact two-row integer
model unit test pass and a wrong expectation fail, on native first and guest
if time remains? This is not adapter/product support or a release prerequisite.

Adapter source_commit d4186f78984aa891f73d3f256f5780630878b21f, dbt-core1.8.7,
original resolved dependencies from the previous unit probe, native12.3.3 exact
digest. The adapter's installed Python source is not patched. The experimental
project macro changes only signed integer fixture casts to CAST AS SIGNED.
No unsigned/overflow/string/decimal/date/NULL coverage or general safe_cast
semantics is claimed. The original failure remains separate evidence.

Exit: same case before/after, a deliberately wrong expected doubled value,
original SQL/errors and subsequent SELECT/cleanup. Stop on the next blocker;
no second layer of adapter fixes in this task. <=30min active including <=10min
tooling, zero heavy CI. Native is amd64 emulated on local macOS arm64; no Ubuntu
coverage or comparative speed claim. No main, guest/generated/API or release
change. This branch excludes the one-off Ubuntu workflow override; that ongoing
CI remains bound to7a9a6f72.
