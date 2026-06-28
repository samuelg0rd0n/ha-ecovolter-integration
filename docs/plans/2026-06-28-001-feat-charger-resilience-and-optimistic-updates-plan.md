---
title: Charger resilience + optimistic entity updates
type: feat
status: completed
date: 2026-06-28
supersedes: docs/resilience-plan.md
---

# ✨ Charger resilience + optimistic entity updates

## Overview

Make the EcoVolter integration tolerant of the charger's intermittent slow HTTP
responses **and** instantly responsive in the UI/automations. This plan extends the
earlier resilience plan (`docs/resilience-plan.md`) with a fourth pillar — **optimistic
state updates** — and folds everything into one coherent design where the four pieces
compose: failure tolerance, request serialization, debounced read-back, and optimistic
display.

## Problem Statement

In "Ecological" mode the user's Tesla charging briefly stops and auto-resumes. Root cause,
confirmed by HA logs (`Timeout error fetching information` + `float got invalid input
'unavailable'` TemplateErrors on `sensor.max_ev_charge_power` / `sensor.max_ev_charge_current`):

1. The charger's embedded HTTP server occasionally answers a GET in **>10s** →
   `asyncio.wait_for(..., 10.0)` in `api.py::_api_wrapper` times out → `UpdateFailed`.
2. Every entity is a `CoordinatorEntity` (`entity.py`) sharing **one** poll
   (`coordinator.py::_async_update_data`), so a single failed poll flips
   `last_update_success=False` and **all** entities go `unavailable` at once — including
   `sensor.ecovolter_actual_power` (key `actualPower`, `sensor.py:84`).
3. The user's template `sensor.max_ev_charge_power` references it with `|float` and **no
   default**, so it raises and goes `unavailable`; `sensor.max_ev_charge_current` follows.
4. The Ecological solar automation then reads a bad target current and briefly drops
   current / cuts charging → **real** charge stop (Tesla notifies).
5. ~15s later the next poll succeeds and everything recovers → charging resumes.

Unmanaged mode never writes to the charger, so the timeout is invisible there.

Secondary problem: every write (`number.py:199`, `switch.py:104/111`, `select.py:83`) does a
PATCH then an **immediate** `async_request_refresh()`. In Ecological mode the solar automation
nudges current frequently, producing a `PATCH, GET, PATCH, GET …` storm against a fragile
single-connection device, and the UI still lags one poll behind every change.

## Proposed Solution

Four composable changes:

1. **Failure tolerance** — a single (or short run of) timeout must not mark all entities
   unavailable; serve last-good data for up to 3 consecutive failures.
2. **Serialize device access** — one `asyncio.Lock` so a write PATCH and a poll GET never
   hit the embedded server concurrently.
3. **Debounced read-back** — coalesce post-write refreshes (~2s) to cut device load.
4. **Optimistic updates (new)** — reflect the written value in the UI the instant a write
   succeeds, holding it until the device confirms or a timeout elapses, so the debounce delay
   and the 15s poll are invisible to the user.

User decisions carried in: tolerate **3** consecutive failures; **debounce 2s**; **add
optimistic updates** (this extension).

## Technical Approach

### Phase 1 — Resilience foundation

**`const.py`** — new constants:
- `MAX_CONSECUTIVE_FAILURES: Final = 3` — tolerate this many consecutive failed polls;
  entities stay available (last-good data) through failures 1–3, go unavailable on the 4th.
- `WRITE_REFRESH_DEBOUNCE_SECONDS: Final = 2.0`.
- `OPTIMISTIC_TIMEOUT_SECONDS: Final = 10.0` — must be ≥ debounce + worst-case single poll
  (lock wait + 10s request) so a *successful* write never flashes back before confirmation.

