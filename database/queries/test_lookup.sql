SELECT
    value
FROM climate.observations
WHERE indicator_id = 9
  AND scenario_id = (SELECT id FROM climate.scenarios WHERE code = 'RCP45')
  AND period_id = (SELECT id FROM climate.periods WHERE label = 'Mid century')
  AND percentile = 50
  AND ST_Contains(
      geom,
      (SELECT geom FROM app.addresses WHERE address_text = 'Test property, Copenhagen')
  );