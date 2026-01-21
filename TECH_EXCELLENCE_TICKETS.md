# Tech Excellence Tickets

A prioritized list of technical improvements to enhance code quality, maintainability, and reliability.

---

## Ticket 1: Add Type Hints and Dataclasses Throughout

### Problem
The codebase uses `Dict[str, Any]` extensively for configuration and API responses, which provides no type safety and makes the code harder to understand and maintain. For example, `config['tibber']['token']` could fail at runtime if the structure changes.

### Solution
1. Create dataclasses for configuration:
   ```python
   @dataclass
   class TibberConfig:
       token: str
       home_id: str
       debug: bool = False

   @dataclass
   class ShellyConfig:
       host: str
       timeout: int = 10
       username: str = ""
       password: str = ""

   @dataclass
   class AppConfig:
       tibber: TibberConfig
       shelly: ShellyConfig
       analysis: AnalysisConfig
       scheduling: SchedulingConfig
   ```
2. Create dataclasses for API responses (price points, consumption data)
3. Add return type hints to all functions
4. Use `TypedDict` for external API responses where full dataclasses are overkill

### Effort
Medium (4-6 hours)

### Impact
High - Catches bugs at development time, improves IDE support, makes refactoring safer

---

## Ticket 2: Implement Proper Error Handling with Custom Exceptions

### Problem
The codebase uses generic `Exception` for all errors, making it difficult to handle specific failure modes. For example, network errors, API errors, and configuration errors are all raised as `Exception`.

```python
# Current approach
raise Exception(f"API request failed with code: {response.status_code}")
raise Exception(f"Failed to load config from {config_file}: {e}")
```

### Solution
1. Create a custom exception hierarchy:
   ```python
   class ShellyTibberError(Exception):
       """Base exception for all application errors"""

   class ConfigurationError(ShellyTibberError):
       """Configuration file missing or invalid"""

   class TibberAPIError(ShellyTibberError):
       """Tibber API request failed"""

   class ShellyConnectionError(ShellyTibberError):
       """Cannot connect to Shelly device"""

   class ScheduleError(ShellyTibberError):
       """Failed to create/update schedule"""
   ```
2. Replace generic exceptions with specific ones
3. Add error codes for programmatic handling
4. Include relevant context in exception messages

### Effort
Low-Medium (2-4 hours)

### Impact
High - Enables proper error recovery, better logging, and clearer debugging

---

## Ticket 3: Add Comprehensive Test Coverage

### Problem
Only one test file exists (`test_create_price_based_schedules.py`) covering a single method. Critical paths like configuration loading, API parsing, and the main scheduling flow have no tests.

### Solution
1. Add unit tests for:
   - `config.py`: Loading, validation, defaults
   - `price_analysis.py`: API response parsing, cheapest hour selection, threshold logic
   - `file_io.py`: File operations, cleanup logic
   - `shelly_schedule.py`: Schedule creation, deletion, weekday handling
2. Add integration tests with mocked HTTP responses
3. Add edge case tests:
   - DST transitions
   - Midnight crossings
   - Empty API responses
   - Network timeouts
4. Set up pytest with coverage reporting
5. Add test fixtures for common test data

### Effort
High (8-12 hours)

### Impact
High - Prevents regressions, enables confident refactoring, documents expected behavior

---

## Ticket 4: Implement Retry Logic with Exponential Backoff

### Problem
Network requests to Tibber API and Shelly device have no retry logic. A single transient failure causes the entire scheduling process to fail.

```python
# Current: Single attempt, immediate failure
response = requests.post(url, json=payload, timeout=self.timeout)
```

### Solution
1. Add a retry decorator or utility:
   ```python
   @retry(
       max_attempts=3,
       backoff_factor=2,
       exceptions=(requests.RequestException, ConnectionError)
   )
   def _make_request(self, method: str, params: dict) -> dict:
       ...
   ```
2. Use `tenacity` library or implement custom retry logic
3. Add configurable retry settings in config.json
4. Log retry attempts for debugging
5. Implement circuit breaker pattern for Shelly device (avoid hammering unresponsive device)

### Effort
Low-Medium (2-3 hours)

### Impact
Medium-High - Significantly improves reliability in real-world network conditions

---

## Ticket 5: Extract HTTP Client into Dedicated Module

### Problem
HTTP request logic is duplicated across `price_analysis.py`, `energy_analysis.py`, and `shelly_schedule.py`. Each has its own error handling, timeout settings, and logging approach.

### Solution
1. Create `src/http_client.py` with a unified HTTP client:
   ```python
   class HTTPClient:
       def __init__(self, base_url: str, timeout: int, headers: dict = None):
           self.session = requests.Session()
           ...

       def post(self, endpoint: str, data: dict) -> dict:
           # Unified error handling, logging, retries
           ...
   ```
2. Create specialized clients:
   - `TibberClient` for GraphQL API
   - `ShellyClient` for RPC API
3. Centralize timeout and retry configuration
4. Add request/response logging in one place

### Effort
Medium (4-6 hours)

### Impact
Medium - Reduces duplication, makes HTTP behavior consistent and easier to modify

---

## Ticket 6: Add Configuration Schema Validation

### Problem
Configuration validation is minimal and happens at runtime. Invalid config files produce unclear errors. The `config.example.json` comment documents requirements but isn't enforced.

### Solution
1. Add JSON Schema or Pydantic validation:
   ```python
   from pydantic import BaseModel, validator

   class TibberConfig(BaseModel):
       token: str
       home_id: str
       debug: bool = False

       @validator('token')
       def token_not_empty(cls, v):
           if not v or v == "YOUR_TIBBER_API_TOKEN_HERE":
               raise ValueError('Tibber token must be configured')
           return v
   ```
