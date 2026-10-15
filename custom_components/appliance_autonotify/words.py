"""Words in a name that say what an appliance is, in English and the language of Home Assistant, from the translations"""

from __future__ import annotations

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.translation import async_get_translations

from .const import DOMAIN

# kept in the translations as the options of a selector that's never shown, the one category with free text, so
# whoever translates the integration adds the words for their language, each a comma separated list by type
WORDS_SELECTOR = "appliance_words"
WORDS_PREFIX = f"component.{DOMAIN}.selector.{WORDS_SELECTOR}.options."
DATA_WORDS = f"{DOMAIN}_words"


async def async_load_words(hass: HomeAssistant) -> None:
    words: dict[str, str] = {}
    # English as well, since a plug may well be named in English whatever the language
    for language in dict.fromkeys(("en", hass.config.language)):
        translations = await async_get_translations(hass, language, "selector", [DOMAIN])
        for key, text in translations.items():
            if key.startswith(WORDS_PREFIX):
                kind = key.removeprefix(WORDS_PREFIX)
                words.update({word.strip().lower(): kind for word in text.split(",") if word.strip()})
    # longest first, so a dishwasher isn't taken for a washer, nor a microwave oven for an oven
    hass.data[DATA_WORDS] = dict(sorted(words.items(), key=lambda item: -len(item[0])))


@callback
def name_type(hass: HomeAssistant, name: str) -> str | None:
    """The type of appliance a name says it is, such as `washer` for a washing machine plug, None if it says none"""
    lowered = name.lower()
    return next((kind for word, kind in hass.data.get(DATA_WORDS, {}).items() if word in lowered), None)
