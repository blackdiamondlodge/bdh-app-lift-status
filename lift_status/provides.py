"""Lift and run counts for other parts of the hub, plus a "it's ski season" hint."""
import logging

from bdh_sdk.provides import SeasonHint, Stat

from .scraper import get_lift_status

log = logging.getLogger(__name__)


def _summary():
    try:
        return (get_lift_status() or {}).get("summary") or {}
    except Exception as exc:
        log.debug("no lift status: %s", exc)
        return {}


def build_stats(summary):
    out = []
    if summary.get("trails_total"):
        out.append(Stat("runs_open", "Runs open", value=f"{summary.get('trails_open', 0)} of {summary['trails_total']}",
                        order=50))
    if summary.get("lifts_total"):
        out.append(Stat("lifts_open", "Lifts open", value=f"{summary.get('lifts_open', 0)} of {summary['lifts_total']}",
                        order=51))
    if summary.get("trails_total") and summary.get("groomed") is not None:
        out.append(Stat("groomed", "Runs groomed", value=str(summary["groomed"]), order=52))
    return out


def build_season(summary):
    n = summary.get("lifts_open") if summary.get("lifts_total") else None
    if n:
        return SeasonHint("winter", f"{n} lift{'s' if n != 1 else ''} open")
    return None


def stats():
    return build_stats(_summary())


def season():
    return build_season(_summary())