2. Validate on startup with clear error messages
3. Add environment variable override support (`TIBBER_TOKEN`, `SHELLY_HOST`)
4. Create a config validation CLI command

### Effort
Medium (3-5 hours)

### Impact
Medium - Catches configuration errors early with actionable messages

---

## Ticket 7: Implement Structured Logging

### Problem
Logging is inconsistent across modules. Some use emojis, some don't. Debug information is scattered. There's no way to easily parse logs programmatically or send them to a logging service.

```python
# Inconsistent styles
logger.info(f"✅ Connected to Shelly device successfully")
logger.info(f"Found {len(cheapest_hours)} cheapest hours")
self.debug_log(f"[DEBUG] {message}")  # Custom debug method
```

### Solution
1. Implement structured logging with JSON output option:
   ```python
   import structlog

   logger = structlog.get_logger()
   logger.info("schedule_created", schedule_id=123, weekday=2, hour=10)
   ```
2. Standardize log levels (DEBUG for verbose, INFO for operations, WARNING for issues)
3. Remove emoji from log messages (use structured fields instead)
4. Add correlation IDs for tracing a single run
5. Configure log output format via environment variable

### Effort
Medium (4-6 hours)

### Impact
Medium - Improves debugging, enables log aggregation, makes logs machine-readable

---

## Ticket 8: Add Dry-Run Mode

### Problem
There's no safe way to test what schedules would be created without actually modifying the Shelly device. This makes testing and debugging risky.

### Solution
1. Add `--dry-run` CLI flag and config option:
   ```python
   if config.get('dry_run', False):
       logger.info(f"[DRY RUN] Would create schedule: {timespec}")
       return fake_schedule_id
   ```
2. In dry-run mode:
   - Fetch real prices from Tibber
   - Calculate schedules normally
   - Log what would be created/deleted
   - Skip actual Shelly API calls
3. Output a summary of planned changes
4. Add `--dry-run` to shell scripts

### Effort
Low (2-3 hours)

### Impact
Medium-High - Enables safe testing, easier debugging, better user confidence

---

## Ticket 9: Refactor Main Orchestrator for Testability

### Problem
`CheapestHoursScheduler.run()` is a 150+ line method that's difficult to test. It mixes business logic with I/O operations and has deep nesting.

### Solution
1. Break down into smaller, focused methods:
   ```python
   def run(self) -> bool:
       if not self._should_run():
           return True
       
       prices = self._fetch_prices()
       schedules = self._plan_schedules(prices)
       self._handle_midnight_conflicts(schedules)
       self._cleanup_old_schedules()
       self._create_schedules(schedules)
       self._save_results(schedules)
       return True
   ```
2. Extract schedule planning logic into pure functions (no I/O)
3. Use dependency injection for testability:
   ```python
   def __init__(self, price_fetcher, schedule_creator, file_manager):
       ...
   ```
4. Add unit tests for each extracted method

### Effort
Medium-High (6-8 hours)

### Impact
Medium - Improves testability, readability, and maintainability

---

## Ticket 10: Add Health Check and Monitoring Endpoint

### Problem
There's no way to monitor the system's health or verify it's running correctly without checking logs manually. Failed runs are only discovered when the device doesn't turn on.

### Solution
1. Create a status file after each run:
   ```json
   {
     "last_run": "2026-01-21T23:05:00",
     "status": "success",
     "schedules_created": 6,
     "next_scheduled_date": "2026-01-22",
     "cheapest_hours": ["02:00", "03:00", "04:00"]
   }
   ```
2. Add a health check script:
   ```bash
   ./scripts/health_check.sh
   # Outputs: OK - Last run 2h ago, 6 schedules active for tomorrow
   ```
3. Add optional webhook notification on failure
4. Create a simple status dashboard (optional HTML file)
5. Add Prometheus metrics endpoint (optional, for advanced monitoring)

### Effort
Medium (4-6 hours)

### Impact
Medium - Enables proactive monitoring, faster issue detection

---

## Ticket 11: Remove sys.path Manipulation

### Problem
Multiple files use `sys.path.append()` to enable imports, which is fragile and non-standard:

```python
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
```

### Solution
1. Convert to a proper Python package with `__init__.py`
2. Create `pyproject.toml` or `setup.py` for package installation
3. Install in development mode: `pip install -e .`
4. Update imports to use package notation:
   ```python
   from shelly_tibber.price_analysis import PriceAnalyzer
   ```
5. Update Dockerfile to install the package
6. Update shell scripts to use module execution: `python -m shelly_tibber.schedule_cheapest_hours`

### Effort
Low-Medium (2-4 hours)

### Impact
Medium - Follows Python best practices, enables proper packaging and distribution

---

## Summary

Ordered by impact (highest first), then by effort (lowest first):

| # | Ticket | Title | Impact | Effort |
|---|--------|-------|--------|--------|
| 1 | 2 | Custom Exceptions | High | Low-Medium |
| 2 | 1 | Type Hints and Dataclasses | High | Medium |
| 3 | 3 | Test Coverage | High | High |
| 4 | 8 | Dry-Run Mode | Medium-High | Low |
| 5 | 4 | Retry Logic | Medium-High | Low-Medium |
| 6 | 11 | Remove sys.path Manipulation | Medium | Low-Medium |
| 7 | 6 | Config Schema Validation | Medium | Medium |
| 8 | 5 | HTTP Client Module | Medium | Medium |
| 9 | 7 | Structured Logging | Medium | Medium |
| 10 | 10 | Health Check/Monitoring | Medium | Medium |
| 11 | 9 | Refactor Orchestrator | Medium | Medium-High |
