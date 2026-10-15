"""Constants for Appliance Auto Notify"""

from typing import Final

DOMAIN: Final[str] = "appliance_autonotify"
SUPERNOTIFY_DOMAIN: Final[str] = "supernotify"

CONF_START_TITLE: Final[str] = "start_title"
CONF_START_MESSAGE: Final[str] = "start_message"
CONF_END_TITLE: Final[str] = "end_title"
CONF_END_MESSAGE: Final[str] = "end_message"
# notify entities, used only without Supernotify
CONF_TARGETS: Final[str] = "targets"
# as the `target` and `custom_target` of supernotify.notify
CONF_TARGET: Final[str] = "target"
CONF_CUSTOM_TARGET: Final[str] = "custom_target"
CONF_DELIVERIES: Final[str] = "deliveries"
# whether progress is told with ordinary notifications, the Live Activity is kept up to date regardless
CONF_NOTIFY_PROGRESS: Final[str] = "notify_progress"
# whether the start and the end are told with ordinary notifications, the Live Activity is opened and closed regardless
CONF_NOTIFY_START: Final[str] = "notify_start"
CONF_NOTIFY_END: Final[str] = "notify_end"
# whether the end of a phase, such as an oven getting up to heat, is told with an ordinary notification
CONF_NOTIFY_PHASE: Final[str] = "notify_phase"
# whether the program goes beside the name in the title of a Live Activity with a timer, for those short enough to fit
CONF_PROGRAM_IN_TITLE: Final[str] = "program_in_title"
# path of the dashboard opened by a tap on a notification, the app is opened where it was last if there's none
CONF_DASHBOARD: Final[str] = "dashboard"
LOVELACE_DOMAIN: Final[str] = "lovelace"
# the dashboard Home Assistant starts with has no path of its own in the list of them
DEFAULT_DASHBOARD: Final[str] = "lovelace"
DEFAULT_DASHBOARD_TITLE: Final[str] = "Overview"
# the one entry that isn't an appliance, holding whether appliances found are set up without asking
TYPE_DISCOVERY: Final[str] = "discovery"
CONF_AUTO_DISCOVER: Final[str] = "auto_discover"
# an appliance with no integration of its own, known only by the power it draws
TYPE_POWER: Final[str] = "power"
CONF_POWER_ENTITY: Final[str] = "power_entity"
# a robot vacuum, of any make, whose cleaning is a cycle
TYPE_VACUUM: Final[str] = "vacuum"
CONF_THRESHOLD: Final[str] = "threshold"
CONF_GRACE_PERIOD: Final[str] = "grace_period"
CONF_MIN_DURATION: Final[str] = "min_duration"
# the smart plug the appliance is on, offered as a button to switch off once it has finished
CONF_SWITCH_ENTITY: Final[str] = "switch_entity"
# whether that button is offered, for a plug chosen but better left on
CONF_SWITCH_OFF_BUTTON: Final[str] = "switch_off_button"
# watts above which the appliance is running
DEFAULT_THRESHOLD: Final[float] = 1
# seconds at or below the threshold before the cycle is over, so short drop outs are ignored
DEFAULT_GRACE_PERIOD: Final[float] = 60
# seconds above the threshold before it counts as a cycle, so a door opened or a button pressed isn't one
DEFAULT_MIN_DURATION: Final[float] = 0

# English only for the MVP
DISCOVERY_TITLE: Final[str] = "Automatic discovery"
NAME_PLACEHOLDER: Final[str] = "{name}"
# the program under way, as Home Assistant shows it, and nothing at all for an appliance that reports none
PROGRAM_PLACEHOLDER: Final[str] = "{program}"
DEFAULT_TITLE: Final[str] = "{name}"
DEFAULT_START_MESSAGE: Final[str] = "{name} started"
DEFAULT_END_MESSAGE: Final[str] = "{name} is finished"
PROGRESS_MESSAGE: Final[str] = "{progress}% complete"

