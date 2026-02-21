# Backlog

## Ticket 17: Unify HTTP Client in price_analysis.py

**Priority:** Medium
**Effort:** Low (1h)

Migrate from raw `requests` to `TibberClient` (same pattern as energy_analysis.py).

**Files:**
- `src/price_analysis.py`

---

## Ticket 18: Fix Bare Except Clause

**Priority:** High
**Effort:** Trivial (5min)

Change `except:` to `except Exception:` at `price_analysis.py:111`.

**Files:**
- `src/price_analysis.py`

---

## Ticket 19: Pin Dependency Versions

**Priority:** Low
**Effort:** Low (30min)

Update `requirements.txt` with pinned versions for reproducibility.

**Files:**
- `requirements.txt`

---

## Ticket 20: Unify HTTP Client in get_home_id.py

**Priority:** Medium
**Effort:** Low (30min)

Migrate from raw `requests` to `TibberClient` for Tibber API calls.

**Files:**
- `src/get_home_id.py`

---

## Ticket 21: Unify HTTP Client in shelly_schedule.py

**Priority:** Medium
**Effort:** Medium (2h)

Replace custom `_make_request_internal` method with `ShellyClient` from `http_client.py`. The `ShellyClient` already provides the same RPC pattern with proper error handling and retry logic.

**Files:**
- `src/shelly_schedule.py`
