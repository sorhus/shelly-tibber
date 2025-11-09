# Shelly Tibber - Electricity Price Scheduling

Automatically schedule your Shelly Pro 1 switch to turn on during the cheapest electricity hours using Tibber API data.

## Quick Start

### Run Daily Scheduling
```bash
./scripts/run_daily.sh
```

The scheduler automatically adds weekday specifications to all schedules, so they only run on the specific day they're meant for. This means you don't need to delete old schedules unless you want to - they'll simply skip execution on non-matching days.

### Run Tests
```bash
./scripts/dev/run_tests.sh
```

### Clear Schedules
```bash
./scripts/dev/clear_schedules.sh
```

### List Schedules
```bash
./scripts/dev/list_schedules.sh
```

## Docker Setup

### Files Structure
```
├── Dockerfile.python              # Python Docker image
├── scripts/                       # Shell scripts for different operations
│   ├── run_daily.sh              # Daily scheduling script
│   └── dev/                      # Development scripts
│       ├── clear_schedules.sh    # Clear Shelly schedules
│       ├── list_schedules.sh     # List Shelly schedules
│       ├── get_home_id.sh        # Get Tibber home ID
│       └── run_tests.sh          # Run all unit tests
├── src/                          # Python source code
│   ├── schedule_cheapest_hours.py # Main scheduling script
│   ├── price_analysis.py         # Price analysis logic
│   ├── file_io.py               # File operations
│   └── shelly_schedule.py       # Shelly API integration
├── tests/                        # Test files
├── requirements.txt              # Python dependencies
├── output/                       # Analysis results (mounted volume)
└── logs/                         # Log files (mounted volume)
```

### Docker Image
- **Base**: Python 3.11-slim
- **Dependencies**: requests library
- **Tools**: curl, jq for debugging
- **Working Directory**: `/app`

## Usage

### 1. Run Daily Scheduling
```bash
# Using the convenience script
./scripts/run_daily.sh

# Or manually with Docker
docker build -f Dockerfile.python -t shelly-tibber .
docker run --rm \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/config.json:/app/config.json:ro \
  shelly-tibber
```

### 2. Run Tests
```bash
# Using the convenience script
./scripts/dev/run_tests.sh

# Or manually with Docker
docker build -f Dockerfile.python -t shelly-tibber .
docker run --rm \
  -v $(pwd)/tests:/app/tests \
  -v $(pwd)/src:/app/src \
  -v $(pwd)/output:/app/output \
  shelly-tibber python -m pytest tests/ -v
```

### 3. Interactive Shell
```bash
# Get a shell in the container
docker run --rm -it \
  -v $(pwd):/app \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/config.json:/app/config.json:ro \
  shelly-tibber bash
```

## Weekday-Based Scheduling

The scheduler automatically creates schedules with weekday specifications (e.g., Monday, Tuesday, etc.). This means:

- **No Schedule Conflicts**: Each schedule only runs on its designated day of the week
- **Accumulate Schedules**: You can run the scheduler multiple days in a row to build up schedules for different days
- **No Need to Clear**: Old schedules automatically skip execution when it's not their day

### Example:
1. Run on Monday evening → Creates schedules for Tuesday (weekday=Tuesday)
2. Run on Tuesday evening → Creates schedules for Wednesday (weekday=Wednesday)
3. Both sets of schedules coexist on the Shelly device
4. On Tuesday, only Tuesday's schedules run
5. On Wednesday, only Wednesday's schedules run

### Midnight Crossing Behavior

The system intelligently handles schedules that cross midnight:

**Scenario:** Tuesday 23:00 is cheap, Wednesday 00:00 is also cheap
1. **Monday evening** (scheduling for Tuesday):
   - Creates: ON at 23:00 Tuesday, OFF at 00:00 Wednesday
