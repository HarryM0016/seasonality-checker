import numpy as np
import rasterio
import xarray
from rasterio.transform import Affine


def create_climate_raster(net_cdf_path: str, raster_path: str) -> None:
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
