"""The device of each appliance's entry, linked to the device Home Assistant already has for it"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_DEVICE_ID, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import CONF_POWER_ENTITY, TYPE_POWER

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


def source_device(hass: HomeAssistant, entry: ConfigEntry) -> dr.DeviceEntry | None:
    """The device the appliance is watched through: its own, or for one known by its power, the plug's"""
    if entry.data.get(CONF_TYPE) == TYPE_POWER:
        power = er.async_get(hass).async_get(entry.options.get(CONF_POWER_ENTITY, ""))
        device_id = power.device_id if power is not None else None
    else:
        device_id = entry.data.get(CONF_DEVICE_ID)
    # a child device of another, such as a part of a bigger appliance, shares no hardware of its own to link to
    return dr.async_get(hass).async_get(device_id, include_child_devices=False) if device_id else None


@callback
def async_register_device(hass: HomeAssistant, entry: ConfigEntry, name: str) -> dr.DeviceEntry:
    """A device for the entry, so it's listed under the entry on the integration's page, and shown alongside the
    appliance's own device: linked to it, as the same hardware, by the identifiers and connections they have in
    common, or for an appliance known by its power, connected through the plug, which is other hardware"""
    source = source_device(hass, entry)
    area = ar.async_get(hass).async_get_area(source.area_id) if source is not None and source.area_id else None
    suggested_area = area.name if area is not None else None
    if source is None:
        # a power sensor of no device, so with nothing to link to
        return dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id, identifiers={(entry.domain, entry.entry_id)}, name=name
        )
    if entry.data.get(CONF_TYPE) == TYPE_POWER:
        return dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(entry.domain, entry.entry_id)},
            name=name,
            suggested_area=suggested_area,
            via_device_id=source.id,
        )
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=set(source.identifiers),
        connections=set(source.connections),
        name=name,
        manufacturer=source.manufacturer,
        model=source.model,
        model_id=source.model_id,
        suggested_area=suggested_area,
    )
