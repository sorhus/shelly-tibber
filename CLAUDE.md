# Claude Code Instructions

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

## Git Workflow

- **Small changes**: Commit directly to main
- **Larger changes**: Use a feature branch
- **One branch per ticket**: Each ticket/task gets its own feature branch, even when implementing multiple tickets in one session
- **Branch naming**: Use `ticket-N-short-description` format (e.g., `ticket-5-health-check-integration`)
- **Always pull first**: Run `git pull origin main` before starting work
- **Return to main**: Switch back to main when done with a feature branch
- **Multiple tickets**: When implementing multiple tickets, create separate branches and PRs for each

## Project Structure

- `src/` - Python source code
- `tests/` - Unit tests (pytest)
- `scripts/` - Shell scripts for running in Docker
- `scripts/dev/` - Development utilities
