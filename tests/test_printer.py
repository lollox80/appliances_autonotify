from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.appliance_autonotify.const import CYCLE_SETTLE, DOMAIN

from .conftest import mock_supernotify
from .test_watcher import ANDROID, ended, pass_time, set_state

ICON = "mdi:printer-3d"
# as ha-bambulab names them, by translation key
PRINT_STATES = ["failed", "finish", "idle", "init", "offline", "pause", "prepare", "running", "slicing", "unknown"]
PRINTER_ENTITIES = ("print_status", "print_progress", "end_time", "remaining_time", "stage", "subtask_name", "current_layer")
EXTRA_ENTITIES = (
    ("binary_sensor", "print_error"),
    ("binary_sensor", "hms_errors"),
    ("sensor", "total_layers"),
    ("button", "pause"),
    ("button", "resume"),
    ("button", "stop"),
    ("camera", "camera"),
    ("sensor", "print_weight"),
    ("sensor", "print_length"),
    ("sensor", "bed_temp"),
)
# the fault of the print of 15 October, as ha-bambulab reported it
NOZZLE = "The nozzle is clogged, or the heatbed is not level"
FAULT = {"code": "0300_8014", "error": NOZZLE}


def add_printer(hass: HomeAssistant, name: str = "A1", extras: bool = False) -> dict[str, str]:
    """Register a Bambu Lab printer as ha-bambulab would, returning its device and entities by translation key, with
    its faults, layer count, pause and resume buttons and camera too where asked for"""
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
            # the states ha-bambulab lists for the print
            capabilities={"options": PRINT_STATES} if key == "print_status" else None,
        ).entity_id
    if extras:
        for domain, key in EXTRA_ENTITIES:
            entities[key] = entity_registry.async_get_or_create(
                domain,
                "bambu_lab",
                f"03919C430101688_{domain}_{key}",
                suggested_object_id=f"{name.lower()}_{key}",
                device_id=device.id,
                config_entry=source,
                translation_key=key,
            ).entity_id
        # and a switch that shares the camera's translation key, which isn't a camera
        entity_registry.async_get_or_create(
            "switch", "bambu_lab", "03919C430101688_enable_camera", device_id=device.id, translation_key="camera"
        )
        hass.states.async_set(entities["camera"], "idle")
        for key in ("print_error", "hms_errors"):
            hass.states.async_set(entities[key], "off")
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
    assert entry.data == {"device_id": printer["device_id"], "dashboard_found": True}


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


def fault_on(hass: HomeAssistant, printer: dict[str, str], attributes: dict[str, str] | None = None) -> None:
    hass.states.async_set(printer["print_error"], "on", FAULT if attributes is None else attributes)


def help_asked(calls: list[ServiceCall]) -> ServiceCall:
    """The notification of the fault, which may go out before or after the Live Activity says it's paused, as the
    fault and the pause reach Home Assistant together"""
    return next(call for call in calls if "_problem" in call.data["extra_data"].get("mobile_push_notification_tag", ""))


def paused(calls: list[ServiceCall]) -> ServiceCall:
    return next(call for call in calls if call.data["extra_data"].get("live_update"))


def buttons(call: ServiceCall) -> list[str]:
    return [a["title"] for a in call.data.get("actions", []) if "action" in a]


async def test_fault_asks_for_help_once(hass: HomeAssistant) -> None:
    """As the print of 15 October: paused by a clogged nozzle, offline a moment while paused, then going again"""
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    hass.states.async_set(printer["stage"], "printing")
    entry = await setup_printer(hass, printer)
    tag = f"appliance_{entry.entry_id}"

    # the fault and the pause came together, the fault first
    fault_on(hass, printer)
    await set_state(hass, printer["print_status"], "pause")
    assert len(calls) == 2
    # the Live Activity offers to carry on, and never to stop
    assert paused(calls).data["message"] == "pause"
    assert buttons(paused(calls)) == ["Resume"]
    assert help_asked(calls).data == {
        "message": f"A1 needs help\n{NOZZLE}",
        "title": "A1",
        "spoken_message": "A1 needs help.",
        "force_resend": True,
        "media": {"camera_entity_id": printer["camera"]},
        "extra_data": {"notification_icon": ICON, "mobile_push_notification_tag": f"{tag}_problem"},
    }

    # off the network and back while still paused, which isn't another fault
    await set_state(hass, printer["print_status"], "offline")
    await set_state(hass, printer["print_status"], "pause")
    assert len(calls) == 3
    assert "needs help" not in calls[2].data["message"]

    # seen to, and going again: the help asked for is out of date, and the Live Activity offers to pause
    hass.states.async_set(printer["print_error"], "off")
    await set_state(hass, printer["print_status"], "running")
    assert len(calls) == 5
    assert calls[3].data["message"] == "printing"
    assert buttons(calls[3]) == ["Pause"]
    assert calls[4].data["extra_data"] == {
        "mobile_push_notification_tag": f"{tag}_problem",
        "mobile_push_clear_notification": True,
    }


