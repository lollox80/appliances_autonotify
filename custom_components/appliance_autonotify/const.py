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
# what the title of a Live Activity names, the program going beside the name unless chosen otherwise, since it's
# where the program shows on the iOS Lock Screen once a timer has taken the message's place
CONF_LIVE_TITLE: Final[str] = "live_title"
LIVE_TITLE_NAME_PROGRAM: Final[str] = "name_program"
LIVE_TITLE_PROGRAM: Final[str] = "program"
LIVE_TITLE_NAME: Final[str] = "name"
LIVE_TITLES: Final[tuple[str, ...]] = (LIVE_TITLE_NAME_PROGRAM, LIVE_TITLE_PROGRAM, LIVE_TITLE_NAME)
# what a Live Activity shows in place of its message, the time left where the appliance reports a finish time, or
# the program, for an appliance whose program is always the same and so not worth the title
CONF_LIVE_DETAIL: Final[str] = "live_detail"
LIVE_DETAIL_TIME: Final[str] = "time_remaining"
LIVE_DETAIL_PROGRAM: Final[str] = "program"
LIVE_DETAILS: Final[tuple[str, ...]] = (LIVE_DETAIL_TIME, LIVE_DETAIL_PROGRAM)
# how a Live Activity counts how far along it is, by percentage, or for a 3D printer by layer
CONF_LIVE_COUNT: Final[str] = "live_count"
LIVE_COUNT_PERCENT: Final[str] = "percent"
LIVE_COUNT_LAYERS: Final[str] = "layers"
LIVE_COUNTS: Final[tuple[str, ...]] = (LIVE_COUNT_PERCENT, LIVE_COUNT_LAYERS)
# whether an appliance that reports a fault is told of when one stops it, for one that has a sensor of its faults
CONF_NOTIFY_PROBLEM: Final[str] = "notify_problem"
# whether a picture from the appliance's own camera goes with its end and its faults, for one with a camera
CONF_SNAPSHOT: Final[str] = "snapshot"
# the switch the title choice took over from, off being the name only
CONF_PROGRAM_IN_TITLE: Final[str] = "program_in_title"
# path of the dashboard opened by a tap on a notification, the app is opened where it was last if there's none
CONF_DASHBOARD: Final[str] = "dashboard"
# whether a dashboard named for the appliance has been looked for, which is done once, as it's first set up, so
# whatever is chosen after is left alone
CONF_DASHBOARD_FOUND: Final[str] = "dashboard_found"
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
# what the cycle came to, as it ends, and nothing at all where that isn't known
DURATION_PLACEHOLDER: Final[str] = "{duration}"
ENERGY_PLACEHOLDER: Final[str] = "{energy}"
COST_PLACEHOLDER: Final[str] = "{cost}"
# the time of day the cycle began, as it runs and once it's over
START_TIME_PLACEHOLDER: Final[str] = "{start_time}"
# the filament a print took, and what it cost at the price per kilo chosen
WEIGHT_PLACEHOLDER: Final[str] = "{weight}"
LENGTH_PLACEHOLDER: Final[str] = "{length}"
FILAMENT_COST_PLACEHOLDER: Final[str] = "{filament_cost}"
# the price of a kilo of filament, in the currency of Home Assistant, 0 or unset for no cost
CONF_FILAMENT_PRICE: Final[str] = "filament_price"
# the bed temperature below which a finished print is ready to come off, 0 or unset for no notification of it
CONF_COOLED_TEMPERATURE: Final[str] = "cooled_temperature"
# hours the bed is waited for, one that never cools as far being left alone
COOLING_WAIT: Final[float] = 6 * 3600
COOLED_MESSAGES: Final[dict[str, str]] = {
    "en": "Bed down to {temperature}, the print can come off",
    "it": "Piatto sceso a {temperature}, la stampa si può staccare",
}
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
# buttons on the Live Activity of a robot vacuum, to pause it, let it carry on, or send it back to its dock
ACTION_PAUSE: Final[str] = "APPLIANCE_PAUSE_"
ACTION_RESUME: Final[str] = "APPLIANCE_RESUME_"
ACTION_RETURN: Final[str] = "APPLIANCE_RETURN_"
# by the language of Home Assistant, English for any other
ACTION_TITLES: Final[dict[str, dict[str, str]]] = {
    "en": {
        ACTION_FINISHED: "Finished",
        ACTION_REMIND: "Remind Later",
        ACTION_SWITCH_OFF: "Switch Off",
        ACTION_PAUSE: "Pause",
        ACTION_RESUME: "Resume",
        ACTION_RETURN: "Return to Dock",
    },
    "it": {
        ACTION_FINISHED: "Finito",
        ACTION_REMIND: "Ricordamelo dopo",
        ACTION_SWITCH_OFF: "Spegni presa",
        ACTION_PAUSE: "Pausa",
        ACTION_RESUME: "Riprendi",
        ACTION_RETURN: "Torna alla base",
    },
}
MOBILE_ACTION_EVENT: Final[str] = "mobile_app_notification_action"
# action buttons Android shows on a notification, any after those being left out
ANDROID_BUTTONS: Final[int] = 3

