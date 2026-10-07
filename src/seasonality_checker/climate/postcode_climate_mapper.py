import pandas
import geopandas
import rasterio
import xarray
import numpy as np
from rasterio.transform import Affine
from rasterio.sample import sample_gen

poa = geopandas.read_file('POA/POA.shp')

climate_ds = xarray.open_dataset('koppen_major_AGCDv2_1991-2020.nc')

climate_var = climate_ds['stern_dehoedt_2000_major']

lats = climate_ds.coords['lat'].values
lons = climate_ds.coords['lon'].values

data = np.flipud(climate_var.values)

lon_res = float(lons[1] - lons[0])
lat_res = float(lats[1] - lats[0])
transform = Affine(lon_res, 0, lons[0], 0, -lat_res, lats[-1])

with rasterio.open(
    'climate_classification.tif',
    'w',
    driver='GTiff',
    height=data.shape[0],
    width=data.shape[1],
    count=1,
    dtype=data.dtype,
    crs='EPSG:4326',
    transform=transform,
) as dst:
    dst.write(data, 1)

print("Wrote climate_classification.tif")

poa_latlon = poa.to_crs('EPSG:4326')

with rasterio.open('climate_classification.tif') as src:
    # For each postal area, get its centroid and sample the climate raster
    postcode_to_climate = []
    postcodes_with_null_geometry = []
    
    for idx, row in poa_latlon.iterrows():
        postcode = row['poa_code_2']
        
        # Check if geometry exists and is valid
        if row.geometry is None or row.geometry.is_empty:
            postcodes_with_null_geometry.append({
                'postcode': postcode,
            })
            continue
        
        # Get centroid (lon, lat)
        centroid = row.geometry.centroid
        lon, lat = centroid.x, centroid.y
        
        # Sample the raster at this point
        sampled_values = list(sample_gen(src, [(lon, lat)]))
        if sampled_values and sampled_values[0] is not None:
            climate_value = sampled_values[0][0]
            if np.isfinite(climate_value):
                climate_code = int(climate_value)
                postcode_to_climate.append({
                    'postcode': postcode,
                    'climate_code': climate_code,
                })

    postcode_climate_df = pandas.DataFrame(postcode_to_climate)
    
climate_code_map = {
    0: 'equatorial',
    1: 'tropical',
    2: 'subtropical',
    3: 'desert',
    4: 'grassland',
    5: 'temperate',
    6: 'cold',
    7: 'polar'
}

postcode_climate_df['climate'] = postcode_climate_df['climate_code'].map(climate_code_map)

postcode_climate_df.to_csv('postcode_climate_mapping.csv', index=False)