# Shelly Tibber - Electricity Price Scheduling

Automatically schedule your Shelly Pro 1 switch to turn on during the cheapest electricity hours using Tibber API data.

## Features

- **Automatic Scheduling**: Fetches tomorrow's electricity prices from Tibber and schedules your Shelly device to run during the cheapest hours
- **Price Threshold Mode**: Optionally schedule any hour below a configurable price threshold
- **Dry-Run Mode**: Test scheduling logic without making actual changes to your device
- **Retry Logic**: Automatic retry with exponential backoff for network requests
- **Health Monitoring**: Track scheduler status and check system health
- **Environment Variable Support**: Override config values via environment variables
- **Structured Logging**: JSON-formatted logs with correlation IDs for debugging

## Quick Start

### 1. Configure

```bash
cp config.example.json config.json
# Edit config.json with your Tibber token, home ID, and Shelly IP
```

### 2. Get Your Tibber Home ID

```bash
./scripts/dev/get_home_id.sh
```

### 3. Run Daily Scheduling

```bash
./scripts/run_daily.sh
```

### 4. Set Up Cron Job

Add to your crontab to run daily at 23:05:
```bash
5 23 * * * cd /path/to/shelly-tibber && ./scripts/run_daily.sh
```

## Configuration

### Configuration File

Create `config.json` from the example:

```json
{
  "tibber": {
    "token": "YOUR_TIBBER_API_TOKEN",
    "home_id": "YOUR_TIBBER_HOME_ID",
    "debug": false
  },
  "shelly": {
    "host": "192.168.1.100",
    "timeout": 10,
    "username": "",
    "password": ""
  },
  "scheduling": {
    "num_cheapest_hours": 10,
    "clear_old_schedules": false,
    "price_threshold": {
      "enabled": false,
      "monthly_thresholds": {
        "1": 0.50, "2": 0.50, "3": 0.50, "4": 0.20,
        "5": 0.10, "6": 0.10, "7": 0.10, "8": 0.10,
        "9": 0.10, "10": 0.20, "11": 0.50, "12": 0.50
      }
    }
  },
  "retry": {
    "enabled": true,
    "max_attempts": 3,
    "initial_delay": 1.0,
    "backoff_factor": 2.0,
    "max_delay": 60.0
  }
}
```

### Environment Variable Overrides

Configuration values can be overridden via environment variables:

| Environment Variable | Config Path | Type |
|---------------------|-------------|------|
| `TIBBER_TOKEN` | `tibber.token` | string |
| `TIBBER_HOME_ID` | `tibber.home_id` | string |
| `TIBBER_DEBUG` | `tibber.debug` | boolean |
| `SHELLY_HOST` | `shelly.host` | string |
| `SHELLY_TIMEOUT` | `shelly.timeout` | integer |
| `SHELLY_USERNAME` | `shelly.username` | string |
| `SHELLY_PASSWORD` | `shelly.password` | string |
| `NUM_CHEAPEST_HOURS` | `scheduling.num_cheapest_hours` | integer |
| `CLEAR_OLD_SCHEDULES` | `scheduling.clear_old_schedules` | boolean |

Example:
```bash
TIBBER_TOKEN=my-token SHELLY_HOST=10.0.0.50 ./scripts/run_daily.sh
```

### Configuration Validation

The application validates configuration on startup:
- **Required fields**: `tibber.token`, `tibber.home_id`, `shelly.host`
- **Placeholder detection**: Rejects unconfigured placeholder values
- **Range validation**: `timeout` (1-300), `num_cheapest_hours` (1-24)
- **Defaults**: `num_cheapest_hours` defaults to 10, `timeout` defaults to 10

## Dry-Run Mode

Test the scheduling logic without making actual changes to your Shelly device:

```bash
# Using Docker
docker run --rm \
  -v $(pwd)/config.json:/app/config.json:ro \
  shelly-tibber python -m src.schedule_cheapest_hours --dry-run

# Output shows what would happen without making changes
```

Dry-run mode:
- Fetches real price data from Tibber
- Calculates cheapest hours
- Simulates schedule creation (no HTTP requests to Shelly)
- Logs all operations that would be performed

## Health Monitoring

Check the status of your scheduler:

```bash
# Basic health check
docker run --rm \
  -v $(pwd)/output:/app/output \
  shelly-tibber python -m src.health_check

# Verbose output
docker run --rm \
  -v $(pwd)/output:/app/output \
  shelly-tibber python -m src.health_check --verbose

# JSON output (for monitoring systems)
docker run --rm \
  -v $(pwd)/output:/app/output \
  shelly-tibber python -m src.health_check --json
```

Health status values:
- **OK**: Last run succeeded within 25 hours
- **WARNING**: Last run was partial success or is stale (>25 hours)
- **ERROR**: Last run failed
- **UNKNOWN**: No status file found

Exit codes: 0 (OK), 1 (WARNING/ERROR), 2 (UNKNOWN)

## Retry Logic

Network requests automatically retry on transient failures:

```json
{
  "retry": {
    "enabled": true,
    "max_attempts": 3,
    "initial_delay": 1.0,
    "backoff_factor": 2.0,
    "max_delay": 60.0
  }
}
```

- **Exponential backoff**: Delays increase between retries (1s, 2s, 4s, ...)
- **Applies to**: Both Tibber API and Shelly device requests
- **Retried errors**: Connection errors, timeouts, HTTP 5xx errors