# minutes after which the end is told again, for as long as nobody says the appliance has been seen to
CONF_REMINDER: Final[str] = "reminder"
# how many times it's told again
CONF_REMINDER_REPEATS: Final[str] = "reminder_repeats"
DEFAULT_REMINDER_REPEATS: Final[int] = 3
# minutes for Remind Later, when no reminder is set
DEFAULT_SNOOZE: Final[int] = 30
# buttons on the end notification, each followed by the entry id of the appliance
ACTION_FINISHED: Final[str] = "APPLIANCE_FINISHED_"
ACTION_REMIND: Final[str] = "APPLIANCE_REMIND_"
ACTION_SWITCH_OFF: Final[str] = "APPLIANCE_SWITCH_OFF_"
# by the language of Home Assistant, English for any other
ACTION_TITLES: Final[dict[str, dict[str, str]]] = {
    "en": {ACTION_FINISHED: "Finished", ACTION_REMIND: "Remind Later", ACTION_SWITCH_OFF: "Switch Off"},
    "it": {ACTION_FINISHED: "Finito", ACTION_REMIND: "Ricordamelo dopo", ACTION_SWITCH_OFF: "Spegni presa"},
}
MOBILE_ACTION_EVENT: Final[str] = "mobile_app_notification_action"
# the text of the Android status bar chip, which shows it in full only up to about 7 characters
PROGRESS_CHIP: Final[str] = "{progress}%"
PREHEAT_PHASE: Final[str] = "Pre-heating"
FAST_PREHEAT_PHASE: Final[str] = "Fast pre-heat"
PREHEAT_MESSAGE: Final[str] = "{phase}, {current} of {target}{unit}"
PREHEATED_MESSAGE: Final[str] = "{name} is pre-heated"
# a robot vacuum that has stopped where it is, stuck or lifted, and won't go on by itself, by the language of Home
# Assistant as for the buttons, English for any other
STUCK_MESSAGES: Final[dict[str, str]] = {"en": "{name} needs help", "it": "{name} ha bisogno di aiuto"}
# the title of a Live Activity with a timer, which iOS shows on the Lock Screen in place of the message
LIVE_TITLE: Final[str] = "{title} · {phase}"
# what an oven up to heat is doing, and how hot it is
OVEN_MESSAGE: Final[str] = "{program}, {current}{unit}"
SUPERNOTIFY_PRESENT: Final[str] = "Supernotify is installed, so mobile apps will show a Live Activity for each cycle."
SUPERNOTIFY_MISSING: Final[str] = (
    "**Supernotify is not installed.** Only a plain start and end notification can be sent, to every phone with the "
    "Home Assistant app, with no Live Activity. Install Supernotify from HACS for the full experience."
)

