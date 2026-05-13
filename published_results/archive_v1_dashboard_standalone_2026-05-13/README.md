# Archive Dashboard Standalone

This folder is a self-contained dashboard bundle for the upgraded archive
snapshots.

## Included campaigns

- `results_doe_L9`
- `results_doe_archive_l9_252`
- `results_doe_otto_l9`
- `results_doe_scholl_l36`
- `results_doe_scholl_l9`

## Launch

From a terminal:

```bash
cd "/Users/admin/Desktop/AMine/published_results/archive_v1_dashboard_standalone_2026-05-13"
./launch_dashboard.sh results_doe_scholl_l9
```

Or double-click `launch_dashboard.command` on macOS.

Standalone HTML pages are also available directly:

```text
/Users/admin/Desktop/AMine/published_results/archive_v1_dashboard_standalone_2026-05-13/index.html
/Users/admin/Desktop/AMine/published_results/archive_v1_dashboard_standalone_2026-05-13/html/all_campaigns.html
/Users/admin/Desktop/AMine/published_results/archive_v1_dashboard_standalone_2026-05-13/html/results_doe_scholl_l9.html
```

Optional environment variables:

```bash
HOST=0.0.0.0 PORT=8050 PYTHON_BIN=python3 ./launch_dashboard.sh results_doe_otto_l9
```

## Notes

- `dashboard.py` is copied from the current repo version.
- The result folders come from:
  `/Users/admin/Desktop/AMine/published_results/archive_v1_newformat_2026-05-13`
- Each campaign directory is already in the new dashboard/result format.
- The dashboard serves one campaign at a time. Pick the campaign name as the
  first argument of `launch_dashboard.sh`.
- The `html/` directory contains static standalone snapshots with embedded data.
- `html/all_campaigns.html` groups all archive campaigns in one page with a
  campaign selector in the header.
