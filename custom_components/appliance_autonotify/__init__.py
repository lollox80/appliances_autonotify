"""Appliance Auto Notify - automatic notifications for household appliance cycles"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_TYPE
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_LIVE_TITLE,
    CONF_PROGRAM_IN_TITLE,
    DOMAIN,
    LIVE_TITLE_NAME,
    TYPE_DISCOVERY,
    TYPE_POWER,
    TYPE_VACUUM,
)
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
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AppliancesConfigEntry) -> bool:
    # the watcher's listeners are removed by the entry's own unload callbacks
    return True
