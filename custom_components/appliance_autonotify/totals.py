"""What a cycle came to: how long it took, the energy it used, and what that cost"""

from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT, STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfEnergy
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

if TYPE_CHECKING:
    from datetime import datetime, timedelta

    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

ENERGY_DOMAIN = "energy"
# symbols of the commonest currencies, any other being shown by its code
CURRENCY_SYMBOLS: dict[str, str] = {"EUR": "€", "USD": "$", "GBP": "£", "CHF": "CHF", "JPY": "¥"}


def format_duration(duration: timedelta) -> str:
    """As short as a notification wants it, such as 50min or 1h 40min"""
    minutes = max(round(duration.total_seconds() / 60), 1)
    hours, minutes = divmod(minutes, 60)
    if not hours:
        return f"{minutes}min"
    return f"{hours}h {minutes}min" if minutes else f"{hours}h"


def _cents(value: float) -> Decimal:
    """Rounded to two places as a person would, half a cent up, not to the nearest float"""
    return Decimal(str(round(value, 6))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_time(when: datetime) -> str:
    """The time of day, in Home Assistant's time zone, such as 11:29"""
    return dt_util.as_local(when).strftime("%H:%M")


def format_energy(kwh: float) -> str:
    return f"{_cents(kwh)} kWh"


def format_cost(hass: HomeAssistant, cost: float) -> str:
    currency = hass.config.currency
    return f"{_cents(cost)} {CURRENCY_SYMBOLS.get(currency, currency)}"


def energy_entity_id(hass: HomeAssistant, device_id: str | None) -> str | None:
    """The sensor of the device that adds up the energy it uses, such as a smart plug's, where it has one"""
    if device_id is None:
        return None
    for entry in er.async_entries_for_device(er.async_get(hass), device_id):
        if entry.domain != "sensor":
            continue
        state = hass.states.get(entry.entity_id)
        device_class = (state.attributes.get(ATTR_DEVICE_CLASS) if state else None) or entry.device_class
        device_class = device_class or entry.original_device_class
        if device_class == SensorDeviceClass.ENERGY:
            return entry.entity_id
    return None


def energy_reading(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """The energy meter's reading, in kWh, None if it isn't known"""
    state = hass.states.get(entity_id) if entity_id else None
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None
    try:
        return EnergyConverter.convert(
            float(state.state),
            state.attributes.get(ATTR_UNIT_OF_MEASUREMENT, UnitOfEnergy.KILO_WATT_HOUR),
            UnitOfEnergy.KILO_WATT_HOUR,
        )
    except ValueError, HomeAssistantError:
        return None


def _price_of(hass: HomeAssistant, source: dict[str, Any]) -> float | None:
    """The price per kWh of a grid source, from an entity or as a number"""
    if number := source.get("number_energy_price"):
        return float(number)
    entity_id = source.get("entity_energy_price")
    state = hass.states.get(entity_id) if entity_id else None
    if state is None:
        return None
    try:
        price = float(state.state)
    except ValueError:
        return None
    # priced per kWh, unless the entity says otherwise
    unit = str(state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) or "").rsplit("/", 1)[-1]
    if unit in EnergyConverter.VALID_UNITS and unit != UnitOfEnergy.KILO_WATT_HOUR:
        price /= EnergyConverter.convert(1, unit, UnitOfEnergy.KILO_WATT_HOUR)
    return price


async def energy_price(hass: HomeAssistant) -> float | None:
    """The price of a kWh from the grid, as set on the Energy dashboard, None where there's none set"""
    if ENERGY_DOMAIN not in hass.config.components:
        return None
    from homeassistant.components.energy.data import async_get_manager

    try:
        manager = await async_get_manager(hass)
    except Exception:
        _LOGGER.debug("APPLIANCES No energy settings to price a cycle with", exc_info=True)
        return None
    # read as plain dicts, since the shape of a grid source has changed between releases of Home Assistant
    settings: dict[str, Any] = dict(manager.data or {})
    sources: list[dict[str, Any]] = settings.get("energy_sources", [])
    for source in sources:
        if source.get("type") != "grid":
            continue
        # one price per grid connection, or, as Home Assistant used to have them, one per meter
        for priced in [source, *source.get("flow_from", [])]:
            if (price := _price_of(hass, priced)) is not None:
                return price
    return None