async def test_fault_reported_after_the_pause(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    await setup_printer(hass, printer)
    await set_state(hass, printer["print_status"], "pause")
    assert len(calls) == 1
    fault_on(hass, printer)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["message"] == f"A1 needs help\n{NOZZLE}"


async def test_paused_by_hand_is_no_fault(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    await setup_printer(hass, printer)
    await set_state(hass, printer["print_status"], "pause")
    await set_state(hass, printer["print_status"], "running")
    # only the Live Activity, paused and going again
    assert len(calls) == 2
    assert all("help" not in c.data["message"] for c in calls)


async def test_fault_from_others_where_the_print_error_says_nothing(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    await setup_printer(hass, printer)
    hass.states.async_set(
        printer["hms_errors"],
        "on",
        {
            "Count": 2,
            "1-Error": "AMS humidity is high",
            "1-Severity": "Common",
            "2-Error": "Heatbed temperature is abnormal",
            "2-Severity": "Serious",
        },
    )
    fault_on(hass, printer, {"code": "0300_8014", "error": "unknown"})
    await set_state(hass, printer["print_status"], "pause")
    assert help_asked(calls).data["message"] == "A1 needs help\nHeatbed temperature is abnormal"


async def test_fault_with_nothing_said_of_it(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    await setup_printer(hass, printer)
    fault_on(hass, printer, {})
    await set_state(hass, printer["print_status"], "pause")
    assert help_asked(calls).data["message"] == "A1 needs help"


async def test_faults_not_told_when_turned_off(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    await setup_printer(hass, printer, notify_problem=False)
    fault_on(hass, printer)
    await set_state(hass, printer["print_status"], "pause")
    await set_state(hass, printer["print_status"], "failed")
    assert [c.data["message"] for c in calls] == ["pause", "A1 is finished"]
    assert calls[1].data["extra_data"]["mobile_push_clear_notification"] is True


async def test_print_failed_by_a_fault(hass: HomeAssistant, freezer) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    entry = await setup_printer(hass, printer)
    await set_state(hass, printer["print_status"], "failed")
    # the Live Activity closed, and the fault, reported a moment after, told as what stopped it
    assert len(calls) == 1
    freezer.tick(3)
    fault_on(hass, printer)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["message"] == f"Print failed\n{NOZZLE}"
    assert calls[1].data["media"] == {"camera_entity_id": printer["camera"]}
    assert calls[1].data["extra_data"]["mobile_push_notification_tag"] == f"appliance_{entry.entry_id}_problem"
    # the once
    hass.states.async_set(printer["print_error"], "off")
    fault_on(hass, printer)
    await hass.async_block_till_done()
    assert len(calls) == 2


async def test_fault_long_after_a_failed_print_is_not_what_stopped_it(hass: HomeAssistant, freezer) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    await setup_printer(hass, printer)
    await set_state(hass, printer["print_status"], "failed")
    freezer.tick(60)
    fault_on(hass, printer)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_print_stopped_by_hand_has_no_fault_to_tell(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    await setup_printer(hass, printer)
    await set_state(hass, printer["print_status"], "failed")
    assert len(calls) == 1
    assert calls[0].data["extra_data"]["mobile_push_clear_notification"] is True


async def test_fault_told_in_italian(hass: HomeAssistant) -> None:
    hass.config.language = "it"
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    await setup_printer(hass, printer)
    fault_on(hass, printer, {"error": "Ugello intasato"})
    await set_state(hass, printer["print_status"], "pause")
    assert help_asked(calls).data["message"] == "A1 ha bisogno di aiuto\nUgello intasato"
    assert buttons(paused(calls)) == ["Riprendi"]
    await set_state(hass, printer["print_status"], "failed")
    assert calls[-1].data["message"] == "Stampa fallita\nUgello intasato"


async def test_end_comes_with_a_picture(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    entry = await setup_printer(hass, printer, reminder=1)
    await set_state(hass, printer["print_status"], "finish")
    assert calls[-1].data == ended("A1", entry.entry_id, ICON, force_resend=True, media={"camera_entity_id": printer["camera"]})
    # a reminder is only to say it's still waiting
    await pass_time(hass, 60)
    assert calls[-1].data["message"] == "A1 is finished"
    assert "media" not in calls[-1].data


async def test_no_picture_from_a_camera_turned_off(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    hass.states.async_set(printer["camera"], "unavailable")
    await setup_printer(hass, printer)
    await set_state(hass, printer["print_status"], "finish")
    assert "media" not in calls[-1].data


async def test_no_picture_when_turned_off(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    await setup_printer(hass, printer, snapshot=False)
    fault_on(hass, printer)
    await set_state(hass, printer["print_status"], "pause")
    await set_state(hass, printer["print_status"], "finish")
    assert all("media" not in call.data for call in calls)


async def test_pause_and_resume_buttons_press_the_printers(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    mock_supernotify(hass)
    pressed = async_mock_service(hass, "button", "press")
    hass.states.async_set(printer["print_status"], "running")
    entry = await setup_printer(hass, printer)
    for button in ("PAUSE", "RESUME"):
        hass.bus.async_fire("mobile_app_notification_action", {"action": f"APPLIANCE_{button}_{entry.entry_id}"})
    await hass.async_block_till_done()
    assert [c.data for c in pressed] == [{"entity_id": printer["pause"]}, {"entity_id": printer["resume"]}]
    # not once the print is over
    await set_state(hass, printer["print_status"], "finish")
    hass.bus.async_fire("mobile_app_notification_action", {"action": f"APPLIANCE_PAUSE_{entry.entry_id}"})
    await hass.async_block_till_done()
    assert len(pressed) == 2


async def test_button_that_fails_is_logged(hass: HomeAssistant, caplog) -> None:
    printer = add_printer(hass, extras=True)
    mock_supernotify(hass)

    async def jammed(call: ServiceCall) -> None:
        raise HomeAssistantError("offline")

    hass.services.async_register("button", "press", jammed)
    hass.states.async_set(printer["print_status"], "running")
    entry = await setup_printer(hass, printer)
    hass.bus.async_fire("mobile_app_notification_action", {"action": f"APPLIANCE_PAUSE_{entry.entry_id}"})
    await hass.async_block_till_done()
    assert "pause of A1 failed" in caplog.text


async def test_no_buttons_while_getting_ready_without_them(hass: HomeAssistant) -> None:
    printer = add_printer(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "idle")
    await setup_printer(hass, printer, notify_start=True)
    await set_state(hass, printer["print_status"], "prepare")
    await set_state(hass, printer["print_status"], "pause")
    assert all(buttons(call) == [] for call in calls)


async def test_layers_counted_where_chosen(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    hass.states.async_set(printer["stage"], "printing")
    hass.states.async_set(printer["total_layers"], "201")
    hass.states.async_set(printer["current_layer"], "45")
    await setup_printer(hass, printer, live_count="layers")
    await set_state(hass, printer["print_progress"], "22")
    assert calls[0].data["message"] == "printing · layer 45/201"
    # with no time left to show, the chip counts layers too
    assert calls[0].data["extra_data"]["critical_text"] == "45/201"
    # with nothing it's doing to say, the layer alone
    hass.states.async_set(printer["stage"], "unknown")
    await set_state(hass, printer["print_progress"], "30")
    assert calls[1].data["message"] == "printing · layer 45/201"


async def test_layers_alone_before_any_stage(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    hass.states.async_set(printer["total_layers"], "201")
    hass.states.async_set(printer["current_layer"], "3")
    hass.config.language = "it"
    await setup_printer(hass, printer, live_count="layers", notify_progress=True)
    await set_state(hass, printer["print_progress"], "10")
    assert calls[0].data["message"] == "Strato 3/201"


async def test_percentage_unless_layers_chosen(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    hass.states.async_set(printer["stage"], "printing")
    hass.states.async_set(printer["total_layers"], "201")
    hass.states.async_set(printer["current_layer"], "45")
    await setup_printer(hass, printer)
    await set_state(hass, printer["print_progress"], "22")
    assert calls[0].data["message"] == "printing"
    assert calls[0].data["extra_data"]["critical_text"] == "22%"


async def test_layers_not_yet_counted(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    hass.states.async_set(printer["stage"], "heatbed_preheating")
    hass.states.async_set(printer["total_layers"], "201")
    hass.states.async_set(printer["current_layer"], "0")
    await setup_printer(hass, printer, live_count="layers")
    await set_state(hass, printer["print_progress"], "5")
    assert calls[0].data["message"] == "heatbed_preheating"
    assert calls[0].data["extra_data"]["critical_text"] == "5%"


async def test_idle_stage_before_the_end_leaves_it_printing(hass: HomeAssistant) -> None:
    """The print of 15 October said `idle` for its last 24 seconds, still running, before `finish`"""
    printer = add_printer(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    hass.states.async_set(printer["subtask_name"], "0.16mm layer, 2 walls, 15% infill")
    await setup_printer(hass, printer)
    await set_state(hass, printer["stage"], "printing")
    assert calls[0].data["message"] == "printing"
    await set_state(hass, printer["stage"], "idle")
    assert len(calls) == 1
    await set_state(hass, printer["print_progress"], "98")
    assert calls[1].data["message"] == "printing"


async def test_settings_of_a_printer(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "idle")
    entry = await setup_printer(hass, printer)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    fields = [str(key) for key in result["data_schema"].schema]
    for field in ("notify_problem", "snapshot", "live_count"):
        assert field in fields
    # left as they come, they aren't settings
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"notify_problem": True, "snapshot": True, "live_count": "percent", "start": {}, "end": {}, "notify": {}},
    )
    assert "notify_problem" not in entry.options
    assert "live_count" not in entry.options
    # those changed are
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"notify_problem": False, "snapshot": False, "live_count": "layers", "start": {}, "end": {}, "notify": {}},
    )
    assert entry.options == {"notify_problem": False, "snapshot": False, "live_count": "layers"}


async def test_settings_of_a_printer_without_them(hass: HomeAssistant) -> None:
    printer = add_printer(hass)
    mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "idle")
    entry = await setup_printer(hass, printer)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    fields = [str(key) for key in result["data_schema"].schema]
    for field in ("notify_problem", "snapshot", "live_count"):
        assert field not in fields


async def test_fault_told_without_supernotify(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    hass.states.async_set(printer["print_status"], "running")
    await setup_printer(hass, printer, targets=["notify.kitchen_display"])
    calls = async_mock_service(hass, "notify", "send_message")
    fault_on(hass, printer)
    await set_state(hass, printer["print_status"], "pause")
    assert [c.data["message"] for c in calls] == [f"A1 needs help\n{NOZZLE}"]
    # going again has nothing to clear
    hass.states.async_set(printer["print_error"], "off")
    await set_state(hass, printer["print_status"], "running")
    assert len(calls) == 1


async def test_print_failed_with_the_fault_already_on(hass: HomeAssistant, freezer) -> None:
    """The fault read as the print is given up, however long its Live Activity takes to close"""
    printer = add_printer(hass, extras=True)
    calls: list[ServiceCall] = []
    mock_supernotify(hass)

    async def slow(call: ServiceCall) -> None:
        calls.append(call)
        freezer.tick(30)

    hass.services.async_register("supernotify", "notify", slow)
    hass.states.async_set(printer["print_status"], "running")
    await setup_printer(hass, printer)
    fault_on(hass, printer)
    await set_state(hass, printer["print_status"], "failed")
    assert [c.data["message"] for c in calls] == ["A1 is finished", f"Print failed\n{NOZZLE}"]


async def test_help_cleared_once_the_print_is_over(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    entry = await setup_printer(hass, printer)
    fault_on(hass, printer)
    await set_state(hass, printer["print_status"], "pause")
    hass.states.async_set(printer["print_error"], "off")
    # cancelled by hand once the fault was seen
    await set_state(hass, printer["print_status"], "failed")
    assert calls[-1].data["extra_data"] == {
        "mobile_push_notification_tag": f"appliance_{entry.entry_id}_problem",
        "mobile_push_clear_notification": True,
    }


async def test_each_layer_shown_no_more_than_once_a_minute(hass: HomeAssistant, freezer) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    hass.states.async_set(printer["stage"], "printing")
    hass.states.async_set(printer["total_layers"], "201")
    hass.states.async_set(printer["current_layer"], "44")
    await setup_printer(hass, printer, live_count="layers")
    await set_state(hass, printer["current_layer"], "45")
    assert [c.data["message"] for c in calls] == ["printing · layer 45/201"]
    freezer.tick(30)
    await set_state(hass, printer["current_layer"], "46")
    assert len(calls) == 1
    freezer.tick(31)
    await set_state(hass, printer["current_layer"], "47")
    assert calls[-1].data["message"] == "printing · layer 47/201"
    # not while paused, which says so
    await set_state(hass, printer["print_status"], "pause")
    freezer.tick(61)
    await set_state(hass, printer["current_layer"], "48")
    assert calls[-1].data["message"] == "pause"


async def test_layers_not_listened_to_unless_chosen(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    hass.states.async_set(printer["total_layers"], "201")
    await setup_printer(hass, printer)
    await set_state(hass, printer["current_layer"], "45")
    assert calls == []


async def test_printer_settings_kept_when_saved_while_it_isnt_running(hass: HomeAssistant) -> None:
    """Settings for a fault, a picture and layers are only on the form while the printer is set up, so saving while
    it couldn't be, as with the printer away, leaves them as they were"""
    mock_supernotify(hass)
    assert await async_setup_component(hass, "notify", {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="A1",
        unique_id="gone",
        data={"device_id": "gone"},
        options={"notify_problem": False, "live_count": "layers", "notify_start": True},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert "notify_problem" not in [str(key) for key in result["data_schema"].schema]
    await hass.config_entries.options.async_configure(
        result["flow_id"], {"notify_start": False, "start": {}, "end": {}, "notify": {}}
    )
    assert entry.options == {"notify_problem": False, "live_count": "layers"}


async def test_filament_in_the_end_message(hass: HomeAssistant) -> None:
    hass.config.language = "it"
    hass.config.currency = "EUR"
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    await setup_printer(
        hass,
        printer,
        end_message="📦 {program}\n🧵 {weight} · {length}\n💰 {filament_cost}",
        filament_price=24.99,
        reminder=1,
    )
    hass.states.async_set(printer["subtask_name"], "Benchy")
    hass.states.async_set(printer["print_weight"], "12.44", {"unit_of_measurement": "g"})
    hass.states.async_set(printer["print_length"], "4.051", {"unit_of_measurement": "m"})
    await set_state(hass, printer["print_status"], "finish")
    assert calls[-1].data["message"] == "📦 Benchy\n🧵 12 g · 4,05 m\n💰 0,31 €"
    assert calls[-1].data["spoken_message"] == "A1. Benchy. 12 grammi, 4,05 metri. 31 centesimi."
    # gone from the printer by the time of the reminder, but still what the print took
    hass.states.async_set(printer["print_weight"], "0")
    hass.states.async_set(printer["print_length"], "0")
    await pass_time(hass, 60)
    assert calls[-1].data["message"] == "📦 Benchy\n🧵 12 g · 4,05 m\n💰 0,31 €"


async def test_filament_unknown_leaves_its_lines_out(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    await setup_printer(hass, printer, end_message="Done\n🧵 {weight}\n💰 {filament_cost}")
    hass.states.async_set(printer["print_weight"], "3.2")
    await set_state(hass, printer["print_status"], "finish")
    # a small print to a decimal, with no price to cost it at
    assert calls[-1].data["message"] == "Done\n🧵 3.2 g"


async def test_ready_to_take_off_once_the_bed_cools(hass: HomeAssistant) -> None:
    hass.config.language = "it"
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    celsius = {"unit_of_measurement": "°C"}
    hass.states.async_set(printer["bed_temp"], "65", celsius)
    entry = await setup_printer(hass, printer, cooled_temperature=35)
    await set_state(hass, printer["print_status"], "finish")
    told = len(calls)
    hass.states.async_set(printer["bed_temp"], "40", celsius)
    await hass.async_block_till_done()
    assert len(calls) == told
    hass.states.async_set(printer["bed_temp"], "34.6", celsius)
    await hass.async_block_till_done()
    assert len(calls) == told + 1
    assert calls[-1].data == {
        "message": "Piatto sceso a 35°C, la stampa si può staccare",
        "title": "A1",
        "force_resend": True,
        "delivery_selection": "fixed",
        "delivery": ["mobile_push", "phones"],
        "extra_data": {"notification_icon": ICON, "mobile_push_notification_tag": f"appliance_{entry.entry_id}_cooled"},
    }
    # the once
    hass.states.async_set(printer["bed_temp"], "30", celsius)
    await hass.async_block_till_done()
    assert len(calls) == told + 1


async def test_bed_already_cool_is_told_straight_away(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    hass.states.async_set(printer["bed_temp"], "28")
    await setup_printer(hass, printer, cooled_temperature=35)
    await set_state(hass, printer["print_status"], "finish")
    assert calls[-1].data["message"] == "Bed down to 28°, the print can come off"


async def test_next_print_stops_waiting_for_the_bed(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    hass.states.async_set(printer["bed_temp"], "65")
    await setup_printer(hass, printer, cooled_temperature=35)
    await set_state(hass, printer["print_status"], "finish")
    await set_state(hass, printer["print_status"], "prepare")
    await pass_time(hass, 5)
    told = len(calls)
    await set_state(hass, printer["bed_temp"], "30")
    assert len(calls) == told


async def test_no_waiting_for_the_bed_unless_asked_or_failed(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    hass.states.async_set(printer["bed_temp"], "65")
    await setup_printer(hass, printer)
    await set_state(hass, printer["print_status"], "finish")
    told = len(calls)
    await set_state(hass, printer["bed_temp"], "20")
    assert len(calls) == told


async def test_ready_to_take_off_without_supernotify(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    hass.states.async_set(printer["print_status"], "running")
    hass.states.async_set(printer["bed_temp"], "65")
    await setup_printer(hass, printer, cooled_temperature=35, targets=["notify.kitchen_display"], notify_end=False)
    calls = async_mock_service(hass, "notify", "send_message")
    await set_state(hass, printer["print_status"], "finish")
    await set_state(hass, printer["bed_temp"], "30")
    assert [c.data["message"] for c in calls] == ["Bed down to 30°, the print can come off"]


async def test_filament_and_bed_settings(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "idle")
    entry = await setup_printer(hass, printer)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    end = next(field for key, field in result["data_schema"].schema.items() if str(key) == "end")
    assert {"filament_price", "cooled_temperature"} <= {str(key) for key in end.schema.schema}
    assert result["description_placeholders"]["filament_placeholders"] == "{weight}, {length}, {filament_cost}"
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"start": {}, "end": {"filament_price": 24.99, "cooled_temperature": 35}, "notify": {}},
    )
    assert entry.options == {"filament_price": 24.99, "cooled_temperature": 35}


async def test_bed_in_fahrenheit_against_a_threshold_in_celsius(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    fahrenheit = {"unit_of_measurement": "°F"}
    hass.states.async_set(printer["bed_temp"], "150", fahrenheit)
    await setup_printer(hass, printer, cooled_temperature=35)
    await set_state(hass, printer["print_status"], "finish")
    told = len(calls)
    # 35°C is 95°F
    hass.states.async_set(printer["bed_temp"], "96", fahrenheit)
    await hass.async_block_till_done()
    assert len(calls) == told
    hass.states.async_set(printer["bed_temp"], "94", fahrenheit)
    await hass.async_block_till_done()
    assert calls[-1].data["message"] == "Bed down to 94°F, the print can come off"


async def test_bed_waited_for_no_longer_than_six_hours(hass: HomeAssistant) -> None:
    printer = add_printer(hass, extras=True)
    calls = mock_supernotify(hass)
    hass.states.async_set(printer["print_status"], "running")
    hass.states.async_set(printer["bed_temp"], "65")
    await setup_printer(hass, printer, cooled_temperature=20)
    await set_state(hass, printer["print_status"], "finish")
    told = len(calls)
    await pass_time(hass, 6 * 3600 + 1)
    await set_state(hass, printer["bed_temp"], "18")
    assert len(calls) == told


async def test_filament_settings_kept_when_saved_while_it_isnt_running(hass: HomeAssistant) -> None:
    mock_supernotify(hass)
    assert await async_setup_component(hass, "notify", {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="A1",
        unique_id="gone",
        data={"device_id": "gone"},
        options={"filament_price": 24.99, "cooled_temperature": 35},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(result["flow_id"], {"start": {}, "end": {}, "notify": {}})
    assert entry.options == {"filament_price": 24.99, "cooled_temperature": 35}
