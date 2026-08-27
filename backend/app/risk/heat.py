"""
Heat risk scoring module.

NOTE: All thresholds, weights, and scoring bands in this file are
prototype calibrations for the MVP — not scientifically validated
building physics or DMI's official risk categories. Do not market
these numbers as authoritative.
"""


def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, value))


def normalize_heatwave_change(reference_days, future_days):
    if reference_days <= 0:
        return 50

    increase = ((future_days - reference_days) / reference_days) * 100

    if increase <= 0:
        return 0
    elif increase <= 25:
        return 10
    elif increase <= 50:
        return 20
    elif increase <= 100:
        return 40
    elif increase <= 200:
        return 60
    elif increase <= 400:
        return 80
    else:
        return 100


def normalize_temperature_change(change):
    if change <= 0.5:
        return 10
    elif change <= 1.0:
        return 25
    elif change <= 1.5:
        return 40
    elif change <= 2.0:
        return 60
    elif change <= 2.5:
        return 75
    else:
        return 100

def calculate_heat_index(temperature_c, relative_humidity_pct=75):
    temperature_c = float(temperature_c)
    relative_humidity_pct = float(relative_humidity_pct)

    """
    Computes "feels like" temperature (heat index) from air temperature
    and relative humidity, using the NOAA/Rothfusz regression.

    relative_humidity_pct defaults to 75%, DMI's published average
    Danish summer relative humidity. This is a national assumption,
    not a location-specific value - Denmark's humidity varies far
    less by region than temperature does, so this is a reasonable
    simplification, but it IS an approximation, not measured data.

    Only valid for temperatures above ~27°C (80°F) - DMI's own
    heat index calculator notes it applies for temps over 25°C and
    humidity of at least 40%. Below that threshold, heat index and
    air temperature are essentially the same, so we just return the
    input temperature unchanged.
    """
    if temperature_c < 25 or relative_humidity_pct < 40:
        return temperature_c

    # Rothfusz regression works in Fahrenheit
    t = temperature_c * 9 / 5 + 32
    rh = relative_humidity_pct

    hi_f = (
        -42.379
        + 2.04901523 * t
        + 10.14333127 * rh
        - 0.22475541 * t * rh
        - 0.00683783 * t * t
        - 0.05481717 * rh * rh
        + 0.00122874 * t * t * rh
        + 0.00085282 * t * rh * rh
        - 0.00000199 * t * t * rh * rh
    )

    heat_index_c = (hi_f - 32) * 5 / 9
    return round(heat_index_c, 1)


def normalize_heat_index_change(reference_heat_index, future_heat_index):
    """
    Same scoring shape as normalize_temperature_change, but applied
    to "feels like" temperature instead of raw air temperature.
    """
    return normalize_temperature_change(future_heat_index - reference_heat_index)


def calculate_climate_exposure(
    heatwave_score,
    highest_temp_score,
    daily_max_score,
    mean_temp_score,
    land_cover_adjustment=0,
):
    base_exposure = (
        0.40 * heatwave_score
        + 0.30 * highest_temp_score
        + 0.20 * daily_max_score
        + 0.10 * mean_temp_score
    )

    return max(0, min(100, base_exposure + land_cover_adjustment))


def calculate_building_susceptibility(
    building_age,
    floor_count,
    building_type,
    wall_heat_risk="unknown",
    roof_heat_risk="unknown",
):
    score = 50

    if building_age < 1980:
        score += 15
    elif building_age < 2000:
        score += 5
    else:
        score -= 5

    if floor_count >= 3:
        score += 10

    if building_type == "detached":
        score -= 5

    risk_adjustment = {"low": -5, "medium": 0, "high": 5, "unknown": 0}
    score += risk_adjustment.get(wall_heat_risk, 0)
    score += risk_adjustment.get(roof_heat_risk, 0)

    return max(0, min(100, score))


def calculate_protection(external_shading, mechanical_cooling):
    protection = 0

    if external_shading is True:
        protection += 10

    if mechanical_cooling is True:
        protection += 15

    return min(protection, 25)


def calculate_heat_risk(climate_exposure, building_susceptibility, protection):
    base_risk = (
        0.65 * climate_exposure
        + 0.35 * building_susceptibility
    )

    final_risk = base_risk - protection

    return max(0, min(100, final_risk))


def categorize_risk(score):
    if score < 20:
        return "very_low"
    if score < 40:
        return "low"
    if score < 60:
        return "moderate"
    if score < 80:
        return "high"
    return "very_high"