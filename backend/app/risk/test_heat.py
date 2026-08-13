import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from services.dmi_ingest import get_raster_value
from risk.heat import (
    normalize_heatwave_change,
    calculate_climate_exposure,
    calculate_building_susceptibility,
    calculate_protection,
    calculate_heat_risk,
    categorize_risk,
)

longitude = 12.5683
latitude = 55.6761

reference = get_raster_value(
    "../data/raw/dmi/heatwave_1981_2010_rcp45.tif", longitude, latitude
)
future = get_raster_value(
    "../data/raw/dmi/heatwave_2041_2070_rcp45.tif", longitude, latitude
)

heatwave_score = normalize_heatwave_change(reference, future)

# Placeholder scores for the other three indicators until those rasters are wired in
highest_temp_score = 50
daily_max_score = 50
mean_temp_score = 50

exposure = calculate_climate_exposure(
    heatwave_score, highest_temp_score, daily_max_score, mean_temp_score
)

susceptibility = calculate_building_susceptibility(
    building_age=1975, floor_count=2, building_type="detached"
)

protection = calculate_protection(
    external_shading=False, mechanical_cooling=False
)

risk_score = calculate_heat_risk(exposure, susceptibility, protection)
category = categorize_risk(risk_score)

print(f"Heatwave days: {reference:.1f} -> {future:.1f}")
print(f"Heatwave score: {heatwave_score}")
print(f"Climate exposure: {exposure:.1f}")
print(f"Building susceptibility: {susceptibility}")
print(f"Protection: {protection}")
print(f"Final risk score: {risk_score:.1f}")
print(f"Category: {category}")