# whether maintenance is tracked for the appliance, unset until it's been asked for or turned down, so it's offered
# once, on the first end notification, rather than left for someone to go looking for
CONF_MAINTENANCE: Final[str] = "maintenance"
# the cycles between each item of maintenance, by item, as `maintenance_drum_clean`, 0 leaving the item out
CONF_MAINTENANCE_PREFIX: Final[str] = "maintenance_"
# the items each type of appliance starts with, and how many cycles apart, generous since vendors are keen to sell
# cleaning tablets and spares, all to be changed or taken out in its settings
MAINTENANCE_ITEMS: Final[dict[str, dict[str, int]]] = {
    "washer": {"drum_clean": 30, "filter": 50},
    "washer_dryer": {"drum_clean": 30, "filter": 50, "lint_filter": 20},
    "dishwasher": {"filter": 30, "machine_clean": 60},
    "dryer": {"condenser": 30},
}
# an entity of the appliance's own that says how much life a part has left, as a robot vacuum's brushes and filters,
# which is the item instead of a count of cycles, due once it's this low
LIFESPAN_KEY: Final[str] = "lifespan"
LIFESPAN_DUE: Final[float] = 10
# the button the same integration has to reset that part, by the translation key, as Ecovacs has it
LIFESPAN_RESET_PREFIX: Final[str] = "reset_"
# days that later is, for one item or all of an appliance's, after which it's due again
MAINTENANCE_SNOOZE_DAYS: Final[int] = 30
# buttons on the notification of an item due, followed by the entry id and the item, and on the first end
# notification of an appliance whose maintenance isn't tracked, followed by the entry id
ACTION_MAINTAINED: Final[str] = "APPLIANCE_MAINTAINED_"
ACTION_MAINTENANCE_LATER: Final[str] = "APPLIANCE_MAINTENANCE_LATER_"
ACTION_TRACK_MAINTENANCE: Final[str] = "APPLIANCE_TRACK_MAINTENANCE_"
MAINTENANCE_ACTION_TITLES: Final[dict[str, dict[str, str]]] = {
    "en": {ACTION_MAINTAINED: "Done", ACTION_MAINTENANCE_LATER: "In a Month", ACTION_TRACK_MAINTENANCE: "Track Maintenance"},
    "it": {ACTION_MAINTAINED: "Fatto", ACTION_MAINTENANCE_LATER: "Tra un mese", ACTION_TRACK_MAINTENANCE: "Segui manutenzione"},
}
# the name of each item, and what its notification says, by the language of Home Assistant as for the buttons
MAINTENANCE_NAMES: Final[dict[str, dict[str, str]]] = {
    "en": {
        "drum_clean": "Drum clean",
        "filter": "Filter clean",
        "lint_filter": "Lint filter clean",
        "machine_clean": "Machine clean",
        "condenser": "Condenser clean",
    },
    "it": {
        "drum_clean": "Pulizia del cestello",
        "filter": "Pulizia del filtro",
        "lint_filter": "Pulizia del filtro lanugine",
        "machine_clean": "Pulizia della macchina",
        "condenser": "Pulizia del condensatore",
    },
}
MAINTENANCE_MESSAGES: Final[dict[str, dict[str, str]]] = {
    "en": {
        "cycle": "{item}, 1 cycle since the last one",
        "cycles": "{item}, {cycles} cycles since the last one",
        "lifespan": "{item} at {value}%",
    },
    "it": {
        "cycle": "{item}, 1 ciclo dall'ultima",
        "cycles": "{item}, {cycles} cicli dall'ultima",
        "lifespan": "{item} al {value}%",
    },
}

