from app.services.dawa_lookup import resolve_address
from app.models.db import get_connection
from app.services.land_cover import get_heat_modifier
from app.risk.periods import year_to_dmi_period, period_label_to_range
from app.risk.heat import (
    normalize_heatwave_change,
    normalize_temperature_change,
    calculate_climate_exposure,
    calculate_building_susceptibility,
    calculate_protection,
    calculate_heat_risk,
    categorize_risk,
    calculate_heat_index,
    normalize_heat_index_change,
)

from app.services.bbr_lookup import get_bbr_building

from app.risk.flood import (
    normalize_cloudburst_change,
    calculate_flood_exposure,
    calculate_building_flood_susceptibility,
    calculate_flood_protection,
    calculate_flood_risk,
    categorize_risk as categorize_flood_risk,
)
from app.services.land_cover import get_heat_modifier, get_flood_modifier
from app.services.terrain import get_terrain_flood_modifier



def get_address(address_text: str):
    """
    Looks up an address in the local database first (fast path).
    If not found, resolves it live via DAWA and inserts it so future
    lookups for the same address are fast.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, address_text, latitude, longitude
        FROM app.addresses
        WHERE address_text = %s
        """,
        (address_text,),
    )
    row = cur.fetchone()

    if row:
        cur.close()
        conn.close()
        return row

    # Not found locally — resolve via DAWA and insert
    resolved = resolve_address(address_text)
    if resolved is None:
        cur.close()
        conn.close()
        return None

    cur.execute(
        """
        INSERT INTO app.addresses (id, address_text, city, latitude, longitude, geom)
        VALUES (
            gen_random_uuid(), %s, %s, %s, %s,
            ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 4326), 25832)
        )
        RETURNING id, address_text, latitude, longitude
        """,
        (
            resolved["address_text"],
            resolved["raw"]["adgangsadresse"]["kommune"]["navn"],
            resolved["latitude"],
            resolved["longitude"],
            resolved["longitude"],
            resolved["latitude"],
        ),
    )
    new_row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return new_row