**`coordinator.py`** — tolerate consecutive failures (core fix). Verified against current HA
`DataUpdateCoordinator` semantics: if `_async_update_data` **returns** instead of raising,
`last_update_success` stays `True`, so unmodified `CoordinatorEntity.available` stays `True`
and entities keep their last values — no entity-layer change needed for availability.
- Add instance state `_consecutive_failures: int = 0` (next to `_type_info_cache`).
- `except EcovolterApiClientAuthenticationError`: raise `ConfigEntryAuthFailed` immediately
  (never tolerated; counter untouched).
- `except EcovolterApiClientError as exception`:
  - `self._consecutive_failures += 1`
  - if `self._consecutive_failures <= MAX_CONSECUTIVE_FAILURES` **and** `self.data is not None`:
    `LOGGER.warning("EcoVolter poll failed (%s/%s), keeping last good data: %s", ...)` and
    `return self.data` (stay available, stale values). The `self.data is None` guard ensures a
    failure during `async_config_entry_first_refresh` still raises → `ConfigEntryNotReady`.
  - else: `raise UpdateFailed(exception) from exception` (→ unavailable).
- success branch: `self._consecutive_failures = 0`, build/return `DataType` as today.
- **Expose freshness for the optimistic layer:**
  `@property def data_is_fresh(self) -> bool: return self._consecutive_failures == 0`
  (True only right after a real successful poll; False while serving tolerated-stale data).

**`api.py`** — serialize all device access:
- In `EcovolterApiClient.__init__`: `self._request_lock = asyncio.Lock()` (constructing a Lock
  in `__init__` is safe on modern Python/HA; it binds to the running loop on first `await`).
- In `_api_wrapper`: wrap the network section in `async with self._request_lock:` covering
  `self._session.request(...)` + `_verify_response_or_raise(response)` + `await response.json()`
  (body must be fully read before releasing). Keep `asyncio.wait_for(..., 10.0)` inside the lock.
- **Do NOT parallelize the poll GETs** — sequential under the lock is the correct posture for a
  single-connection embedded server; three sub-10s requests fit comfortably in 15s.

### Phase 2 — Debounced post-write refresh

Use the coordinator's built-in request-refresh debouncer (no edits to the three write sites):
- Add `EcovolterDataUpdateCoordinator.__init__` that calls `super().__init__(...)` with
  `request_refresh_debouncer=Debouncer(hass, LOGGER, cooldown=WRITE_REFRESH_DEBOUNCE_SECONDS,
  immediate=False)` (`from homeassistant.helpers.debounce import Debouncer`). The coordinator
  wires `function=self._async_refresh` onto the supplied debouncer itself.
- `async_request_refresh()` is the debounced path (`async_refresh()` is not). With
  `immediate=False`, a burst of writes collapses into one refresh ~2s after the last write.
- `__init__.py` constructs the coordinator with `hass, logger, name, update_interval` already;
  the debouncer lives in the coordinator's own `__init__`, so the call site is unchanged.

### Phase 3 — Optimistic updates (new feature)

**Core rule (resolves the type-mismatch class of bugs in one stroke): store the optimistic
value in the RAW device domain — the exact value sent to the device — and always compare it
against the raw `get_settings()[key]`. Map raw → display only in the value property.**

**Shared mixin in `entity.py`** (e.g. `OptimisticEcovolterEntity(IntegrationEcovolterEntity)`,
which the switch/number/select entities then inherit instead of the base directly). State:
- `_optimistic_set: bool = False` — explicit flag (NOT truthiness; `None`/`0`/`False`/`""` are
  all valid real values).
- `_optimistic_value: Any` — raw device-domain value last sent.
- `_optimistic_expiry: float` — `self.hass.loop.time() + OPTIMISTIC_TIMEOUT_SECONDS`
  (**monotonic** loop clock, not `dt_util.utcnow()` — immune to NTP/DST and advanced by the HA
  test time machinery).

