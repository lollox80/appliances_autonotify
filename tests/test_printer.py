from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.appliance_autonotify.const import CYCLE_SETTLE, DOMAIN

from .conftest import mock_supernotify
from .test_watcher import ANDROID, ended, pass_time, set_state

ICON = "mdi:printer-3d"
# as ha-bambulab names them, by translation key
PRINTER_ENTITIES = ("print_status", "print_progress", "end_time", "remaining_time", "stage", "subtask_name", "current_layer")


def add_printer(hass: HomeAssistant, name: str = "A1") -> dict[str, str]:
    """Register a Bambu Lab printer as ha-bambulab would, returning its device and entities by translation key"""
    source = MockConfigEntry(domain="bambu_lab")
    source.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=source.entry_id, identifiers={("bambu_lab", "03919C430101688")}, name=name
    )
    # and an AMS, a device of its own with nothing to say of the print
    dr.async_get(hass).async_get_or_create(
        config_entry_id=source.entry_id, identifiers={("bambu_lab", "AMS-1")}, name=f"{name}_ams_1"
    )
    entity_registry = er.async_get(hass)
    entities = {"device_id": device.id}
    for key in PRINTER_ENTITIES:
        entities[key] = entity_registry.async_get_or_create(
            "sensor",
            "bambu_lab",
            f"03919C430101688_{key}",
            suggested_object_id=f"{name.lower()}_{key}",
            device_id=device.id,
            config_entry=source,
            translation_key=key,
        ).entity_id
    return entities


