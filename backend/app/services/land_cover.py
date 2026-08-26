"""
Land cover classification for local heat exposure modifiers.
Based on DCE/Aarhus University's Basemap05 (2024), aggregated
category codes (C_07 field in the raster's value attribute table).
"""

import os
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
    Efficiently reads a single pixel from the (very large) land cover
    raster using a windowed read, so the entire multi-GB file is never
    loaded into memory.
    """
    with rasterio.open(RASTER_PATH) as src:
        transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        x, y = transformer.transform(longitude, latitude)

        row, col = src.index(x, y)

        window = Window(col, row, 1, 1)
        value = src.read(1, window=window)[0, 0]

        # Handle nodata
        if value == src.nodata:
            return None

        return int(value)


def get_heat_modifier(longitude: float, latitude: float):
    value = get_land_cover_at_point(longitude, latitude)
    if value is None:
        return {"land_cover_value": None, "heat_category": "unknown", "score_adjustment": 0}

    category = HEAT_CATEGORY_BY_VALUE.get(value, "unknown")
    adjustment = HEAT_CATEGORY_TO_SCORE_ADJUSTMENT.get(category, 0)

    return {
        "land_cover_value": value,
        "heat_category": category,
        "score_adjustment": adjustment,
    }


if __name__ == "__main__":
    # Rådhuspladsen 1 - expect "hot" (dense urban center)
    result = get_heat_modifier(12.56957768, 55.6756275)
    print("Rådhuspladsen 1:", result)