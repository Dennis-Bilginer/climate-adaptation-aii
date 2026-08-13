CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS climate;
CREATE SCHEMA IF NOT EXISTS gis;
CREATE SCHEMA IF NOT EXISTS risk;
CREATE SCHEMA IF NOT EXISTS adaptation;

-- Users
CREATE TABLE app.users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Addresses
CREATE TABLE app.addresses (
    id UUID PRIMARY KEY,

    address_text TEXT NOT NULL,

    street_name TEXT,
    house_number TEXT,
    postal_code TEXT,
    city TEXT,
    municipality TEXT,

    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,

    geom GEOMETRY(Point, 25832),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX addresses_geom_idx
ON app.addresses
USING GIST (geom);

-- Properties
CREATE TABLE app.properties (
    id UUID PRIMARY KEY,

    address_id UUID
        REFERENCES app.addresses(id),

    property_identifier TEXT,

    municipality_code TEXT,

    cadastral_reference TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Household information
-- Nullable fields are deliberate: unknown = NULL, not "no".
-- This lets the confidence system distinguish "no shading" from "we don't know".
CREATE TABLE app.household_profiles (
    id UUID PRIMARY KEY,

    user_id UUID
        REFERENCES app.users(id),

    property_id UUID
        REFERENCES app.properties(id),

    mechanical_cooling BOOLEAN,
    external_shading BOOLEAN,
    basement BOOLEAN,
    garden BOOLEAN,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Climate dataset table
CREATE TABLE climate.datasets (
    id UUID PRIMARY KEY,

    provider TEXT NOT NULL,

    dataset_name TEXT NOT NULL,

    dataset_version TEXT,

    source_url TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO climate.datasets (
    id,
    provider,
    dataset_name,
    dataset_version,
    source_url
)
VALUES (
    gen_random_uuid(),
    'DMI',
    'Klimaatlas',
    'v2025a',
    'https://download.dmi.dk/Research_Projects/klimaatlas/latest/'
);

-- Climate indicators
CREATE TABLE climate.indicators (
    id INTEGER PRIMARY KEY,

    name TEXT NOT NULL,

    name_da TEXT,

    unit TEXT,

    hazard_type TEXT,

    description TEXT
);

INSERT INTO climate.indicators
(id, name, name_da, unit, hazard_type)
VALUES
(1, 'Mean temperature', 'Gennemsnitstemperatur', 'C', 'heat'),
(2, 'Daily maximum temperature', 'Daglig maksimumtemperatur', 'C', 'heat'),
(4, 'Highest temperature', 'Hoejeste temperatur', 'C', 'heat'),
(9, 'Heatwave days', 'Varmeboelgedage', 'days', 'heat');

-- Climate scenarios
CREATE TABLE climate.scenarios (
    id SERIAL PRIMARY KEY,

    code TEXT UNIQUE NOT NULL,

    name TEXT NOT NULL,

    description TEXT,

    active BOOLEAN DEFAULT TRUE
);

INSERT INTO climate.scenarios
(code, name, description)
VALUES
(
    'RCP26',
    'Low emissions',
    'DMI Klimaatlas v2025a low emissions scenario'
),
(
    'RCP45',
    'Medium-high emissions',
    'DMI Klimaatlas v2025a medium-high emissions scenario'
),
(
    'RCP85',
    'High emissions',
    'DMI Klimaatlas v2025a high emissions scenario'
);

-- Climate periods
CREATE TABLE climate.periods (
    id SERIAL PRIMARY KEY,

    label TEXT NOT NULL,

    start_year INTEGER NOT NULL,

    end_year INTEGER NOT NULL
);

INSERT INTO climate.periods
(label, start_year, end_year)
VALUES
('Reference', 1981, 2010),
('Early century', 2011, 2040),
('Mid century', 2041, 2070),
('Late century', 2071, 2100);

-- Climate observations
CREATE TABLE climate.observations (
    id BIGSERIAL PRIMARY KEY,

    dataset_id UUID
        REFERENCES climate.datasets(id),

    indicator_id INTEGER
        REFERENCES climate.indicators(id),

    scenario_id INTEGER
        REFERENCES climate.scenarios(id),

    period_id INTEGER
        REFERENCES climate.periods(id),

    percentile INTEGER,

    value NUMERIC NOT NULL,

    unit TEXT,

    grid_cell_id TEXT,

    geom GEOMETRY(Polygon, 25832)
);

CREATE INDEX observations_geom_idx
ON climate.observations
USING GIST (geom);

CREATE INDEX observations_lookup_idx
ON climate.observations (
    indicator_id,
    scenario_id,
    period_id,
    percentile
);

-- Adaptation library
CREATE TABLE adaptation.interventions (
    id UUID PRIMARY KEY,

    slug TEXT UNIQUE NOT NULL,

    name TEXT NOT NULL,

    description TEXT,

    cost_category TEXT NOT NULL,

    min_cost_dkk NUMERIC,

    max_cost_dkk NUMERIC,

    requires_professional BOOLEAN DEFAULT FALSE,

    evidence_quality INTEGER,

    active BOOLEAN DEFAULT TRUE
);

INSERT INTO adaptation.interventions (
    id, slug, name, description, cost_category,
    min_cost_dkk, max_cost_dkk, requires_professional, evidence_quality
)
VALUES
(
    gen_random_uuid(),
    'ventilation-strategy',
    'Improve natural ventilation',
    'Use windows and ventilation strategically to remove heat when outdoor conditions are cooler.',
    'no_cost',
    0,
    0,
    FALSE,
    4
),
(
    gen_random_uuid(),
    'external-shading',
    'External window shading',
    'Reduce solar heat entering the building through windows.',
    'low',
    1000,
    8000,
    FALSE,
    5
),
(
    gen_random_uuid(),
    'green-roof',
    'Green roof',
    'Vegetated roofing can provide multiple environmental benefits, subject to building suitability.',
    'medium',
    15000,
    60000,
    TRUE,
    4
),
(
    gen_random_uuid(),
    'mechanical-cooling',
    'Mechanical cooling',
    'Provide active cooling during periods of excessive indoor heat.',
    'high',
    15000,
    50000,
    TRUE,
    4
);

-- Connect adaptations to hazards
CREATE TABLE adaptation.intervention_hazards (
    intervention_id UUID
        REFERENCES adaptation.interventions(id),

    hazard_type TEXT NOT NULL,

    effectiveness_score INTEGER,

    risk_reduction_min NUMERIC,

    risk_reduction_expected NUMERIC,

    risk_reduction_max NUMERIC,

    PRIMARY KEY (intervention_id, hazard_type)
);

INSERT INTO adaptation.intervention_hazards
SELECT id, 'heat', 3, 3, 5, 7
FROM adaptation.interventions
WHERE slug = 'ventilation-strategy';

INSERT INTO adaptation.intervention_hazards
SELECT id, 'heat', 4, 8, 12, 16
FROM adaptation.interventions
WHERE slug = 'external-shading';

INSERT INTO adaptation.intervention_hazards
SELECT id, 'heat', 3, 3, 6, 9
FROM adaptation.interventions
WHERE slug = 'green-roof';

INSERT INTO adaptation.intervention_hazards
SELECT id, 'heat', 5, 15, 25, 35
FROM adaptation.interventions
WHERE slug = 'mechanical-cooling';