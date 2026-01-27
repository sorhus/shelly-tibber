# Tech Excellence Backlog

> **Status:** Updated after implementation

---

## Completed Tickets

### Ticket 1: Wire Up Health Check Status Tracking

**Status:** COMPLETED
**Priority:** High
**Effort:** Low (1-2 hours)

#### Problem
The `health_check.py` module has a `StatusManager` class that tracks run history, but it's never called from the main scheduler. Health checks currently show "UNKNOWN" because no status data is written.

#### Solution Implemented
- Added `StatusManager` import to `schedule_cheapest_hours.py`
- Added `status_manager` parameter to `CheapestHoursScheduler.__init__`
- Added `_write_status()` helper method to write run status
- Track run start time and duration
- Write success/failure status with all relevant details

#### Files Modified
- `src/schedule_cheapest_hours.py`

#### Acceptance Criteria
- [x] Health check shows "OK" after successful run
- [x] Health check shows "ERROR" with message after failed run
- [x] Run history is preserved in `output/status.json`
- [x] `./scripts/dev/run_tests.sh` passes

---

### Ticket 2: Add Integration Tests for Main Orchestrator

**Status:** COMPLETED
**Priority:** Medium-High
**Effort:** Medium (3-4 hours)

#### Problem
The main orchestrator `schedule_cheapest_hours.py` contains ~170 lines of complex scheduling logic (midnight crossing, weekday handling, conflict detection) with no test coverage.

#### Solution Implemented
Created `tests/test_schedule_cheapest_hours.py` with 13 test cases:
- Initialization tests (config, dry-run, status manager)
- Successful scheduling flow
- Already run today (should skip)
- FORCE_RUN override
- No prices available (should fail gracefully)
- Dry-run mode behavior (no success file, status flag)
- Midnight hour handling
- Exception handling (writes failure status)

#### Files Created
- `tests/test_schedule_cheapest_hours.py`

#### Acceptance Criteria
- [x] At least 5 test cases covering main flows (13 implemented)
- [x] All mocks properly isolate from external services
- [x] Tests run in <5 seconds (no real network calls)
- [x] `./scripts/dev/run_tests.sh` passes

---

### Ticket 3: Unify HTTP Client Usage in energy_analysis.py

**Status:** COMPLETED
**Priority:** Low
**Effort:** Low-Medium (1-2 hours)

#### Problem
`energy_analysis.py` uses raw `requests` library directly while the rest of the codebase uses the `http_client.py` abstraction.

#### Solution Implemented
- Extended `TibberClient.query()` to support GraphQL variables
- Refactored `EnergyAnalyzer` to use `TibberClient` instead of raw `requests`
- Removed direct `requests` import
- Added `retry_config` parameter to `EnergyAnalyzer`

#### Files Modified
- `src/http_client.py` (added variables support to query method)
- `src/energy_analysis.py`

#### Acceptance Criteria
- [x] No direct `requests` import in `energy_analysis.py`
- [x] Uses `TibberClient` for API calls
- [x] Retry logic applies to energy analysis
- [x] `./scripts/dev/run_tests.sh` passes

---

### Ticket 4: Review and Document Test Coverage

**Status:** COMPLETED
**Priority:** Medium
**Effort:** Low (1 hour)

#### Problem
No documented overview of test coverage.

#### Solution Implemented
- Added `pytest-cov>=4.0.0` to requirements.txt
- Ran coverage analysis
- Documented findings below

#### Test Coverage Report

**Overall Coverage: 55%**

| Module | Coverage | Status | Notes |
|--------|----------|--------|-------|
| `__init__.py` | 100% | OK | |
| `exceptions.py` | 100% | OK | |
| `config.py` | 93% | OK | |
| `models.py` | 93% | OK | |
| `logging_config.py` | 90% | OK | |
| `retry.py` | 90% | OK | |
| `http_client.py` | 89% | OK | |
| `file_io.py` | 84% | OK | |
| `health_check.py` | 82% | OK | CLI not tested |
| `price_analysis.py` | 71% | Needs Work | API fetch methods not tested |
| `schedule_cheapest_hours.py` | 66% | Needs Work | Complex flows added in Ticket 2 |
| `shelly_schedule.py` | 52% | Needs Work | Many RPC methods untested |
| `energy_analysis.py` | 0% | Missing | No tests |
| `clear_schedules.py` | 0% | Utility | Standalone script |
| `list_schedules.py` | 0% | Utility | Standalone script |
| `get_home_id.py` | 0% | Utility | Standalone script |
| `set_example_schedule.py` | 0% | Utility | Standalone script |

#### Priority Modules for Future Testing
1. **energy_analysis.py** (0%) - Core analysis functionality with no tests
2. **shelly_schedule.py** (52%) - Many RPC methods and edge cases untested
3. **price_analysis.py** (71%) - API fetch logic needs coverage

#### Acceptance Criteria
- [x] Coverage report generated
- [x] Coverage percentage documented per module
- [x] Gaps identified and prioritized

---

## Future Tickets (Suggested)

### Ticket 5: Add Tests for energy_analysis.py
**Priority:** Medium
**Effort:** Medium (3-4 hours)

Create comprehensive tests for `EnergyAnalyzer` class covering:
- Consumption data fetching
- Response parsing
- Date range filtering
- Scheduled hours marking
- Daily summary calculation

### Ticket 6: Improve shelly_schedule.py Coverage
**Priority:** Medium
**Effort:** Medium (3-4 hours)

Add tests for uncovered RPC methods:
- `list_schedules()` with actual schedules
- `delete_schedule()` error handling
- Edge cases in schedule creation
