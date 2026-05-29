# CCGit Tool — ClearCase to Git Migration Utility
A lightweight migration utility that exports ClearCase VOBs into clean Git repositories. Built as an intern project to support the team's eventual transition from ClearCase to GitHub Enterprise.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage — Web UI](#usage--web-ui)
- [Usage — CLI](#usage--cli)
- [Running Tests](#running-tests)
- [Project Structure](#project-structure)
- [Known Limitations](#known-limitations)
- [Future Roadmap](#future-roadmap)

---

## Overview

CCGit Tool automates the process of:

1. Connecting to a ClearCase VOB
2. Exporting the latest snapshot (or a specific baseline)
3. Creating a clean Git repository from the migrated files
4. Validating migration integrity (file count comparison, optional checksums)
5. Generating migration logs and reports

The tool supports both a **Flask web UI** for interactive use and a **CLI** for scripting and automation.

> **Important:** This tool is a proof-of-concept migration aid. It is not intended for production-scale enterprise migration without further testing and sign-off from the team.

---

## Architecture

```
+----------------------+
| Flask Web UI         |  ← browser-based migration form + log viewer
+----------------------+
           |
           v
+----------------------+
| Migration Engine     |  ← orchestrates the full pipeline
+----------------------+
           |
    ───────────────
    |             |
    v             v
+-----------+  +----------+
| ClearCase |  | Git      |
| Adapter   |  | Adapter  |
+-----------+  +----------+
    (cleartool)  (GitPython)
           |
           v
+----------------------+
| Validator & Reports  |  ← file count checks, JSON reports, log files
+----------------------+
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | Tested on 3.10 and 3.11 |
| ClearCase client | `cleartool` must be on PATH |
| ClearCase view access | Read access to the target VOB |
| Git 2.x | Must be installed and on PATH |

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.sce.com/ems-apps/ccgit-tool.git
cd ccgit-tool

# 2. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and edit the config
cp configs/config.yaml configs/config.local.yaml
# Edit config.local.yaml with your VOB path, output dir, etc.
```

---

## Configuration

Edit `configs/config.yaml` (or a local copy) before running any migration.

```yaml
clearcase:
  view_path: /views/dev_view       # path to your ClearCase view
  vob_path: /vobs/project_vob      # path to the VOB to migrate
  baseline: ""                     # optional: e.g. REL_1

git:
  output_dir: /repos/output        # where the Git repo will be created

migration:
  repo_name: migrated_repo         # name of the output Git repo folder
  dry_run: false                   # true = preview only, no files written
  validate: true                   # run file-count validation after migration
  preserve_tags: false             # convert CC labels to Git tags
  checksums: false                 # MD5 checksum verification (slower)
```

> **Security:** Never hardcode credentials. Use environment variables for anything sensitive.

---

## Usage — Web UI

```bash
python run.py --web
```

Open your browser to: **http://localhost:5000**

The UI provides:
- **Dashboard** — recent migration history and status
- **New Migration form** — configure VOB path, repo name, baseline, and options
- **Progress view** — live status updates while migration runs
- **Results page** — file counts, validation status, downloadable logs

---

## Usage — CLI

```bash
# Basic migration
python run.py --repo billing_app

# With a specific baseline
python run.py --repo billing_app --baseline REL_1

# Dry run — preview without writing anything
python run.py --repo billing_app --dry-run

# Full options
python run.py --repo billing_app --baseline REL_1 --dry-run --validate --preserve-tags

# Custom config file
python run.py --repo billing_app --config configs/config.local.yaml
```

### CLI flags

| Flag | Description |
|---|---|
| `--repo` | ClearCase repository/VOB name (required for CLI) |
| `--baseline` | Baseline or label to export (e.g. `REL_1`) |
| `--dry-run` | Preview migration without writing files |
| `--validate` | Run file-count validation after migration |
| `--preserve-tags` | Convert CC labels to Git tags |
| `--config` | Path to config YAML (default: `configs/config.yaml`) |
| `--web` | Launch the Flask web UI instead |

### Example log output

```
INFO: ============================================================
INFO: CCGit Migration Started
INFO:   Repo     : billing_app
INFO:   Baseline : REL_1
INFO:   Dry Run  : False
INFO: ============================================================
INFO: [1/7] Initialising ClearCase adapter...
INFO: [2/7] Listing files in VOB...
INFO: [2/7] Found 342 files to migrate
INFO: [3/7] Initialising Git repository...
INFO: [4/7] Exporting files from ClearCase...
INFO: [4/7] Migrated: 340  Skipped: 2
INFO: [5/7] Committing to Git...
INFO: [6/7] Tag preservation skipped (not requested)
INFO: [7/7] Running validation...
INFO: [7/7] Validation PASSED — CC: 342, Git: 340, Missing: 2
INFO: Migration completed successfully.
INFO: Report saved: reports/report_billing_app_20240315_143022.json
```

---

## Running Tests

```bash
# Run all tests
pytest

# With coverage report
pytest --cov=migration --cov-report=term-missing

# Run a specific test file
pytest tests/test_validator.py -v
```

> Tests use mocking for ClearCase adapter tests — no live ClearCase connection is required to run the test suite.

---

## Project Structure

```
ccgit-tool/
│
├── run.py                        # Entry point (CLI + web)
│
├── app/                          # Flask web application
│   ├── __init__.py               # App factory
│   ├── routes/
│   │   ├── main.py               # Dashboard routes
│   │   └── migration.py          # Migration form + results routes
│   ├── templates/
│   │   ├── base.html             # Shared layout
│   │   ├── dashboard.html        # Main dashboard
│   │   ├── migration_form.html   # Migration configuration form
│   │   ├── migration_progress.html
│   │   └── migration_results.html
│   └── static/
│       ├── css/style.css
│       └── js/main.js
│
├── migration/                    # Core migration backend
│   ├── clearcase_adapter.py      # cleartool CLI wrapper
│   ├── git_adapter.py            # GitPython wrapper
│   ├── migration_engine.py       # Main pipeline orchestrator
│   ├── validator.py              # Post-migration validation
│   └── metadata_parser.py       # Author/timestamp normalisation
│
├── configs/
│   └── config.yaml               # Default configuration template
│
├── logs/                         # Runtime migration logs (gitignored)
├── reports/                      # JSON migration reports (gitignored)
│
├── tests/
│   ├── test_clearcase_adapter.py
│   ├── test_metadata_parser.py
│   └── test_validator.py
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Known Limitations

- **No history migration** — only the latest snapshot (or a named baseline) is migrated. Full version history reconstruction is out of scope for the current MVP.
- **No real-time bidirectional sync** — this is a one-way, point-in-time migration.
- **Hijacked files** — files modified outside `checkout` in ClearCase may not export cleanly and will be logged as warnings.
- **Large binaries** — no Git LFS support in the current version. Large binary files will be committed to the Git repo directly.
- **No authentication** — the web UI has no login system. This is an internal tool intended for use on a trusted internal network only.
- **ClearCase dependency** — the tool requires `cleartool` and a configured ClearCase view. It cannot be run without ClearCase client access.
- **Single VOB per run** — multi-VOB batch migration is not supported in MVP.

---

## Future Roadmap

These are stretch goals for future iterations after the MVP is validated:

| Feature | Notes |
|---|---|
| History migration | Replay `lshistory` events via `git fast-import` |
| Branch/stream mapping | CC branches → Git branches |
| Git LFS support | Auto-route large binaries through LFS |
| Multi-VOB batching | Migrate multiple VOBs in one run |
| Checksum validation | MD5 comparison on all migrated files |
| Jenkins integration | Trigger migrations from CI pipeline |
| Background job queue | Async migration jobs with Celery/Redis |
| HTML dashboard reports | Rich HTML migration reports instead of JSON |

---