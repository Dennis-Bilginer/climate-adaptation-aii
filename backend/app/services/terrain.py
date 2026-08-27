"""
Terrain/hydrology data via SDFE's Danish Elevation Model (DHM) WMS.

Key finding: GetFeatureInfo only returns real data when queried with
a bbox/width/height matching a "normal" map-rendering context (e.g.
matching the tile grid's native resolution). Tiny bounding boxes
(a few meters, for a single-point query) cause the server to return
"no results" even where real data exists - likely due to internal
resampling/simplification at extreme zoom. The workaround is to
always query with a large, fixed bbox size and pixel resolution,
then request the specific pixel of interest via I/J.
"""

import os
import re
import requests
from dotenv import load_dotenv
from pyproj import Transformer

load_dotenv()

DATAFORSYNINGEN_TOKEN = os.getenv("DATAFORSYNINGEN_TOKEN")
WMS_BASE_URL = "https://api.dataforsyningen.dk/wms/dhm"

_transformer = Transformer.from_crs("EPSG:4326", "EPSG:25832", always_xy=True)

# A fixed, large query window - matches the scale at which this
# service's GetFeatureInfo reliably returns real data. 20km box,
# 800x800 pixels => 25m/pixel.
QUERY_BOX_SIZE_M = 20000
QUERY_PIXELS = 800


def _get_feature_info(layer: str, longitude: float, latitude: float, style: str = ""):
    x, y = _transformer.transform(longitude, latitude)

    half = QUERY_BOX_SIZE_M / 2
    bbox = f"{x - half},{y - half},{x + half},{y + half}"

    # The point of interest is always the center pixel of our fixed window
    center_pixel = QUERY_PIXELS // 2

    params = {
        "TOKEN": DATAFORSYNINGEN_TOKEN,
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetFeatureInfo",
        "LAYERS": layer,
        "QUERY_LAYERS": layer,
        "STYLES": style,
        "CRS": "EPSG:25832",
        "BBOX": bbox,
        "WIDTH": QUERY_PIXELS,
        "HEIGHT": QUERY_PIXELS,
        "I": center_pixel,
        "J": center_pixel,
        "INFO_FORMAT": "text/plain",
    }

    response = requests.get(WMS_BASE_URL, params=params)
    response.raise_for_status()

    match = re.search(r"value(?:_0)?\s*=\s*'?([\-0-9.eE+]+)'?", response.text, re.IGNORECASE)
    if match:
        value = float(match.group(1))
        if value < -1e30:
            return None
        return value

    return None


def get_flow_accumulation(longitude: float, latitude: float):
    """Catchment area in m^2 draining to this point during extreme rain."""
    return _get_feature_info("dhm_flow_ekstremregn", longitude, latitude)


def get_bluespot_depth(longitude: float, latitude: float):
    """
    Meters of rain needed before this depression floods. This is a
    fixed physical property of the location - NOT scenario-dependent.
    (Confirmed by testing: identical value_0 returned regardless of
    which scenario style was requested - the style only changes map
    color-coding for visualization, not the underlying data value.)

    IMPORTANT LIMITATION (per SDFE's own documentation): Bluespot does
    NOT account for drainage or infiltration - it assumes a sealed
    depression with no sewer runoff or soil absorption. This makes it
    a conservative/worst-case screening tool. Real-world flooding at
    a given rainfall amount is likely somewhat less severe than this
    threshold suggests, since actual drainage removes some water.

    None means this point isn't in a mapped depression at all.
    """
    return _get_feature_info("dhm_bluespot_ekstremregn", longitude, latitude, style="")

def get_terrain_flood_modifier(longitude: float, latitude: float):
    flow = get_flow_accumulation(longitude, latitude)
    bluespot = get_bluespot_depth(longitude, latitude)
    # ... rest stays the same

    adjustment = 0.0

    if flow is not None:
        if flow > 100000:
            adjustment += 10
        elif flow > 10000:
            adjustment += 5
        elif flow > 1000:
            adjustment += 2

    if bluespot is not None:
        # bluespot value is in meters of rain needed to flood
        if bluespot < 0.03:
            adjustment += 10
        elif bluespot < 0.06:
            adjustment += 6
        elif bluespot < 0.10:
            adjustment += 3
        else:
            adjustment += 1

    return {
        "flow_accumulation_m2": flow,
        "bluespot_fill_depth_m": bluespot,
        "score_adjustment": round(adjustment, 1),
    }


if __name__ == "__main__":
    print("Known-blue test point:", get_terrain_flood_modifier(*_transformer.transform(715000.0, 6182500.0, direction="INVERSE")))
    print("Rådhuspladsen 1:", get_terrain_flood_modifier(12.56957768, 55.6756275))