# the text of the Android status bar chip, which shows it in full only up to about 7 characters
PROGRESS_CHIP: Final[str] = "{progress}%"
PREHEAT_PHASE: Final[str] = "Pre-heating"
FAST_PREHEAT_PHASE: Final[str] = "Fast pre-heat"
PREHEAT_MESSAGE: Final[str] = "{phase}, {current} of {target}{unit}"
PREHEATED_MESSAGE: Final[str] = "{name} is pre-heated"
# a robot vacuum that has stopped where it is, stuck or lifted, and won't go on by itself, by the language of Home
# Assistant as for the buttons, English for any other
STUCK_MESSAGES: Final[dict[str, str]] = {"en": "{name} needs help", "it": "{name} ha bisogno di aiuto"}
# a cycle stopped for good by a fault, by type of appliance, then for any other
FAILED_MESSAGES: Final[dict[str, dict[str, str]]] = {
    "en": {"3d_printer": "Print failed", "": "Stopped by a fault"},
    "it": {"3d_printer": "Stampa fallita", "": "Interrotto per un guasto"},
}
# what a 3D printer counts its print in, with how far it's got and of how many
LAYER_MESSAGES: Final[dict[str, str]] = {"en": "layer {layer}/{layers}", "it": "strato {layer}/{layers}"}
# the Android status bar chip, short, as for the percentage
LAYER_CHIP: Final[str] = "{layer}/{layers}"
# seconds a fault is given to be reported, as it may come a moment before or after the cycle state that it stopped it
PROBLEM_SETTLE: Final[float] = 5
# seconds between Live Activity updates for the layer, since mobile platforms throttle frequent ones
LAYER_REFRESH: Final[float] = 60
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
VACUUM_PAUSED: Final[str] = "paused"
VACUUM_RETURNING: Final[str] = "returning"
# what the Live Activity of a robot vacuum says it's doing, with buttons to match
VACUUM_SHOWN: Final[tuple[str, ...]] = (VACUUM_CLEANING, VACUUM_PAUSED, VACUUM_RETURNING)
# back where it started, or stopped by itself, the cleaning being over
VACUUM_DONE: Final[tuple[str, ...]] = ("docked", "idle")
VACUUM_ERROR: Final[str] = "error"
# how long a robot vacuum stays on its dock, having said it was on its way back, before its cleaning is over
VACUUM_SETTLE: Final[int] = 600
# how long one stays on its dock having gone straight there from cleaning, as one does part way through to wash its
# mop or fill its tank, which can take over ten minutes, before its cleaning is over
VACUUM_MIDWAY_SETTLE: Final[int] = 30 * 60
VACUUM_MIDWAY_KIND: Final[str] = "midway"
# seconds after setting off within which being back is taken for an integration that reports a vacuum docked as it
# leaves, as Ecovacs does each time one sets off again after washing its mop, and keeps to that while it cleans
VACUUM_BLIP: Final[float] = 5
VACUUM_BLIP_KIND: Final[str] = "blip"
# how long such a report is left before the cleaning is taken to be over, with nothing else heard from the vacuum
VACUUM_BLIP_SETTLE: Final[int] = 3 * 3600
# what each entity made use of does, by its translation key as Home Connect has it: the state of the cycle, how far
# along it is, when it will finish, and the program
CYCLE_KEY: Final[str] = "operation_state"
PROGRESS_KEY: Final[str] = "program_progress"
# the time left, which where an appliance reports it is fresher than its finish time, and is how that's worked out
REMAINING_KEY: Final[str] = "remaining_time"
FINISH_TIME_KEY: Final[str] = "program_finish_time"
# selects, unlike the others, of the program under way, and of the one chosen, which is all an oven reports
SELECTED_PROGRAM_KEYS: Final[tuple[str, ...]] = ("active_program", "selected_program")
# the name of the print under way, which is to a 3D printer what the program is to an appliance
TASK_KEY: Final[str] = "subtask_name"
PROGRAM_KEYS: Final[tuple[str, ...]] = (*SELECTED_PROGRAM_KEYS, TASK_KEY)
# what the appliance is doing within its cycle, such as drying then cooling, or a 3D printer heating its bed then
# printing, which Home Connect doesn't report
STAGE_KEY: Final[str] = "stage"
# a fault that has stopped the cycle, a problem binary sensor whose attributes say what it is, as `error`, and others
# that only say what's wrong, with how serious each is, as HMS errors do
PROBLEM_KEY: Final[str] = "print_error"
FAULTS_KEY: Final[str] = "hms_errors"
PROBLEM_TEXT_ATTRIBUTE: Final[str] = "error"
# the faults, numbered from 1, as `1-Error` and `1-Severity`, and the severities worth telling of
FAULT_TEXT_ATTRIBUTE: Final[str] = "{index}-Error"
FAULT_SEVERITY_ATTRIBUTE: Final[str] = "{index}-Severity"
FAULTS_SERIOUS: Final[tuple[str, ...]] = ("serious", "fatal")
# the layer a 3D printer is on, and of how many
LAYER_KEY: Final[str] = "current_layer"
LAYERS_KEY: Final[str] = "total_layers"
# buttons to pause and carry on, the Live Activity offering whichever there's a use for, but never one to stop, since
# pressed by mistake that loses the cycle
PAUSE_KEY: Final[str] = "pause"
RESUME_KEY: Final[str] = "resume"
# the filament a print takes, in grams and in metres, and how hot the bed is, for it to be taken off once it's cool
WEIGHT_KEY: Final[str] = "print_weight"
LENGTH_KEY: Final[str] = "print_length"
BED_TEMPERATURE_KEY: Final[str] = "bed_temp"
CAMERA_DOMAIN: Final[str] = "camera"
# the same entities as other integrations name them, whichever integration they come from, since it's what an
# entity does that matters, and which entities an appliance has together
ROLE_KEYS: Final[dict[str, str]] = {
    # Bambu Lab 3D printers
    "print_status": CYCLE_KEY,
    "print_progress": PROGRESS_KEY,
    "end_time": FINISH_TIME_KEY,
    # Samsung washers, dryers and dishwashers, through SmartThings
    **{f"{kind}_machine_state": CYCLE_KEY for kind in ("washer", "dryer", "dishwasher")},
    **{f"{kind}_job_state": STAGE_KEY for kind in ("washer", "dryer", "dishwasher")},
    "completion_time": FINISH_TIME_KEY,
    # and through LocalThings, on the local network
    "machine_state": CYCLE_KEY,
    "progress": STAGE_KEY,
    "progress_percentage": PROGRESS_KEY,
    "finish_time": FINISH_TIME_KEY,
}
# beginnings of translation keys of an entity named per model
ROLE_KEY_PREFIXES: Final[dict[str, str]] = {"washer_cycle_table": "selected_program", "dryer_cycle_table": "selected_program"}
# the type of appliance from the beginning of the translation key of any of its entities, for an integration that
# names its entities for the type of appliance
KEY_TYPE_PREFIXES: Final[dict[str, str]] = {"dishwasher_": "dishwasher", "washer_": "washer", "dryer_": "dryer"}
# an oven warming up has no progress of its own, only how hot it is and how hot it's to be
TARGET_TEMPERATURE_KEY: Final[str] = "setpoint_temperature"
CAVITY_TEMPERATURE_KEY: Final[str] = "oven_current_cavity_temperature"
PREHEAT_FINISHED_KEYS: Final[tuple[str, ...]] = ("preheat_finished", "regular_preheat_finished")
FAST_PREHEAT_KEY: Final[str] = "fast_pre_heat"
# domain, by translation key, of each entity of an appliance that's made use of
ENTITY_DOMAINS: Final[dict[str, str]] = {
    PROGRESS_KEY: "sensor",
    STAGE_KEY: "sensor",
    FINISH_TIME_KEY: "sensor",
    REMAINING_KEY: "sensor",
    **dict.fromkeys(SELECTED_PROGRAM_KEYS, "select"),
    TASK_KEY: "sensor",
    TARGET_TEMPERATURE_KEY: "number",
    CAVITY_TEMPERATURE_KEY: "sensor",
    **dict.fromkeys(PREHEAT_FINISHED_KEYS, "sensor"),
    FAST_PREHEAT_KEY: "switch",
    PROBLEM_KEY: "binary_sensor",
    FAULTS_KEY: "binary_sensor",
    LAYER_KEY: "sensor",
    LAYERS_KEY: "sensor",
    PAUSE_KEY: "button",
    RESUME_KEY: "button",
    WEIGHT_KEY: "sensor",
    LENGTH_KEY: "sensor",
    BED_TEMPERATURE_KEY: "sensor",
}
# the type of appliance of a platform that has only the one
PLATFORM_TYPES: Final[dict[str, str]] = {"bambu_lab": "3d_printer"}
# degrees between Live Activity updates of an oven up to heat, whose temperature never stops wandering
TEMPERATURE_STEP: Final[float] = 5
# seconds before an oven saying it's up to heat is believed, since one switched off says so too, just before it's off
PREHEAT_SETTLE: Final[float] = 3
# an event sensor is `off` until whatever it tells of has happened
STATES_EVENT_ON: Final[tuple[str, ...]] = ("present", "confirmed", "on")

