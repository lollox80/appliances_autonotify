from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed, async_mock_service

from custom_components.appliance_autonotify.const import DOMAIN, VACUUM_BLIP_SETTLE, VACUUM_SETTLE

from .conftest import mock_supernotify
from .test_watcher import ANDROID, ended, pass_time, set_state

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

ICON = "mdi:robot-vacuum"


def told(calls: list[ServiceCall]) -> list[ServiceCall]:
    """The notifications, leaving out the silent updates of the Live Activity as the vacuum goes about its cleaning"""
    return [call for call in calls if call.data["message"] not in ("cleaning", "paused", "returning")]


def add_vacuum(hass: HomeAssistant, name: str = "Bruno", platform: str = "roborock") -> tuple[str, str]:
    """Register a robot vacuum as any vendor integration would, returning its device and vacuum entity"""
    source = MockConfigEntry(domain=platform)
    source.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(config_entry_id=source.entry_id, identifiers={(platform, name)}, name=name)
    entity = er.async_get(hass).async_get_or_create(
        "vacuum", platform, name, suggested_object_id=name.lower(), device_id=device.id, config_entry=source
    )
    return device.id, entity.entity_id


async def setup_vacuum(hass: HomeAssistant, device_id: str, **options: object) -> MockConfigEntry:
    assert await async_setup_component(hass, "notify", {})
    entry = MockConfigEntry(
        domain=DOMAIN, title="Bruno", unique_id=device_id, data={"device_id": device_id, "type": "vacuum"}, options=options
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_vacuum_is_set_up_automatically(hass: HomeAssistant) -> None:
    device_id, _ = add_vacuum(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["description_placeholders"]["found"] == "Appliances found:\n\n- Bruno"
    await hass.config_entries.flow.async_configure(result["flow_id"], {"auto_discover": True})
    await hass.async_block_till_done()

    entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, device_id)
    assert entry is not None
    assert entry.data == {"device_id": device_id, "type": "vacuum"}
    assert entry.state is ConfigEntryState.LOADED

    # and one added later is set up as it appears
    other_id, _ = add_vacuum(hass, "Upstairs", "ecovacs")
    await hass.async_block_till_done()
    other = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, other_id)
    assert other is not None
    assert other.data == {"device_id": other_id, "type": "vacuum"}


