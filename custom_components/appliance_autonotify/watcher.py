"""Watch one appliance, and notify as its cycle starts, progresses and ends"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import timedelta
from functools import partial
from typing import TYPE_CHECKING, Any

from homeassistant.components.vacuum import VacuumEntityFeature
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_DEVICE_ID,
    CONF_TYPE,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import CALLBACK_TYPE, Context, Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.translation import async_translate_state
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import DurationConverter, PowerConverter, TemperatureConverter

from .const import (
    ACTION_FINISHED,
    ACTION_MAINTAINED,
    ACTION_MAINTENANCE_LATER,
    ACTION_PAUSE,
    ACTION_REMIND,
    ACTION_RESUME,
    ACTION_RETURN,
    ACTION_SWITCH_OFF,
    ACTION_TITLES,
    ACTION_TRACK_MAINTENANCE,
    ANDROID_BUTTONS,
    ANDROID_CHANNEL,
    APPLIANCE_TYPES,
    BED_TEMPERATURE_KEY,
    CAMERA_DOMAIN,
    CAVITY_TEMPERATURE_KEY,
    CONF_COOLED_TEMPERATURE,
    CONF_CUSTOM_TARGET,
    CONF_DASHBOARD,
    CONF_DELIVERIES,
    CONF_END_MESSAGE,
    CONF_END_TITLE,
    CONF_FILAMENT_PRICE,
    CONF_GRACE_PERIOD,
    CONF_LIVE_COUNT,
    CONF_LIVE_DETAIL,
    CONF_LIVE_TITLE,
    CONF_MAINTENANCE,
    CONF_MIN_DURATION,
    CONF_NOTIFY_END,
    CONF_NOTIFY_PHASE,
    CONF_NOTIFY_PROBLEM,
    CONF_NOTIFY_PROGRESS,
    CONF_NOTIFY_START,
    CONF_POWER_ENTITY,
    CONF_REMINDER,
    CONF_REMINDER_REPEATS,
    CONF_SNAPSHOT,
    CONF_START_MESSAGE,
    CONF_START_TITLE,
    CONF_SWITCH_ENTITY,
    CONF_SWITCH_OFF_BUTTON,
    CONF_TARGET,
    CONF_TARGETS,
    CONF_THRESHOLD,
    COOLED_MESSAGES,
    COOLING_WAIT,
    COST_PLACEHOLDER,
    CYCLE_SETTLE,
    DEFAULT_END_MESSAGE,
    DEFAULT_GRACE_PERIOD,
    DEFAULT_ICON,
    DEFAULT_MIN_DURATION,
    DEFAULT_REMINDER_REPEATS,
    DEFAULT_SNOOZE,
    DEFAULT_START_MESSAGE,
    DEFAULT_THRESHOLD,
    DEFAULT_TITLE,
    DOMAIN,
    DURATION_PLACEHOLDER,
    ENERGY_PLACEHOLDER,
    ENTITY_DOMAINS,
    FAILED_MESSAGES,
    FAST_PREHEAT_KEY,
    FAST_PREHEAT_PHASE,
    FAULT_SEVERITY_ATTRIBUTE,
    FAULT_TEXT_ATTRIBUTE,
    FAULTS_KEY,
    FAULTS_SERIOUS,
    FILAMENT_COST_PLACEHOLDER,
    FINISH_DRIFT,
    FINISH_TIME_KEY,
    KEY_TYPE_PREFIXES,
    LAYER_CHIP,
    LAYER_KEY,
    LAYER_MESSAGES,
    LAYER_REFRESH,
    LAYERS_KEY,
    LENGTH_KEY,
    LENGTH_PLACEHOLDER,
    LIVE_COUNT_LAYERS,
    LIVE_COUNT_PERCENT,
    LIVE_DETAIL_PROGRAM,
    LIVE_DETAIL_TIME,
    LIVE_SETTLE,
    LIVE_TITLE,
    LIVE_TITLE_NAME,
    LIVE_TITLE_NAME_PROGRAM,
    LIVE_TITLE_PROGRAM,
    MAINTENANCE_ACTION_TITLES,
    MOBILE_ACTION_EVENT,
    MOBILE_APP_PLATFORM,
    MOBILE_PUSH_TRANSPORT,
    NAME_PLACEHOLDER,
    OVEN_MESSAGE,
    PAUSE_KEY,
    PHASES_NOTIFIED,
    PLATFORM_TYPES,
    PREHEAT_FINISHED_KEYS,
    PREHEAT_MESSAGE,
    PREHEAT_PHASE,
    PREHEAT_SETTLE,
    PREHEATED_MESSAGE,
    PROBLEM_KEY,
    PROBLEM_SETTLE,
    PROBLEM_TEXT_ATTRIBUTE,
    PROGRAM_KEYS,
    PROGRAM_PLACEHOLDER,
    PROGRESS_CHIP,
    PROGRESS_FINAL,
    PROGRESS_FINAL_STEP,
    PROGRESS_KEY,
    PROGRESS_MESSAGE,
    PROGRESS_NOTIFY_STEP,
    PROGRESS_STEP,
    REMAINING_KEY,
    RESUME_KEY,
    STAGE_KEY,
    STAGES_FINISHED,
    STAGES_NONE,
    START_SETTLE,
    START_TIME_PLACEHOLDER,
    STATES_ABANDONED,
    STATES_ACTIVE,
    STATES_EVENT_ON,
    STATES_FINISHED,
    STATES_PAUSED,
    STATES_RUN,
    STATES_SETTLING,
    STUCK_MESSAGES,
    SUPERNOTIFY_DOMAIN,
    TARGET_TEMPERATURE_KEY,
    TEMPERATURE_STEP,
    TYPE_DISCOVERY,
    TYPE_ICONS,
    TYPE_VACUUM,
    VACUUM_BLIP,
    VACUUM_BLIP_KIND,
    VACUUM_BLIP_SETTLE,
    VACUUM_CLEANING,
    VACUUM_DONE,
    VACUUM_ERROR,
    VACUUM_MIDWAY_KIND,
    VACUUM_MIDWAY_SETTLE,
    VACUUM_PAUSED,
    VACUUM_RETURNING,
    VACUUM_SETTLE,
    VACUUM_SHOWN,
    WEIGHT_KEY,
    WEIGHT_PLACEHOLDER,
)
from .dashboards import dashboard_url
from .discovery import companions, cycle_entities, is_cycle_entity, role_key
from .maintenance import DATA_MAINTENANCE, MaintenanceItem, MaintenanceTracker, maintenance_items, translated
from .supernotify_api import deliveries_by_transport, supernotify_available
from .totals import (
    CycleTotals,
    energy_entity_id,
    energy_price,
    energy_reading,
    format_amount,
    format_cost,
    format_duration,
    format_energy,
    format_time,
    speak_cost,
    speak_duration,
    speak_energy,
    spoken,
)
from .words import name_type

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from datetime import datetime

    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


def _later(context: Context) -> Context:
    """A context of its own for what a timer sets off, leading back to whatever set the timer"""
    return Context(parent_id=context.id)


class ApplianceWatcher:
    """The notifications of a cycle, for subclasses that know when one starts and ends"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.name: str = entry.title
        self.tag: str = f"appliance_{entry.entry_id}"
        # the end has a tag of its own, so it can be cleared or told again without touching a Live Activity
        self.end_tag: str = f"{self.tag}_end"
        # the type of appliance, such as `washer`, from its name until the appliance itself says
        self.appliance_type: str | None = name_type(hass, self.name)
        self.icon: str = self._name_icon()
        self.cycle_entity_id: str | None = None
        # by translation key, whichever of those made use of the appliance has
        self.entity_ids: dict[str, str] = {}
        # the same, of the same appliance through another integration, for while the first can't be heard from
        self.fallback_cycle_entity_id: str | None = None
        self.fallback_ids: dict[str, str] = {}
        self.notify_start: bool = entry.options.get(CONF_NOTIFY_START, False)
        self.notify_end: bool = entry.options.get(CONF_NOTIFY_END, True)
        self.notify_progress: bool = entry.options.get(CONF_NOTIFY_PROGRESS, False)
        self.live_title: str = entry.options.get(CONF_LIVE_TITLE, LIVE_TITLE_NAME_PROGRAM)
        self.live_detail: str = entry.options.get(CONF_LIVE_DETAIL, LIVE_DETAIL_TIME)
        # the program last known, since an appliance may no longer report one by the time its end is told
        self.last_program: str = ""
        # the program of the cycle just over, kept for its reminders, since an appliance may by then have gone back
        # to the program it starts on, as a Samsung dryer does
        self.program_kept: bool = False
        # whether phases are notified unless chosen otherwise, None for an appliance that reports none
        self.phase_default: bool | None = None
        self.notify_phase: bool = False
        self.running: bool = False
        # the progress last sent, rounded down to the step it was sent for
        self.last_progress_mark: int = 0
        # the finish time the Live Activity counts down to, None while it has none
        self.shown_finish: float | None = None
        # whether the Live Activity was last shown paused
        self.shown_paused: bool = False
        # one notification at a time, so a progress update can't overtake the end and reopen the Live Activity
        self._sending: asyncio.Lock = asyncio.Lock()
        self.reminder: float = entry.options.get(CONF_REMINDER, 0)
        self.reminder_repeats: int = int(entry.options.get(CONF_REMINDER_REPEATS, DEFAULT_REMINDER_REPEATS))
        # the smart plug to switch off from the end notification, which only a power monitored appliance has
        self.switch_entity_id: str | None = None
        self._reminders_sent: int = 0
        self._cancel_reminder: CALLBACK_TYPE | None = None
        # the end of the cycle, waiting to see that the appliance doesn't carry on
        self._cancel_end: CALLBACK_TYPE | None = None
        # when the cycle under way began, and when it stopped, if it has, while waiting to see it doesn't carry on
        self.cycle_started: datetime | None = None
        self.cycle_stopped: datetime | None = None
        # the energy meter of the appliance, where it has one, and its reading as the cycle began
        self._energy_entity_id: str | None = None
        self._energy_start: float | None = None
        # what the last cycle came to, by placeholder, for its end and its reminders
        self.totals: CycleTotals = CycleTotals()
        # whether maintenance is tracked, None until it's been asked for or turned down
        self.maintenance: bool | None = entry.options.get(CONF_MAINTENANCE)
        # the items there are to track, whether or not they are, so tracking is only offered where there's something
        self.maintenance_items: list[MaintenanceItem] = []
        # tracking offered on the end notification of the cycle just over
        self._offering: bool = False
        # the appliance's own camera, for a picture with its end and its faults
        self.camera_entity_id: str | None = None
        self.snapshot: bool = entry.options.get(CONF_SNAPSHOT, True)
        # what the appliance was last said to be doing, kept while it reports nothing in particular part way through
        self._last_stage: str | None = None

    @callback
    def async_start(self) -> None:
        raise NotImplementedError

    @property
    def _tracker(self) -> MaintenanceTracker | None:
        return self.hass.data.get(DATA_MAINTENANCE)

    @callback
    def async_start_maintenance(self) -> None:
        """The items for the type of appliance, and those its integration reports the life of, tracked once asked for"""
        self.maintenance_items = maintenance_items(
            self.hass, self.appliance_type, self.entry.data.get(CONF_DEVICE_ID), self.entry.options
        )
        if self.maintenance:
            self._track_maintenance()

    @callback
    def _track_maintenance(self) -> None:
        tracker = self._tracker
        if tracker is None or not self.maintenance_items:
            return
        tracker.async_register(self.entry.entry_id, self.name, self.maintenance_items, self._part_due)
        self.entry.async_on_unload(partial(tracker.async_unregister, self.entry.entry_id))
        if not any(
            entry.data.get(CONF_TYPE) == TYPE_DISCOVERY and not entry.disabled_by
            for entry in self.hass.config_entries.async_entries(DOMAIN)
        ):
            _LOGGER.warning(
                "APPLIANCES Maintenance of %s is tracked, but without the Automatic discovery entry there's no list of it",
                self.name,
            )

    @callback
    def _part_due(self, item: MaintenanceItem) -> None:
        """A part fallen due between cycles, told of straight away"""
        if (tracker := self._tracker) is not None:
            self.entry.async_create_task(self.hass, self._tell_maintenance(tracker, item, Context()))

    @callback
    def async_listen_for_actions(self) -> None:
        """Answer the buttons on the end notification"""
        self.entry.async_on_unload(self.hass.bus.async_listen(MOBILE_ACTION_EVENT, self._action_pressed))
        self.entry.async_on_unload(self._stop_reminding)

    def _keep_running(self) -> None:
        self.cycle_stopped = None
        if self._cancel_end is not None:
            self._cancel_end()
            self._cancel_end = None

    def _totals_device_id(self) -> str | None:
        """The device whose energy meter tells what a cycle used"""
        return self.entry.data.get(CONF_DEVICE_ID)

    @callback
    def _cycle_began(self) -> None:
        """Note when the cycle began, and the energy meter's reading, to tell what it came to once it's over"""
        if self.cycle_started is not None:
            return
        self.cycle_started = dt_util.utcnow()
        self.cycle_stopped = None
        self._energy_entity_id = energy_entity_id(self.hass, self._totals_device_id())
        self._energy_start = energy_reading(self.hass, self._energy_entity_id)

    @callback
    def _cycle_forgotten(self) -> None:
        """Not a cycle after all"""
        self.cycle_started = None
        self.cycle_stopped = None

    async def _sum_up(self) -> None:
        """What the cycle just over came to, nothing being known of one already under way as Home Assistant started"""
        totals = CycleTotals()
        if (started := self.cycle_started) is not None:
            # up to when it stopped, not when that was believed
            duration = (self.cycle_stopped or dt_util.utcnow()) - started
            used = cost = None
            end = energy_reading(self.hass, self._energy_entity_id)
            # nothing to tell if the meter was reset part way through
            if self._energy_start is not None and end is not None and end >= self._energy_start:
                used = end - self._energy_start
                if (price := await energy_price(self.hass)) is not None:
                    cost = used * price
            totals = CycleTotals(started, duration, used, cost)
        self.totals = totals
        self._cycle_forgotten()

    def _name_icon(self) -> str:
        return TYPE_ICONS.get(name_type(self.hass, self.name) or "", DEFAULT_ICON)

    @staticmethod
    def _mark(progress: int) -> int:
        """The progress rounded down to the step it's sent for"""
        return progress - progress % (PROGRESS_FINAL_STEP if progress >= PROGRESS_FINAL else PROGRESS_STEP)

    async def _progress_changed(self, event: Event[EventStateChangedData]) -> None:
        progress = self._progress()
        if not self.running or progress is None:
            return
        mark = self._mark(progress)
        if mark <= self.last_progress_mark:
            return
        # the first reading only fills in the Live Activity, coming straight after the start notification, as do
        # the steps between those notified and the smaller ones towards the end
        step = PROGRESS_NOTIFY_STEP
        ordinary = self.notify_progress and mark // step > max(self.last_progress_mark, 0) // step
        self.last_progress_mark = mark
        live = supernotify_available(self.hass)
        if not live and not ordinary:
            return
        async with self._sending:
            if not self.running:
                # the cycle ended while this waited its turn
                return
            message = self._progress_message(progress)
            if live and not ordinary:
                # the bar already shows how far along it is, so there's room to say what it's doing
                message = self._phase() or message
            await self._tell(message, ordinary, event.context, resend=True)

    async def _started(self, context: Context) -> None:
        self.program_kept = False
        self._last_stage = None
        self._cycle_began()
        # nothing yet to tell of this one
        self.totals = CycleTotals()
        # the last cycle's reminders are no use once the next one is under way
        self._stop_reminding()
        async with self._sending:
            # resent, since to Supernotify a second cycle soon after the first is a repeat to be dropped
            await self._tell(
                self._text(CONF_START_MESSAGE, DEFAULT_START_MESSAGE),
                self.notify_start,
                context,
                resend=True,
                spoken_message=self._text(CONF_START_MESSAGE, DEFAULT_START_MESSAGE, speak=True),
            )
            if supernotify_available(self.hass):
                # whatever comes next waits its turn, the first progress being only moments behind the start
                await asyncio.sleep(LIVE_SETTLE)

    async def _tell(
        self, message: str, ordinary: bool, context: Context, resend: bool = False, spoken_message: str | None = None
    ) -> None:
        """Notify of a cycle under way, either everywhere or with no more than its Live Activity brought up to date"""
        # a Live Activity keeps the title it started with
        title = self._text(CONF_START_TITLE, DEFAULT_TITLE)
        if not supernotify_available(self.hass):
            if ordinary:
                await self._send_message(message, title, context)
        elif ordinary:
            # everywhere, opening or updating the Live Activity on phones as it goes
            await self._supernotify(
                message,
                title,
                context,
                resend=resend,
                extra_data=self._live_data(),
                actions=self._live_actions() + self._tap_actions(),
                spoken_message=spoken_message,
            )
        else:
            data = self._live_data()
            title, message = self._live_title(title, message, timer="when" in data)
            # with nothing to hear, and nothing sent anywhere but to phones
            await self._supernotify(
                message,
                title,
                context,
                mobile_only=True,
                extra_data=data | {"silent": True, "alert_once": True},
                # iOS forgets where a tap goes unless told again on every update, and Android its buttons
                actions=self._live_actions() + self._tap_actions(),
            )

    def _live_title(self, title: str, message: str, timer: bool) -> tuple[str, str]:
        """The title of a quiet Live Activity update as chosen, and its message, which needn't say the program again"""
        phase = self._title_phase()
        # with no timer the message is seen, and says what it's doing itself
        if not timer or self.live_title == LIVE_TITLE_NAME or not phase or phase in title:
            return title, message
        # with a timer there's no message on the iOS Lock Screen, so what it's doing goes in the title
        if message == phase and (progress := self._progress()) is not None:
            message = self._progress_message(progress)
        if self.live_title == LIVE_TITLE_PROGRAM:
            return phase, message
        return LIVE_TITLE.format(title=title, phase=phase), message

    async def _ended(self, finished: bool, context: Context) -> None:
        self.last_program = self._program() or self.last_program
        self.program_kept = True
        await self._sum_up()
        title = self._text(CONF_END_TITLE, DEFAULT_TITLE)
        message = self._text(CONF_END_MESSAGE, DEFAULT_END_MESSAGE)
        notify = finished and self.notify_end
        await self._tell_ended(notify, title, message, context)
        if finished:
            await self._maintenance_due(context)

    async def _tell_ended(self, notify: bool, title: str, message: str, context: Context) -> None:
        async with self._sending:
            if not supernotify_available(self.hass):
                if notify:
                    await self._send_message(message, title, context)
                return
            # closing the Live Activity is not a notification in itself, so the end is told separately
            await self._supernotify(
                message,
                title,
                context,
                mobile_only=True,
                extra_data={"mobile_push_notification_tag": self.tag, "mobile_push_clear_notification": True},
            )
            if notify:
                tracker = self._tracker
                # offered once, so anyone who'd want it needn't go looking, and nobody's bothered who wouldn't
                self._offering = (
                    tracker is not None
                    and self.maintenance is None
                    and bool(self.maintenance_items)
                    and not tracker.offered(self.entry.entry_id)
                )
                # the same end message as the last cycle would otherwise be dropped as a duplicate
                await self._tell_end(context, resend=True)
                if tracker is not None and self._offering:
                    tracker.async_mark_offered(self.entry.entry_id)
                self._reminders_sent = 0
                if self.reminder:
                    self._remind_in(self.reminder, context)

    async def _maintenance_due(self, context: Context) -> None:
        """Another cycle counted, and each item it has made due told of, the once"""
        tracker = self._tracker
        if tracker is None or not tracker.tracked(self.entry.entry_id):
            return
        for item in tracker.async_cycle_ended(self.entry.entry_id):
            await self._tell_maintenance(tracker, item, context)

    def _maintenance_tag(self, item: MaintenanceItem) -> str:
        # short, a part's key being its entity id, and iOS keeping only 64 bytes of a tag
        return f"{self.tag}_maintenance_{hashlib.sha256(item.key.encode()).hexdigest()[:8]}"

    async def _tell_maintenance(self, tracker: MaintenanceTracker, item: MaintenanceItem, context: Context) -> None:
        message = tracker.message(self.entry.entry_id, item)
        if not supernotify_available(self.hass):
            await self._send_message(message, self.name, context)
            return
        titles = translated(self.hass, MAINTENANCE_ACTION_TITLES)
        actions = [
            {"action": f"{button}{self.entry.entry_id}_{item.key}", "title": titles[button]}
            for button in (ACTION_MAINTAINED, ACTION_MAINTENANCE_LATER)
        ]
        async with self._sending:
            await self._supernotify(
                message,
                self.name,
                context,
                resend=True,
                actions=actions + self._tap_actions(),
                extra_data={
                    "notification_icon": "mdi:wrench-clock",
                    "mobile_push_notification_tag": self._maintenance_tag(item),
                },
            )

    async def _maintenance_pressed(self, action: str, context: Context) -> bool:
        """The buttons of the notification of an item due, and the one offering to track maintenance at all"""
        if action == f"{ACTION_TRACK_MAINTENANCE}{self.entry.entry_id}":
            # once only, a press left on an old notification not undoing it being turned off since
            if self.entry.options.get(CONF_MAINTENANCE) is None:
                self.maintenance = True
                # nor offered again by its reminders
                self._offering = False
                # tracked from now without a reload, which would drop the reminders of the end just told
                self._track_maintenance()
                self.hass.config_entries.async_update_entry(
                    self.entry, options=dict(self.entry.options) | {CONF_MAINTENANCE: True}
                )
            return True
        tracker = self._tracker
        for button in (ACTION_MAINTAINED, ACTION_MAINTENANCE_LATER):
            prefix = f"{button}{self.entry.entry_id}_"
            if tracker is None or not action.startswith(prefix):
                continue
            item = tracker.item(self.entry.entry_id, action.removeprefix(prefix))
            if item is None:
                return True
            if button == ACTION_MAINTAINED:
                await tracker.async_done(self.entry.entry_id, item.key, context)
            else:
                tracker.async_snooze(self.entry.entry_id, item.key)
            await self._supernotify(
                self.name,
                self.name,
                context,
                mobile_only=True,
                extra_data={
                    "mobile_push_notification_tag": self._maintenance_tag(item),
                    "mobile_push_clear_notification": True,
                },
            )
            return True
        return False

    async def _tell_end(self, context: Context, resend: bool = False, reminder: bool = False) -> None:
        """The end, with buttons to say the appliance has been seen to, to be reminded later, or to switch it off"""
        title = self._text(CONF_END_TITLE, DEFAULT_TITLE)
        await self._supernotify(
            self._text(CONF_END_MESSAGE, DEFAULT_END_MESSAGE),
            title,
            context,
            resend=resend,
            # a reminder is for whoever is to see to it, not for the whole house to hear again
            mobile_only=reminder,
            spoken_message=self._text(CONF_END_MESSAGE, DEFAULT_END_MESSAGE, speak=True, title=title),
            actions=self._end_actions() + self._tap_actions(),
            extra_data={"notification_icon": self.icon, "mobile_push_notification_tag": self.end_tag},
            # what it came to, the once, a reminder being only to say it's still waiting
            media=None if reminder else self._media(),
        )

    def _media(self) -> dict[str, str] | None:
        """A picture from the appliance's own camera, for Supernotify to take as it sends, where it has one that's
        working, and it hasn't been turned off"""
        if not self.snapshot or self._known(self.camera_entity_id) is None:
            return None
        return {"camera_entity_id": str(self.camera_entity_id)}

    async def _help(self, detail: str | None, context: Context, failed: bool = False) -> None:
        """A fault that has stopped the appliance, saying what it is where the appliance says, as it's stopped part
        way through for someone to see to, or stopped for good"""
        language = self.hass.config.language.split("-")[0]
        if failed:
            messages = FAILED_MESSAGES.get(language, FAILED_MESSAGES["en"])
            headline = messages.get(self.appliance_type or "", messages[""])
        else:
            headline = STUCK_MESSAGES.get(language, STUCK_MESSAGES["en"]).replace(NAME_PLACEHOLDER, self.name)
        message = f"{headline}\n{detail}" if detail else headline
        title = self._text(CONF_START_TITLE, DEFAULT_TITLE)
        async with self._sending:
            if not supernotify_available(self.hass):
                await self._send_message(message, title, context)
                return
            await self._supernotify(
                message,
                title,
                context,
                resend=True,
                # what the fault is may be long, and is for reading
                spoken_message=spoken(f"{title}\n{headline}" if title not in headline else headline),
                extra_data={"notification_icon": self.icon, "mobile_push_notification_tag": self.problem_tag},
                actions=self._tap_actions(),
                media=self._media(),
            )

    @property
    def problem_tag(self) -> str:
        return f"{self.tag}_problem"

    def _end_actions(self) -> list[dict[str, str]]:
        buttons = [ACTION_FINISHED, ACTION_REMIND] + ([ACTION_SWITCH_OFF] if self._switchable() else [])
        if self._offering and len(buttons) >= ANDROID_BUTTONS:
            # Android shows only 3, so in place of Remind Later on the one notification it's offered on
            buttons.remove(ACTION_REMIND)
        actions = self._buttons(buttons)
        if self._offering:
            track = translated(self.hass, MAINTENANCE_ACTION_TITLES)[ACTION_TRACK_MAINTENANCE]
            actions.append({"action": f"{ACTION_TRACK_MAINTENANCE}{self.entry.entry_id}", "title": track})
        return actions

    def _switchable(self) -> bool:
        """Whether there's a smart plug to switch off, one chosen and since removed not being offered"""
        return self.switch_entity_id is not None and self.hass.states.get(self.switch_entity_id) is not None

    def _snooze_minutes(self) -> int:
        return int(self.reminder or DEFAULT_SNOOZE)

    @callback
    def _remind_in(self, minutes: float, context: Context) -> None:
        self._stop_reminding()
        self._cancel_reminder = async_call_later(self.hass, minutes * 60, partial(self._remind, context))

    @callback
    def _stop_reminding(self) -> None:
        if self._cancel_reminder is not None:
            self._cancel_reminder()
            self._cancel_reminder = None

    async def _remind(self, context: Context, now: datetime) -> None:
        self._cancel_reminder = None
        self._reminders_sent += 1
        # Supernotify would drop the same message again as a duplicate
        await self._tell_end(_later(context), resend=True, reminder=True)
        if self.reminder and self._reminders_sent < self.reminder_repeats:
            self._remind_in(self.reminder, context)

    async def _action_pressed(self, event: Event) -> None:
        action = str(event.data.get("action") or "")
        if await self._maintenance_pressed(action, event.context):
            return
        if action == f"{ACTION_FINISHED}{self.entry.entry_id}":
            self._stop_reminding()
            await self._supernotify(
                self._text(CONF_END_MESSAGE, DEFAULT_END_MESSAGE),
                self._text(CONF_END_TITLE, DEFAULT_TITLE),
                event.context,
                mobile_only=True,
                extra_data={"mobile_push_notification_tag": self.end_tag, "mobile_push_clear_notification": True},
            )
        elif action == f"{ACTION_REMIND}{self.entry.entry_id}":
            self._remind_in(self._snooze_minutes(), event.context)
        elif action == f"{ACTION_SWITCH_OFF}{self.entry.entry_id}" and self._switchable():
            if self.running:
                # a button left from the last cycle, pressed once the next one has started
                _LOGGER.warning("APPLIANCES %s is running again, so it was left switched on", self.name)
                return
            try:
                await self.hass.services.async_call(
                    "switch", "turn_off", {ATTR_ENTITY_ID: self.switch_entity_id}, blocking=True, context=event.context
                )
            except HomeAssistantError:
                _LOGGER.exception("APPLIANCES Switching off %s failed", self.name)

    def _text(self, key: str, default: str, speak: bool = False, title: str | None = None) -> str:
        """The text chosen for a notification, filled in, or as a voice assistant is to say it, after its title"""
        text = str(self.entry.options.get(key) or default).replace(NAME_PLACEHOLDER, self.name)
        values: dict[str, str] = {}
        totals = self.totals
        if START_TIME_PLACEHOLDER in text:
            # the cycle under way, else the last one
            started = self.cycle_started or totals.started
            values[START_TIME_PLACEHOLDER] = format_time(started) if started else ""
        if DURATION_PLACEHOLDER in text:
            duration = totals.duration
            values[DURATION_PLACEHOLDER] = (
                "" if duration is None else (speak_duration if speak else format_duration)(self.hass, duration)
            )
        for placeholder, amount, written, said in (
            (ENERGY_PLACEHOLDER, totals.energy, format_energy, speak_energy),
            (COST_PLACEHOLDER, totals.cost, format_cost, speak_cost),
        ):
            if placeholder in text:
                # nothing to say of less than a meter can count, rather than none used, or nothing to pay
                counted = amount is not None and round(amount, 2) > 0
                values[placeholder] = (said if speak else written)(self.hass, amount or 0) if counted else ""
        values.update({p: value for p, value in self._more_values(speak).items() if p in text})
        if PROGRAM_PLACEHOLDER in text:
            if not self.program_kept:
                self.last_program = self._program() or self.last_program
            values[PROGRAM_PLACEHOLDER] = self.last_program
        lines = text.split("\n")
        for placeholder, value in values.items():
            lines = [line.replace(placeholder, value) for line in lines]
        # a line of nothing but a placeholder left empty and its emoji goes, rather than the emoji alone
        text = "\n".join(
            line
            for line, before in zip(lines, text.split("\n"), strict=True)
            if any(c.isalnum() for c in line) or not any(p in before for p in values)
        )
        if speak:
            # the title said first, unless the message already names it
            return spoken(f"{title}\n{text}" if title and title not in text else text)
        if not values:
            return text
        # closing up the gaps left where there's nothing to say, line by line
        return "\n".join(" ".join(line.split()) for line in text.strip().split("\n"))

    def _more_values(self, speak: bool) -> dict[str, str]:
        """Placeholders an appliance of a particular kind has for its messages, filled in"""
        return {}

    def _state(self, key: str) -> State | None:
        """The state of one of the appliance's entities, where it has the entity and its state is known, or failing
        that the same entity through another integration"""
        for ids in (self.entity_ids, self.fallback_ids):
            if (state := self._known(ids.get(key))) is not None:
                return state
        return None

    def _known(self, entity_id: str | None) -> State | None:
        state = self.hass.states.get(entity_id) if entity_id else None
        return None if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE) else state

    def _cycle_state(self) -> State | None:
        """The state of the cycle, from another integration for the same appliance while the first doesn't know it"""
        return self._known(self.cycle_entity_id) or self._known(self.fallback_cycle_entity_id)

    def _number(self, key: str) -> float | None:
        state = self._state(key)
        try:
            return float(state.state) if state is not None else None
        except ValueError:
            return None

    def _progress(self) -> int | None:
        progress = self._number(PROGRESS_KEY)
        return None if progress is None else int(progress)

    def _progress_message(self, progress: int) -> str:
        return PROGRESS_MESSAGE.format(progress=progress)

    def _phase(self) -> str | None:
        """What the appliance is doing, to say alongside a bar that already shows how far along it is"""
        return self._stage() or self._program()

    def _stage(self) -> str | None:
        """What the appliance is doing within its cycle, where its integration tells, or what it last told while it
        says nothing in particular, as a 3D printer does in the moments before it finishes"""
        stage = self._state(STAGE_KEY)
        if stage is not None and stage.state not in STAGES_NONE:
            self._last_stage = self._translated(stage)
            return self._last_stage
        return self._last_stage if self.running else None

    def _title_phase(self) -> str | None:
        """What goes beside the name in the title of a Live Activity with a timer: the program, where the stage is
        what the Live Activity says, or else whatever the Live Activity would say"""
        return self._program() if self._stage() is not None else self._phase()

    def _program_state(self) -> State | None:
        """The program under way, or failing that the one chosen, where the appliance reports either"""
        return next((state for key in PROGRAM_KEYS if (state := self._state(key)) is not None), None)

    def _program(self) -> str | None:
        """The program as Home Assistant shows it"""
        state = self._program_state()
        return self._translated(state) if state is not None else None

    def _translated(self, state: State) -> str:
        """A state as Home Assistant shows it, in its language"""
        entity = er.async_get(self.hass).async_get(state.entity_id)
        if entity is None:
            return state.state
        return async_translate_state(self.hass, state.state, state.domain, entity.platform, entity.translation_key, None)

    def _live_actions(self) -> list[dict[str, str]]:
        """Buttons on the Live Activity, for what can be done with the appliance while it runs"""
        return []

    def _buttons(self, buttons: list[str]) -> list[dict[str, str]]:
        titles = ACTION_TITLES.get(self.hass.config.language.split("-")[0], ACTION_TITLES["en"])
        return [{"action": f"{button}{self.entry.entry_id}", "title": titles[button]} for button in buttons]

    def _tap_actions(self) -> list[dict[str, str]]:
        """Where a tap on the notification goes, if a dashboard has been chosen, as a notification level action
        that Supernotify sends as `url` to iOS and `clickAction` to Android"""
        url = dashboard_url(self.hass, self.entry.options.get(CONF_DASHBOARD))
        return [{"level": "notification", "uri": url}] if url else []

    def _live_data(self) -> dict[str, Any]:
        """Live Activity fields for the mobile app, leaving out whatever the appliance isn't reporting"""
        data: dict[str, Any] = {
            "mobile_push_notification_tag": self.tag,
            "live_update": True,
            "notification_icon": self.icon,
            # Android only, iOS ignores them: a channel of its own so the start sounds, and kept when tapped as
            # a Live Activity is, since otherwise the next update brings it back as a new, sounding, notification
            "channel": ANDROID_CHANNEL,
            "importance": "high",
            "sticky": True,
        }
        progress = self._progress()
        if progress is not None:
            data["progress"] = progress
            data["progress_max"] = 100
        # no counting down while paused, since the time left stands still
        self.shown_paused = self._paused()
        finish_time = None if self.shown_paused or self.live_detail == LIVE_DETAIL_PROGRAM else self._finish_time()
        self.shown_finish = finish_time.timestamp() if finish_time is not None else None
        if finish_time is not None:
            data["chronometer"] = True
            data["when"] = int(finish_time.timestamp())
        elif progress is not None:
            # the Android status bar chip shows this in place of the time left, so only with no time to show, and
            # short, since a longer text leaves the chip with only its icon
            data["critical_text"] = self._chip(progress)
        return data

    def _chip(self, progress: int) -> str:
        return PROGRESS_CHIP.format(progress=progress)

    def _paused(self) -> bool:
        return False

    def _finish_time(self) -> datetime | None:
        """When the appliance will be done, from the time it has left where it reports that, else its finish time"""
        remaining = self._state(REMAINING_KEY)
        if remaining is not None:
            try:
                left = DurationConverter.convert(
                    float(remaining.state),
                    remaining.attributes.get(ATTR_UNIT_OF_MEASUREMENT, UnitOfTime.SECONDS),
                    UnitOfTime.SECONDS,
                )
            except ValueError, HomeAssistantError:
                left = None
            if left is not None and left > 0:
                return dt_util.utcnow() + timedelta(seconds=left)
        state = self._state(FINISH_TIME_KEY)
        return dt_util.parse_datetime(state.state) if state is not None else None

    async def _live_refresh(self, context: Context) -> None:
        """Bring the Live Activity up to date with what the appliance is doing, with nothing to notify"""
        async with self._sending:
            if not self.running:
                return
            progress = self._progress()
            # with nothing else to say, what it said as it started, which a pause may have replaced
            message = self._phase() or (
                self._progress_message(progress)
                if progress is not None
                else self._text(CONF_START_MESSAGE, DEFAULT_START_MESSAGE)
            )
            await self._tell(message, False, context)

    async def _supernotify(
        self,
        message: str,
        title: str,
        context: Context,
        mobile_only: bool = False,
        resend: bool = False,
        extra_data: dict[str, Any] | None = None,
        actions: list[dict[str, str]] | None = None,
        spoken_message: str | None = None,
        media: dict[str, str] | None = None,
    ) -> None:
        data: dict[str, Any] = {"message": message, "title": title}
        if media:
            data["media"] = media
        if spoken_message and spoken_message.rstrip(".") != message.rstrip(".") and not mobile_only:
            # what Alexa or a speaker says, with no emoji and the numbers in words
            data["spoken_message"] = spoken_message
        if actions:
            data["actions"] = actions
        if resend:
            # Supernotify's duplicate check ignores digits, so would drop progress updates as repeats
            data["force_resend"] = True
        deliveries: list[str] = list(self.entry.options.get(CONF_DELIVERIES) or [])
        try:
            if mobile_only:
                mobile = (await deliveries_by_transport(self.hass, context)).get(MOBILE_PUSH_TRANSPORT, [])
                deliveries = [d for d in mobile if not deliveries or d in deliveries]
                if not deliveries:
                    _LOGGER.warning("APPLIANCES No mobile push delivery found for %s, Live Activity not updated", self.name)
                    return
                data["delivery_selection"] = "fixed"
                data["force_resend"] = True
            elif deliveries:
                data["delivery_selection"] = "explicit"
            if deliveries:
                data["delivery"] = deliveries
            for key in (CONF_TARGET, CONF_CUSTOM_TARGET):
                if value := self.entry.options.get(key):
                    data[key] = value
            if extra_data:
                data["extra_data"] = extra_data
            await self.hass.services.async_call(SUPERNOTIFY_DOMAIN, "notify", data, blocking=True, context=context)
        except HomeAssistantError:
            _LOGGER.exception("APPLIANCES Supernotify notification failed for %s", self.name)

    async def _send_message(self, message: str, title: str, context: Context) -> None:
        # with none chosen, every phone with the mobile app is told
        targets: list[str] = self.entry.options.get(CONF_TARGETS) or [
            entity.entity_id
            for entity in er.async_get(self.hass).entities.values()
            if entity.domain == "notify" and entity.platform == MOBILE_APP_PLATFORM and not entity.disabled
        ]
        if not targets:
            _LOGGER.warning("APPLIANCES Nothing to notify for %s, choose targets in its settings", self.name)
            return
        try:
            await self.hass.services.async_call(
                "notify",
                "send_message",
                {ATTR_ENTITY_ID: targets, "message": message, "title": title},
                blocking=True,
                context=context,
            )
        except HomeAssistantError:
            _LOGGER.exception("APPLIANCES Notification failed for %s", self.name)


