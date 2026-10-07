from pathlib import Path
from tempfile import TemporaryDirectory

from src.seasonality_checker.climate.climate_raster import create_climate_raster
from src.seasonality_checker.climate.postcode_climate_mapper import (
    map_postcodes_to_climate,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POSTCODE_SHAPEFILE = PROJECT_ROOT / "data" / "POA" / "POA.shp"
CLIMATE_DATASET = PROJECT_ROOT / "data" / "koppen_major_AGCDv2_1991-2020.nc"
OUTPUT_CSV = PROJECT_ROOT / "postcode_climate_mapping.csv"


def main() -> None:
    with TemporaryDirectory() as temp_dir:
        raster_path = Path(temp_dir) / "climate_classification.tif"
        create_climate_raster(str(CLIMATE_DATASET), str(raster_path))
        postcode_climate_df = map_postcodes_to_climate(
            str(POSTCODE_SHAPEFILE),
            str(raster_path),
        )
        postcode_climate_df.to_csv(OUTPUT_CSV, index=False)

    print(f"Wrote {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
