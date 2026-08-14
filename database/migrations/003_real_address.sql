DELETE FROM app.addresses WHERE address_text LIKE 'R%dhuspladsen%';

INSERT INTO app.addresses (id, address_text, city, latitude, longitude, geom)
VALUES (
    gen_random_uuid(),
    'Rådhuspladsen 1, København',
    'Copenhagen',
    55.6756275,
    12.56957768,
    ST_Transform(ST_SetSRID(ST_MakePoint(12.56957768, 55.6756275), 4326), 25832)
);