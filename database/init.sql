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