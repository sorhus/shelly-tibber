# Backlog

## Ticket 36: Clean up unused imports

**Priority:** Low
**Effort:** Trivial (<15min)
**Impact:** Low

Unused imports in `clear_schedules.py` (`os`, `Dict`, `Any`), `list_schedules.py` (`os`, `Dict`, `Any`), `set_example_schedule.py` (`os`, `Dict`, `Any`), `logging_config.py` (`os`).

**Fix:** Remove unused imports.

**Files:**
- `src/clear_schedules.py`
- `src/list_schedules.py`
- `src/set_example_schedule.py`
- `src/logging_config.py`

---

## Ticket 37: Remove deprecated `load_config()` wrapper

**Priority:** Low
**Effort:** Trivial (<15min)
**Impact:** Low

`load_config()` is marked deprecated but still imported in tests. It is just an alias for `load_config_dict()`.

**Fix:** Update callers to use `load_config_dict()` and remove the function.

**Files:**
- `src/config.py`
- `tests/test_config.py`

---

## Ticket 38: Modernize type annotations to Python 3.11 syntax

**Priority:** Low
**Effort:** Low (<1h)
**Impact:** Low

Uses `from typing import List, Dict, Optional` throughout. Since the project targets Python 3.11, the built-in `list[...]`, `dict[...]`, and `X | None` syntax is preferred.

**Fix:** Replace `List[X]` with `list[X]`, `Dict[K, V]` with `dict[K, V]`, `Optional[X]` with `X | None`.

**Files:**
- Multiple files across `src/`

---

## Ticket 39: Remove emoji from logger calls

**Priority:** Low
**Effort:** Trivial (<15min)
**Impact:** Low

Emoji in `logger.info()`/`logger.warning()` calls can cause encoding issues in log aggregation tools. Emoji is fine in `print()` statements for user-facing output.

**Fix:** Remove emoji from `logger.*()` calls.

**Files:**
- `src/clear_schedules.py`
- `src/list_schedules.py`
- `src/set_example_schedule.py`
- `src/energy_analysis.py`

---

## Ticket 40: Replace deprecated `datetime.utcnow()`

**Priority:** Low
**Effort:** Trivial (<15min)
**Impact:** Low

`datetime.utcnow()` was deprecated in Python 3.12.

**Fix:** Replace with `datetime.now(timezone.utc)`.

**Files:**
- `src/logging_config.py`
- `src/health_check.py`

---

## Ticket 41: Fix inconsistent `DRY_RUN` boolean parsing

**Priority:** Low
**Effort:** Trivial (<15min)
**Impact:** Low

Same issue as `FORCE_RUN` — only accepts `"true"` when other boolean env vars accept `"1"`, `"yes"`, `"on"`.

**Fix:** Use consistent boolean parsing.

**Files:**
- `src/schedule_cheapest_hours.py`

---

## Ticket 42: Add tests for `analyze_last_7_days()` and utility scripts

**Priority:** Low
**Effort:** Medium (2-4h)
**Impact:** Medium

`analyze_last_7_days()` and `save_analysis_results()` have no tests. Utility scripts (`clear_schedules.py`, `list_schedules.py`, `set_example_schedule.py`, `get_home_id.py`) have no test coverage.

**Fix:** Add tests with mocked Tibber/Shelly clients.

**Files:**
- `tests/test_energy_analysis.py`
- New test files for utility scripts

---

## Ticket 43: Close HTTP sessions explicitly

**Priority:** Low
**Effort:** Trivial (<15min)
**Impact:** Low

`TibberClient` and `ShellyClient` support context manager protocol (`__enter__`/`__exit__`) but no caller uses it. Sessions are never explicitly closed.

**Fix:** Use clients as context managers with `with` statements, or close them in cleanup.

**Files:**
- `src/schedule_cheapest_hours.py`
- `src/energy_analysis.py`
