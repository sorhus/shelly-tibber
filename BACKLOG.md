# Backlog

## Ticket 22: Fix mDNS resolution failure in cron job

**Priority:** Critical
**Effort:** Low (30min)

### Problem

The daily cron job (`scripts/run_daily.sh`) fails intermittently because mDNS resolution of the Shelly device hostname (`shellypro1-ec62608d6038.local`) is unreliable.

### Root Cause

The script resolves the `.local` mDNS hostname on the host before passing the IP to Docker (since Docker containers can't use the host's avahi/mDNS resolver). When `getent hosts` fails to resolve, the script logs a warning but **continues anyway**, passing the unresolved `.local` hostname into Docker where it will always fail.

Evidence from `logs/cron.log` on the Raspberry Pi:

- **2026-02-19 (success)**: `Resolved mDNS: shellypro1-ec62608d6038.local -> 192.168.68.54` — resolved, job succeeded
- **2026-02-20 (failure)**: `WARNING: Could not resolve mDNS hostname shellypro1-ec62608d6038.local` — failed to resolve, all Shelly RPC calls failed with `Failed to resolve 'shellypro1-ec62608d6038.local'`

mDNS is inherently flaky — it relies on multicast DNS which can fail due to network timing, device sleep, or avahi-daemon issues.

### Investigation Still Needed

- SSH into `raspberrypi.local` and check which recent days succeeded vs failed:
  ```bash
  for d in ~/shelly-tibber/output/2026-02-*/; do
    day=$(basename $d)
    has_success=$(ls $d/success_*.txt 2>/dev/null && echo YES || echo NO)
    echo "$day: $has_success"
  done
  ```
- Check if the Shelly device has a static IP or DHCP reservation (the resolved IP `192.168.68.54` suggests it may already have one)

### Fix Plan

#### 1. Immediate fix: Make mDNS resolution more robust in `run_daily.sh`

The current code (line 48-54) tries `getent hosts` once and gives up. Improvements:

- **Retry mDNS resolution** with a few attempts and short delays (mDNS often succeeds on a second try)
- **Fail the script** if resolution fails after retries, instead of silently continuing with an unresolvable hostname
- **Cache the last known IP** to a file and fall back to it when mDNS fails

Example approach for `scripts/run_daily.sh`:

```bash
resolve_mdns() {
    local hostname="$1"
    local max_attempts=5
    local delay=2
    for i in $(seq 1 $max_attempts); do
        RESOLVED_IP=$(getent hosts "$hostname" 2>/dev/null | awk '{print $1}')
        if [ -n "$RESOLVED_IP" ]; then
            echo "$RESOLVED_IP"
            return 0
        fi
        [ $i -lt $max_attempts ] && sleep $delay
    done
    return 1
}

if [[ "$SHELLY_HOST" == *.local ]]; then
    RESOLVED_IP=$(resolve_mdns "$SHELLY_HOST")
    if [ -n "$RESOLVED_IP" ]; then
        log "Resolved mDNS: $SHELLY_HOST -> $RESOLVED_IP"
        echo "$RESOLVED_IP" > "$PROJECT_DIR/.last_known_shelly_ip"
        SHELLY_HOST_ENV="-e SHELLY_HOST=$RESOLVED_IP"
    elif [ -f "$PROJECT_DIR/.last_known_shelly_ip" ]; then
        CACHED_IP=$(cat "$PROJECT_DIR/.last_known_shelly_ip")
        log "WARNING: mDNS failed, using cached IP: $CACHED_IP"
        SHELLY_HOST_ENV="-e SHELLY_HOST=$CACHED_IP"
    else
        log "ERROR: Could not resolve $SHELLY_HOST and no cached IP available"
        exit 1
    fi
fi
```

#### 2. Long-term robustness: Use a static IP or DHCP reservation

The most reliable fix is to avoid mDNS entirely:

- Assign a static IP or DHCP reservation to the Shelly device (it's currently at `192.168.68.54`)
- Update `config.json` to use the IP directly instead of the `.local` hostname
- This eliminates the mDNS dependency completely

---

## Ticket 22: Fix mDNS Resolution Failure in Cron Job

**Priority:** Urgent
**Effort:** Low

The daily cron job fails intermittently because mDNS resolution of the Shelly hostname (`shellypro1-ec62608d6038.local`) is unreliable. When `getent hosts` fails, `run_daily.sh` logs a warning but continues anyway, passing the unresolved `.local` hostname into Docker where it always fails (Docker can't use the host's avahi resolver).

Evidence from `logs/cron.log` on the Raspberry Pi:
- **2026-02-19** (success): `Resolved mDNS: shellypro1-ec62608d6038.local -> 192.168.68.54`
- **2026-02-20** (failure): `WARNING: Could not resolve mDNS hostname` — all Shelly RPC calls failed with `NameResolutionError`

**Fix in `scripts/run_daily.sh`:**

1. Add a `resolve_mdns` function that retries `getent hosts` up to 5 times with a 2s delay between attempts
2. On successful resolution, cache the IP to `$PROJECT_DIR/.last_known_shelly_ip`
3. On failed resolution, fall back to the cached IP file
4. If no cached IP exists either, abort the script with an error instead of continuing into certain failure

**Files:**
- `scripts/run_daily.sh` (lines 42-55)

---

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
