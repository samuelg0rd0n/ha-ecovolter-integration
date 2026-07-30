---
title: No-op PATCH /settings writes suspected of cycling an EV charger's contactor
date: 2026-07-30
category: docs/solutions/integration-issues
module: custom_components/ecovolter/entity.py
problem_type: integration_issue
component: service_object
symptoms:
  - "Charger contactor drops and the charging session resets during active charging"
  - "Each interruption coincided 1:1 with a PATCH /settings request timeout"
  - "The setpoint (6A, the device minimum) was unchanged across all three interruptions"
root_cause: logic_error
resolution_type: code_fix
severity: high
tags:
  - home-assistant
  - ecovolter
  - no-op-write
  - contactor-cycling
  - optimistic-update
  - config-entry-auth-failed
  - reauth-gap
  - external-api-write
---

# No-op PATCH /settings writes suspected of cycling an EV charger's contactor

## Problem

On 2026-07-25 the user's EcoVolter EV charger dropped its contactor and reset the active charging session three times — 12:00:55, 12:06:34, and 13:56:12 local time. Session energy zeroed and all three phase currents fell together (5.7/5.8/5.6 A → 0.2/0.2/0.2 A), recovering to the same values roughly 30 seconds later. Each drop coincided 1:1 with a `PATCH /settings` request timing out in the user's Home Assistant automation. The requested value in every one of those writes was 6 A — the configured minimum, and already the charger's current setting. Every PATCH in the window was rewriting a value the charger already had.

The leading hypothesis: the firmware re-applies the current limit unconditionally on `PATCH /settings`, cycling the contactor to do so, even when the requested value is unchanged. Home Assistant's own automation was writing the target current on every tick regardless of whether it had actually changed, so the integration itself was generating pure no-op traffic against a device that reacts destructively to being told what it already knows.

Two secondary defects were entangled with the same write paths. A failed PATCH raised `EcovolterApiClientCommunicationError`, which does not subclass `HomeAssistantError`, so Home Assistant logged it as an unexpected exception with a full traceback and the automation's `continue_on_error: true` could not suppress it. Separately, `totalChargedEnergy` — a lifetime, never-resetting counter — was declared `SensorStateClass.TOTAL_INCREASING`, a state class Home Assistant's recorder reserves for counters that reset to zero and only climb; an observed device-side dip (1905.34 → 1905.27 kWh) was tripping the recorder's monotonicity warning.

