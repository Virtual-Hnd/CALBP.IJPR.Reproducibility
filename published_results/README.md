# Published Result Snapshots

This directory contains Git-tracked snapshots of benchmark outputs that were
copied from the live working result folders.

Snapshot included in this commit:

- `scholl_l9_final_2026-04-28_09-54-03`
  - DOE: `L9`
  - Fixed parameters: `R_e = 0.05`, `C_c = 5.0`
  - Status at snapshot time: `126 / 126` completed, `0` failed
- `otto_l9_progress_2026-04-28_09-54-03`
  - DOE: `L9`
  - Fixed parameters: `R_e = 0.05`, `C_c = 5.0`
  - Status at snapshot time: `109 / 126` completed, `0` failed
  - This is a progress snapshot, not the final Otto benchmark state

To launch the dashboard on a snapshot:

```bash
DOE_RESULTS_DIR=/path/to/snapshot ./.venv/bin/python scripts/dashboard.py --host 0.0.0.0 --port 8050 --no-open
```
