import geopandas
import numpy as np
import pandas
import rasterio
from rasterio.sample import sample_gen


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


def map_postcodes_to_climate(
    postcode_shapefile_path: str,
    climate_raster_path: str,
) -> pandas.DataFrame:
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
                    postcode_to_climate.append({
                        "postcode": postcode,
                        "climate_code": int(climate_value),
                    })

    postcode_climate_df = pandas.DataFrame(postcode_to_climate)
    postcode_climate_df["climate"] = postcode_climate_df["climate_code"].map(
        CLIMATE_CODE_MAP
    )
    return postcode_climate_df