class HomeConnectWatcher(ApplianceWatcher):
    """An appliance whose integration reports the state of its cycle"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry)
        # an oven on its way up to heat, and one that has been there since it was last switched on
        self.preheating: bool = False
        self.preheated: bool = False
        # the temperature the Live Activity last showed, of an oven up to heat
        self.shown_temperature: float | None = None
        # the oven saying it's up to heat, waiting to see that it wasn't being switched off
        self._cancel_preheated: CALLBACK_TYPE | None = None
        # over by its stage while its cycle state still says it's running, so not a new cycle till that says it's over
        self.over_by_stage: bool = False
        # started, and waiting a moment for the program and stage to be reported before that's told
        self.starting: bool = False
        self.appliance_type: str | None = None
        self.notify_problem: bool = entry.options.get(CONF_NOTIFY_PROBLEM, True)
        self.live_count: str = entry.options.get(CONF_LIVE_COUNT, LIVE_COUNT_PERCENT)
        # a fault told of while paused, the once until it's going again, however often it drops off the network
        self._helped: bool = False
        # when the cycle was given up, for a fault that may be reported a moment after, as what gave it up
        self._abandoned_at: datetime | None = None
        # when the Live Activity was last brought up to date for a layer
        self._layer_shown: datetime | None = None
        self.filament_price: float = float(entry.options.get(CONF_FILAMENT_PRICE) or 0)
        self.cooled_temperature: float = float(entry.options.get(CONF_COOLED_TEMPERATURE) or 0)
        # the grams and metres of filament the print just over took, kept for its reminders
        self._filament: tuple[float | None, float | None] = (None, None)
        # waiting for the bed to cool, after a print
        self._cancel_cooling: CALLBACK_TYPE | None = None

    @callback
    def async_start(self) -> None:
        device_id: str = self.entry.data[CONF_DEVICE_ID]
        device = dr.async_get(self.hass).async_get(device_id)
        if device is not None:
            self.name = device.name_by_user or device.name or self.name
        programs: list[str] = []
        platform = ""
        translation_keys: list[str] = []
        entity_registry = er.async_get(self.hass)
        for entity in er.async_entries_for_device(entity_registry, device_id):
            if entity.domain == CAMERA_DOMAIN and not entity.disabled:
                self.camera_entity_id = self.camera_entity_id or entity.entity_id
            key = role_key(entity)
            if key is None or entity.disabled:
                continue
            translation_keys.append(entity.translation_key or "")
            if is_cycle_entity(entity):
                self.cycle_entity_id = entity.entity_id
                platform = entity.platform
            elif ENTITY_DOMAINS.get(key) == entity.domain:
                self.entity_ids[key] = entity.entity_id
                if key in PROGRAM_KEYS:
                    programs.extend((entity.capabilities or {}).get("options") or [])
        if self.cycle_entity_id is None:
            raise ConfigEntryNotReady(f"No cycle state entity found for {self.name}")
        # the same appliance through another integration, heard from only while this one can't be
        cycles = cycle_entities(self.hass)
        for companion in companions(self.hass, device_id, cycles):
            self.fallback_cycle_entity_id = self.fallback_cycle_entity_id or cycles[companion].entity_id
            for entity in er.async_entries_for_device(entity_registry, companion):
                key = role_key(entity)
                if key is not None and not entity.disabled and ENTITY_DOMAINS.get(key) == entity.domain:
                    self.fallback_ids.setdefault(key, entity.entity_id)
        # the type of appliance isn't kept anywhere to be read, but for a platform of only the one type, its programs
        # are named for it, or failing that, for an integration with several types, its entities
        self.appliance_type = appliance_type = (
            PLATFORM_TYPES.get(platform)
            or next((kind for prefix, kind in APPLIANCE_TYPES.items() if any(p.startswith(prefix) for p in programs)), None)
            or next(
                (kind for prefix, kind in KEY_TYPE_PREFIXES.items() if any(k.startswith(prefix) for k in translation_keys)),
                None,
            )
        )
        self.appliance_type = appliance_type or name_type(self.hass, self.name)
        self.icon = TYPE_ICONS.get(appliance_type or "", self._name_icon())
        # the one phase there is to know of is an oven warming up, Home Connect reporting none for anything else
        if CAVITY_TEMPERATURE_KEY in self.entity_ids and TARGET_TEMPERATURE_KEY in self.entity_ids:
            self.phase_default = appliance_type in PHASES_NOTIFIED
            self.notify_phase = self.entry.options.get(CONF_NOTIFY_PHASE, self.phase_default)

        # a cycle under way at startup still has its Live Activity closed when it ends
        state = self._cycle_state()
        self.running = state is not None and state.state in STATES_ACTIVE
        # and with no knowing whether its oven has been up to heat, it isn't taken to be warming up
        self.preheated = self.running

        cycle_entity_ids = [e for e in (self.cycle_entity_id, self.fallback_cycle_entity_id) if e]
        self.entry.async_on_unload(async_track_state_change_event(self.hass, cycle_entity_ids, self._cycle_changed))
        self.entry.async_on_unload(self._keep_running)
        self.entry.async_on_unload(self._forget_preheated)
        self.entry.async_on_unload(self._stop_cooling)
        for keys, listener in (
            ((PROGRESS_KEY,), self._progress_changed),
            ((STAGE_KEY,), self._stage_changed),
            ((REMAINING_KEY, FINISH_TIME_KEY), self._finish_changed),
            ((CAVITY_TEMPERATURE_KEY, TARGET_TEMPERATURE_KEY), self._temperature_changed),
            (PREHEAT_FINISHED_KEYS, self._preheat_finished),
            ((PROBLEM_KEY,), self._problem_changed),
            ((LAYER_KEY,) if self.live_count == LIVE_COUNT_LAYERS else (), self._layer_changed),
        ):
            if entity_ids := [ids[key] for ids in (self.entity_ids, self.fallback_ids) for key in keys if key in ids]:
                self.entry.async_on_unload(async_track_state_change_event(self.hass, entity_ids, listener))

    def _temperatures(self) -> tuple[float, float] | None:
        """How hot the oven is and how hot it's to be, where both are known"""
        current, target = self._number(CAVITY_TEMPERATURE_KEY), self._number(TARGET_TEMPERATURE_KEY)
        return None if current is None or target is None or target <= 0 else (current, target)

    def _preheating(self) -> tuple[float, float] | None:
        """The temperatures of an oven still on its way up to heat, whatever program it's on"""
        temperatures = None if self.preheated or not self.running else self._temperatures()
        return None if temperatures is None or temperatures[0] >= temperatures[1] else temperatures

    def _progress(self) -> int | None:
        temperatures = self._preheating()
        if temperatures is None:
            return super()._progress()
        # an oven without a timer set has no progress to speak of, so the bar is how near it is to its temperature
        return max(0, int(temperatures[0] * 100 / temperatures[1]))

    def _preheat_message(self) -> str | None:
        temperatures = self._preheating()
        if temperatures is None:
            return None
        # a button on the oven for more of its elements to be used, which goes off by itself
        fast = self._state(FAST_PREHEAT_KEY)
        phase = FAST_PREHEAT_PHASE if fast is not None and fast.state == STATE_ON else PREHEAT_PHASE
        return PREHEAT_MESSAGE.format(
            phase=phase, current=f"{temperatures[0]:g}", target=f"{temperatures[1]:g}", unit=self._temperature_unit()
        )

    def _temperature_unit(self) -> str:
        cavity = self._state(CAVITY_TEMPERATURE_KEY)
        return cavity.attributes.get(ATTR_UNIT_OF_MEASUREMENT, "°") if cavity is not None else "°"

    def _phase(self) -> str | None:
        if self._paused() and (cycle := self._cycle_state()) is not None:
            return self._translated(cycle)
        if message := self._preheat_message():
            return message
        program, current = super()._phase(), self._number(CAVITY_TEMPERATURE_KEY)
        if (layer := self._layer_text()) is not None:
            # what it's doing, and how far it's got with it
            return f"{program} · {layer}" if program else layer[:1].upper() + layer[1:]
        if program is None or current is None:
            return program
        return OVEN_MESSAGE.format(program=program, current=f"{current:g}", unit=self._temperature_unit())

    def _progress_message(self, progress: int) -> str:
        if message := self._preheat_message():
            return message
        if (layer := self._layer_text()) is not None:
            return layer[:1].upper() + layer[1:]
        return super()._progress_message(progress)

    def _title_phase(self) -> str | None:
        # a 3D printer is named alone, since the name of a print is often that of its settings, and long
        if self.appliance_type in PLATFORM_TYPES.values():
            return None
        return super()._title_phase()

    @property
    def has_filament(self) -> bool:
        """Whether the appliance says how much filament a print takes, as a 3D printer does"""
        return WEIGHT_KEY in self.entity_ids

    @property
    def has_bed(self) -> bool:
        """Whether the appliance says how hot its bed is, as a 3D printer does"""
        return BED_TEMPERATURE_KEY in self.entity_ids

    def _filament_now(self) -> tuple[float | None, float | None]:
        weight, length = self._number(WEIGHT_KEY), self._number(LENGTH_KEY)
        return (weight or None, length or None)

    def _more_values(self, speak: bool) -> dict[str, str]:
        """The filament a print takes, as it runs, or took, once it's over, and its cost, empty where not known"""
        weight, length = self._filament_now() if self.running else self._filament
        language = self.hass.config.language.split("-")[0]
        grams, metres = ("grammi", "metri") if language == "it" else ("grams", "metres")
        values = {
            WEIGHT_PLACEHOLDER: "",
            LENGTH_PLACEHOLDER: "",
            FILAMENT_COST_PLACEHOLDER: "",
        }
        if weight is not None:
            values[WEIGHT_PLACEHOLDER] = format_amount(self.hass, weight, grams if speak else "g", 0 if weight >= 10 else 1)
            if self.filament_price > 0 and (cost := weight / 1000 * self.filament_price) >= 0.005:
                values[FILAMENT_COST_PLACEHOLDER] = (speak_cost if speak else format_cost)(self.hass, cost)
        if length is not None:
            values[LENGTH_PLACEHOLDER] = format_amount(self.hass, length, metres if speak else "m", 2)
        return values

    async def _ended(self, finished: bool, context: Context) -> None:
        self._filament = self._filament_now()
        await super()._ended(finished, context)
        if finished:
            self._watch_cooling(context)

    @callback
    def _watch_cooling(self, context: Context) -> None:
        """Tell once the bed is cool enough for the print to come off, where that's been asked for"""
        self._stop_cooling()
        entity_id = self.entity_ids.get(BED_TEMPERATURE_KEY)
        if self.cooled_temperature <= 0 or entity_id is None:
            return

        async def bed_changed(event: Event[EventStateChangedData]) -> None:
            await self._cooling(context)

        stop_listening = async_track_state_change_event(self.hass, entity_id, bed_changed)

        # nor for ever, in case it never cools that far
        @callback
        def waited(now: datetime) -> None:
            self._stop_cooling()

        stop_waiting = async_call_later(self.hass, COOLING_WAIT, waited)

        @callback
        def stop() -> None:
            stop_listening()
            stop_waiting()

        self._cancel_cooling = stop
        self.entry.async_create_task(self.hass, self._cooling(context))

    @callback
    def _stop_cooling(self) -> None:
        if self._cancel_cooling is not None:
            self._cancel_cooling()
            self._cancel_cooling = None

    async def _cooling(self, context: Context) -> None:
        bed = self._state(BED_TEMPERATURE_KEY)
        temperature = self._number(BED_TEMPERATURE_KEY)
        if self._cancel_cooling is None or bed is None or temperature is None:
            return
        unit = bed.attributes.get(ATTR_UNIT_OF_MEASUREMENT, "°")
        system = self.hass.config.units.temperature_unit
        # the threshold is in the units Home Assistant is set to, the bed in its own
        if unit in TemperatureConverter.VALID_UNITS and unit != system:
            if TemperatureConverter.convert(temperature, unit, system) >= self.cooled_temperature:
                return
        elif temperature >= self.cooled_temperature:
            return
        self._stop_cooling()
        language = self.hass.config.language.split("-")[0]
        text = COOLED_MESSAGES.get(language, COOLED_MESSAGES["en"]).format(temperature=f"{round(temperature)}{unit}")
        title = self._text(CONF_END_TITLE, DEFAULT_TITLE)
        async with self._sending:
            if not supernotify_available(self.hass):
                await self._send_message(text, title, context)
                return
            # for whoever is to take it off, not for the whole house to hear
            await self._supernotify(
                text,
                title,
                context,
                mobile_only=True,
                resend=True,
                extra_data={"notification_icon": self.icon, "mobile_push_notification_tag": f"{self.tag}_cooled"},
                actions=self._tap_actions(),
            )

    @property
    def has_problem(self) -> bool:
        """Whether the appliance reports the fault that stops it"""
        return PROBLEM_KEY in self.entity_ids

    @property
    def has_layers(self) -> bool:
        """Whether the appliance counts its cycle in layers, as a 3D printer does"""
        return LAYER_KEY in self.entity_ids and LAYERS_KEY in self.entity_ids

    def _layers(self) -> tuple[int, int] | None:
        """The layer it's on, and of how many, counted that way where chosen, once it's on the first"""
        if self.live_count != LIVE_COUNT_LAYERS:
            return None
        layer, layers = self._number(LAYER_KEY), self._number(LAYERS_KEY)
        if layer is None or layers is None or layer < 1 or layers < 1:
            return None
        return int(layer), int(layers)

    def _layer_text(self) -> str | None:
        if (layers := self._layers()) is None:
            return None
        text = LAYER_MESSAGES.get(self.hass.config.language.split("-")[0], LAYER_MESSAGES["en"])
        return text.format(layer=layers[0], layers=layers[1])

    async def _layer_changed(self, event: Event[EventStateChangedData]) -> None:
        """Another layer, shown no more often than mobile platforms allow, a small print going through its layers
        quicker than they'll show them"""
        now = dt_util.utcnow()
        if not self.running or self._paused() or self._layers() is None or not supernotify_available(self.hass):
            return
        if self._layer_shown is not None and (now - self._layer_shown).total_seconds() < LAYER_REFRESH:
            return
        self._layer_shown = now
        await self._live_refresh(event.context)

    def _chip(self, progress: int) -> str:
        if (layers := self._layers()) is not None:
            return LAYER_CHIP.format(layer=layers[0], layers=layers[1])
        return super()._chip(progress)

    def _live_actions(self) -> list[dict[str, str]]:
        """Pause while it runs, and carry on once paused, where the appliance has buttons for them"""
        state = self._cycle_state()
        if not self.running or state is None:
            return []
        if state.state in STATES_PAUSED:
            return self._buttons([ACTION_RESUME]) if RESUME_KEY in self.entity_ids else []
        if state.state in STATES_RUN and PAUSE_KEY in self.entity_ids:
            return self._buttons([ACTION_PAUSE])
        return []

    async def _action_pressed(self, event: Event) -> None:
        buttons = {ACTION_PAUSE: PAUSE_KEY, ACTION_RESUME: RESUME_KEY}
        action = str(event.data.get("action") or "")
        key = next((k for button, k in buttons.items() if action == f"{button}{self.entry.entry_id}"), None)
        if key is None:
            await super()._action_pressed(event)
            return
        if not self.running or (entity_id := self.entity_ids.get(key)) is None:
            # a button left on a Live Activity of a cycle since over
            return
        try:
            await self.hass.services.async_call(
                "button", "press", {ATTR_ENTITY_ID: entity_id}, blocking=True, context=event.context
            )
        except HomeAssistantError:
            _LOGGER.exception("APPLIANCES %s of %s failed", key, self.name)

    def _problem(self) -> str | None:
        """What the fault is, where the appliance reports one that's stopped it, else None. Said by the integration in
        its own words, or failing that the first serious one of its others, and empty if neither says"""
        problem = self._state(PROBLEM_KEY)
        if problem is None or problem.state != STATE_ON:
            return None
        text = str(problem.attributes.get(PROBLEM_TEXT_ATTRIBUTE) or "").strip()
        if text and text.lower() != "unknown":
            return text
        faults = self._state(FAULTS_KEY)
        if faults is not None and faults.state == STATE_ON:
            index = 1
            while (fault := faults.attributes.get(FAULT_TEXT_ATTRIBUTE.format(index=index))) is not None:
                severity = str(faults.attributes.get(FAULT_SEVERITY_ATTRIBUTE.format(index=index)) or "").lower()
                if severity in FAULTS_SERIOUS and str(fault).strip():
                    return str(fault).strip()
                index += 1
        return ""

    async def _problem_changed(self, event: Event[EventStateChangedData]) -> None:
        """A fault reported a moment after the cycle state it caused"""
        await self._problem_check(event.context)

    async def _problem_check(self, context: Context) -> None:
        """Tell of a fault that has stopped the appliance, whether it reached the cycle state first or the fault"""
        if not self.notify_problem or (detail := self._problem()) is None:
            return
        cycle = self._cycle_state()
        if self.running and cycle is not None and cycle.state in STATES_PAUSED:
            if not self._helped:
                self._helped = True
                await self._help(detail or None, context)
        elif (
            not self.running
            and self._abandoned_at is not None
            and (dt_util.utcnow() - self._abandoned_at).total_seconds() <= PROBLEM_SETTLE
        ):
            # once only, for the cycle given up
            self._abandoned_at = None
            await self._help(detail or None, context, failed=True)

    async def _problem_cleared(self, context: Context) -> None:
        """Going again after a fault was told of, so its notification is out of date"""
        if not self._helped:
            return
        self._helped = False
        if supernotify_available(self.hass):
            await self._supernotify(
                self.name,
                self.name,
                context,
                mobile_only=True,
                extra_data={"mobile_push_notification_tag": self.problem_tag, "mobile_push_clear_notification": True},
            )

    async def _finish_changed(self, event: Event[EventStateChangedData]) -> None:
        """The finish time moved on from the one counted down to, by a slower print, say, or one paused a while"""
        if not self.running or self._paused() or (finish := self._finish_time()) is None:
            return
        # the first finish time waits for the next progress to be shown with, so only one that has moved on
        if self.shown_finish is not None and abs(finish.timestamp() - self.shown_finish) >= FINISH_DRIFT:
            await self._live_refresh(event.context)

    def _paused(self) -> bool:
        state = self._cycle_state()
        return state is not None and state.state in STATES_PAUSED

    async def _temperature_changed(self, event: Event[EventStateChangedData]) -> None:
        if not self.running:
            return
        if self.preheated:
            await self._temperature_shown(event.context)
            return
        temperatures = self._temperatures()
        if temperatures is None:
            return
        if temperatures[0] < temperatures[1]:
            if not self.preheating:
                # whatever progress has been shown till now wasn't of this
                self.preheating = True
                self.last_progress_mark = -1
            await self._progress_changed(event)
        elif self.preheating:
            await self._preheated(event.context)
        else:
            # already hot when it was switched on
            self.preheated = True

    async def _preheat_finished(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        # only as it happens, since the sensor may still be telling of the last time the oven was heated
        if self.running and not self.preheated and new_state is not None and new_state.state in STATES_EVENT_ON:
            self._forget_preheated()
            self._cancel_preheated = async_call_later(self.hass, PREHEAT_SETTLE, partial(self._preheat_settled, event.context))

    async def _preheat_settled(self, context: Context, now: datetime) -> None:
        self._cancel_preheated = None
        if self.running and not self.preheated and self._cancel_end is None:
            await self._preheated(_later(context))

    @callback
    def _forget_preheated(self) -> None:
        if self._cancel_preheated is not None:
            self._cancel_preheated()
            self._cancel_preheated = None

    async def _temperature_shown(self, context: Context, always: bool = False) -> None:
        """Keep the Live Activity of an oven up to heat to its temperature, give or take a few degrees"""
        current = self._number(CAVITY_TEMPERATURE_KEY)
        shown = self.shown_temperature
        if not always and (current is None or (shown is not None and abs(current - shown) < TEMPERATURE_STEP)):
            return
        self.shown_temperature = current
        async with self._sending:
            if self.running and (message := self._phase()):
                await self._tell(message, False, context)

    async def _preheated(self, context: Context) -> None:
        """The oven is up to heat, and however its temperature then wanders isn't warming up again till it's been off"""
        self.preheated = True
        self.preheating = False
        # back to the progress of the program, for an oven with a timer set
        progress = self._progress()
        self.last_progress_mark = -1 if progress is None else self._mark(progress)
        message = PREHEATED_MESSAGE.replace(NAME_PLACEHOLDER, self.name)
        title = self._text(CONF_START_TITLE, DEFAULT_TITLE)
        async with self._sending:
            if not self.running or not self.notify_phase:
                pass
            elif supernotify_available(self.hass):
                # a notification of its own, so that it isn't lost as the Live Activity moves on
                await self._supernotify(
                    message,
                    title,
                    context,
                    resend=True,
                    extra_data={"notification_icon": self.icon},
                    actions=self._tap_actions(),
                )
            else:
                await self._send_message(message, title, context)
        # which goes straight on to what the oven is now doing
        await self._temperature_shown(context, always=True)

    async def _cycle_changed(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        if new_state is None:
            return
        if new_state.entity_id != self.cycle_entity_id and self._known(self.cycle_entity_id):
            # the other integration for the same appliance, while this one can be heard from, is only an echo
            return
        state: str = new_state.state
        _LOGGER.debug("APPLIANCES %s cycle state %s, running: %s", self.name, state, self.running)
        old_state = event.data["old_state"]
        if old_state is not None and old_state.state == state:
            # only its attributes changed, and a cycle over by its stage may still be running till it stops
            return
        if state in (STATE_UNKNOWN, STATE_UNAVAILABLE) and new_state.entity_id == self.cycle_entity_id:
            # can't be heard from, so the other integration for the appliance may already have told of its end
            await self._fallback_over(event.context)
            return
        await self._cycle_is(state, event.context)

    async def _cycle_is(self, state: str, context: Context) -> None:
        if state in (*STATES_FINISHED, *STATES_SETTLING, *STATES_ABANDONED):
            self.over_by_stage = False
        if state in STATES_RUN and self.over_by_stage:
            # still running after its stage said it was over, a dryer carrying on as it is, door opened or not
            return
        if state in STATES_RUN:
            # back on within moments of going off, so the same cycle
            self._keep_running()
            if self.running:
                if self.shown_paused:
                    # going again, so counting down again
                    await self._live_refresh(context)
                await self._problem_cleared(context)
                return
            if self.starting:
                return
            # a moment for the program and stage, which may come just after, to be what's told
            self.starting = True
            try:
                await asyncio.sleep(START_SETTLE)
            finally:
                self.starting = False
            cycle = self._cycle_state()
            if self.running or cycle is None or cycle.state not in STATES_ACTIVE:
                # over, or started by another report, while it waited
                return
            self.running = True
            self._helped = False
            self._abandoned_at = None
            # the last print's bed is no longer what's waited for
            self._stop_cooling()
            # unless it's hot already, from not long having been off
            temperatures = self._temperatures()
            self.preheated = temperatures is not None and temperatures[0] >= temperatures[1]
            self.preheating = self._preheating() is not None
            self.shown_temperature = None
            # with no progress yet to open the Live Activity with, the first reading is sent whatever it is, and
            # an oven already warm starts part of the way along
            progress = self._progress()
            self.last_progress_mark = -1 if progress is None else self._mark(progress)
            await self._started(context)
        elif not self.running:
            return
        elif state in STATES_PAUSED:
            await self._live_refresh(context)
            # stopped by a fault for someone to see to, unless it's only been paused
            await self._problem_check(context)
        elif state in STATES_SETTLING:
            if self._cancel_end is None:
                self._cancel_end = async_call_later(self.hass, CYCLE_SETTLE, partial(self._settled, context))
        elif state in STATES_FINISHED:
            await self._cycle_over(True, context)
        elif state in STATES_ABANDONED:
            # given up by a fault, told of with what it was, or stopped by hand, which needs no telling, the fault
            # read as it's given up, since closing its Live Activity may take a while, and one reported a moment
            # after still taken for what gave it up
            self._abandoned_at = dt_util.utcnow()
            fault = self._problem() if self.notify_problem else None
            await self._cycle_over(False, context)
            if fault is not None:
                self._abandoned_at = None
                await self._help(fault or None, context, failed=True)
        # anything else, such as `unavailable` while the vendor cloud is away, leaves the cycle as it was

    async def _fallback_over(self, context: Context) -> None:
        """The end of the cycle, if that's what the other integration for the appliance last said, since it went
        unheard while this one could be heard from. A start isn't taken from it, the cloud often lagging behind"""
        if not self.running:
            return
        stage = self._known(self.fallback_ids.get(STAGE_KEY))
        if stage is not None and stage.state in STAGES_FINISHED:
            await self._over_by_stage(context)
            return
        cycle = self._known(self.fallback_cycle_entity_id)
        if cycle is not None and cycle.state in (*STATES_FINISHED, *STATES_SETTLING, *STATES_ABANDONED):
            await self._cycle_is(cycle.state, context)

    async def _stage_changed(self, event: Event[EventStateChangedData]) -> None:
        """The appliance moving on within its cycle, such as a dryer from drying to cooling"""
        new_state = event.data["new_state"]
        if not self.running or new_state is None or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return
        if new_state.entity_id != self.entity_ids.get(STAGE_KEY) and self._known(self.cycle_entity_id):
            # the other integration for the same appliance, while this one can be heard from, is only an echo
            return
        if new_state.state in STAGES_FINISHED:
            await self._over_by_stage(event.context)
            return
        if new_state.state in STAGES_NONE or not supernotify_available(self.hass):
            # nothing in particular, as a 3D printer says in the moments before it finishes, leaves what it was doing
            return
        async with self._sending:
            if self.running and (message := self._phase()):
                await self._tell(message, False, event.context)

    async def _over_by_stage(self, context: Context) -> None:
        # done, though it may carry on as it is a while, a dryer tumbling its load now and then
        cycle = self._cycle_state()
        self.over_by_stage = cycle is not None and cycle.state in STATES_ACTIVE
        await self._cycle_over(True, context)

    async def _settled(self, context: Context, now: datetime) -> None:
        self._cancel_end = None
        await self._cycle_over(True, _later(context))

    async def _cycle_over(self, finished: bool, context: Context) -> None:
        self._keep_running()
        self._forget_preheated()
        self.running = False
        await self._ended(finished, context)
        # whatever it needed help with is over with it
        await self._problem_cleared(context)


class PowerWatcher(ApplianceWatcher):
    """An appliance known only by the power it draws, running while that is above a threshold"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry)
        self.power_entity_id: str = entry.options[CONF_POWER_ENTITY]
        self.threshold: float = entry.options.get(CONF_THRESHOLD, DEFAULT_THRESHOLD)
        self.grace_period: float = entry.options.get(CONF_GRACE_PERIOD, DEFAULT_GRACE_PERIOD)
        self.min_duration: float = entry.options.get(CONF_MIN_DURATION, DEFAULT_MIN_DURATION)
        if entry.options.get(CONF_SWITCH_OFF_BUTTON, True):
            self.switch_entity_id = entry.options.get(CONF_SWITCH_ENTITY)
        # power drawn, but not yet for long enough to count as a cycle
        self.pending: bool = False
        self._drawn_for: float = 0
        self._drawing_since: datetime | None = None
        self._cancel_end: CALLBACK_TYPE | None = None
        self._cancel_start: CALLBACK_TYPE | None = None

    @callback
    def async_start(self) -> None:
        # a cycle under way at startup still has its Live Activity closed when it ends
        self.running = self._drawing(self.hass.states.get(self.power_entity_id)) is True
        self.entry.async_on_unload(async_track_state_change_event(self.hass, self.power_entity_id, self._power_changed))
        self.entry.async_on_unload(self._keep_running)
        self.entry.async_on_unload(self._stop_counting)

    def _drawing(self, state: State | None) -> bool | None:
        """Whether more power than the threshold is drawn, None if the power isn't known"""
        try:
            power = float(state.state) if state is not None else None
        except ValueError:
            power = None
        if state is None or power is None:
            return None
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if unit in PowerConverter.VALID_UNITS:
            power = PowerConverter.convert(power, unit, UnitOfPower.WATT)
        return power > self.threshold

    async def _power_changed(self, event: Event[EventStateChangedData]) -> None:
        drawing = self._drawing(event.data["new_state"])
        _LOGGER.debug(
            "APPLIANCES %s drawing power %s, running: %s, pending: %s", self.name, drawing, self.running, self.pending
        )
        if drawing is None:
            # `unavailable` while the power monitor is away leaves the cycle as it was
            return
        if drawing:
            self._keep_running()
            if self.running:
                return
            if not self.pending:
                self.pending = True
                self._drawn_for = 0
                # the cycle began as it first drew power, not once it had for long enough to count
                self._cycle_began()
            if self._drawing_since is None:
                # time above the threshold adds up across drop outs, so one in the first minute doesn't start it over
                self._drawing_since = dt_util.utcnow()
                remaining = self.min_duration - self._drawn_for
                if remaining > 0:
                    self._cancel_start = async_call_later(self.hass, remaining, partial(self._long_enough, event.context))
                else:
                    await self._confirmed(event.context)
        elif self.running or self.pending:
            self._stop_counting()
            if self._cancel_end is None:
                self.cycle_stopped = dt_util.utcnow()
                self._cancel_end = async_call_later(self.hass, self.grace_period, partial(self._grace_over, event.context))

    @callback
    def _keep_running(self) -> None:
        self.cycle_stopped = None
        if self._cancel_end is not None:
            self._cancel_end()
            self._cancel_end = None

    def _totals_device_id(self) -> str | None:
        entity = er.async_get(self.hass).async_get(self.power_entity_id)
        return entity.device_id if entity is not None else None

    @callback
    def _stop_counting(self) -> None:
        """Add up the time above the threshold so far, while it isn't yet a cycle"""
        if self._drawing_since is not None:
            self._drawn_for += (dt_util.utcnow() - self._drawing_since).total_seconds()
            self._drawing_since = None
        if self._cancel_start is not None:
            self._cancel_start()
            self._cancel_start = None

    async def _long_enough(self, context: Context, now: datetime) -> None:
        self._cancel_start = None
        await self._confirmed(_later(context))

    async def _confirmed(self, context: Context) -> None:
        self.pending = False
        self._drawing_since = None
        self.running = True
        await self._started(context)

    async def _grace_over(self, context: Context, now: datetime) -> None:
        self._cancel_end = None
        if self.pending:
            _LOGGER.debug("APPLIANCES %s drew power for %.0fs, too short for a cycle", self.name, self._drawn_for)
            self.pending = False
            self._drawn_for = 0
            self._cycle_forgotten()
            return
        self.running = False
        await self._ended(True, _later(context))


class VacuumWatcher(ApplianceWatcher):
    """A robot vacuum of any make, whose cleaning is the cycle, from setting off till it's back or stopped by itself"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry)
        self._cancel_end: CALLBACK_TYPE | None = None
        # what it's waiting to see last, back on its dock or stuck
        self._pending: str | tuple[str, ...] | None = None
        # what the Live Activity last said it was doing, cleaning, paused or on its way back
        self._shown_activity: str | None = None
        # not yet known whether it was cleaning when Home Assistant started, until it says something telling
        self._unsure = False

    @callback
    def async_start(self) -> None:
        device_id: str = self.entry.data[CONF_DEVICE_ID]
        device = dr.async_get(self.hass).async_get(device_id)
        if device is not None:
            self.name = device.name_by_user or device.name or self.name
        self.cycle_entity_id = next(
            (e.entity_id for e in er.async_entries_for_device(er.async_get(self.hass), device_id) if e.domain == TYPE_VACUUM),
            None,
        )
        if self.cycle_entity_id is None:
            raise ConfigEntryNotReady(f"No vacuum entity found for {self.name}")
        self.appliance_type = "cleaning_robot"
        self.icon = TYPE_ICONS[self.appliance_type]
        # a cleaning under way at startup still has its Live Activity closed when it ends
        state = self.hass.states.get(self.cycle_entity_id)
        self.running = state is not None and state.state not in (*VACUUM_DONE, VACUUM_ERROR, STATE_UNAVAILABLE, STATE_UNKNOWN)
        # with nothing to go by yet, or an error that some integrations report again on reconnecting, whatever it says
        # next tells whether a cleaning was under way
        self._unsure = state is None or state.state in (VACUUM_ERROR, STATE_UNAVAILABLE, STATE_UNKNOWN)
        self.entry.async_on_unload(async_track_state_change_event(self.hass, self.cycle_entity_id, self._activity_changed))
        self.entry.async_on_unload(self._keep_running)

    @callback
    def _keep_running(self) -> None:
        self._pending = None
        self.cycle_stopped = None
        if self._cancel_end is not None:
            self._cancel_end()
            self._cancel_end = None

    async def _activity_changed(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        if new_state is None:
            return
        state: str = new_state.state
        _LOGGER.debug("APPLIANCES %s vacuum %s, running: %s", self.name, state, self.running)
        if state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            # away with the vendor cloud, which changes nothing
            return
        if self._unsure and state != VACUUM_ERROR:
            self._unsure = False
            if not self.running and state in VACUUM_SHOWN:
                # cleaning since before Home Assistant started, so already told, and its end still to tell
                self.running = True
                self._shown_activity = state
                return
        if not self.running:
            if state == VACUUM_CLEANING:
                self.running = True
                self._shown_activity = state
                await self._started(event.context)
            return
        old_state = event.data["old_state"]
        if state in VACUUM_DONE:
            if old_state is not None and old_state.state == VACUUM_CLEANING:
                if (new_state.last_changed - old_state.last_changed).total_seconds() < VACUUM_BLIP:
                    # back within a moment of setting off, which some integrations report as a vacuum leaves its dock
                    # and then keep to while it cleans, so only believed if nothing more is heard for a long while
                    if self._pending is None:
                        self._wait(self._settled, VACUUM_BLIP_KIND, event.context, VACUUM_BLIP_SETTLE)
                elif self._pending not in (VACUUM_DONE, VACUUM_MIDWAY_KIND):
                    # straight back from cleaning, without saying it was on its way, as when it washes its mop or
                    # fills its tank part way through, so given longer to set off again
                    self._wait(self._settled, VACUUM_MIDWAY_KIND, event.context, VACUUM_MIDWAY_SETTLE)
            elif self._pending not in (VACUUM_DONE, VACUUM_MIDWAY_KIND):
                # over only once it has stayed back
                self._wait(self._settled, VACUUM_DONE, event.context)
        elif state == VACUUM_ERROR:
            # stuck only if it stays so, since some integrations report a past error again on reconnecting, while
            # the vacuum carries on, and an error once back on its dock is for its own app to tell
            if self._pending is None:
                self._wait(self._stuck_for_good, VACUUM_ERROR, event.context)
        elif state == VACUUM_PAUSED and self._pending in (VACUUM_DONE, VACUUM_MIDWAY_KIND):
            # paused on its dock, which some integrations report once one is back, isn't setting off again
            return
        else:
            # cleaning, paused or on its way back is the same cleaning
            self._keep_running()
            if state in VACUUM_SHOWN and state != self._shown_activity:
                # what it's doing, with the buttons that go with it
                self._shown_activity = state
                await self._live_refresh(event.context)

    def _phase(self) -> str | None:
        state = self.hass.states.get(self.cycle_entity_id) if self.cycle_entity_id else None
        return self._translated(state) if state is not None and state.state in VACUUM_SHOWN else None

    def _live_actions(self) -> list[dict[str, str]]:
        state = self.hass.states.get(self.cycle_entity_id) if self.cycle_entity_id else None
        if state is None or not self.running:
            return []
        features = int(state.attributes.get(ATTR_SUPPORTED_FEATURES) or 0)
        buttons: list[str] = []
        if state.state == VACUUM_PAUSED:
            if features & VacuumEntityFeature.START:
                buttons.append(ACTION_RESUME)
        elif state.state != VACUUM_RETURNING and features & VacuumEntityFeature.PAUSE:
            buttons.append(ACTION_PAUSE)
        if state.state != VACUUM_RETURNING and features & VacuumEntityFeature.RETURN_HOME:
            buttons.append(ACTION_RETURN)
        return self._buttons(buttons)

    async def _action_pressed(self, event: Event) -> None:
        services = {ACTION_PAUSE: "pause", ACTION_RESUME: "start", ACTION_RETURN: "return_to_base"}
        action = str(event.data.get("action") or "")
        service = next((s for button, s in services.items() if action == f"{button}{self.entry.entry_id}"), None)
        if service is None:
            await super()._action_pressed(event)
            return
        try:
            await self.hass.services.async_call(
                TYPE_VACUUM, service, {ATTR_ENTITY_ID: self.cycle_entity_id}, blocking=True, context=event.context
            )
        except HomeAssistantError:
            _LOGGER.exception("APPLIANCES %s of %s failed", service, self.name)

    @callback
    def _wait(
        self,
        then: Callable[[Context, datetime], Coroutine[Any, Any, None]],
        kind: str | tuple[str, ...],
        context: Context,
        delay: float = VACUUM_SETTLE,
    ) -> None:
        self._keep_running()
        self._pending = kind
        # back, or stuck, from now on unless it carries on
        self.cycle_stopped = dt_util.utcnow()
        self._cancel_end = async_call_later(self.hass, delay, partial(then, context))

    async def _settled(self, context: Context, now: datetime) -> None:
        self._cancel_end = None
        self._pending = None
        self.running = False
        await self._ended(True, _later(context))

    async def _stuck_for_good(self, context: Context, now: datetime) -> None:
        # stopped where it is, so no end to tell, only that it can't go on without someone
        self._cancel_end = None
        self._pending = None
        self.running = False
        await self._ended(False, _later(context))
        await self._stuck(_later(context))

    async def _stuck(self, context: Context) -> None:
        stuck = STUCK_MESSAGES.get(self.hass.config.language.split("-")[0], STUCK_MESSAGES["en"])
        message = stuck.replace(NAME_PLACEHOLDER, self.name)
        title = self._text(CONF_START_TITLE, DEFAULT_TITLE)
        async with self._sending:
            if supernotify_available(self.hass):
                await self._supernotify(
                    message,
                    title,
                    context,
                    resend=True,
                    extra_data={"notification_icon": self.icon},
                    actions=self._tap_actions(),
                )
            else:
                await self._send_message(message, title, context)
