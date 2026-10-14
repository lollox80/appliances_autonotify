"""Find appliances with an identifiable cycle, and set each up or offer it as a discovered config entry"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_INTEGRATION_DISCOVERY
from homeassistant.const import CONF_DEVICE_ID, CONF_NAME, CONF_TYPE, UnitOfPower
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import discovery_flow
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_AUTO_DISCOVER,
    CONF_POWER_ENTITY,
    CYCLE_KEYS,
    CYCLE_TYPES,
    DERIVED_POWER_PLATFORMS,
    DOMAIN,
    TYPE_DISCOVERY,
)
from .words import name_type

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import EventDeviceRegistryUpdatedData
    from homeassistant.helpers.entity_registry import EventEntityRegistryUpdatedData

POWER_DEVICE_CLASS = "power"
SENSOR_DOMAIN = "sensor"
SWITCH_DOMAIN = "switch"


@dataclass(frozen=True)
class Appliance:
    device_id: str
    name: str


@dataclass(frozen=True)
class PowerMonitor:
    """A power sensor whose name says it's on an appliance that runs in cycles"""

    entity_id: str
    name: str


@callback
def find_appliances(hass: HomeAssistant) -> list[Appliance]:
    """Devices of the known platforms that have a cycle state entity"""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    found: dict[str, Appliance] = {}
    for entity in entity_registry.entities.values():
        if entity.device_id is None or entity.disabled or entity.translation_key is None:
            continue
        if CYCLE_KEYS.get(entity.platform) != entity.translation_key:
            continue
        device = device_registry.async_get(entity.device_id)
        if device is not None:
            found[device.id] = Appliance(device.id, device.name_by_user or device.name or entity.entity_id)
    return list(found.values())


def is_power_sensor(entity: er.RegistryEntry) -> bool:
    """A power sensor in watts, measured by the device itself rather than estimated or worked out from others"""
    return (
        entity.domain == SENSOR_DOMAIN
        and (entity.device_class or entity.original_device_class) == POWER_DEVICE_CLASS
        and entity.unit_of_measurement == UnitOfPower.WATT
        and entity.platform not in DERIVED_POWER_PLATFORMS
    )


def names_cycle_appliance(hass: HomeAssistant, name: str) -> bool:
    """Whether a name is that of an appliance that runs in cycles, by the same words that choose its icon"""
    return name_type(hass, name) in CYCLE_TYPES


@callback
def find_power_monitors(hass: HomeAssistant) -> list[PowerMonitor]:
    """Power sensors named for an appliance, such as a "Washing machine" plug, one for each device"""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    # a device already set up by its own integration has no need of its power too
    configured = {entry.unique_id for entry in hass.config_entries.async_entries(DOMAIN, include_ignore=True)}
    found: dict[str, PowerMonitor] = {}
    for entity in sorted(entity_registry.entities.values(), key=lambda e: e.entity_id):
        if entity.disabled or not is_power_sensor(entity):
            continue
        device = device_registry.async_get(entity.device_id) if entity.device_id else None
        if device is not None and (device.id in configured or device.id in found):
            continue
        device_name = (device.name_by_user or device.name or "") if device is not None else ""
        entity_name = entity.name or entity.original_name or ""
        if not names_cycle_appliance(hass, f"{device_name} {entity_name}"):
            continue
        found[device.id if device is not None else entity.entity_id] = PowerMonitor(
            entity.entity_id, device_name or entity_name or entity.entity_id
        )
    return list(found.values())


@callback
def plug_switch(hass: HomeAssistant, power_entity_id: str) -> str | None:
    """The switch of the device a power sensor is on, where it has only the one, so the plug the appliance is on"""
    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(power_entity_id)
    if entity is None or entity.device_id is None:
        return None
    switches = [
        switch.entity_id
        for switch in er.async_entries_for_device(entity_registry, entity.device_id)
        if switch.domain == SWITCH_DOMAIN
    ]
    return switches[0] if len(switches) == 1 else None


@callback
def auto_discovery(hass: HomeAssistant) -> bool:
    """Whether appliances found are set up without asking, so not while the discovery entry is disabled or deleted"""
    return any(
        entry.data.get(CONF_TYPE) == TYPE_DISCOVERY and entry.options.get(CONF_AUTO_DISCOVER)
        for entry in hass.config_entries.async_entries(DOMAIN, include_disabled=False)
    )


@callback
def async_discover(hass: HomeAssistant) -> None:
    """Set up every appliance found, or with automatic discovery off, offer each to be added"""
    source = SOURCE_IMPORT if auto_discovery(hass) else SOURCE_INTEGRATION_DISCOVERY
    for appliance in find_appliances(hass):
        # appliances already configured, ignored or in progress are dropped by the flow's unique id
        discovery_flow.async_create_flow(
            hass,
            DOMAIN,
            context={"source": source},
            data={CONF_DEVICE_ID: appliance.device_id, CONF_NAME: appliance.name},
        )
    for monitor in find_power_monitors(hass):
        # only ever offered, since the name is a guess where a cycle state entity isn't, and the threshold is
        # worth a look before it's set up
        discovery_flow.async_create_flow(
            hass,
            DOMAIN,
            context={"source": SOURCE_INTEGRATION_DISCOVERY},
            data={CONF_POWER_ENTITY: monitor.entity_id, CONF_NAME: monitor.name},
        )


@callback
def async_start_discovery(hass: HomeAssistant) -> None:
    """Look for appliances now, and again whenever one may have been added or named"""

    @callback
    def entity_registry_updated(event: Event[EventEntityRegistryUpdatedData]) -> None:
        if event.data["action"] not in ("create", "update"):
            return
        entity = er.async_get(hass).async_get(event.data["entity_id"])
        if entity is None:
            return
        if (event.data["action"] == "create" and entity.platform in CYCLE_KEYS) or is_power_sensor(entity):
            async_discover(hass)

    @callback
    def device_registry_updated(event: Event[EventDeviceRegistryUpdatedData]) -> None:
        # a plug renamed after the appliance it's on
        if event.data["action"] == "update" and {"name", "name_by_user"} & set(event.data["changes"]):
            async_discover(hass)

    hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, entity_registry_updated)
    hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, device_registry_updated)
    async_discover(hass)
