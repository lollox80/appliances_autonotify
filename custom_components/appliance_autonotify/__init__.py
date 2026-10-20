"""Appliance Auto Notify - automatic notifications for household appliance cycles"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_TYPE
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_DASHBOARD,
    CONF_DASHBOARD_FOUND,
    CONF_LIVE_TITLE,
    CONF_PROGRAM_IN_TITLE,
    DOMAIN,
    LIVE_TITLE_NAME,
    TYPE_DISCOVERY,
    TYPE_POWER,
    TYPE_VACUUM,
)
from .dashboards import matching_dashboard
from .device import async_register_device
from .discovery import async_discover, async_start_discovery
from .watcher import ApplianceWatcher, HomeConnectWatcher, PowerWatcher, VacuumWatcher
from .words import async_load_words

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type AppliancesConfigEntry = ConfigEntry[ApplianceWatcher]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    await async_load_words(hass)
    async_start_discovery(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: AppliancesConfigEntry) -> bool:
    if entry.version > 1:
        # from a later version, so not to be guessed at
        return False
    if entry.minor_version < 2:
        options = dict(entry.options)
        # the program left out of the title is the name alone, and left in it is the choice as it comes
        if options.pop(CONF_PROGRAM_IN_TITLE, True) is False:
            options[CONF_LIVE_TITLE] = LIVE_TITLE_NAME
        hass.config_entries.async_update_entry(entry, options=options, minor_version=2)
    if entry.minor_version < 3:
        # set up before a dashboard was looked for, so left with whatever was chosen
        hass.config_entries.async_update_entry(entry, data=entry.data | {CONF_DASHBOARD_FOUND: True}, minor_version=3)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AppliancesConfigEntry) -> bool:
    if entry.data.get(CONF_TYPE) == TYPE_DISCOVERY:
        # nothing to watch, only to look again now that automatic discovery may have been switched
        async_discover(hass)
        return True
    watchers: dict[str | None, type[ApplianceWatcher]] = {TYPE_POWER: PowerWatcher, TYPE_VACUUM: VacuumWatcher}
    watcher = watchers.get(entry.data.get(CONF_TYPE), HomeConnectWatcher)(hass, entry)
    watcher.async_start()
    watcher.async_listen_for_actions()
    entry.runtime_data = watcher
    async_register_device(hass, entry, watcher.name)
    if not entry.data.get(CONF_DASHBOARD_FOUND):
        _choose_dashboard(hass, entry, watcher)
    return True


def _choose_dashboard(hass: HomeAssistant, entry: AppliancesConfigEntry, watcher: ApplianceWatcher) -> None:
    """A dashboard named for the appliance or its type, chosen as it's first set up, once its type is known, to be
    changed or cleared in its settings like one chosen by hand"""
    options = dict(entry.options)
    if not options.get(CONF_DASHBOARD) and (match := matching_dashboard(hass, watcher.name, watcher.appliance_type)):
        options[CONF_DASHBOARD] = match
    hass.config_entries.async_update_entry(entry, data=entry.data | {CONF_DASHBOARD_FOUND: True}, options=options)


async def async_unload_entry(hass: HomeAssistant, entry: AppliancesConfigEntry) -> bool:
    # the watcher's listeners are removed by the entry's own unload callbacks
    return True
