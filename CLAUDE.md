# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running Python

Python is always run inside Docker. Never use `python` or `python3` directly.

### Run tests
```bash
./scripts/dev/run_tests.sh
```

### Run the scheduler
```bash
./scripts/run_daily.sh
```

### Run a specific Python module
```bash
docker run --rm \
  -v $(pwd)/src:/app/src \
  -v $(pwd)/config.json:/app/config.json:ro \
  shelly-tibber python -m src.module_name
```

### Build the Docker image
```bash
docker build -f Dockerfile.python -t shelly-tibber .
```

## Git Workflow

> **CRITICAL**: Always run `git pull origin main` BEFORE making any file edits.

- **Small changes**: Commit directly to main
- **Larger changes**: Use a feature branch
- **One branch per ticket**: Each ticket/task gets its own feature branch, even when implementing multiple tickets in one session
- **Branch naming**: Use `ticket-N-short-description` format (e.g., `ticket-5-health-check-integration`)
- **Always pull first**: Run `git pull origin main` before starting work
- **Return to main**: Switch back to main when done with a feature branch
- **Multiple tickets**: When implementing multiple tickets, create separate branches and PRs for each
- **Never rewrite remote history**: No `git push --force`, `git rebase`, or `git commit --amend` on pushed branches

## Architecture

This project automatically schedules a Shelly Pro 1 switch to turn on during the cheapest electricity hours using Tibber price data.

### Core Flow

The main orchestrator is `src/schedule_cheapest_hours.py`. A daily run:

1. **Config** (`config.py`) loads `config.json`, applies defaults, validates, and overlays environment variable overrides (e.g., `TIBBER_TOKEN`, `SHELLY_HOST`, `NUM_CHEAPEST_HOURS`)
2. **Price fetching** (`price_analysis.py`) queries the Tibber GraphQL API for tomorrow's 24 hourly prices, then selects the N cheapest hours (optionally also hours below a monthly price threshold)
3. **Schedule creation** (`shelly_schedule.py`) groups consecutive cheap hours into blocks, then creates ON/OFF cron schedules on the Shelly device via its RPC API (`Schedule.Create`, `Schedule.Delete`, `Schedule.List`)
4. **Output** (`file_io.py`) writes results to `output/YYYY-MM-DD/` and a success marker file that prevents re-runs on the same day
5. **Health tracking** (`health_check.py`) updates `output/status.json` with run history

### Key Design Decisions

- **Weekday tagging**: Schedules are tagged with the target day's weekday number (0=Sun, 6=Sat) so multiple days' schedules coexist without conflict
- **Midnight crossing**: When cheap hours span midnight, conflicting OFF schedules at midnight are automatically removed
- **Once-per-day guard**: `success_YYYY-MM-DD.txt` prevents duplicate runs; override with `FORCE_RUN=1`
- **Dry-run mode**: `--dry-run` flag or `DRY_RUN` env var skips Shelly API calls while logging what would happen
- **Retry with backoff** (`retry.py`): Retries Tibber/Shelly network errors with exponential backoff; does NOT retry Shelly RPC errors (device-side failures)
- **Data models** (`models.py`): All types are dataclasses (`AppConfig`, `TibberConfig`, `ShellyConfig`, `PricePoint`, `ShellySchedule`, `RunStatus`, etc.)
- **Exception hierarchy** (`exceptions.py`): Structured under `ShellyTibberError` with specific subtypes for config, Tibber API, Shelly device, scheduling, and network errors

## Project Structure

- `src/` - Python source code
- `tests/` - Unit tests (pytest, one `test_*.py` per module)
- `scripts/` - Shell scripts for running in Docker
- `scripts/dev/` - Development utilities (list/clear schedules, get home ID, energy analysis, etc.)
- `output/` - Generated results and status files (gitignored)
