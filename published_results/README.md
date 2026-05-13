# Published Result Snapshots

This directory contains Git-tracked snapshots of benchmark outputs that were
copied from the live working result folders.

To publish a new snapshot from a live results directory:

```bash
RESULTS_DIR=/path/to/results_doe_l9_task \
SNAPSHOT_LABEL=my_campaign \
./scripts/export_results_snapshot.sh
```

Snapshots currently published:

- `scholl_l9_final_2026-04-28_09-54-03`
  - DOE: `L9`
  - Fixed parameters: `R_e = 0.05`, `C_c = 5.0`
  - Status at snapshot time: `126 / 126` completed, `0` failed
- `otto_l9_progress_2026-04-28_09-54-03`
  - DOE: `L9`
  - Fixed parameters: `R_e = 0.05`, `C_c = 5.0`
  - Status at snapshot time: `109 / 126` completed, `0` failed
  - This is a progress snapshot, not the final Otto benchmark state
- `otto_l9_final_2026-04-29_12-09-52`
  - DOE: `L9`
  - Fixed parameters: `R_e = 0.05`, `C_c = 5.0`
  - Status at snapshot time: `126 / 126` completed, `0` failed
  - This is the final Otto benchmark snapshot
- `l9_task_progress_220of252_2026-05-13_19-21-43`
  - DOE: `L9`
  - Factor granularity: `task`
  - Status at snapshot time: `220 / 252` completed, `0` failed
  - This is a progress snapshot of the post-regeneration IJPR campaign

To launch the dashboard on a snapshot:

```bash
DOE_RESULTS_DIR=/path/to/snapshot ./.venv/bin/python scripts/dashboard.py --host 0.0.0.0 --port 8050 --no-open
```

## Archive V1 Upgrades

The historical archive under `archive/V1_experimentation/` can be exported to
the current dashboard/result schema with:

```bash
./.venv/bin/python scripts/export_archive_v1_bundle.py
```

Latest upgraded archive bundle:

- `archive_v1_newformat_2026-05-13`
  - contains one dashboard-ready snapshot per archived campaign
  - includes `results_doe_archive_l9_252`, the combined historical `252`-run L9 archive
  - adds `run_info_flat.csv`, `pareto_points_flat.csv`, `solution_assets.csv`,
    `campaign_summary.json`, and generated `instance.json` files
  - preserves the original archive CSVs as `doe_manifest_legacy.csv` and
    `doe_results_legacy.csv` when they existed
- `archive_v1_dashboard_standalone_2026-05-13`
  - standalone dashboard bundle for the upgraded archive snapshots
  - includes `html/results_doe_archive_l9_252.html` and `html/all_campaigns.html`
