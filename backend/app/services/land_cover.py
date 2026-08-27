"""
Land cover classification for local heat exposure modifiers.
Based on DCE/Aarhus University's Basemap05 (2024), aggregated
category codes (C_07 field in the raster's value attribute table).

Uses area-averaging (a small window around the point) rather than
a single pixel, since address points often sit on a road (the
building's street access point per DAWA), which would otherwise
bias every result toward "hot" even for houses with green gardens.
"""

import os
import numpy as np
import rasterio
from rasterio.windows import Window
from pyproj import Transformer

RASTER_PATH = os.getenv(
    "BASEMAP_PATH",
    r"C:\Users\Denni\OneDrive\Desktop\Basemap05_extracted\lu_aggregated_2024.tif",
)

# Maps the raster's detailed "Value" codes to a heat category.
# Extend this as more codes are confirmed from the full legend.
HEAT_CATEGORY_BY_VALUE = {
    100000: "unknown",   # Terrestrial (not classified)
    101101: "hot",       # Continuous residential -> Other built up
    101102: "hot",       # Continuous commercial/industrial
    101201: "hot",       # Discontinuous residential
    101202: "hot",       # Discontinuous commercial/industrial
    101301: "hot",       # Road/rail networks
    101303: "hot",       # Airports
    101305: "hot",       # Mineral extraction
    101402: "moderate",  # Sports/recreation
    101502: "moderate",  # Cemeteries
    102100: "moderate",  # Annual cropland
    102300: "moderate",  # Permanent crops
    102402: "moderate",  # Agro-forestry
    102600: "moderate",  # Other farmland
    102601: "moderate",  # Nurseries
    102602: "moderate",  # Christmas tree plantations
    102603: "moderate",  # Perennial bioenergy crops
    103100: "moderate",  # Sown pastures / modified grassland
    103202: "cool",       # Dry grassland (natural)
    103203: "cool",       # Wet grassland (natural)
    104000: "cool",       # Forest undefined
    104100: "cool",       # Broadleaved deciduous forest
    104200: "cool",       # Coniferous forest
    105203: "cool",       # Heathland/shrub
    106101: "moderate",  # Rocky pavements/outcrops
    106203: "moderate",  # Sparsely vegetated
    107000: "cool",       # Inland wetlands
    108000: "coolest",    # Rivers and canals
    109100: "coolest",    # Lakes and ponds
    109201: "hot",        # Artificial reservoirs (classified as "built up" in source)
    110100: "coolest",    # Coastal lagoons
    110301: "coolest",    # Intertidal flats
    111201: "moderate",  # Coastal dunes
    111202: "moderate",  # Beaches
    111300: "moderate",  # Rocky shores
    111401: "cool",       # Coastal saltmarshes
    112501: "coolest",    # Subtidal sand/mud (sea)
    112601: "coolest",    # Subtidal rocky (sea)
}

HEAT_CATEGORY_TO_SCORE_ADJUSTMENT = {
    "hot": 10,
    "moderate": 0,
    "cool": -8,
    "coolest": -12,
    "unknown": 0,
}


def get_land_cover_at_point(longitude: float, latitude: float):
    """
    Single-pixel read (kept for debugging/comparison purposes).
    Prefer get_land_cover_area() for actual risk scoring.
    """
    with rasterio.open(RASTER_PATH) as src:
        transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        x, y = transformer.transform(longitude, latitude)
        row, col = src.index(x, y)

        window = Window(col, row, 1, 1)
        value = src.read(1, window=window)[0, 0]

        if value == src.nodata:
            return None

        return int(value)


