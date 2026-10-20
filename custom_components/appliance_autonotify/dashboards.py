"""The dashboards a notification can open when tapped, chosen from those there are so never a URL of anyone's making"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .const import DEFAULT_DASHBOARD, DEFAULT_DASHBOARD_TITLE, LOVELACE_DOMAIN
from .words import name_type

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def dashboards(hass: HomeAssistant) -> dict[str, str]:
    """The title of each dashboard, by the path it's found at"""
    found: dict[str, str] = {}
    for url_path, dashboard in getattr(hass.data.get(LOVELACE_DOMAIN), "dashboards", {}).items():
        if url_path is None:
            found[DEFAULT_DASHBOARD] = DEFAULT_DASHBOARD_TITLE
        else:
            found[url_path] = (getattr(dashboard, "config", None) or {}).get("title") or url_path
    # those that would look the same in a list are told apart by their paths
    titles = [title.lower() for title in found.values()]
    found = {path: f"{title} ({path})" if titles.count(title.lower()) > 1 else title for path, title in found.items()}
    return dict(sorted(found.items(), key=lambda item: item[1].lower()))


def _plain(text: str) -> str:
    """Letters and digits alone, so "Dish Washer", "dishwasher" and the path `dashboard-dish-washer` are alike"""
    return re.sub(r"[^0-9a-z]", "", text.lower().removeprefix("dashboard-"))


def matching_dashboard(hass: HomeAssistant, name: str, kind: str | None) -> str | None:
    """The one dashboard named for the appliance, or failing that the one named for its type, such as "Washing
    Machine" for a washer, by its title or its path, and None where there's none or no telling which"""
    found = {path: title for path, title in dashboards(hass).items() if path != DEFAULT_DASHBOARD}
    tiers = [
        [path for path, title in found.items() if _plain(name) in (_plain(title), _plain(path))],
        [
            path
            for path, title in found.items()
            if kind is not None and kind in (name_type(hass, title), name_type(hass, path.replace("-", " ")))
        ],
    ]
    return next((matches[0] for matches in tiers if len(matches) == 1), None)


def dashboard_url(hass: HomeAssistant, path: str | None) -> str | None:
    """Where to send a tap, only ever to a dashboard that exists"""
    return f"/{path}" if path and path in dashboards(hass) else None