# activities of a robot vacuum, as Home Assistant has them for every make
VACUUM_CLEANING: Final[str] = "cleaning"
# back where it started, or stopped by itself, the cleaning being over
VACUUM_DONE: Final[tuple[str, ...]] = ("docked", "idle")
VACUUM_ERROR: Final[str] = "error"
# how long a robot vacuum stays on its dock before its cleaning is over, since one goes back mid-cleaning to wash its
# mop, and some integrations report it docked for a while as it sets off
VACUUM_SETTLE: Final[int] = 600
# seconds after setting off within which being back is taken for an integration that reports a vacuum docked as it
# leaves, as Ecovacs does each time one sets off again after washing its mop, and keeps to that while it cleans
VACUUM_BLIP: Final[float] = 5
VACUUM_BLIP_KIND: Final[str] = "blip"
# how long such a report is left before the cleaning is taken to be over, with nothing else heard from the vacuum
VACUUM_BLIP_SETTLE: Final[int] = 3 * 3600
# translation key, per vendor platform, of the entity whose state follows the appliance cycle
CYCLE_KEYS: Final[dict[str, str]] = {"home_connect": "operation_state", "bambu_lab": "print_status"}
PROGRESS_KEY: Final[str] = "program_progress"
# the time left, which where an appliance reports it is fresher than its finish time, and is how that's worked out
REMAINING_KEY: Final[str] = "remaining_time"
FINISH_TIME_KEY: Final[str] = "program_finish_time"
# selects, unlike the others, of the program under way, and of the one chosen, which is all an oven reports
SELECTED_PROGRAM_KEYS: Final[tuple[str, ...]] = ("active_program", "selected_program")
# the name of the print under way, which is to a 3D printer what the program is to an appliance
TASK_KEY: Final[str] = "subtask_name"
PROGRAM_KEYS: Final[tuple[str, ...]] = (*SELECTED_PROGRAM_KEYS, TASK_KEY)
# what a 3D printer is doing, from heating its bed to printing, said alongside the bar
STAGE_KEY: Final[str] = "stage"
# an oven warming up has no progress of its own, only how hot it is and how hot it's to be
TARGET_TEMPERATURE_KEY: Final[str] = "setpoint_temperature"
CAVITY_TEMPERATURE_KEY: Final[str] = "oven_current_cavity_temperature"
PREHEAT_FINISHED_KEYS: Final[tuple[str, ...]] = ("preheat_finished", "regular_preheat_finished")
FAST_PREHEAT_KEY: Final[str] = "fast_pre_heat"
# domain, by translation key, of each entity of an appliance that's made use of
ENTITY_DOMAINS: Final[dict[str, str]] = {
    PROGRESS_KEY: "sensor",
    FINISH_TIME_KEY: "sensor",
    REMAINING_KEY: "sensor",
    **dict.fromkeys(SELECTED_PROGRAM_KEYS, "select"),
    TASK_KEY: "sensor",
    STAGE_KEY: "sensor",
    TARGET_TEMPERATURE_KEY: "number",
    CAVITY_TEMPERATURE_KEY: "sensor",
    **dict.fromkeys(PREHEAT_FINISHED_KEYS, "sensor"),
    FAST_PREHEAT_KEY: "switch",
}
# translation keys of a vendor platform for the entities named otherwise by Home Connect
VENDOR_KEYS: Final[dict[str, dict[str, str]]] = {
    "bambu_lab": {"print_progress": PROGRESS_KEY, "end_time": FINISH_TIME_KEY},
}
# the type of appliance of a platform that has only the one
PLATFORM_TYPES: Final[dict[str, str]] = {"bambu_lab": "3d_printer"}
# degrees between Live Activity updates of an oven up to heat, whose temperature never stops wandering
TEMPERATURE_STEP: Final[float] = 5
# seconds before an oven saying it's up to heat is believed, since one switched off says so too, just before it's off
PREHEAT_SETTLE: Final[float] = 3
# an event sensor is `off` until whatever it tells of has happened
STATES_EVENT_ON: Final[tuple[str, ...]] = ("present", "confirmed", "on")

# the cycle has started, a 3D printer first heating up and levelling its bed as it gets ready to print
STATES_RUN: Final[tuple[str, ...]] = ("run", "prepare", "running")
# a cycle already under way, so not a new start when `run` follows
STATES_ACTIVE: Final[tuple[str, ...]] = (*STATES_RUN, "pause", "actionrequired")
# the cycle is over, an oven switched off goes straight from `run` to `inactive` without ever being `finished`
STATES_FINISHED: Final[tuple[str, ...]] = ("finished", "inactive", "finish")
# over too unless `run` soon follows, an oven being `ready` for a moment as it starts or has its settings changed,
# and a 3D printer `idle` with no word of how its print ended
STATES_SETTLING: Final[tuple[str, ...]] = ("ready", "idle")
# paused part way through, with the time left standing still
STATES_PAUSED: Final[tuple[str, ...]] = ("pause",)
# seconds the finish time can drift from the one on the Live Activity before it's brought up to date, since the time
# left may be counted only in whole minutes
FINISH_DRIFT: Final[float] = 120
# seconds an appliance is left to settle before the cycle is over
CYCLE_SETTLE: Final[float] = 10
# seconds a Live Activity is left to open before anything more is sent to it, since a push sent straight after the
# start can reach a phone ahead of it, and then be overwritten by the start, with no bar and no program
LIVE_SETTLE: Final[float] = 5
# the cycle is over without finishing, so the Live Activity goes without an end notification
STATES_ABANDONED: Final[tuple[str, ...]] = ("error", "aborting", "failed")

