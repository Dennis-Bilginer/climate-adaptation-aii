from fastapi import FastAPI
from app.services.assessment import run_assessment

app = FastAPI(title="Climate Adaptation AI")


@app.get("/")
def root():
    return {
        "name": "Climate Adaptation AI",
        "status": "running",
        "version": "0.1.0",
    }


@app.post("/api/assessments")
def create_assessment(
    address_text: str = "Rådhuspladsen 1, København",
    target_year: int = 2050,
    scenario_code: str = "RCP45",
    external_shading: bool = False,
    mechanical_cooling: bool = False,
):
    return run_assessment(
        address_text=address_text,
        target_year=target_year,
        scenario_code=scenario_code,
        external_shading=external_shading,
        mechanical_cooling=mechanical_cooling,
    )