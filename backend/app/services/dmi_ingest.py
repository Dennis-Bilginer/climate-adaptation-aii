import os
os.environ.pop("PROJ_LIB", None)
os.environ.pop("PROJ_DATA", None)

import rasterio
import rasterio.warp


def get_raster_value(
    raster_path: str,
    longitude: float,
    latitude: float,
):
    with rasterio.open(raster_path) as src:

        # Transform WGS84 coordinates into raster CRS
        x, y = rasterio.warp.transform(
            "EPSG:4326",
            src.crs,
            [longitude],
            [latitude],
        )

        row, col = src.index(x[0], y[0])

        value = src.read(1)[row, col]

        return float(value)


if __name__ == "__main__":
    future = get_raster_value(
        "../data/raw/dmi/heatwave_2041_2070.tif",
        12.5683,
        55.6761,
    )
    reference = get_raster_value(
        "../data/raw/dmi/heatwave_1981_2010.tif",
        12.5683,
        55.6761,
    )
    change = future - reference

    print(f"Reference (1981-2010): {reference:.2f} days")
    print(f"Future (2041-2070):    {future:.2f} days")
    print(f"Change:                 +{change:.2f} days")
    