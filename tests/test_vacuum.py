from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.appliance_autonotify.const import DOMAIN, VACUUM_SETTLE

from .conftest import mock_supernotify
from .test_watcher import ANDROID, ended, pass_time, set_state

ICON = "mdi:robot-vacuum"


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
    assert len(calls) == 1
    assert calls[0].data == {
        "message": "Bruno started",
        "title": "Bruno",
        "force_resend": True,
        "extra_data": {"mobile_push_notification_tag": tag, "live_update": True, "notification_icon": ICON, **ANDROID},
    }

    # paused, on its way back, or away with the vendor cloud, it's still the same cleaning
    for state in ("paused", "cleaning", "returning", "unavailable"):
        await set_state(hass, vacuum, state)
    assert len(calls) == 1

    # back, but not over till it has stayed back
    await set_state(hass, vacuum, "docked")
    assert len(calls) == 1
    await pass_time(hass, VACUUM_SETTLE)
    assert len(calls) == 3
    assert calls[1].data["extra_data"] == {"mobile_push_notification_tag": tag, "mobile_push_clear_notification": True}
    assert calls[2].data == ended("Bruno", entry.entry_id, ICON, force_resend=True)

    # docked again is no new end
    await set_state(hass, vacuum, "idle")
    assert len(calls) == 3


async def test_vacuum_stuck_is_told(hass: HomeAssistant) -> None:
    device_id, vacuum = add_vacuum(hass)
    calls = mock_supernotify(hass)
    # already cleaning when Home Assistant starts
    hass.states.async_set(vacuum, "cleaning")
    entry = await setup_vacuum(hass, device_id)
    tag = f"appliance_{entry.entry_id}"

    await set_state(hass, vacuum, "error")
    assert calls == []
    # stuck once it has stayed so, the Live Activity closed, with no end since it didn't finish, and a call for help
    await pass_time(hass, VACUUM_SETTLE)
    assert len(calls) == 2
    assert calls[0].data["extra_data"] == {"mobile_push_notification_tag": tag, "mobile_push_clear_notification": True}
    assert calls[1].data == {
        "message": "Bruno needs help",
        "title": "Bruno",
        "force_resend": True,
        "extra_data": {"notification_icon": ICON},
    }

    # once seen to and docked, nothing more to tell
    await set_state(hass, vacuum, "docked")
    assert len(calls) == 2


async def test_vacuum_without_supernotify(hass: HomeAssistant) -> None:
    device_id, vacuum = add_vacuum(hass)
    hass.states.async_set(vacuum, "docked")
    await setup_vacuum(hass, device_id, targets=["notify.phone"])
    calls = async_mock_service(hass, "notify", "send_message")
    await set_state(hass, vacuum, "cleaning")
    await set_state(hass, vacuum, "error")
    await pass_time(hass, VACUUM_SETTLE)
    assert [call.data["message"] for call in calls] == ["Bruno needs help"]


async def test_vacuum_gone_is_retried(hass: HomeAssistant) -> None:
    device_id, vacuum = add_vacuum(hass)
    er.async_get(hass).async_remove(vacuum)
    entry = MockConfigEntry(domain=DOMAIN, title="Bruno", data={"device_id": device_id, "type": "vacuum"})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_vacuum_back_to_wash_its_mop_is_the_same_cleaning(hass: HomeAssistant) -> None:
    device_id, vacuum = add_vacuum(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(vacuum, "docked")
    await setup_vacuum(hass, device_id, notify_start=True)

    await set_state(hass, vacuum, "cleaning")
    await set_state(hass, vacuum, "returning")
    await set_state(hass, vacuum, "docked")
    await pass_time(hass, VACUUM_SETTLE - 60)
    await set_state(hass, vacuum, "cleaning")
    await pass_time(hass, VACUUM_SETTLE)
    assert len(calls) == 1

    await set_state(hass, vacuum, "docked")
    await pass_time(hass, VACUUM_SETTLE)
    assert len(calls) == 3


async def test_vacuum_as_a_real_one_reports_it(hass: HomeAssistant) -> None:
    """The activities of a real vacuum, docked with an error, washing its mop, then out for a short cleaning that it
    reports docked for two minutes as it sets off"""
    device_id, vacuum = add_vacuum(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(vacuum, "unknown")
    await setup_vacuum(hass, device_id, notify_start=True)

    for state in ("docked", "error", "docked", "paused", "docked", "paused", "docked"):
        await set_state(hass, vacuum, state)
    assert calls == []

    await set_state(hass, vacuum, "cleaning")
    await set_state(hass, vacuum, "docked")
    await pass_time(hass, 128)
    await set_state(hass, vacuum, "returning")
    await set_state(hass, vacuum, "docked")
    assert len(calls) == 1
    await pass_time(hass, VACUUM_SETTLE)
    assert len(calls) == 3
    assert calls[2].data["message"] == "Bruno is finished"


async def test_vacuum_error_once_back_is_the_end(hass: HomeAssistant) -> None:
    device_id, vacuum = add_vacuum(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(vacuum, "cleaning")
    await setup_vacuum(hass, device_id)

    await set_state(hass, vacuum, "docked")
    # an empty water tank, say, which the vacuum's own app tells of
    await set_state(hass, vacuum, "error")
    await pass_time(hass, VACUUM_SETTLE)
    assert len(calls) == 2
    assert calls[1].data["message"] == "Bruno is finished"


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
    assert len(calls) == 1
    await pass_time(hass, VACUUM_SETTLE)
    assert len(calls) == 3
    assert calls[2].data["message"] == "Bruno is finished"
    assert "Bruno needs help" not in [call.data["message"] for call in calls]


async def test_vacuum_stuck_in_italian(hass: HomeAssistant) -> None:
    hass.config.language = "it"
    device_id, vacuum = add_vacuum(hass)
    hass.states.async_set(vacuum, "cleaning")
    await setup_vacuum(hass, device_id, targets=["notify.phone"])
    calls = async_mock_service(hass, "notify", "send_message")
    await set_state(hass, vacuum, "error")
    await pass_time(hass, VACUUM_SETTLE)
    assert [call.data["message"] for call in calls] == ["Bruno ha bisogno di aiuto"]
