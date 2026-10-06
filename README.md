# IJPR DOE Experiments

This repository contains the CALBP DOE code, the curated benchmark instances,
the live monitoring tools, and optional published snapshots of completed runs.

## What Is Tracked

- Source code: `MILP_Audrey.py`, `MILP_V1.py`, `calbp/`, `scripts/`
- Input instances: `CAL-instances/`, `SALBP-data-sets/`
- Curated benchmark selection: `benchmark_selection.csv`
- Archived pre-regeneration experiment folders: `archive/V1_experimentation/`
- Optional Git snapshots of completed campaigns: `published_results/`

## What Is Generated Locally

The following working folders are intentionally ignored by Git:

- `results_doe_*/` for live benchmark outputs
- `logs/` for watchdog and dashboard logs
- `run_control/` for heartbeat and stop files
- `__pycache__/`, virtual environments, and other local runtime artifacts

This keeps the repository clean while still allowing deliberate publication of
final result snapshots under `published_results/`.

## Benchmark Scope

- 14 Scholl instances
- 14 Otto `n=20` instances
- 9 L9 configurations
- Total: `252` runs

The default DOE behavior is:

- factor levels defined by Taguchi `low / mid / high`
- task-level factor draws inside the selected level interval
- deterministic seeds for reproducibility
- Audrey competitive MILP profile: `C2a + C4wy`, `C5bc` disabled

With the default `task` mode:

- the DOE manifest reports factor levels
- each generated instance stores realized task-level draws in `instance.json`
- run summaries report realized per-instance means and standard deviations

To reproduce the older one-value-per-instance behavior, use:

```bash
python3 scripts/run_doe_L9.py --factor-granularity instance
```

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

CPLEX must be available through one of the following:

- `CPLEX_CMD=/absolute/path/to/cplex`
- `CPLEX_BIN=/absolute/path/to/cplex/bin/<platform>`
- `CPLEX_STUDIO_DIR=/absolute/path/to/CPLEX_StudioXXXX`
- or simply `cplex` on `PATH`

## Quick Start

Smoke test:

```bash
python3 scripts/run_doe_L9.py --smoke --time-limit 30
```

One-shot full benchmark:

```bash
python3 scripts/run_doe_L9.py --design l9 --time-limit 300 --factor-granularity task
```

Watchdog + dashboard stack:

```bash
./scripts/start_full_benchmark_stack.sh
```

Status:

```bash
./scripts/status_full_benchmark.sh
```

Stop stack:

```bash
./scripts/stop_full_benchmark_stack.sh
```

## Main Scripts

- `scripts/run_doe_L9.py`: core DOE launcher
- `scripts/start_full_benchmark_stack.sh`: starts benchmark watchdog, export watcher, and dashboard
- `scripts/watch_full_campaign.sh`: resumes the full benchmark until completion
- `scripts/start_dashboard.sh`: launches the dashboard in a detached `screen` session
- `scripts/watch_export_on_completion.sh`: exports a Git-friendly snapshot once the campaign finishes cleanly
- `scripts/export_results_snapshot.sh`: manually copies one live results tree into `published_results/`
- `scripts/collect_run_info.py`: flattens `run_info.json` files into one CSV

## Result Tree

A live results directory such as `results_doe_l9_task/` contains:

- `doe_manifest.csv`: expected `(instance, config)` matrix and DOE levels
- `doe_results.csv`: campaign-level flat summary
- `solutions/<run_name>/instance.txt`: solver input instance
- `solutions/<run_name>/instance.json`: same instance with generation metadata and task-level draws
- `solutions/<run_name>/pareto_front.csv`: Pareto points
- `solutions/<run_name>/assignments.json`: extracted decisions
- `solutions/<run_name>/run_info.json`: run summary, DOE levels, realized means/std, and indicators

## Documentation

Detailed workflow documentation is available in
[docs/BENCHMARK_WORKFLOW.md](docs/BENCHMARK_WORKFLOW.md).
