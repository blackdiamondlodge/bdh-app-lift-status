import re

import requests
from bs4 import BeautifulSoup
from html import unescape


# The Sun Peaks lift/trail status page URL
LIFT_STATUS_URL = (
    "https://www.sunpeaksresort.com/ski-ride/"
    "weather-conditions-cams/lifts-trail-status"
)

# Zone keys → display names (order determines tab order)
ZONES = [
    ("mt-morrisey", "Mt. Morrisey"),
    ("sundance", "Sundance"),
    ("tod-mountain", "Tod Mountain"),
    ("orient-ridge", "Orient Ridge"),
]

# Areas Sun Peaks tags separately but which we show as a section of a
# parent zone (West Bowl is reached from Tod Mountain and has its own map).
SUBZONES = [
    ("west-bowl", "West Bowl", "tod-mountain"),
]

# Difficulty slug → display name (ordered easiest → hardest)
DIFFICULTY_ORDER = [
    "1-easiest",
    "2-more-difficult",
    "3-most-difficult",
    "4-experts-only",
    "5-park",
    "5-black-diamond-park",
    "6-glades",
]

DIFFICULTY_LABELS = {
    "1-easiest": "Easiest",
    "2-more-difficult": "More Difficult",
    "2-intermediate": "Intermediate",
    "3-most-difficult": "Most Difficult",
    "3-advanced": "Advanced",
    "4-experts-only": "Experts Only",
    "4-expert": "Expert",
    "5-park": "Terrain Park",
    "5-black-diamond-park": "Terrain Park",
    "6-glades": "Glades",
}

# CSS class → Font Awesome icon class for difficulty indicators
DIFFICULTY_ICONS = {
    "1-easiest": "fa-circle diff-green",
    "2-more-difficult": "fa-square diff-blue",
    "2-intermediate": "fa-square diff-blue",
    "3-most-difficult": "fa-diamond diff-black",
    "3-advanced": "fa-diamond diff-black",
    "4-experts-only": "fa-diamond diff-black diff-double",
    "4-expert": "fa-diamond diff-black diff-double",
    "5-park": "fa-square-full diff-park",
    "5-black-diamond-park": "fa-square-full diff-park",
    "6-glades": "fa-tree diff-glade",
}


def fetch_lift_status_html():
    """Fetch the raw HTML from the Sun Peaks lift/trail status page."""
    response = requests.get(LIFT_STATUS_URL, timeout=15)
    response.raise_for_status()
    return response.content


def parse_lift_status(html):
    """Parse the lift/trail status HTML and return structured data.

    Returns a dict with:
        - lifts: list of lift dicts
        - zones: list of zone dicts (trails grouped by difficulty, plus
          any sub-areas such as West Bowl under ``sections``)
        - summary: open/total counts for lifts and trails, groomed count
        - update: the resort's operations update (or None)
    """
    soup = BeautifulSoup(html, "html.parser")

    lifts = _parse_lifts(soup)
    zones = _parse_trails_by_zone(soup)
    trails = [t for z in zones for t in _zone_trails(z)]

    summary = {
        "lifts_open": sum(1 for l in lifts if l["status"] == "open"),
        "lifts_total": len(lifts),
        "trails_open": sum(1 for t in trails if t["status"] == "open"),
        "trails_total": len(trails),
        "groomed": sum(
            1 for t in trails
            if t["status"] == "open" and t["grooming"] != "none"
        ),
    }

    return {
        "lifts": lifts,
        "zones": zones,
        "summary": summary,
        "update": _parse_operations_update(soup),
    }


def _zone_trails(zone):
    """All trails in a zone, including its sub-area sections."""
    groups = list(zone["trails_by_difficulty"])
    for section in zone.get("sections", []):
        groups.extend(section["trails_by_difficulty"])
    return [t for g in groups for t in g["trails"]]


_UPDATE_DATE_RE = re.compile(r"\(([^)]*\d{4})\)\s*:?\s*")


def _parse_operations_update(soup):
    """Extract the 'Operations Update' block at the top of the page body.

    Sun Peaks posts a dated headline (``<h2>Operations Update (April 6,
    2026): Alpine Area Closed</h2>``) followed by paragraphs, then the
    next ``<h2>`` starts boilerplate about the status table.
    """
    body = soup.find("div", class_="field--name-body")
    if body is None:
        return None
    heading = None
    for h2 in body.find_all("h2"):
        if "update" in h2.get_text(" ", strip=True).lower():
            heading = h2
            break
    if heading is None:
        return None

    title = " ".join(heading.get_text(" ", strip=True).split())
    date = ""
    headline = title
    m = _UPDATE_DATE_RE.search(title)
    if m:
        date = m.group(1).strip()
        headline = title[m.end():].strip(" :-") or title[:m.start()].strip()

    paragraphs = []
    for sib in heading.find_next_siblings():
        if sib.name in ("h1", "h2"):
            break
        text = " ".join(unescape(sib.get_text(" ", strip=True)).split())
        text = re.sub(r"\s+([.,;:!?])", r"\1", text)
        if text:
            paragraphs.append(text)

    return {"date": date, "headline": headline, "paragraphs": paragraphs}


def _lift_kind(name):
    lowered = name.lower()
    if "carpet" in lowered:
        return "Carpet"
    if "platter" in lowered:
        return "Platter"
    if "express" in lowered:
        return "Express chair"
    if "chair" in lowered:
        return "Chairlift"
    return ""