## Weekday-Based Scheduling

Schedules are automatically tagged with weekday specifications:

- **No conflicts**: Each schedule only runs on its designated day
- **Accumulative**: Run multiple days to build up a week of schedules
- **Self-cleaning**: Old schedules skip execution on non-matching days

### Midnight Crossing

The system handles schedules that cross midnight intelligently:

**Example**: Tuesday 23:00 and Wednesday 00:00 are both cheap
1. Monday evening → Creates: ON at 23:00 Tuesday, OFF at 00:00 Wednesday
2. Tuesday evening → Detects 00:00 is cheap, removes conflicting OFF, creates: ON at 00:00 Wednesday
3. Result: Device stays on continuously from 23:00 Tuesday through 01:00 Wednesday

### Clearing Old Schedules

Enable automatic cleanup of old schedules:

```json
{
  "scheduling": {
    "clear_old_schedules": true
  }
}
```

When enabled, schedules from yesterday and the day before are removed.

## Price Threshold Mode

Schedule any hour below a price threshold (in addition to the N cheapest):

```json
{
  "scheduling": {
    "price_threshold": {
      "enabled": true,
      "monthly_thresholds": {
        "1": 0.50,
        "6": 0.90,
        "12": 0.50
      }
    }
  }
}
```

- Thresholds are compared against **spot price only** (not total price)
- Always schedules the N cheapest hours, plus any others below threshold
- Different thresholds per month allow seasonal adjustments

## Development

<<<<<<< HEAD
=======
### Git Guidelines

Git is a distributed tool for managing code. Follow these practices:

- **Never rewrite remote history**: Do not use `git push --force`, `git rebase`, or `git commit --amend` on branches that have been pushed to a remote. This can cause data loss for other collaborators.
- **Always pull before developing**: Run `git pull origin main` before starting new work to ensure you have the latest changes.

>>>>>>> improve-documentation
### Run Tests

```bash
./scripts/dev/run_tests.sh
```

### Project Structure

```
├── src/
│   ├── schedule_cheapest_hours.py  # Main orchestrator
│   ├── price_analysis.py           # Tibber API & price logic
│   ├── shelly_schedule.py          # Shelly device control
│   ├── config.py                   # Configuration management
│   ├── models.py                   # Type definitions (dataclasses)
│   ├── exceptions.py               # Custom exception hierarchy
│   ├── retry.py                    # Retry logic with backoff
│   ├── http_client.py              # HTTP client abstraction
│   ├── logging_config.py           # Structured logging
│   ├── health_check.py             # Status tracking & monitoring
│   └── file_io.py                  # File operations
├── tests/                          # Unit tests
├── scripts/
│   ├── run_daily.sh               # Daily scheduling
│   └── dev/                       # Development utilities
├── config.example.json            # Configuration template
├── Dockerfile.python              # Docker image
├── pyproject.toml                 # Python package config
└── requirements.txt               # Dependencies
```

### Development Scripts

| Script | Description |
|--------|-------------|
| `./scripts/run_daily.sh` | Run the daily scheduler |
| `./scripts/dev/run_tests.sh` | Run all unit tests |
| `./scripts/dev/list_schedules.sh` | List current Shelly schedules |
| `./scripts/dev/clear_schedules.sh` | Clear all Shelly schedules |
| `./scripts/dev/get_home_id.sh` | Get your Tibber home ID |
| `./scripts/dev/set_example_schedule.sh` | Test Shelly connection |

### Docker Usage

```bash
# Build image
docker build -f Dockerfile.python -t shelly-tibber .

# Run scheduler
docker run --rm \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/config.json:/app/config.json:ro \
  shelly-tibber

# Interactive shell
docker run --rm -it \
  -v $(pwd):/app \
  shelly-tibber bash
```

## Output

### Files Generated

- `./output/YYYY-MM-DD/result_YYYY-MM-DD.json` - Analysis results
- `./output/YYYY-MM-DD/success_YYYY-MM-DD.txt` - Success indicator
- `./output/status.json` - Scheduler status (for health checks)
- `./logs/cron.log` - Execution logs

### Sample Output

```
📊 Top 10 Cheapest Hours for Tomorrow:
============================================================
 1. 02:00 - 0.123 SEK/kWh
 2. 03:00 - 0.145 SEK/kWh
 3. 01:00 - 0.156 SEK/kWh
...
============================================================
💰 Price difference: 0.111 SEK/kWh
💡 Consider shifting consumption to cheaper hours!
```

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Permission denied | `sudo chown -R $USER:$USER output/ logs/` |
| Config validation error | Check for placeholder values in config.json |
| Network timeout | Increase `shelly.timeout` or check connectivity |
| No price data | Tibber releases tomorrow's prices around 13:00 CET |
| Import errors | Rebuild Docker image: `docker build --no-cache ...` |

### Debug Mode

Enable verbose logging:

```json
{
  "tibber": {
    "debug": true
  }
}
```

### Check Shelly Connection

```bash
curl http://YOUR_SHELLY_IP/rpc/Shelly.GetStatus
```

## Security

- `config.json` is excluded from source control (`.gitignore`)
- Never commit API tokens
- Use environment variables for sensitive values in CI/CD

## License

MIT License - see LICENSE file for details.