Causality between the no-op writes and the contactor drops cannot be proven from Home Assistant's own data: a write holds `_request_lock` in `custom_components/ecovolter/api.py`, which blocks the poll queued behind it, so the ~24 seconds during which the contactor actually opened are unobservable from the coordinator's perspective. The fix (PR #7, opened against `main`, unmerged as of this writing) treats write suppression as justified on its own terms — a device that already holds a value should never be told to set it again — independent of whether it turns out to be the root cause of the interruptions.

## Symptoms

- Charging interrupted three times in one day, each a contactor-drop-and-session-reset pattern (all three phase currents collapsing together, session energy resetting to zero), not a current reduction or thermal derate (`temperature_current_limit` stayed at 0 A throughout).
- Each interruption aligned exactly with a timed-out `PATCH /settings` call from the user's automation.
- The requested value in every failing write matched the charger's already-current setting (6 A) — the automation was rewriting an unchanged value on every tick.
- Write failures surfaced in the Home Assistant log as unexpected-exception tracebacks rather than a single categorized error line, and `continue_on_error: true` on the automation's write step had no effect because `EcovolterApiClientCommunicationError` did not subclass `HomeAssistantError`.
- The recorder logged a `total_increasing` monotonicity warning against `totalChargedEnergy` whenever the device-reported lifetime total dipped slightly.

## What Didn't Work

**Adding an explicit `async_start_reauth()` call for write-path auth failures, mirroring core Blink's pattern.** All the framework paths in this section are inside the installed Home Assistant package (`.venv/lib/python3.14/site-packages/homeassistant/`), not this repo. Home Assistant's coordinator machinery (`helpers/update_coordinator.py`) automatically calls `self.config_entry.async_start_reauth(self.hass)` when `ConfigEntryAuthFailed` is caught *inside* `_async_refresh()` (the exception is caught and re-dispatched around lines 458–461 and 523–539 of that file). But `ConfigEntryAuthFailed` raised from a service-call handler — `async_turn_on`, `async_set_native_value`, `async_select_option` — never goes through `_async_refresh()`. Neither `helpers/entity_platform.py` nor `helpers/service.py` (the generic entity service-call dispatch path) has any special-case handling for `ConfigEntryAuthFailed`; the only place `entity_platform.py` catches it (line 543) is in platform-forwarding setup, and `config_entries.py`'s only catch (around its `except ConfigEntryAuthFailed as exc:` block near line 813) is in `async_setup_entry`'s exception handling — neither runs on the service-call path. So raising `ConfigEntryAuthFailed` from our write handlers, as originally shipped in an early commit in PR #7, propagates as an ordinary `HomeAssistantError` subclass with no reauth side effect, despite that commit's message claiming it "also starts reauthentication."

Core's `blink/switch.py` (also in the installed `homeassistant` package, under `homeassistant/components/blink/switch.py`) proves this is a known, necessary pattern: it calls `self.coordinator.config_entry.async_start_reauth(self.hass)` explicitly, immediately before `raise ConfigEntryAuthFailed(...)`, from its own `async_turn_on`/`async_turn_off`. We tried the same thing here. It broke immediately: `ConfigEntry.async_start_reauth()` (`config_entries.py`, `async_start_reauth`) schedules `hass.async_create_task(self._async_init_reauth(...))` — a background task — and that task crashed with `homeassistant.data_entry_flow.UnknownStep: Handler EcovolterFlowHandler doesn't support step reauth`, because `custom_components/ecovolter/config_flow.py` defines only `async_step_user` (confirmed: grepping the file for `async_step` and `reauth` turns up no `async_step_reauth`/`async_step_reauth_confirm` methods at all). The crash surfaced through `tests/test_write_errors.py` when `hass.async_block_till_done()` re-raised the scheduled task's exception. We reverted the `async_start_reauth()` call rather than build the missing reauth config-flow steps in this PR — see Prevention.

**Using `caplog.at_level(...)` to assert the debug log line for a suppressed write.** In this environment, `pytest` 9.0.3 (unpinned in `requirements.txt`) and `pytest-homeassistant-custom-component` 0.13.340 disagree over the `caplog` fixture's override mechanics — calling `caplog.at_level(...)` raised `recursive dependency involving fixture 'caplog' detected`. Worked around in `tests/test_no_op_writes.py` (`test_suppressed_write_logs_at_debug`) by patching the shared `LOGGER` instance directly (`custom_components/ecovolter/const.py`) with `unittest.mock.patch.object(LOGGER, "debug")` and asserting on the captured call args instead of going through `caplog` at all.

**Assuming the `TOTAL_INCREASING` → `TOTAL` state-class change would need a statistics migration/repair.** This was a wrong assumption from training-data memory, not a real requirement. `DEFAULT_STATISTICS` in `.venv/lib/python3.14/site-packages/homeassistant/components/sensor/recorder.py` maps `SensorStateClass.TOTAL` and `SensorStateClass.TOTAL_INCREASING` to identical statistics metadata and mean type, so switching the declared state class needed no statistics repair prompt or user action.

## Solution

**1. A shared no-op predicate on the optimistic entity base, checked before every PATCH.** `OptimisticEcovolterEntity._is_no_op_write()` in `custom_components/ecovolter/entity.py:91-104`:

```python
def _is_no_op_write(self, requested_raw: Any) -> bool:
    if self._optimistic_set:
        return self._values_match(requested_raw, self._optimistic_value)
    if not self.coordinator.data_is_fresh:
        return False
    return self._values_match(requested_raw, self._device_value())
```

It compares against a pending optimistic value first (the integration's own record of what it last sent — freshness doesn't apply to it), otherwise against the coordinator's device value, gated on `coordinator.data_is_fresh` (`custom_components/ecovolter/coordinator.py:80`) so a value the device silently dropped is still re-asserted while stale data is being served.

**2. A single write-sequence helper, added after a code-review finding that the suppression/PATCH/optimistic/refresh sequence was duplicated across all three write platforms.** `OptimisticEcovolterEntity._async_write_setting()` in `custom_components/ecovolter/entity.py:130-147` (introduced as a follow-up commit in PR #7, consolidating logic first added per-platform earlier in the same PR):

```python
async def _async_write_setting(self, key: str, value: Any) -> None:
    if self._is_no_op_write(value):
        LOGGER.debug(
            "Skipping no-op write for %s: %s already in effect",
            self.entity_id,
            value,
        )
        return

    await self._async_set_settings({key: value})
    self._apply_optimistic(value)
    await self.coordinator.async_request_refresh()
```

Each platform's write handler now applies its own value transform first, then delegates:
- `number.py:198-215` — `async_set_native_value` clamps current keys via `clamp_int(int(value), lo, hi)` or rounds `kwhPrice` to two decimals, *then* calls `self._async_write_setting(key, value)` with the post-transform value — so a 40 A request that clamps to 32 A is compared, stored optimistically, and would be suppressed against 32, never against the pre-clamp 40.
- `switch.py:105-111` — `async_turn_on`/`async_turn_off` call `self._async_write_setting(self.entity_description.key, True/False)` directly (no transform needed for booleans).
- `select.py:84-96` — `async_select_option` maps the ISO currency code to the device's int encoding via `CURRENCY_INV_MAP`, raises `ServiceValidationError` (translation key `unsupported_currency`) for an unmapped option, then calls `self._async_write_setting("currency", value)`.

**3. Write failures mapped to Home Assistant error types.** `OptimisticEcovolterEntity._async_set_settings()` in `entity.py:106-128`:

```python
try:
    await self.coordinator.config_entry.runtime_data.client.async_set_settings(data)
except EcovolterApiClientAuthenticationError as exception:
    raise ConfigEntryAuthFailed(
        translation_domain=DOMAIN,
        translation_key="write_auth_failed",
    ) from exception
except EcovolterApiClientError as exception:
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="write_failed",
        translation_placeholders={"error": str(exception)},
    ) from exception
