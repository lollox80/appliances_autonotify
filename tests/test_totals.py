from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.appliance_autonotify.const import VACUUM_SETTLE
from custom_components.appliance_autonotify.totals import (
    energy_entity_id,
    format_duration,
    speak_cost,
    speak_duration,
    speak_energy,
    spoken,
)

from .conftest import mock_supernotify
from .test_vacuum import add_vacuum, advance, setup_vacuum
from .test_watcher import set_state, setup_power_watcher

if TYPE_CHECKING:
    from unittest.mock import _patch

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

POWER = "sensor.washer_power"
ENERGY = "sensor.washer_energy"
SUMMARY = "📌 Done\n⏱ {duration}\n⚡ {energy}\n💰 {cost}"


def add_plug(hass: HomeAssistant, energy_unit: str = "kWh") -> None:
    """A smart plug, measuring both the power drawn and the energy used, as most do"""
    source = MockConfigEntry(domain="mqtt")
    source.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(config_entry_id=source.entry_id, identifiers={("mqtt", "plug")})
    registry = er.async_get(hass)
    for key, device_class in (("power", "power"), ("energy", "energy")):
        registry.async_get_or_create(
            "sensor",
            "mqtt",
            key,
            suggested_object_id=f"washer_{key}",
            device_id=device.id,
            config_entry=source,
            original_device_class=device_class,
        )
    hass.states.async_set(ENERGY, "100.0", {"unit_of_measurement": energy_unit, "device_class": "energy"})


def priced(hass: HomeAssistant, *sources: dict[str, Any]) -> _patch[Any]:
    """Energy settings with the grid sources given"""
    hass.config.components.add("energy")

    async def manager(_: HomeAssistant) -> SimpleNamespace:
        return SimpleNamespace(data={"energy_sources": [{"type": "solar"}, *sources]})

    return patch("homeassistant.components.energy.data.async_get_manager", manager)


async def tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float) -> None:
    await advance(hass, freezer, seconds)


async def wash(hass: HomeAssistant, freezer: FrozenDateTimeFactory, used: float, minutes: float = 50) -> None:
    """A wash drawing power for the minutes given, the meter going up by what it used"""
    await set_state(hass, POWER, "1800")
    await tick(hass, freezer, minutes * 60)
    hass.states.async_set(ENERGY, f"{100 + used}", hass.states.get(ENERGY).attributes)
    await set_state(hass, POWER, "0")
    await tick(hass, freezer, 120)


