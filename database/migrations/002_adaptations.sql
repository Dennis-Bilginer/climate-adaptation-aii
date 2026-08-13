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