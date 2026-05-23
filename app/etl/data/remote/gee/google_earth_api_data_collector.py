import ee
import pandas as pd
from app.etl.data.remote.gee.data_processor import DataProcessor


class GoogleEarthAPIDataCollector:
    def __init__(self, projectname):
        ee.Authenticate()
        ee.Initialize(project=projectname)

    def collect(self, start_date, end_date, longitude, latitude, scale):
        dataset = "ECMWF/ERA5_LAND/DAILY_AGGR"
        df = self.__load_data_from_dataset(
            dataset, start_date, end_date, longitude, latitude, scale
        )
        weather_df = self.__process_data(df)
        return weather_df
    
    def collect_area(self, dataset, start_date, end_date, coordinates):
        """Collect data from Earth Engine for a polygon area."""
        
        # Auto-close the ring if needed
        if coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])
        
        polygon = ee.Geometry.Polygon([coordinates])
        
        return self.__load_area_from_dataset(dataset, start_date, end_date, polygon)
    
    def __load_area_from_dataset(self, dataset, start_date, end_date, polygon):
        """Load any Earth Engine dataset for a polygon area."""
        try:
            collection = ee.ImageCollection(dataset).filterDate(start_date, end_date)
            if collection.limit(1).size().getInfo() == 0:
                return pd.DataFrame()
        except ee.EEException as e:
            if "found 'Image'" in str(e):
                collection = ee.ImageCollection([ee.Image(dataset)])
            else:
                raise e

        first_image_bands = ee.Image(collection.first()).bandNames()
        collection = collection.select(first_image_bands)

        data = collection.getRegion(polygon, 1000).getInfo()
        if not data or len(data) < 2:
            return pd.DataFrame()

        df = pd.DataFrame(data[1:], columns=data[0])
        if "time" in df.columns:
            df["date"] = df["time"].apply(
                lambda x: pd.to_datetime(x / 1000, unit="s").date()
            )

        cols = [c for c in df.columns if c not in ["time", "longitude", "latitude"]]
        cols = cols + [c for c in ["time", "longitude", "latitude"] if c in df.columns]
        df = df[cols]

        return df

    def __process_data(self, df):
        calculator_instance = DataProcessor()
        weather_df = pd.DataFrame()
        weather_df["date"] = df["time"].apply(
            lambda x: pd.to_datetime(x / 1000, unit="s")
        )
        weather_df["temperature"] = df["temperature_2m"] - 273.15
        weather_df["soil_temperature"] = df["soil_temperature_level_1"] - 273.15
        weather_df["season"] = weather_df["date"].apply(
            calculator_instance.assign_season
        )
        weather_df["year"] = weather_df["date"].apply(calculator_instance.assign_year)

        # m/s meters per second
        weather_df["wind_speed"] = calculator_instance.calculate_wind_speed(
            df["u_component_of_wind_10m"], df["v_component_of_wind_10m"]
        )

        # Degree In 360
        weather_df["wind_direction"] = calculator_instance.calculate_wind_direction(
            df["u_component_of_wind_10m"], df["v_component_of_wind_10m"]
        )

        # meters (m)
        # 1 m of precipitation = 1000 mm = 1000 liters per square meter.
        weather_df["total_precipitation"] = df["total_precipitation_sum"]

        weather_df["relative_humidity"] = (
            calculator_instance.calculate_relative_humidity(
                df["temperature_2m"], df["dewpoint_temperature_2m"]
            )
        )

        # grams of water vapor per kilogram of moist air (g/kg).
        weather_df["specific_humidity"] = (
            calculator_instance.calculate_specific_humidity(
                df["dewpoint_temperature_2m"], df["surface_pressure"]
            )
        )

        # negative values indicate evaporation and positive values indicate condensation
        # depth of water (in meters) that would result from
        # the evaporation or evapotranspiration processes.
        weather_df["evapotranspiration"] = df["total_evaporation_sum"]
        weather_df["evaporation"] = (
            df["total_evaporation_sum"]
            - df["evaporation_from_vegetation_transpiration_sum"]
        )
        weather_df = weather_df.round(5)
        return weather_df

    def __load_generic_dataset(
        self, dataset, start_date, end_date, longitude, latitude, scale
    ):
        """Load any Earth Engine dataset for a point, returning all bands."""
        point = ee.Geometry.Point([longitude, latitude])

        try:
            collection = ee.ImageCollection(dataset).filterDate(start_date, end_date)
            # Check if collection is empty. This triggers the API call which might fail if dataset is an Image.
            if collection.limit(1).size().getInfo() == 0:
                return pd.DataFrame()
        except ee.EEException as e:
            # Handle case where dataset is a single Image (e.g. OSU/GIMP/2000_IMAGERY_MOSAIC)
            if "found 'Image'" in str(e):
                collection = ee.ImageCollection([ee.Image(dataset)])
            else:
                raise e

        # Handle heterogeneous collections like Sentinel-1 GRD (different polarization modes: HH/HV vs VV/VH)
        if "COPERNICUS/S1" in dataset:
            # For Sentinel-1, use mosaic to merge all images and handle heterogeneous bands
            # This creates a composite of all images, which works even with different polarization modes
            image = collection.mosaic()
            # Convert single image back to collection for getRegion()
            collection = ee.ImageCollection([image])
        else:
            # For other datasets, try standard band homogenization
            try:
                first_image_bands = ee.Image(collection.first()).bandNames()
                collection = collection.select(first_image_bands)
            except ee.EEException:
                # If band selection fails, use the collection as-is
                pass

        data = collection.getRegion(point, scale).getInfo()
        if not data or len(data) < 2:
            return pd.DataFrame()

        df = pd.DataFrame(data[1:], columns=data[0])
        if "time" in df.columns:
            df["date"] = df["time"].apply(lambda x: pd.to_datetime(x / 1000, unit="s").date())

        # Reorder columns to put location and time at the end
        cols = [c for c in df.columns if c not in ["time", "longitude", "latitude"]]
        cols = cols + [c for c in ["time", "longitude", "latitude"] if c in df.columns]
        df = df[cols]

        return df

    def __load_data_from_dataset(
        self, dataset, start_date, end_date, latitude, longitude, scale
    ):
        point = ee.Geometry.Point([longitude, latitude])

        dataset = ee.ImageCollection(dataset).filterDate(start_date, end_date)
        dataset = dataset.select(
            [
                "temperature_2m",
                "soil_temperature_level_1",
                "u_component_of_wind_10m",
                "v_component_of_wind_10m",
                "total_precipitation_sum",
                "dewpoint_temperature_2m",
                "surface_pressure",
                "total_evaporation_sum",
                "evaporation_from_vegetation_transpiration_sum",
            ]
        )
        data = dataset.getRegion(point, scale).getInfo()
        df = pd.DataFrame(data[1:], columns=data[0])

        return df
