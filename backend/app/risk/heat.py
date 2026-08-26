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