Helper API:
```python
def _apply_optimistic(self, raw_value) -> None:
    self._optimistic_value = raw_value
    self._optimistic_expiry = self.hass.loop.time() + OPTIMISTIC_TIMEOUT_SECONDS
    self._optimistic_set = True
    if self.hass is not None:           # guard: no-op before entity added to hass
        self.async_write_ha_state()

def _clear_optimistic(self) -> None:
    self._optimistic_set = False
    self._optimistic_value = None
```
Abstract hooks each platform implements:
- `_device_value(self)` → the raw coordinator value for this entity's key, normalized to the
  optimistic domain (switch: `bool(...)`; number: `as_float(...)`; select: the raw `int`).
- `_values_match(self, optimistic_raw, device_raw)` → default exact `==`; **number overrides**
  with a tolerance (`abs(a-b) <= 0.005`) to survive float round-trip drift on `kwhPrice` and
  int echoes.

Reconciliation — override `_handle_coordinator_update` once in the mixin (fires every cycle
because `always_update` stays at its `True` default):
```python
@callback
def _handle_coordinator_update(self) -> None:
    if self._optimistic_set:
        if not self.coordinator.last_update_success:
            self._clear_optimistic()                 # AC6: never survive an unavailable transition
        elif not self.coordinator.data_is_fresh:
            pass                                      # AC5: serving tolerated-stale data — keep, don't confirm/expire
        elif self._values_match(self._optimistic_value, self._device_value()):
            self._clear_optimistic()                 # confirmed against fresh data
        elif self.hass.loop.time() >= self._optimistic_expiry:
            self._clear_optimistic()                 # timeout — only ever checked against fresh data
    super()._handle_coordinator_update()
```

**Write sites** — pattern in all three platforms: PATCH first; only on success set optimistic;
if the PATCH raises, do **not** set optimistic — let it propagate (HA surfaces the error and
the property falls back to coordinator data). Then request the (debounced) refresh.

- `switch.py` (`async_turn_on/off`, `is_on`): send `bool`; `_apply_optimistic(True/False)`.
  `is_on` returns `self._optimistic_value if self._optimistic_set else bool(coordinator value)`.
- `number.py` (`async_set_native_value`, `native_value`): capture the **post-transform** value
  actually sent (after `clamp_int`/`round`/`int`) and `_apply_optimistic(sent_value)` — never
  the raw pre-clamp request (a requested 40 A clamped to 32 A must show 32, never 40).
  `native_value` returns optimistic float when set, else as today. `_values_match` uses tolerance.
- `select.py` (`async_select_option`, `current_option`): send the int (`CURRENCY_INV_MAP[option]`)
  and `_apply_optimistic(value_int)`. `current_option` returns `CURRENCY_MAP[self._optimistic_value]`
  when set, else as today. Comparison is int-vs-int against `get_settings()['currency']`.