2. **Tuesday evening** (scheduling for Wednesday):
   - Detects 00:00 is in cheapest hours
   - **Removes the OFF at 00:00 Wednesday** (from yesterday's schedule)
   - Creates: ON at 00:00 Wednesday, OFF at 01:00 Wednesday
3. **Result**: Device stays on continuously from 23:00 Tuesday through 01:00 Wednesday (no flicker!)

This ensures seamless operation across midnight when consecutive hours are cheap.

### Clearing Old Schedules (Optional)
If you want to clean up old schedules, set the `CLEAR_SCHEDULES` environment variable. This will delete schedules for **yesterday** and the **day before yesterday** only, keeping today's and future schedules intact:

```bash
# Clear old schedules (yesterday and day before) before creating new ones
CLEAR_SCHEDULES=true ./scripts/run_daily.sh

# Or with Docker
docker run --rm \
  -e CLEAR_SCHEDULES=true \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/config.json:/app/config.json:ro \
  shelly-tibber
```

**Note:** By default, `CLEAR_SCHEDULES=false`, so old schedules are kept. When enabled, only schedules from the past 2 days are removed, preserving schedules for today and any future days.

### Example Cleanup Scenario

Running on **Wednesday evening** with `CLEAR_SCHEDULES=true`:
- ✅ **Keeps**: Wednesday's schedules (today)
- ✅ **Keeps**: Any future schedules (if they exist)
- ❌ **Deletes**: Tuesday's schedules (yesterday)
- ❌ **Deletes**: Monday's schedules (day before yesterday)

This ensures your Shelly device stays clean without accidentally removing schedules that haven't run yet.

## Configuration

### Configuration File
The application uses `config.json` for all configuration:

```json
{
  "tibber": {
    "token": "YOUR_TIBBER_API_TOKEN",
    "home_id": "YOUR_TIBBER_HOME_ID",
    "debug": false
  },
  "shelly": {
    "host": "YOUR_SHELLY_IP_HERE",
    "username": "",
    "password": ""
  },
  "analysis": {
    "num_cheapest_hours": 10  // <--- Configurable number of hours
  }
}
```

**Note**: The application uses switch ID 0 by default for Shelly devices. If your Shelly Pro 1 has multiple switches or you need to control a different switch, you can modify the `switch_id` parameter in the schedule creation methods in the source code.

### Setup Steps

1. **Copy the example config file and fill in your details:**
```bash
cp config.example.json config.json
```

2. **Get Your Tibber API Token:**
   - Go to [Tibber Developer Portal](https://developer.tibber.com/)
   - Create an account and get your API token
   - Add the token to your `config.json`

3. **Get Your Home ID:**
```bash
./scripts/dev/get_home_id.sh
```
This will show you available homes and their IDs. Add the correct home ID to your `config.json`.

4. **Test Shelly Connection:**
```bash
./scripts/dev/set_example_schedule.sh
```
This will test the connection to your Shelly device and set a simple example schedule (ON at 08:00, OFF at 10:00).

5. **Test the Setup:**
```bash
./scripts/run_daily.sh
```

6. **Set Up Daily Scheduling:**
Add to your crontab to run daily at 23:05:
```bash
5 23 * * * cd /path/to/shelly-tibber && ./scripts/run_daily.sh
```

## Output

### Files Generated
- **Results**: `./output/YYYY-MM-DD/` (daily subdirectories)
  - `result_YYYY-MM-DD.json` - Complete analysis results
  - `success_YYYY-MM-DD.txt` - Success indicator file
- **Logs**: `./logs/cron.log` - Execution logs

### Sample Output
```
📊 Top N Cheapest Hours for Tomorrow (N is configurable):
============================================================
 1. 02:00 - 0.123 SEK/kWh
 2. 03:00 - 0.145 SEK/kWh
 3. 01:00 - 0.156 SEK/kWh
...
============================================================
💰 Price difference: 0.111 SEK/kWh
💡 Consider shifting consumption to cheaper hours!

💾 Results saved to: /app/output/2024-01-15/result_2024-01-15.json
```

### Volumes
- `./output:/app/output`: Persists analysis results
- `./logs:/app/logs`: Persists log files
- `./config.json:/app/config.json:ro`: Configuration file (read-only)

## Development

### Building Locally
```bash
# Build the image
docker build -f Dockerfile.python -t shelly-tibber .

# Run with volume mounts for development
docker run --rm \
  -v $(pwd):/app \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/config.json:/app/config.json:ro \
  shelly-tibber
```

### Debugging
```bash
# Run with interactive shell
docker run --rm -it -v $(pwd):/app -v $(pwd)/config.json:/app/config.json:ro shelly-tibber bash

# Check logs
tail -f logs/cron.log

# View output files
ls -la output/
```

## Troubleshooting

### Common Issues

1. **Permission Denied**
   ```bash
   # Fix permissions
   sudo chown -R $USER:$USER output/ logs/
   ```

2. **Container Can't Write to Volumes**
   ```bash
   # Ensure directories exist and are writable
   mkdir -p output logs
   chmod 755 output logs
   ```

3. **Network Issues**
   ```bash
   # Test network connectivity
   docker run --rm shelly-tibber curl -I https://api.tibber.com
   ```

4. **Python Import Errors**
   ```bash
   # Rebuild the image
   docker build -f Dockerfile.python -t shelly-tibber . --no-cache
   ```

5. **Configuration Issues**
   ```bash
   # Check config file exists and is valid
   cat config.json | jq .
   ```

6. **Token not found**: Make sure your `config.json` has the correct Tibber token
7. **Home ID not found**: Run `get_home_id.py` to find your correct home ID
8. **Shelly connection failed**: Check the IP address and network connectivity
9. **No price data**: Tibber might not have tomorrow's prices yet

### Debug Mode
Enable debug logging by setting `"debug": true` in your `config.json`.

## Security

- The `config.json` file is excluded from source control
- Never commit your actual API tokens
- Use the `config.example.json` as a template

## Advantages of Docker

1. **Consistency**: Same environment across development and production
2. **Isolation**: No conflicts with system Python packages
3. **Portability**: Easy to deploy on any system with Docker
4. **Reproducibility**: Exact same dependencies and versions
5. **Security**: Isolated execution environment
6. **CI/CD**: Simple integration with automated systems

## License

MIT License - see LICENSE file for details. 