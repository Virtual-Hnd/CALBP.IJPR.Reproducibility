# Archive V1 Export Bundle

This bundle contains upgraded snapshots exported from `archive/V1_experimentation`.
Each subdirectory is a standalone results folder compatible with the current dashboard.

## Campaigns

- `results_doe_L9`
  - source: `/Users/admin/Desktop/AMine/archive/V1_experimentation/results_doe_L9`
  - runs: `36` | Pareto points: `100` | configs: `9` | instances: `4`
  - dashboard root: `/Users/admin/Desktop/AMine/published_results/archive_v1_newformat_2026-05-13/results_doe_L9`
- `results_doe_archive_l9_252`
  - source: `results_doe_scholl_l9 + results_doe_otto_l9`
  - runs: `252` | Pareto points: `1075` | configs: `9` | instances: `28`
  - dashboard root: `/Users/admin/Desktop/AMine/published_results/archive_v1_newformat_2026-05-13/results_doe_archive_l9_252`
- `results_doe_otto_l9`
  - source: `/Users/admin/Desktop/AMine/archive/V1_experimentation/results_doe_otto_l9`
  - runs: `126` | Pareto points: `676` | configs: `9` | instances: `14`
  - dashboard root: `/Users/admin/Desktop/AMine/published_results/archive_v1_newformat_2026-05-13/results_doe_otto_l9`
- `results_doe_scholl_l36`
  - source: `/Users/admin/Desktop/AMine/archive/V1_experimentation/results_doe_scholl_l36`
  - runs: `120` | Pareto points: `316` | configs: `36` | instances: `4`
  - dashboard root: `/Users/admin/Desktop/AMine/published_results/archive_v1_newformat_2026-05-13/results_doe_scholl_l36`
- `results_doe_scholl_l9`
  - source: `/Users/admin/Desktop/AMine/archive/V1_experimentation/results_doe_scholl_l9`
  - runs: `126` | Pareto points: `399` | configs: `9` | instances: `14`
  - dashboard root: `/Users/admin/Desktop/AMine/published_results/archive_v1_newformat_2026-05-13/results_doe_scholl_l9`

## Notes

- The archive did not contain raw solver console logs.
- The execution traces available for interpretation are `run_info.json`, `pareto_front.csv`, `assignments.json`, `instance.txt`, and the generated `instance.json`.
- `run_info_flat.csv` and `pareto_points_flat.csv` were generated to help co-authors work directly in spreadsheets.