Known minor cosmetic lag (document, don't fix): the `kwhPrice` number's
`native_unit_of_measurement` reads `currency` straight from `coordinator.data`, so after
changing the currency select the price unit label trails the selection by up to ~2s + a poll.

## Alternative Approaches Considered

- **Parallelize the 3 poll GETs** — rejected; would force concurrent connections to a device
  suspected of not tolerating them, worsening the timeouts the lock is meant to prevent.
- **Bare optimistic (SwitchBot-style: write state, let next poll override unconditionally)** —
  rejected; flickers when a stale in-flight poll lands first (real risk with a 15s flaky poll).
- **Non-optimistic, refresh-only (TPLink `@async_refresh_after`-style)** — solid and simplest,
  but leaves the read-back lag the user explicitly asked to remove.
- **`always_update=False`** — rejected; it suppresses `_handle_coordinator_update` on unchanged
  polls, breaking the timeout/expiry reconciliation. Keep the `True` default.

## System-Wide Impact

- **Interaction graph:** write → `client.async_set_settings` (PATCH, under lock) → on success
  `_apply_optimistic` → `async_write_ha_state` (instant UI) → `async_request_refresh` (debounced
  2s) → coordinator poll (under lock) → `_handle_coordinator_update` on every entity → confirm /
  expire / keep optimistic.
- **Error propagation:** PATCH errors propagate as today (no optimistic set). Poll comms errors
  are tolerated for 3 cycles (warning logged), then `UpdateFailed` → unavailable. Auth errors
  always raise `ConfigEntryAuthFailed`.
- **State lifecycle risks:** optimistic state is per-entity/per-key (matches the single-key
  writes today). It is cleared on confirm, on fresh-data timeout, and on the unavailable
  transition — it must never resurrect after `available` returns (AC6).
- **API surface parity:** all three write platforms (switch/number/select) get the same
  optimistic treatment via the shared mixin; sensors/binary_sensors are read-only and unchanged.
- **Integration test scenarios:** stale-poll race, write burst, silently-ignored write, and the
  failure-window/timeout interaction (below) — none catchable by simple unit mocks.

## Acceptance Criteria

### Functional
- [ ] A single (or up to 3 consecutive) poll timeout does **not** mark entities unavailable;
      they show last-good values. The 4th consecutive failure marks them unavailable.
- [ ] Auth failure raises `ConfigEntryAuthFailed` immediately and is never tolerated.
- [ ] First-refresh failure (no prior data) still raises (→ `ConfigEntryNotReady`).
- [ ] A write PATCH and a poll GET never overlap on the wire (serialized by the lock); the lock
      is released on the exception path.
- [ ] A burst of N writes within the cooldown produces exactly one read-back refresh.
- [ ] After a successful write the UI shows the new value immediately (optimistic), without
      waiting for the debounce or the next poll.
- [ ] Optimistic value stored = the **post-clamp/round/int** value actually sent (clamped
      current shows the clamped value, never the raw request).
- [ ] Confirmation compares like-for-like in the device domain (select int↔int, switch
      bool-normalized, number current/duration int-equal, `kwhPrice` within tolerance).
- [ ] A second write while the first is unconfirmed overwrites both value **and** expiry; UI
      shows the latest written value throughout the burst.
- [ ] A write the device silently ignores reverts to truth **after** `OPTIMISTIC_TIMEOUT_SECONDS`;
      a write the device *did* apply never flashes back before confirmation.
- [ ] During tolerated failures (`last_update_success True`, `data_is_fresh False`) an applied
      optimistic value is **not** cleared by an elapsed timeout against stale data.
- [ ] On `available → unavailable` the optimistic state is cleared; on recovery the UI shows
      fresh polled data, not a resurrected optimistic guess.
- [ ] PATCH failure sets no optimistic state and propagates the error; the property falls back
      to coordinator data (uses the explicit `_optimistic_set` flag, not truthiness).
- [ ] `async_write_ha_state()` is guarded/no-op when the entity is not yet added to hass.

### Quality gates
- [ ] `ruff` + `mypy` clean (per `.github/workflows/check_and_test.yaml`).
- [ ] New unit tests pass under `pytest` (`pytest-homeassistant-custom-component`).

## Risk Analysis & Mitigation

- **HA version drift** — the `request_refresh_debouncer.function` override and the 2025
  coordinator "retrigger queueing" (a refresh requested mid-poll is queued, not dropped) are
  confirmed on `dev`. Mitigation: verify against the installed `homeassistant` pin; if older
  than 2025.11, confirm the coordinator wires `function` onto the supplied Debouncer and that a
  post-write refresh isn't silently dropped during an in-flight poll.
- **OPTIMISTIC_TIMEOUT too short** — would flash back a successful write. Mitigation: 10s ≥
  debounce (2s) + worst-case single poll; covered by an explicit AC and a test.
- **Lock latency** — a queued write can wait up to ~10s behind a timing-out GET. Acceptable and
  strictly safer than collisions; revisit the per-request timeout only if it bites.

## Verification

Unit tests (`tests/`, `pytest-homeassistant-custom-component`, monkeypatched client), e.g.
`tests/test_coordinator_resilience.py`, `tests/test_api_lock.py`, `tests/test_optimistic.py`:

1. **Tolerance:** seed one success; raise `EcovolterApiClientCommunicationError` 3× → each time
   `last_update_success is True` and `data` == seeded; 4th → `last_update_success is False`;
   then success → `_consecutive_failures == 0`. Interleaved fail/success/fail never goes
   unavailable. Auth raises immediately. `data is None` + comms error → `UpdateFailed`.
2. **Lock:** fake session records enter/exit around an `asyncio.Event`; GET+PATCH via
   `asyncio.gather` never overlap; lock releases after a forced `TimeoutError`.
3. **Debounce:** N `async_request_refresh()` within cooldown → `_async_update_data` runs once;
   advance the HA test clock past the cooldown to flush (avoids "Lingering timer").
4. **Optimistic happy path:** `switch.turn_on` (blocking) → state `on` immediately; `freezer.tick`
   + `async_fire_time_changed` + `async_block_till_done` to flush the 2s debounce → state stays
   `on` after a poll returning `on` (confirmed, optimistic cleared).
5. **Stale-poll race:** mock first post-write poll to return the OLD value, next poll the NEW —
   assert state never flips back to old between cycles.
6. **Clamp:** request `targetCurrent` above max → optimistic shows the clamped value.
7. **Select cross-type:** change currency → optimistic shows new ISO; confirms when polled int
   matches (no spurious full-timeout hold).
8. **Silently-ignored write:** device keeps old value → state holds new value until
   `OPTIMISTIC_TIMEOUT`, then reverts (advance clock past timeout).
9. **Failure-window timeout:** apply optimistic, then drive tolerated failures so `data_is_fresh`
   is False and let the timeout elapse → optimistic NOT cleared; on the next fresh confirming
   poll it clears.
10. **Unavailable transition:** apply optimistic, drive the 4th failure → entity unavailable and
    optimistic cleared; on recovery shows fresh data.

Use `freezer` + `async_fire_time_changed(hass)` + `await hass.async_block_till_done()` to drive
timers; flush pending debounce timers before test end.

Manual smoke test: point `base_uri` at a local mock that times out ~1/10 requests; confirm in
the HA UI that entities no longer blip on isolated failures, rapid number changes produce one
coalesced refresh, and the displayed value updates the instant a switch/number is changed.

## Sources & References

### Origin
- Base resilience plan carried forward and superseded: `docs/resilience-plan.md` (failure
  tolerance, lock, debounce decisions).

### Internal references
- `custom_components/ecovolter/coordinator.py:43` — `_async_update_data` (tolerance + freshness)
- `custom_components/ecovolter/api.py:86` — `_api_wrapper` (serialization lock)
- `custom_components/ecovolter/entity.py:16` — base entity (optimistic mixin home)
- `custom_components/ecovolter/number.py:181`, `switch.py:99`, `select.py:75` — write sites
- `custom_components/ecovolter/const.py` — new constants

### External references (HA dev docs / core, verified 2026)
- Fetching data / CoordinatorEntity / `_handle_coordinator_update`:
  https://developers.home-assistant.io/docs/integration_fetching_data/
- Coordinator + Debouncer source:
  https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/update_coordinator.py ,
  https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/debounce.py
- Coordinator retrigger (2025): https://developers.home-assistant.io/blog/2025/10/05/coordinator-retrigger/
- Optimistic / expected-state architecture discussion:
  https://github.com/home-assistant/architecture/discussions/740
- Real integrations referenced: SwitchBot (optimistic + reconcile), TPLink (`async_refresh_after`),
  La Marzocco (immediate write), WLED (non-optimistic baseline).
- Testing helpers: https://github.com/MatthewFlamm/pytest-homeassistant-custom-component

## Companion user actions (outside this repo — recommended defense in depth)
Even with tolerance, an outage longer than 3 polls still surfaces as `unavailable`, so harden
the HA config too:
- Add defaults to the templates so they never raise on `unavailable`, e.g.
  `states('sensor.ecovolter_actual_power')|float(0)` (and the solax sources).
- Guard the Ecological current-setting automation with a condition that all input sensors are
  not `unavailable`/`unknown` before it writes to the charger.
