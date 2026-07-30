"""EcovolterEntity class."""

from __future__ import annotations

from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    DOMAIN,
    CONF_SERIAL_NUMBER,
    OPTIMISTIC_TIMEOUT_SECONDS,
)
from .coordinator import EcovolterDataUpdateCoordinator


class IntegrationEcovolterEntity(CoordinatorEntity[EcovolterDataUpdateCoordinator]):
    """EcovolterEntity class."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True  # let HA compose "<Device name> <Entity name>"

    def __init__(self, coordinator: EcovolterDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)

        serial = coordinator.config_entry.data.get(CONF_SERIAL_NUMBER) or "unknown"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="EcoVolter",
            model="EcoVolter II",  # change if you detect model dynamically
            name=f"EcoVolter ({serial})",  # -> shows up instead of "undefined"
        )


class OptimisticEcovolterEntity(IntegrationEcovolterEntity):
    """Base for writable entities that reflect a write in the UI immediately.

    The optimistic value is always stored in the RAW device domain — the exact
    value sent to the device — and compared against the raw coordinator value.
    Subclasses map raw → display only in their value property. This collapses
    the whole type-mismatch class of bugs (select int↔ISO, switch bool, number
    float) into one rule.
    """

    # Explicit flag, NOT truthiness: None/0/False/"" are all valid real values.
    _optimistic_set: bool = False
    # Raw device-domain value last sent.
    _optimistic_value: Any = None
    # Monotonic loop-clock deadline (immune to NTP/DST; advanced by HA's test
    # time machinery), not dt_util.utcnow().
    _optimistic_expiry: float = 0.0

    def _apply_optimistic(self, raw_value: Any) -> None:
        """Record the just-written raw value and show it immediately.

        Only ever called from the write handlers (async_turn_*/async_set_*),
        which HA invokes after the entity is added to hass, so ``self.hass`` and
        the entity_id are always set here.
        """
        self._optimistic_value = raw_value
        self._optimistic_expiry = self.hass.loop.time() + OPTIMISTIC_TIMEOUT_SECONDS
        self._optimistic_set = True
        self.async_write_ha_state()

    def _clear_optimistic(self) -> None:
        """Drop optimistic state and fall back to coordinator truth."""
        self._optimistic_set = False
        self._optimistic_value = None

    def _device_value(self) -> Any:
        """Raw coordinator value for this entity's key, normalized to the
        optimistic domain. Subclasses must implement."""
        raise NotImplementedError

    def _values_match(self, optimistic_raw: Any, device_raw: Any) -> bool:
        """Whether the device has confirmed the optimistic value.

        Default exact equality; the number platform overrides with a tolerance
        to survive float round-trip drift.
        """
        return optimistic_raw == device_raw

    def _is_no_op_write(self, requested_raw: Any) -> bool:
        """Whether writing requested_raw would not change anything the device holds.

        Compares against a pending optimistic value first (it's the
        integration's own record of what it last sent, so freshness doesn't
        apply to it); otherwise against the coordinator's device value, gated
        on ``data_is_fresh`` so a value the device silently dropped is still
        re-asserted while stale data is being served.
        """
        if self._optimistic_set:
            return self._values_match(requested_raw, self._optimistic_value)
        if not self.coordinator.data_is_fresh:
            return False
        return self._values_match(requested_raw, self._device_value())

    @callback
    def _handle_coordinator_update(self) -> None:
        """Reconcile optimistic state on every coordinator cycle.

        Fires every cycle because always_update keeps its True default.
        """
        if self._optimistic_set:
            if not self.coordinator.last_update_success:
                # AC6: optimistic state must never survive an unavailable
                # transition (and must not resurrect on recovery).
                self._clear_optimistic()
            elif not self.coordinator.data_is_fresh:
                # AC5: serving tolerated-stale data — keep the optimistic value;
                # don't confirm or expire it against data we know is stale.
                pass
            elif self._values_match(self._optimistic_value, self._device_value()):
                self._clear_optimistic()  # confirmed against fresh data
            elif self.hass.loop.time() >= self._optimistic_expiry:
                # Timeout — only ever evaluated against fresh data.
                self._clear_optimistic()
        super()._handle_coordinator_update()
