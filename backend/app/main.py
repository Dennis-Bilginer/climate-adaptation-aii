from fastapi import FastAPI
from app.risk.periods import year_to_dmi_period, period_label_to_range

app = FastAPI(title="Climate Adaptation AI")


@app.get("/")
def root():
    return {
        "name": "Climate Adaptation AI",
        "status": "running",
        "version": "0.1.0",
    }


@app.post("/api/assessments")
def create_assessment(target_year: int = 2050):
    # 1. Find property
    # 2. Find building
    # 3. Find climate grid
    # 4. Retrieve DMI values
    # 5. Calculate heat exposure
    # 6. Calculate building susceptibility
    # 7. Apply household protections
    # 8. Calculate final risk
    # 9. Find adaptations
    # 10. Rank adaptations
    # -- all still to be wired in; this is a placeholder shape for now

    period = year_to_dmi_period(target_year)
    period_range = period_label_to_range(period)

    return {
        "hazard": "heat",
        "risk_score": 73,
        "risk_category": "high",
        "uncertainty": {
            "low": 64,
            "central": 73,
            "high": 84,
        },
        "target_year": target_year,
        "dmi_period": period,
        "dmi_period_range": period_range,
    }