```

Both exception types carry `translation_domain`/`translation_key`, resolved through `custom_components/ecovolter/strings.json:28-38` and mirrored in `custom_components/ecovolter/translations/en.json:28-38` and `custom_components/ecovolter/translations/cs.json:28-38` (`write_failed`, `write_auth_failed`, `unsupported_currency`). Because `ConfigEntryAuthFailed` subclasses `HomeAssistantError`, both get single-line categorized logging and both honor `continue_on_error` in the caller's automation. The original client exception is chained with `from exception` so it still appears in debug-level tracebacks.

**4. The lifetime energy sensor's state class corrected.** `custom_components/ecovolter/sensor.py:233-240`, the `totalChargedEnergy` `SensorEntityDescription`, now declares `state_class=SensorStateClass.TOTAL` (was `TOTAL_INCREASING`), with `device_class`, unit, and `suggested_display_precision` unchanged, and no `last_reset` set.

**5. Test coverage** added across three new files:
- `tests/test_no_op_writes.py` — suppression on an unchanged value across all three platforms; the optimistic-pending-vs-fresh-coordinator comparison branches (`test_repeat_write_same_value_while_optimistic_pending_records_no_second_call`, `test_write_different_value_while_optimistic_pending_is_sent`); clamp-before-compare (`test_clamped_value_matching_device_value_records_no_call` — a 100 A request that clamps to the already-confirmed 32 A max is suppressed); the `kwhPrice` 0.005 tolerance window in both directions; the stale-data bypass (`test_stale_data_does_not_suppress_matching_write`, forcing `data_is_fresh` false via a fake communication failure then confirming a matching write is still sent); a missing coordinator key being written, not suppressed; and the debug log assertion via `patch.object(LOGGER, "debug")` (`test_suppressed_write_logs_at_debug`).
- `tests/test_write_errors.py` — `HomeAssistantError` on communication failure, `ConfigEntryAuthFailed` on auth failure, translation-catalogue resolution (asserting the raised message is not the raw `write_failed` key), `ServiceValidationError` on an unsupported currency, and a static cross-catalogue check (`test_exception_translation_keys_match_across_catalogues`) that every `exceptions` key in `custom_components/ecovolter/strings.json` also exists in both `custom_components/ecovolter/translations/en.json` and `custom_components/ecovolter/translations/cs.json`.
- `tests/test_sensor_statistics.py` — the `total` state class attribute, a decreasing-value sequence (1905.34 → 1905.27) accepted without error, and device class/unit unchanged.

## Why This Works

**Suppression removes writes that cannot change anything, on a device that has shown it does not tolerate being told what it already knows.** The correlation between no-op PATCH timeouts and contactor drops was 1:1 across all three 2026-07-25 interruptions and the setpoint was unchanged across the whole window at 6 A. Whether the firmware's unconditional reapplication of the current limit is truly the cause of the contactor cycling remains a field question — the write holds `_request_lock` in `custom_components/ecovolter/api.py`, blocking the poll queued behind it, so the ~24-second window in which the contactor actually opened is unobservable from Home Assistant's side and causality cannot be proven from this data alone. But suppressing no-op writes is justified independent of that hypothesis: a PATCH that cannot change device state has no legitimate reason to be sent to a fragile single-connection device, regardless of what turns out to be causing the drops.

**Reusing `_values_match()`/`_device_value()` instead of new comparison logic keeps suppression aligned with each platform's value domain.** These hooks already encode per-platform comparison semantics established in the prior resilience work (switch: bool equality; select: int equality; number: 0.005 float tolerance for round-trip drift). A parallel comparison path for suppression would have risked drifting out of sync with the optimistic-confirmation logic in `_handle_coordinator_update()` (`entity.py:149-169`), which uses the same hooks to decide when a pending optimistic value is confirmed.

**Gating on `data_is_fresh` prevents suppression from masking a device that silently dropped a setting.** If the coordinator is serving tolerated-stale data, its cached value may predate a device-side change the integration hasn't observed yet; suppressing a write in that state could permanently leave the device out of sync with the user's intent. `data_is_fresh` (`coordinator.py:80`) was added in the prior resilience work specifically to make this kind of staleness-aware decision, and suppression reuses it rather than introducing a second freshness signal.

**`ConfigEntryAuthFailed` subclassing `HomeAssistantError` gets single-line logging and `continue_on_error` support "for free," even without a working reauth flow.** The categorized-logging and `continue_on_error` behavior that motivated this fix come purely from the exception being a `HomeAssistantError` subclass, verified independent of whether reauth actually triggers. The reauth side effect is a separate, best-effort bonus that only fires today when `ConfigEntryAuthFailed` is raised from inside the coordinator's own `_async_refresh()` — not from these write handlers — which is why "an auth failure during a write starts reauthentication" is only partially met, and is called out explicitly rather than silently left broken.

**`SensorStateClass.TOTAL` matches the actual shape of the data.** Home Assistant's sensor entity docs assign `TOTAL_INCREASING` to counters that reset to zero and climb (e.g. per-session energy), and `TOTAL` (without `last_reset`) to values that never reset. `totalChargedEnergy` is a lifetime counter that can dip slightly on a device-side adjustment — exactly the case `TOTAL` is documented for — and the recorder's `DEFAULT_STATISTICS` mapping (`.venv/lib/python3.14/site-packages/homeassistant/components/sensor/recorder.py`, the installed Home Assistant package — not a path in this repo) treats the two classes identically for statistics metadata, so the correction was free of migration cost.

## Prevention

- **Never add write retries to this integration.** A timed-out `PATCH /settings` may have already applied on the device before the timeout was observed; retrying risks requesting a second, unwanted contactor cycle. This was an explicit plan decision (KTD7 in `docs/plans/2026-07-29-001-fix-no-op-write-suppression-plan.md`), not an oversight — treat any future proposal to add retry logic on this write path as contraindicated by the evidence, not merely unnecessary.
- **The write-path reauth gap is a known, accepted scope boundary, not a bug to silently fix later.** `ConfigEntryAuthFailed` raised from `async_turn_on`/`async_set_native_value`/`async_select_option` does not currently trigger Home Assistant's reauth flow, because that only happens automatically when the exception is caught inside the coordinator's `_async_refresh()` (`helpers/update_coordinator.py`), and this integration's `config_flow.py` has no `async_step_reauth`/`async_step_reauth_confirm` at all. Fixing this properly requires adding those config-flow steps (following the pattern in the installed Home Assistant package's `blink/config_flow.py` alongside its `switch.py`'s explicit `async_start_reauth()` call) — a new feature, deliberately deferred out of this PR. If a future auth-failure investigation touches this integration, check whether the reauth flow was added before assuming write-path auth failures self-heal.
- **A narrow write-suppression race is a documented residual risk, not an oversight.** `_is_no_op_write()` runs before the PATCH is awaited, and optimistic state is only recorded after the PATCH succeeds (`_async_write_setting`, `entity.py:130-147`). Two same-value writes issued close together (e.g. two rapid automation ticks) can both pass the no-op check before either records optimistic state, both sending PATCHes. A synchronous in-flight-write guard would close this but was deliberately not added in this PR — if it needs revisiting, the fix belongs in `_async_write_setting`, not in the per-platform handlers.
- **`caplog` is broken for this repo's pytest/pytest-homeassistant-custom-component combination.** If a future test needs to assert on a log line, patch the target `LOGGER` instance directly (as in `tests/test_no_op_writes.py`'s `test_suppressed_write_logs_at_debug`) rather than reaching for `caplog.at_level(...)`, which raises `recursive dependency involving fixture 'caplog' detected` in this environment (`pytest` 9.0.3 unpinned in `requirements.txt`, `pytest-homeassistant-custom-component` 0.13.340).
- **Don't assume a `SensorStateClass` change needs a statistics migration without checking `DEFAULT_STATISTICS` in Home Assistant's own `homeassistant/components/sensor/recorder.py` (installed under `.venv/lib/.../site-packages/`) first.** `TOTAL` and `TOTAL_INCREASING` share identical statistics metadata and mean-type mapping; only changes that cross into a genuinely different statistics type need a repair story.
- **When reusing a core pattern from another integration (e.g. Blink's explicit `async_start_reauth()` before raising `ConfigEntryAuthFailed`), verify the local config flow actually implements the corresponding step before wiring the call in** — the failure mode is a background-task crash (`UnknownStep`) that only surfaces once `hass.async_block_till_done()` re-raises it, which can look unrelated to the change that caused it.

## Related Issues

- `docs/plans/2026-07-29-001-fix-no-op-write-suppression-plan.md` — the plan this fix implements.
- `docs/plans/2026-06-28-001-feat-charger-resilience-and-optimistic-updates-plan.md` — the prior resilience/optimistic-updates work whose `_values_match`/`_device_value`/`data_is_fresh` hooks this fix reuses.
- PR #7 (`fix/no-op-write-suppression`, opened against `main`, unmerged as of this writing).
