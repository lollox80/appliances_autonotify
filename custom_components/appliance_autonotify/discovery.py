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
    PREFERRED_PLATFORMS,
    TYPE_DISCOVERY,
    TYPE_VACUUM,
    VENDOR_KEY_PREFIXES,
    VENDOR_KEYS,
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
    # how its cycle is told, None for an appliance of a vendor platform
    type: str | None = None


@dataclass(frozen=True)
class PowerMonitor:
    """A power sensor whose name says it's on an appliance that runs in cycles"""

    entity_id: str
    name: str


def vendor_key(entity: er.RegistryEntry) -> str:
    """The translation key of an entity, as Home Connect has it where its platform names it otherwise"""
    key = entity.translation_key or ""
    if key in (keys := VENDOR_KEYS.get(entity.platform, {})):
        return keys[key]
    return next((k for prefix, k in VENDOR_KEY_PREFIXES.get(entity.platform, {}).items() if key.startswith(prefix)), key)


def device_with(device_registry: dr.DeviceRegistry, identifier: tuple[str, str]) -> dr.DeviceEntry | None:
    """The device with the identifier, of whichever config entry, by the lookup of the Home Assistant release"""
    if hasattr(device_registry, "async_get_devices"):
        # from Home Assistant 2026.10, when identifiers stopped being unique across config entries
        return next(iter(device_registry.async_get_devices(identifiers={identifier})), None)
    return device_registry.async_get_device(identifiers={identifier})


def companion_ids(identifiers: set[tuple[str, str]], platform: str) -> set[tuple[str, str]]:
    """The identifiers another platform would have for the same appliance, by the same id within its own platform"""
    return {(platform, value) for _, value in identifiers}


@callback
def preferred_device(hass: HomeAssistant, identifiers: set[tuple[str, str]]) -> dr.DeviceEntry | None:
    """The device of the platform preferred to that of the identifiers for the same appliance, where there is one"""
    device_registry = dr.async_get(hass)
    for domain, _ in identifiers:
        if (preferred := PREFERRED_PLATFORMS.get(domain)) is None:
            continue
        for identifier in companion_ids(identifiers, preferred):
            if (other := device_with(device_registry, identifier)) is not None:
                return other
    return None


@callback
def fallback_device(hass: HomeAssistant, identifiers: set[tuple[str, str]]) -> dr.DeviceEntry | None:
    """The device of a platform that of the identifiers is preferred to, for the same appliance, where there is one"""
    device_registry = dr.async_get(hass)
    for domain, _ in identifiers:
        for other_platform, preferred in PREFERRED_PLATFORMS.items():
            if preferred != domain:
                continue
            for identifier in companion_ids(identifiers, other_platform):
                if (other := device_with(device_registry, identifier)) is not None:
                    return other
    return None


@callback
def find_appliances(hass: HomeAssistant) -> list[Appliance]:
    """Devices of the known platforms that have a cycle state entity, and robot vacuums of any make"""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    found: dict[str, Appliance] = {}
    for entity in entity_registry.entities.values():
        if entity.device_id is None or entity.disabled:
            continue
        if entity.domain == TYPE_VACUUM:
            kind: str | None = TYPE_VACUUM
        elif entity.translation_key is not None and CYCLE_KEYS.get(entity.platform) == vendor_key(entity):
            kind = None
        else:
            continue
        device = device_registry.async_get(entity.device_id)
        if device is not None and kind is None and preferred_device(hass, device.identifiers) is not None:
            # the same appliance through a platform preferred to this one, so set up through that instead
            continue
        if device is not None:
            found[device.id] = Appliance(device.id, device.name_by_user or device.name or entity.entity_id, kind)
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
    """The switch of the device a power sensor is on, where it has only the one, so the plug the appliance is on.
    A setting, such as a dryer's own Wrinkle prevent, isn't a plug, so isn't counted"""
    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(power_entity_id)
    if entity is None or entity.device_id is None:
        return None
    switches = [
        switch.entity_id
        for switch in er.async_entries_for_device(entity_registry, entity.device_id)
        if switch.domain == SWITCH_DOMAIN and switch.entity_category is None
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
            data={CONF_DEVICE_ID: appliance.device_id, CONF_NAME: appliance.name}
            | ({CONF_TYPE: appliance.type} if appliance.type else {}),
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
        created = event.data["action"] == "create"
        if (created and (entity.platform in CYCLE_KEYS or entity.domain == TYPE_VACUUM)) or is_power_sensor(entity):
            async_discover(hass)

    @callback
    def device_registry_updated(event: Event[EventDeviceRegistryUpdatedData]) -> None:
        # a plug renamed after the appliance it's on
        if event.data["action"] == "update" and {"name", "name_by_user"} & set(event.data["changes"]):
            async_discover(hass)

    hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, entity_registry_updated)
    hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, device_registry_updated)
    async_discover(hass)
