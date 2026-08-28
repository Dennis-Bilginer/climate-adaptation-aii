# Climate Adaptation AI — Project Notes for Claude Code

## What this project is

A climate risk assessment API for Danish properties. Given an address,
it returns heat and flood risk scores, real climate projections, and
ranked adaptation recommendations. Architecture follows:
ADDRESS → PROPERTY PROFILE → CLIMATE EXPOSURE → HAZARD ENGINE
↓
┌───────────┼───────────┐
↓           ↓           ↓
HEAT      FLOOD       COAST (not started)
│           │
       └───────────┘
↓
RISK PROFILE
↓
ADAPTATION ENGINE
↓
PORTFOLIO OPTIMIZER (not started)
↓
CLIMATE PLAN (not started)
↓
AI / HUMAN EXPLANATION (not started)


## Stack

- Backend: Python/FastAPI, PostgreSQL+PostGIS (Docker)
- Frontend: not built yet — planning a map with toggleable hazard
  layers (Leaflet), possibly deployed on Vercel
- Data sources: DMI Klimaatlas, BBR (Danish building registry), DAWA
  (Danish address API), Basemap05 (land cover), SDFE DHM (terrain/flood)

## Critical gotchas — read before running anything

- **Run scripts as modules, not files**: `python -m app.services.X`,
  NOT `python app\services\X.py` — the latter breaks `from app...`
  imports. Always run from inside `backend/`.
- **Docker Postgres runs on port 5433**, not 5432 — a local (non-Docker)
  PostgreSQL install on this machine occupies 5432.
- **`.env` needs dotenv loading explicitly** — every service file that
  reads env vars must call `load_dotenv()` at the top, or the var
  silently returns `None` (bit us multiple times with BBR/terrain API
  keys).
- **`.env` required keys**: `DATAFORDELER_API_KEY` (BBR/DAR GraphQL),
  `DATAFORSYNINGEN_TOKEN` (DHM WMS terrain/bluespot), `ANTHROPIC_API_KEY`
  (for future AI explanation layer / extraction scripts).
- **Postgres `NUMERIC` columns return Python `Decimal`**, not `float` —
  cast explicitly with `float(...)` before doing math with plain floats
  (bit us in `heat_index` calculation).

## Data sources and their quirks

### DMI Klimaatlas (climate.observations + climate.municipal_observations)
- `climate.observations`: 1km grid, imported from GeoTIFF rasters via
  `dmi_grid_import.py`. Only contains indicators/scenarios/periods we've
  explicitly imported: indicators 1 (mean temp), 2 (daily max temp), 4
  (highest temp), 9 (heatwave days), 107 (cloudburst days) — each for
  RCP26 and RCP45, Reference and Mid century periods.
- `climate.municipal_observations`: kommune-level, ALL ~50+ indicators,
  all scenarios incl. RCP85, all periods, imported from a bulk Excel
  export (`import_municipal_excel.py`). Includes median/10th/90th
  percentiles. Use this for uncertainty bands and indicators not in the
  1km grid (e.g. precipitation return periods 151-156 hourly, 157-162
  daily).
- Indicators 151-156 = HOURLY return periods (2/5/10/20/50/100yr).
  Indicators 157-162 = DAILY return periods. Bluespot fill depth is
  hourly-based — always compare against 151-156, never 157-162.
- Scenario code for the reference period is `'REFERENCE'`, not
  `'RCP26'`/`'RCP45'` — the reference period is scenario-independent.

### BBR (Danish Building Registry) — `bbr_lookup.py`
- Accessed via Datafordeler GraphQL (`graphql.datafordeler.dk/BBR/v3`).
- Chain: address text → DAWA resolves husnummer ID → BBR_Bygning query
  filtered by `husnummer` field → building record(s).
- One address can return MULTIPLE building records (main building +
  outbuildings) — pick the one with a non-null construction year.