# the states of a cycle, with the words different integrations use for the same thing, a 3D printer first heating
# up and levelling its bed as it gets ready to print
STATES_RUN: Final[tuple[str, ...]] = ("run", "active", "prepare", "running")
# a cycle already under way, so not a new start when `run` follows
STATES_ACTIVE: Final[tuple[str, ...]] = (*STATES_RUN, "pause", "actionrequired")
# the cycle is over, an oven switched off goes straight from `run` to `inactive` without ever being `finished`
STATES_FINISHED: Final[tuple[str, ...]] = ("finished", "inactive", "stop", "finish")
# over too unless `run` soon follows, an oven being `ready` for a moment as it starts or has its settings changed,
# and a 3D printer `idle` with no word of how its print ended
STATES_SETTLING: Final[tuple[str, ...]] = ("ready", "idle")
# stages that mean the cycle is over, though the cycle state may stay running a long while after, as a dryer's does
# while it tumbles its load now and then so it won't crease
STAGES_FINISHED: Final[tuple[str, ...]] = ("finished", "finish", "wrinkle_prevent")
# stages that say nothing of what it's doing
STAGES_NONE: Final[tuple[str, ...]] = ("none", "idle")
# paused part way through, with the time left standing still
STATES_PAUSED: Final[tuple[str, ...]] = ("pause",)
# seconds the finish time can drift from the one on the Live Activity before it's brought up to date, since the time
# left may be counted only in whole minutes
FINISH_DRIFT: Final[float] = 120
# seconds an appliance is left to settle before the cycle is over
CYCLE_SETTLE: Final[float] = 10
# seconds after the cycle starts before it's told of, since an integration may report its program and stage a moment
# after the state of its cycle, as LocalThings does
START_SETTLE: Final[float] = 3
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