async def setup_printer(hass: HomeAssistant, printer: dict[str, str], **options: object) -> MockConfigEntry:
    assert await async_setup_component(hass, "notify", {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="A1",
        unique_id=printer["device_id"],
        data={"device_id": printer["device_id"]},
        options=options,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_printer_is_found(hass: HomeAssistant) -> None:
    printer = add_printer(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["description_placeholders"]["found"] == "Appliances found:\n\n- A1"
    await hass.config_entries.flow.async_configure(result["flow_id"], {"auto_discover": True})
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, printer["device_id"])
    assert entry is not None
    assert entry.data == {"device_id": printer["device_id"]}


async def test_print_is_a_cycle(hass: HomeAssistant) -> None:
    printer = add_printer(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "finish")
    entry = await setup_printer(hass, printer, notify_start=True)
    tag = f"appliance_{entry.entry_id}"

    # getting ready to print is already the start, with the bed still to heat and level
    hass.states.async_set(printer["subtask_name"], "Benchy")
    hass.states.async_set(printer["print_progress"], "0")
    await set_state(hass, printer["print_status"], "prepare")
    assert len(calls) == 1
    assert calls[0].data == {
        "message": "A1 started",
        "title": "A1",
        "force_resend": True,
        "extra_data": {
            "mobile_push_notification_tag": tag,
            "live_update": True,
            "notification_icon": ICON,
            **ANDROID,
            "progress": 0,
            "progress_max": 100,
            "critical_text": "0%",
        },
    }

    # what it's doing as it gets ready, with no progress to show for it
    await set_state(hass, printer["stage"], "heatbed_preheating")
    assert len(calls) == 2
    assert calls[1].data["message"] == "heatbed_preheating"
    assert calls[1].data["title"] == "A1"
    await set_state(hass, printer["stage"], "auto_bed_leveling")
    assert calls[2].data["message"] == "auto_bed_leveling"

    # printing, the same cycle, the printer named alone even with a countdown
    await set_state(hass, printer["print_status"], "running")
    assert len(calls) == 3
    await set_state(hass, printer["end_time"], "2026-10-15T12:30:00+00:00")
    assert len(calls) == 3
    await set_state(hass, printer["stage"], "printing")
    assert calls[3].data["title"] == "A1"
    assert calls[3].data["message"] == "printing"
    assert calls[3].data["extra_data"]["when"] == 1792067400
    await set_state(hass, printer["print_progress"], "5")
    assert calls[4].data["title"] == "A1"
    assert calls[4].data["message"] == "printing"
    assert calls[4].data["extra_data"]["progress"] == 5

    # away for a while, which changes nothing
    for state in ("offline", "unavailable", "running"):
        await set_state(hass, printer["print_status"], state)
    assert len(calls) == 5

    await set_state(hass, printer["print_status"], "finish")
    assert len(calls) == 7
    assert calls[5].data["extra_data"] == {"mobile_push_notification_tag": tag, "mobile_push_clear_notification": True}
    assert calls[6].data == ended("A1", entry.entry_id, ICON, force_resend=True)


async def test_failed_print_has_no_end(hass: HomeAssistant) -> None:
    printer = add_printer(hass)
    calls = mock_supernotify(hass)
    # already printing when Home Assistant starts
    hass.states.async_set(printer["print_status"], "running")
    await setup_printer(hass, printer)
    await set_state(hass, printer["print_status"], "pause")
    await set_state(hass, printer["print_status"], "failed")
    assert len(calls) == 2
    assert calls[0].data["message"] == "pause"
    assert calls[1].data["extra_data"]["mobile_push_clear_notification"] is True


async def test_printer_idle_with_no_word_of_the_end_is_over(hass: HomeAssistant) -> None:
    printer = add_printer(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "idle")
    entry = await setup_printer(hass, printer)
    await set_state(hass, printer["print_status"], "prepare")
    await set_state(hass, printer["print_status"], "idle")
    assert len(calls) == 1
    await pass_time(hass, CYCLE_SETTLE)
    assert len(calls) == 3
    assert calls[2].data == ended("A1", entry.entry_id, ICON, force_resend=True)


async def test_stage_while_idle_is_not_told(hass: HomeAssistant) -> None:
    printer = add_printer(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "idle")
    await setup_printer(hass, printer)
    await set_state(hass, printer["stage"], "changing_filament")
    assert calls == []


async def test_countdown_follows_the_time_left(hass: HomeAssistant, freezer) -> None:
    """The finish time worked out from the time left, which is fresher, and kept to it as the print runs late"""
    freezer.move_to("2026-10-15T09:31:00+00:00")
    printer = add_printer(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    hass.states.async_set(printer["stage"], "printing")
    await setup_printer(hass, printer)
    # a finish time that's a minute out, which the time left, in hours, stands in for
    hours = {"unit_of_measurement": "h"}
    hass.states.async_set(printer["remaining_time"], "0.45", hours)
    hass.states.async_set(printer["end_time"], "2026-10-15T09:59:00+00:00")
    await set_state(hass, printer["print_progress"], "18")
    assert len(calls) == 1
    assert calls[0].data["extra_data"]["when"] == 1792058280
    # a minute on and a minute less, so still on time
    freezer.tick(60)
    hass.states.async_set(printer["remaining_time"], "0.433333333333333", hours)
    await hass.async_block_till_done()
    assert len(calls) == 1
    # running two minutes late
    freezer.tick(60)
    hass.states.async_set(printer["remaining_time"], "0.45", hours)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["extra_data"]["when"] == 1792058280 + 120


async def test_pause_stops_the_countdown(hass: HomeAssistant, freezer) -> None:
    """As a real print, paused for twenty minutes by a clogged nozzle, offline for a moment, then going again"""
    freezer.move_to("2026-10-15T09:32:00+00:00")
    printer = add_printer(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    hass.states.async_set(printer["stage"], "printing")
    hass.states.async_set(printer["remaining_time"], "0.433333333333333", {"unit_of_measurement": "h"})
    await setup_printer(hass, printer)

    await set_state(hass, printer["print_status"], "pause")
    assert len(calls) == 1
    assert calls[0].data["message"] == "pause"
    assert calls[0].data["title"] == "A1"
    assert "when" not in calls[0].data["extra_data"]
    # the time left standing still tells nothing while paused
    freezer.tick(900)
    await set_state(hass, printer["print_status"], "offline")
    await set_state(hass, printer["print_status"], "pause")
    await set_state(hass, printer["end_time"], "2026-10-15T09:58:00+00:00")
    assert len(calls) == 2
    assert "when" not in calls[1].data["extra_data"]

    freezer.tick(300)
    await set_state(hass, printer["print_status"], "running")
    assert len(calls) == 3
    assert calls[2].data["message"] == "printing"
    assert calls[2].data["extra_data"]["when"] == 1792056720 + 1200 + 1560