async def test_end_tells_what_the_cycle_came_to(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    hass.config.currency = "EUR"
    add_plug(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(POWER, "0", {"unit_of_measurement": "W"})
    with priced(hass, {"type": "grid", "number_energy_price": 0.25, "entity_energy_price": None}):
        await setup_power_watcher(hass, grace_period=120, end_message=SUMMARY, end_title="Lavatrice")
        await wash(hass, freezer, 0.74)
    # up to when it stopped drawing power, not once that was believed
    assert calls[-1].data["message"] == "📌 Done\n⏱ 50 min\n⚡ 0.74 kWh\n💰 0.19 €"


async def test_reminder_tells_it_again(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    add_plug(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(POWER, "0", {"unit_of_measurement": "W"})
    await setup_power_watcher(hass, grace_period=120, reminder=30, end_message="Washed in {duration}")
    await wash(hass, freezer, 0.5, minutes=100)
    assert calls[-1].data["message"] == "Washed in 1 h 40 min"
    await tick(hass, freezer, 30 * 60)
    assert calls[-1].data["message"] == "Washed in 1 h 40 min"


async def test_price_from_an_entity(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    hass.config.currency = "GBP"
    add_plug(hass, energy_unit="Wh")
    calls = mock_supernotify(hass)
    hass.states.async_set(POWER, "0", {"unit_of_measurement": "W"})
    # per MWh, and set the way it was before grid connections, one price per meter
    hass.states.async_set("sensor.tariff", "300", {"unit_of_measurement": "GBP/MWh"})
    source = {"type": "grid", "flow_from": [{"stat_energy_from": "sensor.meter", "entity_energy_price": "sensor.tariff"}]}
    with priced(hass, source):
        await setup_power_watcher(hass, grace_period=120, end_message="{energy}, {cost}")
        await wash(hass, freezer, 2000)
    assert calls[-1].data["message"] == "2.00 kWh, 0.60 £"


async def test_nothing_told_that_isnt_known(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    calls = mock_supernotify(hass)
    hass.states.async_set(POWER, "0", {"unit_of_measurement": "W"})
    # no energy meter, and no price
    with priced(hass, {"type": "grid", "entity_energy_price": "sensor.gone"}):
        await setup_power_watcher(hass, grace_period=120, end_message="{name} done in {duration} using {energy} {cost}")
        await set_state(hass, POWER, "1800")
        await tick(hass, freezer, 10)
        await set_state(hass, POWER, "0")
        await tick(hass, freezer, 120)
    assert calls[-1].data["message"] == "Washer done in 1 min using"


async def test_meter_reset_part_way_through(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    add_plug(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(POWER, "0", {"unit_of_measurement": "W"})
    await setup_power_watcher(hass, grace_period=120, end_message="{duration} {energy}")
    await wash(hass, freezer, -99)
    assert calls[-1].data["message"] == "50 min"


async def test_cycle_under_way_at_startup_has_no_totals(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    add_plug(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(POWER, "1800", {"unit_of_measurement": "W"})
    await setup_power_watcher(hass, grace_period=120, end_message="Washer finished {duration}")
    await set_state(hass, POWER, "0")
    await tick(hass, freezer, 120)
    assert calls[-1].data["message"] == "Washer finished"


async def test_too_short_is_forgotten(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    calls = mock_supernotify(hass)
    hass.states.async_set(POWER, "0", {"unit_of_measurement": "W"})
    await setup_power_watcher(hass, grace_period=60, min_duration=300, end_message="{duration}")
    await set_state(hass, POWER, "1800")
    await tick(hass, freezer, 60)
    await set_state(hass, POWER, "0")
    await tick(hass, freezer, 3600)
    assert calls == []
    # so the next cycle is timed from when it began
    await set_state(hass, POWER, "1800")
    await tick(hass, freezer, 1200)
    await set_state(hass, POWER, "0")
    await tick(hass, freezer, 60)
    assert calls[-1].data["message"] == "20 min"


async def test_vacuum_cleaning_is_timed_till_it_was_back(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    device_id, vacuum = add_vacuum(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(vacuum, "docked")
    await setup_vacuum(hass, device_id, end_message="{name}: {duration}")
    await set_state(hass, vacuum, "cleaning")
    await advance(hass, freezer, 1800)
    # back to wash its mop, then out again
    await set_state(hass, vacuum, "docked")
    await advance(hass, freezer, 120)
    await set_state(hass, vacuum, "cleaning")
    await advance(hass, freezer, 1800)
    await set_state(hass, vacuum, "returning")
    await set_state(hass, vacuum, "docked")
    await advance(hass, freezer, VACUUM_SETTLE)
    assert calls[-1].data["message"] == "Bruno: 1 h 2 min"


async def test_durations(hass: HomeAssistant) -> None:
    assert format_duration(hass, timedelta(seconds=20)) == "1 min"
    assert format_duration(hass, timedelta(minutes=8, seconds=20)) == "8 min"
    assert format_duration(hass, timedelta(hours=2)) == "2 h"
    assert format_duration(hass, timedelta(hours=1, minutes=40)) == "1 h 40 min"


async def test_start_time_as_it_starts_and_ends(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    await hass.config.async_set_time_zone("Europe/Rome")
    freezer.move_to("2026-10-19T09:29:00+00:00")
    add_plug(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(POWER, "0", {"unit_of_measurement": "W"})
    await setup_power_watcher(
        hass,
        grace_period=120,
        notify_start=True,
        start_message="🧺 Started at {start_time}",
        end_message="Started at {start_time}, done in {duration}",
    )
    await wash(hass, freezer, 0.5)
    assert calls[0].data["message"] == "🧺 Started at 11:29"
    assert calls[-1].data["message"] == "Started at 11:29, done in 50 min"


async def test_in_italian_with_a_voice_of_its_own(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    hass.config.language = "it"
    hass.config.currency = "EUR"
    add_plug(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(POWER, "0", {"unit_of_measurement": "W"})
    with priced(hass, {"type": "grid", "number_energy_price": 0.25}):
        await setup_power_watcher(
            hass, grace_period=120, end_title="🧺 Bucato pronto", end_message="{duration} · {energy} · {cost}"
        )
        await wash(hass, freezer, 0.74)
    assert calls[-1].data["title"] == "🧺 Bucato pronto"
    assert calls[-1].data["message"] == "50 min · 0,74 kWh · 0,19 €"
    assert calls[-1].data["spoken_message"] == "Bucato pronto. 50 minuti, 0,74 kilowattora, 19 centesimi."
    # closing the Live Activity says nothing
    assert "spoken_message" not in calls[-2].data


async def test_no_voice_of_its_own_where_the_message_will_do(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    calls = mock_supernotify(hass)
    hass.states.async_set(POWER, "0", {"unit_of_measurement": "W"})
    await setup_power_watcher(hass, grace_period=120, notify_start=True)
    await set_state(hass, POWER, "1800")
    await tick(hass, freezer, 600)
    await set_state(hass, POWER, "0")
    await tick(hass, freezer, 120)
    assert [c.data["message"] for c in calls] == ["Washer started", "Washer is finished", "Washer is finished"]
    assert not any("spoken_message" in c.data for c in calls)


async def test_said_aloud(hass: HomeAssistant) -> None:
    hass.config.currency = "EUR"
    hass.config.language = "it"
    assert speak_duration(hass, timedelta(hours=1, minutes=40)) == "un'ora e 40 minuti"
    assert speak_duration(hass, timedelta(hours=2)) == "2 ore"  # codespell:ignore ore
    assert speak_duration(hass, timedelta(minutes=1)) == "1 minuto"
    assert speak_cost(hass, 1.2) == "1 euro e 20 centesimi"
    assert speak_cost(hass, 0.01) == "1 centesimo"
    assert speak_cost(hass, 0) == "0 centesimi"
    hass.config.language = "en"
    assert speak_duration(hass, timedelta(hours=1, minutes=1)) == "1 hour 1 minute"
    assert speak_cost(hass, 2) == "2 euro"
    assert speak_energy(hass, 1.5) == "1.50 kilowatt hours"
    hass.config.language = "de"
    assert speak_duration(hass, timedelta(minutes=50)) == "50 min"
    assert speak_energy(hass, 1.5) == "1,50 kWh"
    hass.config.currency = "USD"
    assert speak_cost(hass, 1.5) == "1,50 $"
    assert spoken("📌 Done\n⏱️ 50 min\n\n· ok |") == "Done. 50 min. ok."


async def test_energy_meter_rather_than_what_was_used_since_the_last_reading(hass: HomeAssistant) -> None:
    source = MockConfigEntry(domain="smartthings")
    source.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(config_entry_id=source.entry_id, identifiers={("smartthings", "x")})
    registry = er.async_get(hass)
    for key, state_class in (("delta", "measurement"), ("energy", "total_increasing"), ("saved", None)):
        entity = registry.async_get_or_create(
            "sensor", "smartthings", key, suggested_object_id=f"dryer_{key}", device_id=device.id, config_entry=source
        )
        attributes = {"device_class": "energy", "unit_of_measurement": "kWh"}
        hass.states.async_set(entity.entity_id, "1", attributes | ({"state_class": state_class} if state_class else {}))
    assert energy_entity_id(hass, device.id) == "sensor.dryer_energy"
    assert energy_entity_id(hass, None) is None