def _parse_lifts(soup):
    """Extract all lift status entries."""
    lifts = []
    for article in soup.find_all("article", class_="node-type-lift"):
        name_span = article.find("span", class_="field--name-title")
        name = unescape(name_span.get_text(strip=True)) if name_span else ""

        # Notes hold one schedule per line, separated by <br>
        notes_span = article.find("span", class_="notes")
        hours = []
        if notes_span:
            hours = [
                " ".join(unescape(line).split())
                for line in notes_span.get_text("\n", strip=True).split("\n")
            ]
            hours = [h for h in hours if h]
        notes = " / ".join(hours)

        # Status: icon-open or icon-close span
        status_cell = article.find("div", class_="row-cell status")
        status = "unknown"
        if status_cell:
            if status_cell.find("span", class_="icon-open"):
                status = "open"
            elif status_cell.find("span", class_="icon-close"):
                status = "closed"

        lifts.append({
            "name": name,
            "short_name": name.replace(" Chairlift", "") or name,
            "kind": _lift_kind(name),
            "status": status,
            "notes": notes,
            "hours": hours,
        })

    return lifts


def _parse_trails_by_zone(soup):
    """Extract trail data grouped by zone, then by difficulty."""
    # Collect all trails first
    area_keys = [key for key, _ in ZONES] + [key for key, _, _ in SUBZONES]
    trails_by_zone = {key: [] for key in area_keys}

    for article in soup.find_all("article", class_="node-type-trail"):
        classes = article.get("class", [])

        name_span = article.find("span", class_="field--name-title")
        name = unescape(name_span.get_text(strip=True)) if name_span else ""

        # Determine zone from cat- classes
        zone = None
        for zone_key in area_keys:
            if f"cat-{zone_key}" in classes:
                zone = zone_key
                break

        if zone is None:
            continue  # skip trails without a known zone

        # Determine difficulty from cat- classes
        difficulty = "unknown"
        for diff_key in DIFFICULTY_ORDER:
            if f"cat-{diff_key}" in classes:
                difficulty = diff_key
                break

        # Grooming status from icon-tick span or cat-groomed class
        grooming = "none"
        status_cell = article.find("div", class_="row-cell status")
        if status_cell:
            tick = status_cell.find("span", class_=lambda c: c and "icon-tick" in c)
            if tick:
                tick_classes = tick.get("class", [])
                if "groomed-with-fresh" in tick_classes:
                    grooming = "groomed-with-fresh"
                elif "groomed" in tick_classes:
                    grooming = "groomed"
        # Fallback: check article-level cat-groomed class
        if grooming == "none" and "cat-groomed" in classes:
            grooming = "groomed"

        # Trail open/closed status
        status = "open"  # default — most trails are open
        if status_cell:
            if status_cell.find("span", class_="icon-close"):
                status = "closed"
            elif status_cell.find("span", class_="icon-open"):
                status = "open"

        trails_by_zone[zone].append({
            "name": name,
            "difficulty": difficulty,
            "difficulty_label": DIFFICULTY_LABELS.get(difficulty, difficulty),
            "difficulty_icon": DIFFICULTY_ICONS.get(difficulty, ""),
            "grooming": grooming,
            "status": status,
        })

    # Build ordered zone list with trails grouped by difficulty
    zones = []
    for zone_key, zone_label in ZONES:
        zone = _build_area(zone_key, zone_label, trails_by_zone[zone_key])
        zone["sections"] = [
            _build_area(key, label, trails_by_zone[key])
            for key, label, parent in SUBZONES
            if parent == zone_key and trails_by_zone[key]
        ]
        # Tab counts cover the zone's own trails plus its sections
        all_trails = _zone_trails(zone)
        zone["trail_count"] = len(all_trails)
        zone["open_count"] = sum(1 for t in all_trails if t["status"] == "open")
        zones.append(zone)

    return zones


def _build_area(key, label, trails):
    """Group an area's trails by difficulty (in DIFFICULTY_ORDER)."""
    trails_by_diff = []
    for diff_key in DIFFICULTY_ORDER:
        diff_trails = [t for t in trails if t["difficulty"] == diff_key]
        if diff_trails:
            trails_by_diff.append({
                "difficulty_key": diff_key,
                "difficulty_label": DIFFICULTY_LABELS.get(diff_key, diff_key),
                "difficulty_icon": DIFFICULTY_ICONS.get(diff_key, ""),
                "open_count": sum(1 for t in diff_trails if t["status"] == "open"),
                "trails": sorted(diff_trails, key=lambda t: t["name"]),
            })
    return {
        "key": key,
        "label": label,
        "trail_count": len(trails),
        "open_count": sum(1 for t in trails if t["status"] == "open"),
        "trails_by_difficulty": trails_by_diff,
    }


def get_lift_status():
    """Fetch and parse lift/trail status, with 5-minute cache.

    The scrape takes a few seconds, so we cache the result to make
    subsequent page loads instant.  The default Django LocMemCache is
    fine because we run a single Daphne process.
    """
    from django.core.cache import cache

    CACHE_KEY = "lift_status_data"
    CACHE_TTL = 5 * 60  # 5 minutes

    data = cache.get(CACHE_KEY)
    if data is None:
        html = fetch_lift_status_html()
        data = parse_lift_status(html)
        cache.set(CACHE_KEY, data, CACHE_TTL)
    return data