- Confirmed field names (verified against real schema, don't guess):
  `byg026Opfoerelsesaar` (construction year), `byg054AntalEtager`
  (floor count), `byg021BygningensAnvendelse` (use code),
  `byg032YdervaeggensMateriale` (wall material),
  `byg033Tagdaekningsmateriale` (roof material),
  `byg111StormraadetsOversvoemmelsesSelvrisiko` (Stormrådet flood
  deductible flag — note "Selvrisiko" not "risiko").
- Wall material codes confirmed against official kodeliste (1=brick/low
  risk, 4=timber frame, 5=wood, 8=metal/high risk, etc.) Roof material
  codes also confirmed (5=tegl/clay tile=low risk, 1/2=built-up/felt=
  high risk, 7=thatch=low risk).

### DAWA (Danish address API) — `dawa_lookup.py`
- Free, no auth needed. `resolve_address()` returns coords + kommune
  name + full raw response (needed for BBR husnummer ID extraction).
- `adgangsadresse.id` = the husnummer ID BBR needs (not the top-level
  `id`, which is unit/apartment-specific).

### Land cover — `land_cover.py`
- Source: Basemap05 (Aarhus University), `lu_aggregated_2024.tif`,
  14.4GB national raster, extracted locally to
  `C:\Users\Denni\OneDrive\Desktop\Basemap05_extracted\`.
- Uses AREA-AVERAGING (7x7 pixel window = ~70m), not single-pixel
  sampling — address points often sit on roads (DAWA convention), so a
  single pixel biases toward "hot"/paved. Area averaging fixes this.
- Two weight tables: `HEAT_CATEGORY_TO_SCORE_ADJUSTMENT` (green=good)
  and `FLOOD_CATEGORY_TO_SCORE_ADJUSTMENT` (paved=bad, water=bad too).

### Terrain/Bluespot — `terrain.py`
- Source: SDFE DHM WMS (`api.dataforsyningen.dk/wms/dhm`), layers
  `dhm_bluespot_ekstremregn` (fill depth in meters) and
  `dhm_flow_ekstremregn` (catchment area — CURRENTLY ALWAYS RETURNS
  NONE, never got this working, likely sparse/no coverage — don't
  assume it works without re-testing).
- **CRITICAL QUIRK**: `GetFeatureInfo` only returns real data when
  queried with a LARGE bbox (~20km, matching normal map-render scale,
  800x800px) and reading a specific pixel via I/J — NOT a small bbox
  around the point. Tiny bboxes silently return "no results" even
  where real data exists. This took extensive debugging to discover.
- The `STYLES` parameter does NOT change the returned data value for
  bluespot — it only changes map color rendering. The underlying fill
  depth is a single fixed physical property per location, NOT
  scenario-dependent. Don't re-add a `scenario_mm` parameter.
- Per SDFE's own docs: Bluespot assumes ZERO drainage/infiltration —
  it's a conservative worst-case screening tool. Real flood risk at a
  given rainfall amount is likely somewhat lower than Bluespot implies.
- We tried and REMOVED a "flood annual probability" feature that
  compared bluespot depth against return-period curves — it added
  complexity without much practical value (see git history if curious,
  commit "Remove flood annual probability estimate").

### Datafordeler vs Dataforsyningen — TWO SEPARATE PLATFORMS
- `datafordeler.dk` — BBR, DAR GraphQL. Uses `apiKey` param.
- `dataforsyningen.dk` — DHM WMS/WMTS terrain/bluespot. Uses `token`
  param. Separate account/credentials from Datafordeler.

## What's built and working

- Full heat hazard model: DMI indicators, land cover, BBR materials,
  humidity-adjusted heat index (assumes DMI's published 75% avg summer
  humidity — Denmark has no location-specific humidity indicator)
- Full flood hazard model: cloudburst days, land cover, terrain/
  bluespot, Stormrådet official flag
- Dynamic address resolution (any Danish address, resolved via DAWA
  on first lookup, cached in `app.addresses` afterward)
- Adaptation recommendation engine (ranked by expected risk reduction)
- Municipal-level uncertainty bands (median/10th/90th percentile)

## What's NOT built yet

- COAST hazard branch (storm surge — DMI indicators 201-213 and DHM
  WMS layers `dhm_havvandpaaland`/`dhm_rubberbootindex_havvand` already
  identified as viable data sources, not yet integrated)
- Portfolio Optimizer (selecting an optimal adaptation combo given a
  budget constraint — currently just returns ALL adaptations ranked)
- Climate Plan synthesis layer (combining multiple hazards into one
  coherent plan)
- AI / Human Explanation layer (natural-language explanation of
  results via Claude API — a good candidate for actual API usage,
  vs. one-off data extraction scripts)
- Frontend of any kind (currently API-only, tested via /docs Swagger UI)
- Soil permeability data (considered, deprioritized — land cover +
  Bluespot's conservative zero-infiltration assumption already cover
  most of this signal)
- Tree canopy density (Basemap's leaf-type layer only distinguishes
  broadleaf/conifer within existing forest polygons, doesn't add new
  signal beyond what land cover already captures)

## Database schema quick reference

- `app.addresses` — resolved addresses, lat/lon, geom (25832), city
  (kommune name)
- `app.users`, `app.properties`, `app.household_profiles` — scaffolded,
  not actively used yet
- `climate.datasets`, `climate.indicators`, `climate.scenarios`,
  `climate.periods` — reference tables
- `climate.observations` — 1km grid values (see DMI section above)
- `climate.municipal_observations` — kommune-level, all indicators
- `adaptation.interventions`, `adaptation.intervention_hazards` —
  adaptation library, hazard-tagged

## Known dead ends (don't re-attempt without new information)

- `terrain.py`'s `flow_accumulation_m2` — consistently returns None,
  every location tested. Either sparse data or another undiscovered
  API quirk. Not worth re-debugging without a specific reason to.
- CORDEX raw climate model data (Copernicus CDS) — considered for
  humidity data, rejected as too much effort for the value (single
  model run, no bias correction, no ensemble — worse rigor than
  Klimaatlas despite more effort).
  