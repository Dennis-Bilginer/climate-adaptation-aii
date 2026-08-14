"""
Grid preprocessing pipeline.

Reads a DMI GeoTIFF raster once, extracts every grid cell as a
polygon + value, and bulk-inserts the results into
climate.observations. After this runs, the application queries
the database instead of opening raster files at request time.
"""

import os

os.environ.pop("PROJ_LIB", None)
os.environ.pop("PROJ_DATA", None)

import numpy as np
import rasterio
import rasterio.warp
from shapely.geometry import box
from shapely.ops import transform as shapely_transform
import pyproj
import psycopg2
from psycopg2.extras import execute_values


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://climate_user:climate_password@localhost:5433/climate_adaptation",
)

TARGET_SRID = 25832  # matches climate.observations.geom in init.sql


def import_raster_to_grid(
    raster_path: str,
    indicator_id: int,
    scenario_code: str,
    period_label: str,
    percentile: int = 50,
    unit: str = "days",
    nodata_override: float | None = None,
    batch_size: int = 5000,
):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Look up foreign keys once
    cur.execute("SELECT id FROM climate.datasets WHERE provider = 'DMI' LIMIT 1;")
    dataset_id = cur.fetchone()[0]

    cur.execute("SELECT id FROM climate.scenarios WHERE code = %s;", (scenario_code,))
    scenario_id = cur.fetchone()[0]

    cur.execute("SELECT id FROM climate.periods WHERE label = %s;", (period_label,))
    period_id = cur.fetchone()[0]

    with rasterio.open(raster_path) as src:
        nodata = nodata_override if nodata_override is not None else src.nodata
        transform = src.transform
        band = src.read(1)

        # Set up a reusable coordinate transformer: raster CRS -> target SRID
        project = pyproj.Transformer.from_crs(
            src.crs, f"EPSG:{TARGET_SRID}", always_xy=True
        ).transform

        rows_to_insert = []
        total_inserted = 0
        height, width = band.shape

        for row in range(height):
            for col in range(width):
                value = band[row, col]

                if nodata is not None and value == nodata:
                    continue
                if np.isnan(value):
                    continue

                # Pixel bounds in raster CRS
                x_min, y_max = transform * (col, row)
                x_max, y_min = transform * (col + 1, row + 1)

                cell_poly = box(x_min, y_min, x_max, y_max)
                cell_poly_transformed = shapely_transform(project, cell_poly)

                grid_cell_id = f"{row}_{col}"

                rows_to_insert.append((
                    dataset_id,
                    indicator_id,
                    scenario_id,
                    period_id,
                    percentile,
                    float(value),
                    unit,
                    grid_cell_id,
                    cell_poly_transformed.wkt,
                ))

                if len(rows_to_insert) >= batch_size:
                    _insert_batch(cur, rows_to_insert)
                    total_inserted += len(rows_to_insert)
                    print(f"  Inserted {total_inserted} cells so far...")
                    rows_to_insert = []

        if rows_to_insert:
            _insert_batch(cur, rows_to_insert)
            total_inserted += len(rows_to_insert)

    conn.commit()
    cur.close()
    conn.close()

    print(f"Done. Inserted {total_inserted} grid cells from {raster_path}")


def _insert_batch(cur, rows):
    execute_values(
        cur,
        """
        INSERT INTO climate.observations (
            dataset_id, indicator_id, scenario_id, period_id,
            percentile, value, unit, grid_cell_id, geom
        )
        VALUES %s
        """,
        rows,
        template="(%s, %s, %s, %s, %s, %s, %s, %s, ST_GeomFromText(%s, {}))".format(
            TARGET_SRID
        ),
    )


if __name__ == "__main__":
    imports = [
        # RCP45
        ("../data/raw/dmi/heatwave_2041_2070_rcp45.tif", 9, "RCP45", "Mid century"),
        ("../data/raw/dmi/heatwave_1981_2010_rcp45.tif", 9, "RCP45", "Reference"),
        ("../data/raw/dmi/meantemp_2041_2070_rcp45.tif", 1, "RCP45", "Mid century"),
        ("../data/raw/dmi/meantemp_1981_2010_rcp45.tif", 1, "RCP45", "Reference"),
        ("../data/raw/dmi/dailymax_2041_2070_rcp45.tif", 2, "RCP45", "Mid century"),
        ("../data/raw/dmi/dailymax_1981_2010_rcp45.tif", 2, "RCP45", "Reference"),
        ("../data/raw/dmi/highesttemp_2041_2070_rcp45.tif", 4, "RCP45", "Mid century"),
        ("../data/raw/dmi/highesttemp_1981_2010_rcp45.tif", 4, "RCP45", "Reference"),
        ("../data/raw/dmi/cloudburst_2041_2070_rcp45.tif", 107, "RCP45", "Mid century"),
        ("../data/raw/dmi/cloudburst_1981_2010_rcp45.tif", 107, "RCP45", "Reference"),

        # RCP26
        ("../data/raw/dmi/heatwave_2041_2070_rcp26.tif", 9, "RCP26", "Mid century"),
        ("../data/raw/dmi/heatwave_1981_2010_rcp26.tif", 9, "RCP26", "Reference"),
        ("../data/raw/dmi/meantemp_2041_2070_rcp26.tif", 1, "RCP26", "Mid century"),
        ("../data/raw/dmi/meantemp_1981_2010_rcp26.tif", 1, "RCP26", "Reference"),
        ("../data/raw/dmi/dailymax_2041_2070_rcp26.tif", 2, "RCP26", "Mid century"),
        ("../data/raw/dmi/dailymax_1981_2010_rcp26.tif", 2, "RCP26", "Reference"),
        ("../data/raw/dmi/highesttemp_2041_2070_rcp26.tif", 4, "RCP26", "Mid century"),
        ("../data/raw/dmi/highesttemp_1981_2010_rcp26.tif", 4, "RCP26", "Reference"),
        ("../data/raw/dmi/cloudburst_2041_2070_rcp26.tif", 107, "RCP26", "Mid century"),
        ("../data/raw/dmi/cloudburst_1981_2010_rcp26.tif", 107, "RCP26", "Reference"),
    ]

    for raster_path, indicator_id, scenario_code, period_label in imports:
        print(f"\nImporting {raster_path} (indicator {indicator_id}, {scenario_code}, {period_label})...")
        import_raster_to_grid(
            raster_path=raster_path,
            indicator_id=indicator_id,
            scenario_code=scenario_code,
            period_label=period_label,
            percentile=50,
            unit="C" if indicator_id in (1, 2, 4) else "days",
        )