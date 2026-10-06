# First Selection Instances Package

Generated: 2026-07-22

This folder contains only the first analysis selection requested:

- Scholl_MERTENS
- Scholl_BOWMAN8
- Scholl_JAESCHKE
- Scholl_JACKSON
- Scholl_MANSOOR
- Otto_instance_n=20_69 (source campaign name: instance_n=20_69)
- Otto_instance_n=20_74 (source campaign name: instance_n=20_74)
- Otto_instance_n=20_288
- Otto_instance_n=20_455

Contents:

- `doe_results.csv`: DOE summary rows for the selected instances only.
- `doe_manifest.csv`: compact provenance table with source campaign for each run.
- `all_pareto_fronts.csv`: all Pareto points from selected runs.
- `all_run_info.csv`: flattened run metadata.
- `all_epsilon_trace.csv`: epsilon-constraint trace rows.
- `solutions/`: copied MILP solution folders, including generated instance files and per-run CSV/JSON outputs.

Source campaigns used:

- `full_campaign_median_T_252_2026-06-04`
- `extra_remaining_instances_2026-06-10`