# percentage points between Live Activity updates, since mobile platforms throttle frequent ones
PROGRESS_STEP: Final[int] = 5
# percentage points between ordinary notifications of progress, where those are asked for
PROGRESS_NOTIFY_STEP: Final[int] = 10
# from here on the end is in sight and the bar is being watched, so it's kept closer to the appliance
PROGRESS_FINAL: Final[int] = 90
PROGRESS_FINAL_STEP: Final[int] = 2

MOBILE_PUSH_TRANSPORT: Final[str] = "mobile_push"
# Android notification channel of its own, made with sound on the first notification, since a Live Update in the
# app's default channel arrives without a sound
ANDROID_CHANNEL: Final[str] = "Appliances"
# platform of the notify entities used when there's no Supernotify and none have been chosen
MOBILE_APP_PLATFORM: Final[str] = "mobile_app"

DEFAULT_ICON: Final[str] = "mdi:progress-clock"
TYPE_OVEN: Final[str] = "oven"
# the type of a Home Connect appliance, by how its programs are named
APPLIANCE_TYPES: Final[dict[str, str]] = {
    "dishcare_dishwasher_program_": "dishwasher",
    "laundry_care_washer_program_": "washer",
    "laundry_care_washer_dryer_program_": "washer_dryer",
    "laundry_care_dryer_program_": "dryer",
    "cooking_oven_program_": TYPE_OVEN,
    "cooking_hob_program_": "hob",
    "cooking_common_program_hood_": "hood",
    "consumer_products_coffee_maker_program_": "coffee_maker",
    "consumer_products_cleaning_robot_program_": "cleaning_robot",
    "heating_ventilation_air_conditioning_air_conditioner_program_": "air_conditioner",
}
TYPE_ICONS: Final[dict[str, str]] = {
    "dishwasher": "mdi:dishwasher",
    "washer": "mdi:washing-machine",
    "washer_dryer": "mdi:washing-machine",
    "dryer": "mdi:tumble-dryer",
    TYPE_OVEN: "mdi:stove",
    "hob": "mdi:pot-steam",
    "hood": "mdi:fan",
    "coffee_maker": "mdi:coffee-maker",
    "cleaning_robot": "mdi:robot-vacuum",
    "air_conditioner": "mdi:air-conditioner",
    "3d_printer": "mdi:printer-3d",
    # types known only from the name
    "microwave": "mdi:microwave",
    "kettle": "mdi:kettle",
}
# the types whose phases are worth a notification unless it's turned off, an oven up to heat being waited
# for where a dishwasher starting to rinse isn't
PHASES_NOTIFIED: Final[tuple[str, ...]] = (TYPE_OVEN,)
# a power monitor is offered as an appliance when its name says it's one of these, appliances that run in cycles
# worth being told of, where a kettle or a coffee maker is done in a minute or two
CYCLE_TYPES: Final[tuple[str, ...]] = ("dishwasher", "washer", "washer_dryer", "dryer", TYPE_OVEN)
# platforms whose power sensors are estimated or worked out from others, so never the appliance's own measurement,
# such as the standby draw Powercalc adds to a smart plug's device
DERIVED_POWER_PLATFORMS: Final[tuple[str, ...]] = (
    "powercalc",
    "template",
    "integration",
    "utility_meter",
    "group",
    "min_max",
    "statistics",
    "derivative",
    "filter",
)