async def test_vacuum_offered_keeps_its_type(hass: HomeAssistant) -> None:
    device_id, _ = add_vacuum(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    await hass.config_entries.flow.async_configure(result["flow_id"], {"auto_discover": False})
    await hass.async_block_till_done()
    flow = next(f for f in hass.config_entries.flow.async_progress_by_handler(DOMAIN) if f["context"]["unique_id"] == device_id)
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    assert result["data"] == {"device_id": device_id, "type": "vacuum"}


async def test_vacuum_cleaning_is_a_cycle(hass: HomeAssistant) -> None:
    device_id, vacuum = add_vacuum(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(vacuum, "docked")
    entry = await setup_vacuum(hass, device_id, notify_start=True)
    tag = f"appliance_{entry.entry_id}"

    await set_state(hass, vacuum, "cleaning")
    assert len(told(calls)) == 1
    assert told(calls)[0].data == {
        "message": "Bruno started",
        "title": "Bruno",
        "force_resend": True,
        "extra_data": {"mobile_push_notification_tag": tag, "live_update": True, "notification_icon": ICON, **ANDROID},
    }

    # paused, on its way back, or away with the vendor cloud, it's still the same cleaning
    for state in ("paused", "cleaning", "returning", "unavailable"):
        await set_state(hass, vacuum, state)
    assert len(told(calls)) == 1

    # back, but not over till it has stayed back
    await set_state(hass, vacuum, "docked")
    assert len(told(calls)) == 1
    await pass_time(hass, VACUUM_SETTLE)
    assert len(told(calls)) == 3
    assert told(calls)[1].data["extra_data"] == {"mobile_push_notification_tag": tag, "mobile_push_clear_notification": True}
    assert told(calls)[2].data == ended("Bruno", entry.entry_id, ICON, force_resend=True)

    # docked again is no new end
    await set_state(hass, vacuum, "idle")
    assert len(told(calls)) == 3


async def test_vacuum_stuck_is_told(hass: HomeAssistant) -> None:
    device_id, vacuum = add_vacuum(hass)
    calls = mock_supernotify(hass)
    # already cleaning when Home Assistant starts
    hass.states.async_set(vacuum, "cleaning")
    entry = await setup_vacuum(hass, device_id)
    tag = f"appliance_{entry.entry_id}"

    await set_state(hass, vacuum, "error")
    assert told(calls) == []
    # stuck once it has stayed so, the Live Activity closed, with no end since it didn't finish, and a call for help
    await pass_time(hass, VACUUM_SETTLE)
    assert len(told(calls)) == 2
    assert told(calls)[0].data["extra_data"] == {"mobile_push_notification_tag": tag, "mobile_push_clear_notification": True}
    assert told(calls)[1].data == {
        "message": "Bruno needs help",
        "title": "Bruno",
        "force_resend": True,
        "extra_data": {"notification_icon": ICON},
    }

    # once seen to and docked, nothing more to tell
    await set_state(hass, vacuum, "docked")
    assert len(told(calls)) == 2


async def test_vacuum_without_supernotify(hass: HomeAssistant) -> None:
    device_id, vacuum = add_vacuum(hass)
    hass.states.async_set(vacuum, "docked")
    await setup_vacuum(hass, device_id, targets=["notify.phone"])
    calls = async_mock_service(hass, "notify", "send_message")
    await set_state(hass, vacuum, "cleaning")
    await set_state(hass, vacuum, "error")
    await pass_time(hass, VACUUM_SETTLE)
    assert [call.data["message"] for call in told(calls)] == ["Bruno needs help"]


async def test_vacuum_gone_is_retried(hass: HomeAssistant) -> None:
    device_id, vacuum = add_vacuum(hass)
    er.async_get(hass).async_remove(vacuum)
    entry = MockConfigEntry(domain=DOMAIN, title="Bruno", data={"device_id": device_id, "type": "vacuum"})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float) -> None:
    """Time passing, on the clock the states are stamped with as well as for the timers"""
    freezer.tick(seconds)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_vacuum_back_to_wash_its_mop_is_the_same_cleaning(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    device_id, vacuum = add_vacuum(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(vacuum, "docked")
    await setup_vacuum(hass, device_id, notify_start=True)

    await set_state(hass, vacuum, "cleaning")
    await set_state(hass, vacuum, "returning")
    await set_state(hass, vacuum, "docked")
    await advance(hass, freezer, VACUUM_SETTLE - 60)
    await set_state(hass, vacuum, "cleaning")
    await advance(hass, freezer, VACUUM_SETTLE)
    assert len(told(calls)) == 1

    await set_state(hass, vacuum, "docked")
    await advance(hass, freezer, VACUUM_SETTLE)
    assert len(told(calls)) == 3


async def test_vacuum_docked_as_it_sets_off_is_the_same_cleaning(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """A real Ecovacs cleaning, washing its mop after each room, which its integration reports docked within a second
    of most times it sets off, and keeps to while it cleans the room, until it's back for the next wash"""
    freezer.move_to("2026-10-15T12:46:00+00:00")
    device_id, vacuum = add_vacuum(hass, platform="ecovacs")
    calls = mock_supernotify(hass)
    hass.states.async_set(vacuum, "docked")
    await setup_vacuum(hass, device_id, notify_start=True)

    # seconds from one activity to the next, as reported from 14:46:53 to 15:59:30
    for state, seconds in (
        ("cleaning", 0.6),
        ("docked", 1161),  # out cleaning for 19 minutes, said to be docked, and back for its mop till 15:06:15
        ("cleaning", 1123),
        ("docked", 117),  # back for its mop
        ("cleaning", 0.8),
        ("docked", 290),
        ("cleaning", 0.6),
        ("docked", 339),
        ("cleaning", 1051),
        ("docked", 110),
        ("cleaning", 119),
        ("returning", 44),
    ):
        await set_state(hass, vacuum, state)
        await advance(hass, freezer, seconds)
    assert [call.data["message"] for call in told(calls)] == ["Bruno started"]

    # back for good, and over once it has stayed so
    await set_state(hass, vacuum, "docked")
    await advance(hass, freezer, VACUUM_SETTLE - 1)
    assert len(told(calls)) == 1
    await advance(hass, freezer, 1)
    assert [call.data["message"] for call in told(calls)] == ["Bruno started", "Bruno is finished", "Bruno is finished"]


async def test_vacuum_docked_as_it_sets_off_and_never_heard_from_again(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Stopped as soon as it set off, which the integration reports just as it would one leaving its dock"""
    device_id, vacuum = add_vacuum(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(vacuum, "docked")
    await setup_vacuum(hass, device_id)

    await set_state(hass, vacuum, "cleaning")
    await advance(hass, freezer, 1)
    await set_state(hass, vacuum, "docked")
    await advance(hass, freezer, VACUUM_SETTLE)
    assert len(told(calls)) == 1
    await advance(hass, freezer, VACUUM_BLIP_SETTLE)
    assert [call.data["message"] for call in told(calls)] == ["Bruno started", "Bruno is finished", "Bruno is finished"]


async def test_vacuum_as_a_real_one_reports_it(hass: HomeAssistant) -> None:
    """The activities of a real vacuum, docked with an error, washing its mop, then out for a short cleaning that it
    reports docked for two minutes as it sets off"""
    device_id, vacuum = add_vacuum(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(vacuum, "unknown")
    await setup_vacuum(hass, device_id, notify_start=True)

    for state in ("docked", "error", "docked", "paused", "docked", "paused", "docked"):
        await set_state(hass, vacuum, state)
    assert told(calls) == []

    await set_state(hass, vacuum, "cleaning")
    await set_state(hass, vacuum, "docked")
    await pass_time(hass, 128)
    await set_state(hass, vacuum, "returning")
    await set_state(hass, vacuum, "docked")
    assert len(told(calls)) == 1
    await pass_time(hass, VACUUM_SETTLE)
    assert len(told(calls)) == 3
    assert told(calls)[2].data["message"] == "Bruno is finished"


async def test_vacuum_error_once_back_is_the_end(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    device_id, vacuum = add_vacuum(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(vacuum, "cleaning")
    await setup_vacuum(hass, device_id)

    await advance(hass, freezer, 1200)
    await set_state(hass, vacuum, "docked")
    # an empty water tank, say, which the vacuum's own app tells of
    await set_state(hass, vacuum, "error")
    await pass_time(hass, VACUUM_SETTLE)
    assert len(told(calls)) == 2
    assert told(calls)[1].data["message"] == "Bruno is finished"


async def test_vacuum_error_again_on_reconnecting_isnt_stuck(hass: HomeAssistant) -> None:
    """A real vacuum whose integration, on reconnecting part way through, reports a past error for four minutes while
    the vacuum carries on, washing its mop twice before"""
    device_id, vacuum = add_vacuum(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(vacuum, "docked")
    await setup_vacuum(hass, device_id, notify_start=True)

    await set_state(hass, vacuum, "cleaning")
    for _ in range(2):
        await set_state(hass, vacuum, "docked")
        await pass_time(hass, 180)
        await set_state(hass, vacuum, "cleaning")
    for state in ("unknown", "cleaning", "error"):
        await set_state(hass, vacuum, state)
    await pass_time(hass, 240)
    await set_state(hass, vacuum, "returning")
    await set_state(hass, vacuum, "docked")
    assert len(told(calls)) == 1
    await pass_time(hass, VACUUM_SETTLE)
    assert len(told(calls)) == 3
    assert told(calls)[2].data["message"] == "Bruno is finished"
    assert "Bruno needs help" not in [call.data["message"] for call in told(calls)]


async def test_vacuum_stuck_in_italian(hass: HomeAssistant) -> None:
    hass.config.language = "it"
    device_id, vacuum = add_vacuum(hass)
    hass.states.async_set(vacuum, "cleaning")
    await setup_vacuum(hass, device_id, targets=["notify.phone"])
    calls = async_mock_service(hass, "notify", "send_message")
    await set_state(hass, vacuum, "error")
    await pass_time(hass, VACUUM_SETTLE)
    assert [call.data["message"] for call in told(calls)] == ["Bruno ha bisogno di aiuto"]


async def test_vacuum_buttons_follow_what_it_is_doing(hass: HomeAssistant) -> None:
    hass.config.language = "it"
    device_id, vacuum = add_vacuum(hass)
    calls = mock_supernotify(hass)
    # pause, return home and start
    features = {"supported_features": 4 | 16 | 8192}
    hass.states.async_set(vacuum, "docked", features)
    entry = await setup_vacuum(hass, device_id, notify_start=True)
    pause, resume, back = (f"APPLIANCE_{a}_{entry.entry_id}" for a in ("PAUSE", "RESUME", "RETURN"))

    hass.states.async_set(vacuum, "cleaning", features)
    await hass.async_block_till_done()
    assert calls[0].data["actions"] == [{"action": pause, "title": "Pausa"}, {"action": back, "title": "Torna alla base"}]

    hass.states.async_set(vacuum, "paused", features)
    await hass.async_block_till_done()
    assert calls[1].data["message"] == "paused"
    assert calls[1].data["extra_data"]["silent"] is True
    assert calls[1].data["actions"] == [{"action": resume, "title": "Riprendi"}, {"action": back, "title": "Torna alla base"}]

    hass.states.async_set(vacuum, "returning", features)
    await hass.async_block_till_done()
    assert calls[2].data["message"] == "returning"
    assert "actions" not in calls[2].data
    # said again with nothing new is no update
    hass.states.async_set(vacuum, "returning", features | {"battery_level": 50})
    await hass.async_block_till_done()
    assert len(calls) == 3

    # the buttons do as they say
    pressed = async_mock_service(hass, "vacuum", "return_to_base")
    started = async_mock_service(hass, "vacuum", "start")
    hass.bus.async_fire("mobile_app_notification_action", {"action": back})
    hass.bus.async_fire("mobile_app_notification_action", {"action": resume})
    await hass.async_block_till_done()
    assert [c.data for c in pressed] == [{"entity_id": vacuum}]
    assert [c.data for c in started] == [{"entity_id": vacuum}]


async def test_vacuum_with_no_buttons_it_can_use(hass: HomeAssistant) -> None:
    device_id, vacuum = add_vacuum(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(vacuum, "docked")
    await setup_vacuum(hass, device_id, notify_start=True)
    await set_state(hass, vacuum, "cleaning")
    assert "actions" not in calls[0].data
    failing: list[ServiceCall] = []

    async def away(call: ServiceCall) -> None:
        failing.append(call)
        raise HomeAssistantError("away")

    hass.services.async_register("vacuum", "pause", away)
    entry = hass.config_entries.async_entries("appliance_autonotify")[0]
    hass.bus.async_fire("mobile_app_notification_action", {"action": f"APPLIANCE_PAUSE_{entry.entry_id}"})
    await hass.async_block_till_done()
    assert len(failing) == 1
