# Timing-method correction (2026-11-16)

After the first fixed88 timing processes, source inspection found that
scripts/experiment_disk.py run_guarded checks allocated_bytes via recursive
os.walk at its default0.5second interval. This ran concurrently with benchmark
processes under experiment_workspace.py run. It also applies to previous
read-transport campaign10665616 and is an uncontrolled interference source.
No attribution of observed variability solely to this scan or to other users is
established. Guest child CPU samples do not include this supervising Python CPU.

Before observing corrected results, choose exactly one replacement timing cohort:
same binary hash, same88 processes/seed/order/SQL/parameters. No rebuild,
profile/counter rerun, or optimization adjustment. Full disk checks before and
after each process, outside measured timing; finite900s campaign deadline,
per-process180s timeout. No concurrent recursive scanner. Retain all old data
under scanning-guard-cohort; use corrected data for performance recommendation
regardless of whether results are favorable. Do not run another cohort if noisy.
Diagnosis/profiles establish mechanism with the concurrent-scanner limitation;
profile percentages are not paired causal wall-time savings.
