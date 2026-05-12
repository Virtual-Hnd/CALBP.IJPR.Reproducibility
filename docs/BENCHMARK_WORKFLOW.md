# Benchmark Workflow

This document explains how the repository is organized, how to launch the DOE,
what the watchdog scripts do, and how to interpret the generated files.

## 1. Repository Layout

### Source Code

- `calbp/`
  - DOE scenario construction
  - instance generation
  - input/output helpers
  - metrics and indicators
- `MILP_Audrey.py`
  - main competitive MILP solver used by the campaign
- `MILP_V1.py`
  - older reference implementation
- `scripts/`
  - launchers, watchdogs, dashboard, status, export helpers

### Input Data

- `CAL-instances/`
  - curated Scholl CAL instances
- `SALBP-data-sets/`
  - curated Otto `n=20` instances
- `benchmark_selection.csv`
  - traceability for the selected benchmark subset

### Output Data

- `results_doe_*/`
  - live working folders generated during benchmark execution
  - ignored by Git
- `archive/V1_experimentation/`
  - archived pre-regeneration result folders that are safe to keep in the
    repository when historical context is needed
- `published_results/`
  - explicit snapshots that may be versioned in Git

## 2. Git-Friendly Policy

The repository is designed so that:

- source files and curated inputs are versioned
- large transient benchmark outputs are not versioned by default
- final or intermediate snapshots can still be copied into `published_results/`
  when they need to be archived or shared

Ignored runtime folders:

- `results_doe_*/`
- `logs/`
- `run_control/`
- virtual environments and Python caches

This makes the repository safe to clone, branch, and review without dragging
live machine-specific artifacts into Git history.

## 3. DOE Semantics

The current default is `--factor-granularity task`.

That means:

- each configuration still belongs to DOE levels such as `alpha_level=low`
- each task draws its own `alpha/beta/gamma/sigma` uniformly inside the chosen
  level interval
- `run_info.json` stores the realized instance-level means and standard
  deviations
- `instance.json` stores the full task-level draw vectors

The older behavior is still available with:

```bash
python3 scripts/run_doe_L9.py --factor-granularity instance
```

## 4. Core Execution Modes

### Smoke Test

Use this first to validate the solver and the pipeline:

```bash
python3 scripts/run_doe_L9.py --smoke --time-limit 30
```

### Direct Full Run

This launches the DOE once in the foreground:

```bash
python3 scripts/run_doe_L9.py \
  --design l9 \
  --time-limit 300 \
  --factor-granularity task
```

This is the simplest option, but if the process stops, you must relaunch it
manually.

### Full Stack with Watchdog

This is the recommended option for long campaigns:

```bash
./scripts/start_full_benchmark_stack.sh
```

It starts three detached `screen` sessions:

- benchmark watchdog
- export watcher
- dashboard

## 5. Watchdog Scripts

### `scripts/watch_full_campaign.sh`

Purpose:

- launch the full benchmark
- use `--resume` so already completed runs are skipped
- restart automatically after a non-zero exit code
- stop only when the campaign succeeds or a stop file is created

Key files:

- heartbeat: `run_control/full_watchdog.heartbeat`
- log: `logs/full_watchdog.log`
- stop file: `run_control/STOP_FULL_WATCHDOG`

### `scripts/watch_export_on_completion.sh`

Purpose:

- poll the live results directory
- detect when all expected runs are complete and successful
- trigger snapshot export into `published_results/`

Key files:

- heartbeat: `run_control/export_watch.heartbeat`
- log: `logs/export_watch.log`
- stop file: `run_control/STOP_EXPORT_WATCH`

## 6. Dashboard

Start manually:

```bash
./scripts/start_dashboard.sh
```

Or as part of the full stack:

```bash
./scripts/start_full_benchmark_stack.sh
```

Default URL:

```text
http://localhost:8050/
```

The dashboard reads:

- `doe_manifest.csv`
- `doe_results.csv`
- `solutions/*/run_info.json`
- `solutions/*/pareto_front.csv`

## 7. Status and Stop Helpers

Current benchmark status:

```bash
./scripts/status_full_benchmark.sh
```

This reports:

- active `screen` sessions
- number of completed / pending runs
- latest watchdog and export logs
- dashboard availability

Stop the full stack:

```bash
./scripts/stop_full_benchmark_stack.sh
```

This:

- creates the stop files for the watchdogs
- closes the related `screen` sessions when possible

## 8. Generated Result Files

Inside a live folder such as `results_doe_l9_task/`:

### `doe_manifest.csv`

Contains:

- base instance name
- config identifier
- DOE levels (`alpha_level`, `beta_level`, `gamma_level`, `sigma_level`)
- fixed DOE metadata such as `R_e`, `C_c`, and seed

### `doe_results.csv`

Campaign-wide flat summary with one row per run. It includes:

- DOE levels
- realized means and standard deviations
- runtime and Pareto summary metrics
- indicator values

### `solutions/<run_name>/instance.txt`

Solver-ready text instance.

### `solutions/<run_name>/instance.json`

Richer generated instance with:

- DOE levels
- realized means and standard deviations
- full task-level factor draws
- mode times and energies

### `solutions/<run_name>/run_info.json`

Per-run summary with:

- solver status
- DOE levels
- realized means and standard deviations
- CPU time
- indicator values

### `solutions/<run_name>/pareto_front.csv`

Per-Pareto-point metrics such as:

- cost
- energy
- station / worker / cobot counts
- CPU time
- mode distributions

### `solutions/<run_name>/assignments.json`

Decision-variable level export for post-analysis.

## 9. Exporting a Snapshot

Manual export:

```bash
RESULTS_DIR=/path/to/results_doe_l9_task \
SNAPSHOT_LABEL=my_campaign \
./scripts/export_results_snapshot.sh
```

The exported snapshot lands in:

```text
published_results/<SNAPSHOT_LABEL>_<timestamp>/
```

This is the Git-friendly way to preserve a finished campaign without committing
the whole live working directory.

## 10. Typical End-to-End Usage

1. Install Python dependencies.
2. Make sure CPLEX is discoverable.
3. Run a smoke test.
4. Start the full stack with `./scripts/start_full_benchmark_stack.sh`.
5. Follow progress with `./scripts/status_full_benchmark.sh` or the dashboard.
6. Let the export watcher create the final snapshot automatically.
