from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.appliance_autonotify.const import CYCLE_SETTLE, DOMAIN

from .conftest import mock_supernotify
from .test_watcher import ended, pass_time, set_state

UUID = "e0e642fe-074f-343c-a118-dd5b73b7c5e0"


def add_samsung(hass: HomeAssistant, kind: str = "dryer", name: str = "Asciugatrice") -> dict[str, str]:
    """A Samsung appliance as the SmartThings integration registers it, its entities by translation key"""
    source = MockConfigEntry(domain="smartthings")
    source.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=source.entry_id, identifiers={("smartthings", UUID)}, name=name
    )
    registry = er.async_get(hass)
    entities = {"device_id": device.id}
    for key in (f"{kind}_machine_state", f"{kind}_job_state", "completion_time", "energy_difference"):
        entities[key] = registry.async_get_or_create(
            "sensor",
            "smartthings",
            f"{UUID}_{key}",
            suggested_object_id=f"{name.lower()}_{key}",
            device_id=device.id,
            config_entry=source,
            translation_key=key,
        ).entity_id
    return entities


async def setup_samsung(hass: HomeAssistant, appliance: dict[str, str], **options: object) -> MockConfigEntry:
    assert await async_setup_component(hass, "notify", {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Asciugatrice",
        unique_id=appliance["device_id"],
        data={"device_id": appliance["device_id"]},
        options=options,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_samsung_appliance_is_found(hass: HomeAssistant) -> None:
    dryer = add_samsung(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["description_placeholders"]["found"] == "Appliances found:\n\n- Asciugatrice"
    await hass.config_entries.flow.async_configure(result["flow_id"], {"auto_discover": True})
    await hass.async_block_till_done()
    assert hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, dryer["device_id"]) is not None


async def test_drying_is_a_cycle_over_once_it_only_tumbles(hass: HomeAssistant) -> None:
    dryer = add_samsung(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(dryer["dryer_machine_state"], "stop")
    hass.states.async_set(dryer["dryer_job_state"], "none")
    entry = await setup_samsung(hass, dryer, notify_start=True)

    await set_state(hass, dryer["dryer_machine_state"], "run")
    assert len(calls) == 1
    assert calls[0].data["message"] == "Asciugatrice started"
    assert calls[0].data["extra_data"]["notification_icon"] == "mdi:tumble-dryer"

    # what it's doing, and when it will be done, on the Live Activity
    hass.states.async_set(dryer["completion_time"], "2026-10-19T14:30:00+00:00")
    await set_state(hass, dryer["dryer_job_state"], "drying")
    assert calls[1].data["message"] == "drying"
    assert calls[1].data["extra_data"]["when"] == 1792420200
    await set_state(hass, dryer["dryer_job_state"], "cooling")
    assert calls[2].data["message"] == "cooling"

    # tumbling now and then so the load won't crease is the end, though it's still running
    await set_state(hass, dryer["dryer_job_state"], "wrinkle_prevent")
    assert len(calls) == 5
    assert calls[4].data == ended("Asciugatrice", entry.entry_id, "mdi:tumble-dryer", force_resend=True)

    # nothing more once it stops, nor while it's still said to be running
    hass.states.async_set(dryer["dryer_machine_state"], "run", {"refreshed": True})
    await hass.async_block_till_done()
    await set_state(hass, dryer["dryer_machine_state"], "stop")
    assert len(calls) == 5

    # and the next is a cycle of its own
    await set_state(hass, dryer["dryer_machine_state"], "run")
    assert len(calls) == 6


async def test_paused_and_stopped(hass: HomeAssistant) -> None:
    washer = add_samsung(hass, "washer", "Lavatrice")
    calls = mock_supernotify(hass)
    hass.states.async_set(washer["washer_machine_state"], "run")
    hass.states.async_set(washer["washer_job_state"], "wash")
    entry = await setup_samsung(hass, washer)
    await set_state(hass, washer["washer_machine_state"], "pause")
    assert calls[-1].data["message"] == "pause"
    await set_state(hass, washer["washer_machine_state"], "run")
    await set_state(hass, washer["washer_machine_state"], "stop")
    assert calls[-1].data == ended("Lavatrice", entry.entry_id, "mdi:washing-machine", force_resend=True)


def add_localthings(hass: HomeAssistant, name: str = "Samsung Dryer") -> dict[str, str]:
    """The same dryer as LocalThings registers it, on the local network, by the same SmartThings id"""
    source = MockConfigEntry(domain="localthings")
    source.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=source.entry_id, identifiers={("localthings", UUID)}, name=name
    )
    registry = er.async_get(hass)
    entities = {"device_id": device.id}
    for domain, key in (
        ("sensor", "machine_state"),
        ("sensor", "progress"),
        ("sensor", "progress_percentage"),
        ("sensor", "finish_time"),
        ("sensor", "dryer_type"),
        ("select", "dryer_cycle_table_03"),
    ):
        entities[key] = registry.async_get_or_create(
            domain,
            "localthings",
            f"{UUID}_{key}",
            suggested_object_id=f"samsung_dryer_{key}",
            device_id=device.id,
            config_entry=source,
            translation_key=key,
        ).entity_id
    return entities


async def test_local_network_preferred_to_the_cloud(hass: HomeAssistant) -> None:
    add_samsung(hass)
    local = add_localthings(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["description_placeholders"]["found"] == "Appliances found:\n\n- Samsung Dryer"
    await hass.config_entries.flow.async_configure(result["flow_id"], {"auto_discover": True})
    await hass.async_block_till_done()
    appliances = [e.unique_id for e in hass.config_entries.async_entries(DOMAIN) if e.data.get("device_id")]
    assert appliances == [local["device_id"]]


async def test_drying_on_the_local_network(hass: HomeAssistant) -> None:
    local = add_localthings(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(local["machine_state"], "idle")
    hass.states.async_set(local["dryer_cycle_table_03"], "16")
    entry = await setup_samsung(hass, local, notify_start=True)

    await set_state(hass, local["machine_state"], "active")
    assert calls[0].data["extra_data"]["notification_icon"] == "mdi:tumble-dryer"
    hass.states.async_set(local["finish_time"], "2026-10-19T14:30:00+00:00")
    await set_state(hass, local["progress"], "drying")
    assert calls[1].data["message"] == "drying"
    assert calls[1].data["extra_data"]["when"] == 1792420200
    await set_state(hass, local["progress_percentage"], "40")
    assert calls[-1].data["extra_data"]["progress"] == 40

    await set_state(hass, local["progress"], "finish")
    assert calls[-1].data == ended("Samsung Dryer", entry.entry_id, "mdi:tumble-dryer", force_resend=True)


async def test_the_cloud_while_the_local_network_is_away(hass: HomeAssistant) -> None:
    cloud = add_samsung(hass)
    local = add_localthings(hass)
    calls = mock_supernotify(hass)
    hass.states.async_set(local["machine_state"], "unavailable")
    hass.states.async_set(cloud["dryer_machine_state"], "stop")
    entry = await setup_samsung(hass, local, notify_start=True)

    # started as told by the cloud, what it's doing from there too
    await set_state(hass, cloud["dryer_machine_state"], "run")
    assert len(calls) == 1
    await set_state(hass, cloud["dryer_job_state"], "drying")
    assert calls[-1].data["message"] == "drying"

    # back on the local network, which is listened to from then on, the cloud lagging behind
    await set_state(hass, local["machine_state"], "active")
    await set_state(hass, local["progress"], "cooling")
    assert calls[-1].data["message"] == "cooling"
    count = len(calls)
    await set_state(hass, local["machine_state"], "idle")
    await pass_time(hass, CYCLE_SETTLE)
    assert len(calls) == count + 2
    assert calls[-1].data == ended("Samsung Dryer", entry.entry_id, "mdi:tumble-dryer", force_resend=True)
    await set_state(hass, cloud["dryer_machine_state"], "pause")
    await set_state(hass, cloud["dryer_machine_state"], "run")
    assert len(calls) == count + 2