def get_land_cover_area(longitude: float, latitude: float, radius_pixels: int = 3):
    """
    Samples a window of pixels around the point (default: 7x7 at
    10m resolution = ~70m across) instead of a single pixel, and
    returns a weighted-average heat adjustment based on the mix of
    land cover found nearby.
    """
    with rasterio.open(RASTER_PATH) as src:
        transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        x, y = transformer.transform(longitude, latitude)
        row, col = src.index(x, y)

        size = radius_pixels * 2 + 1
        window = Window(col - radius_pixels, row - radius_pixels, size, size)

        try:
            block = src.read(1, window=window)
        except Exception:
            # Window falls outside raster bounds (e.g. address near
            # the edge of Denmark's coverage) - fall back to single pixel
            single = get_land_cover_at_point(longitude, latitude)
            if single is None:
                return {
                    "dominant_category": "unknown",
                    "category_breakdown": {},
                    "score_adjustment": 0,
                }
            category = HEAT_CATEGORY_BY_VALUE.get(single, "unknown")
            return {
                "dominant_category": category,
                "category_breakdown": {category: 100.0},
                "score_adjustment": HEAT_CATEGORY_TO_SCORE_ADJUSTMENT.get(category, 0),
            }

        if src.nodata is not None:
            block = block[block != src.nodata]

        if block.size == 0:
            return {
                "dominant_category": "unknown",
                "category_breakdown": {},
                "score_adjustment": 0,
            }

        values, counts = np.unique(block, return_counts=True)
        total = counts.sum()

        category_counts = {}
        for val, count in zip(values, counts):
            category = HEAT_CATEGORY_BY_VALUE.get(int(val), "unknown")
            category_counts[category] = category_counts.get(category, 0) + int(count)

        weighted_adjustment = sum(
            HEAT_CATEGORY_TO_SCORE_ADJUSTMENT.get(cat, 0) * count / total
            for cat, count in category_counts.items()
        )

        dominant_category = max(category_counts, key=category_counts.get)

        return {
            "dominant_category": dominant_category,
            "category_breakdown": {
                k: round(float(v) / float(total) * 100, 1) for k, v in category_counts.items()
            },
            "score_adjustment": round(float(weighted_adjustment), 1),
        }


def get_heat_modifier(longitude: float, latitude: float, radius_pixels: int = 3):
    """
    Main entry point used by assessment.py. Returns the area-averaged
    heat modifier for a given point.
    """
    result = get_land_cover_area(longitude, latitude, radius_pixels=radius_pixels)
    return {
        "heat_category": result["dominant_category"],
        "category_breakdown": result["category_breakdown"],
        "score_adjustment": result["score_adjustment"],
    }


if __name__ == "__main__":
    # Rådhuspladsen 1 - expect mostly "hot" (dense urban center)
    print("Rådhuspladsen 1:", get_heat_modifier(12.56957768, 55.6756275))

    # Dyrehavevej 1 - address point sits on the road, but averaging
    # nearby pixels should now show some "cool" mixed in from the park
    print("Dyrehavevej 1:", get_heat_modifier(12.58742527, 55.77750907))

FLOOD_CATEGORY_TO_SCORE_ADJUSTMENT = {
    "hot": 8,        # paved/built-up -> impervious, poor drainage, higher runoff risk
    "moderate": 0,   # agriculture/mixed -> neutral
    "cool": -6,       # forest/nature -> absorbs water, reduces runoff
    "coolest": 5,     # water bodies -> proximity to water/low-lying areas raises flood risk
    "unknown": 0,
}


def get_flood_modifier(longitude: float, latitude: float, radius_pixels: int = 3):
    """
    Reuses the same land cover data as heat, but with flood-relevant
    weights: paved surfaces worsen pluvial flood risk (poor
    infiltration), while proximity to water bodies also raises risk
    (low-lying, potential for overflow) rather than being purely
    beneficial as it is for heat.
    """
    result = get_land_cover_area(longitude, latitude, radius_pixels=radius_pixels)

    weighted_adjustment = 0
    breakdown = result["category_breakdown"]
    for category, pct in breakdown.items():
        weighted_adjustment += FLOOD_CATEGORY_TO_SCORE_ADJUSTMENT.get(category, 0) * (pct / 100)

    return {
        "dominant_category": result["dominant_category"],
        "category_breakdown": breakdown,
        "score_adjustment": round(weighted_adjustment, 1),
    }