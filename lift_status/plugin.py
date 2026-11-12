from bdh_sdk import PluginSpec, Tile
from bdh_sdk.provides import SEASON, STATS

STAT_KEYS = (
    ("runs_open", "Runs open"),
    ("lifts_open", "Lifts open"),
    ("groomed", "Runs groomed"),
)

spec = PluginSpec(
    id="lift_status",
    app="lift_status",
    urls="lift_status.urls",
    status="lift_status.homepage.status",
    provides={STATS: "lift_status.provides.stats", SEASON: "lift_status.provides.season"},
    stat_keys=STAT_KEYS,
    tiles=(
        Tile(
            title="Lift Status",
            url_name="lift_status",
            icon="lift_status/hub/icon.svg",
            section="mountain",
            subtitle="Which lifts are running",
            order=20,
        ),
    ),
)