def get_indicator_value(address_geom_id, indicator_id: int, scenario_code: str, period_label: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT o.value
        FROM climate.observations o
        JOIN app.addresses a ON ST_Contains(o.geom, a.geom)
        WHERE a.id = %s
          AND o.indicator_id = %s
          AND o.scenario_id = (SELECT id FROM climate.scenarios WHERE code = %s)
          AND o.period_id = (SELECT id FROM climate.periods WHERE label = %s)
          AND o.percentile = 50
        LIMIT 1
        """,
        (address_geom_id, indicator_id, scenario_code, period_label),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row["value"] if row else None


def get_ranked_adaptations(hazard_type: str = "heat"):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            i.slug, i.name, i.description, i.cost_category,
            i.min_cost_dkk, i.max_cost_dkk,
            ih.effectiveness_score, ih.risk_reduction_expected
        FROM adaptation.interventions i
        JOIN adaptation.intervention_hazards ih ON ih.intervention_id = i.id
        WHERE ih.hazard_type = %s AND i.active = TRUE
        ORDER BY ih.risk_reduction_expected DESC
        """,
        (hazard_type,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def run_assessment(
    address_text: str = "Rådhuspladsen 1, København",
    target_year: int = 2050,
    scenario_code: str = "RCP45",
    external_shading: bool = False,
    mechanical_cooling: bool = False,
):
    address = get_address(address_text)
    if address is None:
        return {"error": f"Address '{address_text}' not found in database. "
                          f"Has it been inserted into app.addresses?"}

    bbr_data = get_bbr_building(address_text)
    if "error" in bbr_data:
        building_age = 1990
        floor_count = 2
        building_type = "unknown"
        bbr_note = f"BBR lookup failed ({bbr_data['error']}), using fallback defaults"
    else:
        building_age = bbr_data["building_age"] or 1990
        floor_count = bbr_data["floor_count"] or 2
        building_type = bbr_data["building_type"]
        bbr_note = None

    period_label = year_to_dmi_period(target_year)
    period_range = period_label_to_range(period_label)

    # Indicator 9: Heatwave days
    future_heatwave = get_indicator_value(address["id"], 9, scenario_code, period_label)
    reference_heatwave = get_indicator_value(address["id"], 9, scenario_code, "Reference")

    # Indicator 1: Mean temperature
    future_meantemp = get_indicator_value(address["id"], 1, scenario_code, period_label)
    reference_meantemp = get_indicator_value(address["id"], 1, scenario_code, "Reference")

    # Indicator 2: Daily maximum temperature
    future_dailymax = get_indicator_value(address["id"], 2, scenario_code, period_label)
    reference_dailymax = get_indicator_value(address["id"], 2, scenario_code, "Reference")

    # Indicator 4: Highest temperature
    future_highesttemp = get_indicator_value(address["id"], 4, scenario_code, period_label)
    reference_highesttemp = get_indicator_value(address["id"], 4, scenario_code, "Reference")


    if future_heatwave is None or reference_heatwave is None:
        return {
            "error": "No climate grid data found for this location/scenario/period."
        }

    heatwave_score = normalize_heatwave_change(reference_heatwave, future_heatwave)

    
    # For temperature indicators, use absolute change (future - reference), not percent change
    mean_temp_score = (
        normalize_temperature_change(future_meantemp - reference_meantemp)
        if future_meantemp is not None and reference_meantemp is not None
        else 50
    )
    daily_max_score = (
        normalize_temperature_change(future_dailymax - reference_dailymax)
        if future_dailymax is not None and reference_dailymax is not None
        else 50
    )
    highest_temp_score = (
        normalize_temperature_change(future_highesttemp - reference_highesttemp)
        if future_highesttemp is not None and reference_highesttemp is not None
        else 50
    )

        # "Feels like" temperature using DMI's published average Danish
    # summer relative humidity (75%) as a national baseline assumption
    heat_index_score = 50
    reference_heat_index = None
    future_heat_index = None

    if future_highesttemp is not None and reference_highesttemp is not None:
        reference_heat_index = calculate_heat_index(reference_highesttemp)
        future_heat_index = calculate_heat_index(future_highesttemp)
        heat_index_score = normalize_heat_index_change(reference_heat_index, future_heat_index)

    land_cover = get_heat_modifier(address["longitude"], address["latitude"])

    exposure = calculate_climate_exposure(
        heatwave_score,
        heat_index_score,  # was highest_temp_score - now humidity-adjusted
        daily_max_score,
        mean_temp_score,
        land_cover_adjustment=land_cover["score_adjustment"],
    )

    susceptibility = calculate_building_susceptibility(
        building_age,
        floor_count,
        building_type,
        wall_heat_risk=bbr_data.get("wall_heat_risk", "unknown") if "error" not in bbr_data else "unknown",
        roof_heat_risk=bbr_data.get("roof_heat_risk", "unknown") if "error" not in bbr_data else "unknown",
    )

    protection = calculate_protection(external_shading, mechanical_cooling)

    risk_score = calculate_heat_risk(exposure, susceptibility, protection)
    category = categorize_risk(risk_score)

    adaptations = get_ranked_adaptations("heat")
    # --- FLOOD ---
    future_cloudburst = get_indicator_value(address["id"], 107, scenario_code, period_label)
    reference_cloudburst = get_indicator_value(address["id"], 107, scenario_code, "Reference")

    flood_result = None
    if future_cloudburst is not None and reference_cloudburst is not None:
        cloudburst_score = normalize_cloudburst_change(reference_cloudburst, future_cloudburst)

        flood_land_cover = get_flood_modifier(address["longitude"], address["latitude"])
        terrain_modifier = get_terrain_flood_modifier(address["longitude"], address["latitude"])

        flood_exposure = calculate_flood_exposure(
            cloudburst_score,
            land_cover_adjustment=flood_land_cover["score_adjustment"],
            terrain_adjustment=terrain_modifier["score_adjustment"],
        )

        stormraad_flag = bbr_data.get("stormraad_flood_risk") if "error" not in bbr_data else None

        flood_susceptibility = calculate_building_flood_susceptibility(
            basement=None,
            building_age=building_age,
            stormraad_risk_flag=stormraad_flag,
        )
        flood_protection = calculate_flood_protection(
            has_flood_barriers=False, has_improved_drainage=False
        )

        flood_risk_score = calculate_flood_risk(
            flood_exposure, flood_susceptibility, flood_protection
        )
        flood_category = categorize_flood_risk(flood_risk_score)

        flood_adaptations = get_ranked_adaptations("flood")

        flood_result = {
            "risk_score": round(flood_risk_score, 1),
            "risk_category": flood_category,
            "stormraad_flood_flag": stormraad_flag,
            "local_land_cover": {
                "category": flood_land_cover["dominant_category"],
                "breakdown": flood_land_cover["category_breakdown"],
                "adjustment_applied": flood_land_cover["score_adjustment"],
            },
            "terrain": {
                "bluespot_fill_depth_m": terrain_modifier["bluespot_fill_depth_m"],
                "flow_accumulation_m2": terrain_modifier["flow_accumulation_m2"],
                "adjustment_applied": terrain_modifier["score_adjustment"],
            },
            "cloudburst_days": {
                "reference": reference_cloudburst,
                "future": future_cloudburst,
            },
            "recommended_adaptations": [
                {
                    "name": a["name"],
                    "description": a["description"],
                    "cost_category": a["cost_category"],
                    "cost_range_dkk": f"{a['min_cost_dkk']:.0f}-{a['max_cost_dkk']:.0f}",
                    "expected_risk_reduction": a["risk_reduction_expected"],
                }
                for a in flood_adaptations
            ],
        }

    result = {
        "address": address["address_text"],
        "target_year": target_year,
        "dmi_period": period_label,
        "dmi_period_range": period_range,
        "scenario": scenario_code,
        "building": {
            "age": building_age,
            "floor_count": floor_count,
            "type": building_type,
            "source": "BBR" if bbr_note is None else "fallback default",
        },
        "hazards": {
            "heat": {
                "risk_score": round(risk_score, 1),
                "risk_category": category,
                "local_land_cover": {
                    "category": land_cover["heat_category"],
                    "breakdown": land_cover["category_breakdown"],
                    "adjustment_applied": land_cover["score_adjustment"],
                },
                "climate_indicators": {
                    "heatwave_days": {"reference": reference_heatwave, "future": future_heatwave},
                    "mean_temperature_c": {"reference": reference_meantemp, "future": future_meantemp},
                    "daily_max_temperature_c": {"reference": reference_dailymax, "future": future_dailymax},
                    "highest_temperature_c": {"reference": reference_highesttemp, "future": future_highesttemp},
                    "feels_like_highest_temperature_c": {
                        "reference": reference_heat_index,
                        "future": future_heat_index,
                        "assumed_relative_humidity_pct": 75,
                        "note": "Based on DMI's published average Danish summer humidity, not location-specific",
                    },
                },
                "uncertainty": {
                    "low": round(max(0, risk_score - 9), 1),
                    "central": round(risk_score, 1),
                    "high": round(min(100, risk_score + 11), 1),
                },
                "recommended_adaptations": [
                    {
                        "name": a["name"],
                        "description": a["description"],
                        "cost_category": a["cost_category"],
                        "cost_range_dkk": f"{a['min_cost_dkk']:.0f}-{a['max_cost_dkk']:.0f}",
                        "expected_risk_reduction": a["risk_reduction_expected"],
                    }
                    for a in adaptations
                ],
            },
            "flood": flood_result,
        },
    }

    if bbr_note:
        result["bbr_note"] = bbr_note

    return result