"""Build data/postcode_climate_mapping.csv: the climate zone of every Australian postcode.

One-off data preparation, not part of the app. Each postcode area's centre is looked up in the
Köppen climate classification grid. Load the result into the database with load_postcodes.py.

Inputs (see README.md for where to download them):
    data/POA/POA.shp                           postcode area boundaries (ABS)
    data/koppen_major_AGCDv2_1991-2020.nc      Köppen major climate classes (BoM)

Run (needs the data dependencies: pip install --group data):
    python scripts/build_postcode_climates.py
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import geopandas
import numpy as np
import pandas
import rasterio
import xarray
from rasterio.sample import sample_gen
from rasterio.transform import Affine

BACKEND_DIR = Path(__file__).resolve().parents[1]
POSTCODE_SHAPEFILE = BACKEND_DIR / "data" / "POA" / "POA.shp"
CLIMATE_DATASET = BACKEND_DIR / "data" / "koppen_major_AGCDv2_1991-2020.nc"
OUTPUT_CSV = BACKEND_DIR / "data" / "postcode_climate_mapping.csv"

CLIMATE_CODE_MAP = {
    0: "equatorial",
    1: "tropical",
    2: "subtropical",
    3: "desert",
    4: "grassland",
    5: "temperate",
    6: "cold",
    7: "polar",
}


def create_climate_raster(net_cdf_path: Path, raster_path: Path) -> None:
    """Convert the NetCDF climate grid into a GeoTIFF that rasterio can sample."""
    with xarray.open_dataset(net_cdf_path) as climate_ds:
        climate_var = climate_ds["stern_dehoedt_2000_major"]
        lats = climate_ds.coords["lat"].values
        lons = climate_ds.coords["lon"].values
        data = np.flipud(climate_var.values)

        lon_res = float(lons[1] - lons[0])
        lat_res = float(lats[1] - lats[0])
        transform = Affine(lon_res, 0, lons[0], 0, -lat_res, lats[-1])

        with rasterio.open(
            raster_path,
            "w",
            driver="GTiff",
            height=data.shape[0],
            width=data.shape[1],
            count=1,
            dtype=data.dtype,
            crs="EPSG:4326",
            transform=transform,
        ) as dst:
            dst.write(data, 1)


def map_postcodes_to_climate(postcode_shapefile_path: Path, climate_raster_path: Path) -> pandas.DataFrame:
    """The climate at the centre of each postcode area."""
    postcodes = geopandas.read_file(postcode_shapefile_path).to_crs("EPSG:4326")
    postcode_to_climate = []

    with rasterio.open(climate_raster_path) as src:
        for _, row in postcodes.iterrows():
            postcode = row["poa_code_2"]
            if row.geometry is None or row.geometry.is_empty:
                continue

            centroid = row.geometry.centroid
            sampled_values = list(sample_gen(src, [(centroid.x, centroid.y)]))
            if sampled_values and sampled_values[0] is not None:
                climate_value = sampled_values[0][0]
                if np.isfinite(climate_value):
                    postcode_to_climate.append(
                        {"postcode": postcode, "climate_code": int(climate_value)}
                    )

    postcode_climate_df = pandas.DataFrame(postcode_to_climate)
    postcode_climate_df["climate"] = postcode_climate_df["climate_code"].map(CLIMATE_CODE_MAP)
    return postcode_climate_df


def main() -> None:
    with TemporaryDirectory() as temp_dir:
        raster_path = Path(temp_dir) / "climate_classification.tif"
        create_climate_raster(CLIMATE_DATASET, raster_path)
        postcode_climate_df = map_postcodes_to_climate(POSTCODE_SHAPEFILE, raster_path)
        postcode_climate_df.to_csv(OUTPUT_CSV, index=False)

    print(f"Wrote {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
