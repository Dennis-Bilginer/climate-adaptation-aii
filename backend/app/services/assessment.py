from app.models.db import get_connection
from app.risk.periods import year_to_dmi_period, period_label_to_range
from app.risk.heat import (
    normalize_heatwave_change,
    calculate_climate_exposure,
    calculate_building_susceptibility,
    calculate_protection,
    calculate_heat_risk,
    categorize_risk,
)
from app.services.bbr_lookup import get_bbr_building


def get_address(address_text: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, address_text, latitude, longitude, geom
        FROM app.addresses
        WHERE address_text = %s
        """,
        (address_text,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def get_heatwave_value(address_geom_id, scenario_code: str, period_label: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT o.value
        FROM climate.observations o
        JOIN app.addresses a ON ST_Contains(o.geom, a.geom)
        WHERE a.id = %s
          AND o.indicator_id = 9
          AND o.scenario_id = (SELECT id FROM climate.scenarios WHERE code = %s)
          AND o.period_id = (SELECT id FROM climate.periods WHERE label = %s)
          AND o.percentile = 50
        LIMIT 1
        """,
        (address_geom_id, scenario_code, period_label),
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

    future_value = get_heatwave_value(address["id"], scenario_code, period_label)
    reference_value = get_heatwave_value(address["id"], scenario_code, "Reference")

    if future_value is None or reference_value is None:
        return {
            "error": "No climate grid data found for this location/scenario/period."
        }

    heatwave_score = normalize_heatwave_change(reference_value, future_value)

    highest_temp_score = 50
    daily_max_score = 50
    mean_temp_score = 50

    exposure = calculate_climate_exposure(
        heatwave_score, highest_temp_score, daily_max_score, mean_temp_score
    )

    susceptibility = calculate_building_susceptibility(
        building_age, floor_count, building_type
    )

    protection = calculate_protection(external_shading, mechanical_cooling)

    risk_score = calculate_heat_risk(exposure, susceptibility, protection)
    category = categorize_risk(risk_score)

    adaptations = get_ranked_adaptations("heat")

    result = {
        "hazard": "heat",
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
        "heatwave_days": {
            "reference": reference_value,
            "future": future_value,
        },
        "risk_score": round(risk_score, 1),
        "risk_category": category,
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
    }

    if bbr_note:
        result["bbr_note"] = bbr_note

    return result