"""
Enhanced Metadata Provider with ALL datasets and comprehensive attribute support
Order: {location|start_date|end_date|longitude|latitude|scale|dataset}
"""

from typing import List, Dict, Optional, Set, Tuple
import re
import pandas as pd
from pathlib import Path


class MetadataProvider:
    """Provides metadata for autocomplete - COMPREHENSIVE with ALL attributes"""
    
    # Public GEE project examples (NO private info)
    COMMON_LOCATIONS = [
        "my-project",
        "ee-username",
        "your-project",
        "gee-project",
    ]
    
    # ALL Known GEE Datasets with full paths
    KNOWN_DATASETS = {
        # Climate & Weather - ERA5
        "ERA5": "ECMWF/ERA5/DAILY",
        "ERA5_LAND": "ECMWF/ERA5_LAND/DAILY_AGGR",
        "ERA5_MONTHLY": "ECMWF/ERA5/MONTHLY",
        "ERA5_HOURLY": "ECMWF/ERA5/HOURLY",
        
        # Sentinel-2
        "SENTINEL2": "COPERNICUS/S2_SR",
        "S2": "COPERNICUS/S2_SR",
        "S2_SR": "COPERNICUS/S2_SR",
        "COPERNICUS/S2_SR": "COPERNICUS/S2_SR",
        "S2_HARMONIZED": "COPERNICUS/S2_SR_HARMONIZED",
        "S2_TOA": "COPERNICUS/S2",
        
        # Sentinel-1
        "SENTINEL1": "COPERNICUS/S1_GRD",
        "S1": "COPERNICUS/S1_GRD",
        "S1_GRD": "COPERNICUS/S1_GRD",
        
        # Landsat
        "LANDSAT": "LANDSAT/LC08/C02/T1_L2",
        "LANDSAT8": "LANDSAT/LC08/C02/T1_L2",
        "LANDSAT9": "LANDSAT/LC09/C02/T1_L2",
        "LANDSAT7": "LANDSAT/LE07/C02/T1_L2",
        "LANDSAT5": "LANDSAT/LT05/C02/T1_L2",
        "LC08": "LANDSAT/LC08/C02/T1_L2",
        "LC09": "LANDSAT/LC09/C02/T1_L2",
        
        # MODIS - Vegetation
        "MODIS": "MODIS/006/MOD13A1",
        "MODIS_VEGETATION": "MODIS/006/MOD13A1",
        "MOD13A1": "MODIS/006/MOD13A1",
        "MOD13Q1": "MODIS/006/MOD13Q1",
        "MYD13A1": "MODIS/006/MYD13A1",
        
        # MODIS - Land Surface Temperature
        "MODIS_LST": "MODIS/006/MOD11A1",
        "MOD11A1": "MODIS/006/MOD11A1",
        "MOD11A2": "MODIS/006/MOD11A2",
        "MYD11A1": "MODIS/006/MYD11A1",
        
        # MODIS - NDVI
        "MODIS_NDVI": "MODIS/006/MOD13A1",
        
        # MODIS - Other
        "MODIS_BRDF": "MODIS/006/MCD43A4",
        "MODIS_SNOW": "MODIS/006/MOD10A1",
        
        # CHIRPS - Precipitation
        "CHIRPS": "UCSB-CHG/CHIRPS/DAILY",
        "CHIRPS_DAILY": "UCSB-CHG/CHIRPS/DAILY",
        "CHIRPS_PENTAD": "UCSB-CHG/CHIRPS/PENTAD",
        
        # SRTM - Elevation
        "SRTM": "USGS/SRTMGL1_003",
        "SRTM_90": "CGIAR/SRTM90_V4",
        "DEM": "USGS/SRTMGL1_003",
        
        # Global Land Cover
        "ESA_LANDCOVER": "ESA/WorldCover/v100",
        "WORLDCOVER": "ESA/WorldCover/v100",
        "COPERNICUS_LANDCOVER": "COPERNICUS/Landcover/100m/Proba-V-C3/Global",
        
        # NASA Datasets
        "GPM": "NASA/GPM_L3/IMERG_V06",
        "GRACE": "NASA/GRACE/MASS_GRIDS/LAND",
        "GLDAS": "NASA/GLDAS/V021/NOAH/G025/T3H",
        
        # Others
        "DYNAMIC_WORLD": "GOOGLE/DYNAMICWORLD/V1",
        "POPULATION": "CIESIN/GPWv411/GPW_Population_Count",
        "NIGHTLIGHTS": "NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG",
    }
    
    # Comprehensive dataset attributes - ALL POSSIBLE ATTRIBUTES
    DATASET_ATTRIBUTES = {
        "ERA5": [
            # Temperature
            "temperature_2m", "temperature_2m_max", "temperature_2m_min",
            "dewpoint_temperature_2m", "skin_temperature",
            # Precipitation
            "total_precipitation", "convective_precipitation",
            # Pressure
            "surface_pressure", "mean_sea_level_pressure",
            # Wind
            "u_component_of_wind_10m", "v_component_of_wind_10m",
            "wind_speed_10m", "wind_direction_10m",
            "u_component_of_wind_100m", "v_component_of_wind_100m",
            # Clouds
            "total_cloud_cover", "low_cloud_cover", "medium_cloud_cover", "high_cloud_cover",
            # Radiation
            "surface_solar_radiation_downwards", "surface_thermal_radiation_downwards",
            "surface_net_solar_radiation", "surface_net_thermal_radiation",
            # Other
            "total_column_water_vapour", "boundary_layer_height",
        ],
        
        "ERA5_LAND": [
            # Temperature
            "temperature_2m", "dewpoint_temperature_2m", "skin_temperature",
            "soil_temperature_level_1", "soil_temperature_level_2",
            "soil_temperature_level_3", "soil_temperature_level_4",
            # Precipitation
            "total_precipitation", "snow_depth", "snowfall",
            # Pressure
            "surface_pressure",
            # Wind
            "u_component_of_wind_10m", "v_component_of_wind_10m",
            "wind_speed", "wind_direction",
            # Radiation
            "surface_solar_radiation_downwards", "surface_solar_radiation_downward_clear_sky",
            "surface_thermal_radiation_downwards", "surface_net_solar_radiation",
            "surface_net_thermal_radiation",
            # Evapotranspiration
            "evaporation", "potential_evapotranspiration",
            "evaporation_from_bare_soil", "evaporation_from_vegetation_transpiration",
            "evaporation_from_open_water_surfaces_and_sea_ice",
            # Soil moisture
            "volumetric_soil_water_layer_1", "volumetric_soil_water_layer_2",
            "volumetric_soil_water_layer_3", "volumetric_soil_water_layer_4",
            # Runoff
            "surface_runoff", "subsurface_runoff",
            # Lakes
            "lake_cover", "lake_depth", "lake_ice_depth", "lake_ice_temperature",
        ],
        
        "SENTINEL2": [
            # All Sentinel-2 bands
            "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A",
            "B9", "B11", "B12",
            # Quality
            "QA60", "MSK_CLDPRB", "MSK_SNWPRB",
            # Derived indices
            "NDVI", "NDWI", "NDMI", "EVI", "SAVI", "NBR",
            # Metadata
            "solar_azimuth", "solar_zenith", "view_azimuth", "view_zenith",
        ],
        
        "SENTINEL1": [
            # SAR bands
            "VV", "VH", "HV", "HH",
            # Angles
            "angle", "incidence_angle",
        ],
        
        "LANDSAT": [
            # Landsat 8/9 Surface Reflectance bands
            "SR_B1", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7",
            # Thermal
            "ST_B10",
            # Quality
            "QA_PIXEL", "QA_RADSAT",
            # Derived indices
            "NDVI", "NDWI", "EVI", "SAVI", "NBR",
            # Angles
            "solar_azimuth", "solar_zenith", "view_azimuth", "view_zenith",
        ],
        
        "MODIS": [
            # MODIS Vegetation Indices
            "NDVI", "EVI", "EVI2",
            # Surface reflectance
            "sur_refl_b01", "sur_refl_b02", "sur_refl_b03", "sur_refl_b04",
            "sur_refl_b05", "sur_refl_b06", "sur_refl_b07",
            # Quality
            "DetailedQA", "SummaryQA",
            # Angles
            "ViewZenith", "SolarZenith", "RelativeAzimuth",
        ],
        
        "MODIS_LST": [
            # Land Surface Temperature
            "LST_Day_1km", "LST_Night_1km",
            # Quality
            "QC_Day", "QC_Night",
            # Emissivity
            "Emis_31", "Emis_32",
            # View time and angles
            "Day_view_time", "Night_view_time", "Day_view_angl", "Night_view_angl",
        ],
        
        "CHIRPS": [
            # Precipitation
            "precipitation",
        ],
        
        "SRTM": [
            # Elevation
            "elevation",
        ],
        
        "GPM": [
            # Precipitation
            "precipitationCal", "randomError", "HQprecipitation",
            "precipitationQualityIndex", "probabilityLiquidPrecipitation",
        ],
        
        "GLDAS": [
            # Temperature
            "Tair_f_inst", "AvgSurfT_inst",
            # Precipitation
            "Rainf_f_tavg", "Snowf_tavg",
            # Humidity
            "Qair_f_inst", "RH_inst",
            # Wind
            "Wind_f_inst",
            # Pressure
            "Psurf_f_inst",
            # Radiation
            "SWdown_f_tavg", "LWdown_f_tavg",
            # Evapotranspiration
            "Evap_tavg", "PotEvap_tavg",
            # Soil
            "SoilMoi0_10cm_inst", "SoilMoi10_40cm_inst", "SoilMoi40_100cm_inst",
            "SoilTMP0_10cm_inst", "SoilTMP10_40cm_inst",
            # Runoff
            "Qs_acc", "Qsb_acc",
        ],
    }
    
    def __init__(self):
        """Initialize metadata provider"""
        self.datasource_cache: Dict[str, List[str]] = {}
        self.table_aliases: Dict[str, str] = {}
        self.available_datasources: Set[str] = set()
        
        # Register known datasets with their attributes
        for dataset_name, attributes in self.DATASET_ATTRIBUTES.items():
            if dataset_name in self.KNOWN_DATASETS:
                full_path = self.KNOWN_DATASETS[dataset_name]
                self.register_datasource(full_path, attributes)
    
    def register_datasource(self, datasource: str, columns: List[str]):
        """Register a datasource with its columns"""
        self.datasource_cache[datasource] = columns
        self.available_datasources.add(datasource)
        print(f"[METADATA] Registered {datasource} with {len(columns)} columns")
    
    def load_datasource_from_file(self, datasource: str) -> Optional[List[str]]:
        """Load column information from a file datasource"""
        if datasource in self.datasource_cache:
            return self.datasource_cache[datasource]
        
        try:
            if ':' not in datasource:
                return None
            
            file_type, file_path = datasource.split(':', 1)
            file_type = file_type.lower()
            
            columns = None
            
            if file_type == 'csv':
                df = pd.read_csv(file_path, nrows=0)
                columns = df.columns.tolist()
            
            elif file_type == 'json':
                df = pd.read_json(file_path, nrows=0)
                columns = df.columns.tolist()
            
            elif file_type == 'excel':
                df = pd.read_excel(file_path, nrows=0)
                columns = df.columns.tolist()
            
            elif file_type == 'sqlite':
                parts = file_path.split(':')
                if len(parts) == 2:
                    db_path, table_name = parts
                    import sqlite3
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = [row[1] for row in cursor.fetchall()]
                    conn.close()
            
            if columns:
                self.register_datasource(datasource, columns)
                return columns
        
        except Exception as e:
            print(f"[ERROR] Loading datasource {datasource}: {e}")
            return None
        
        return None
    
    def get_datasource_context(self, query_text: str) -> Tuple[str, int]:
        """
        Determine what part of the datasource string we're in
        ORDER: {location|start_date|end_date|longitude|latitude|scale|dataset}
        """
        pattern = r'\{([^}]*?)$'
        match = re.search(pattern, query_text)
        
        if not match:
            return ('none', 0)
        
        content = match.group(1)
        parts = content.split('|')
        position = len(parts)
        
        context_map = {
            1: 'location',      # {project-name
            2: 'start_date',    # {project-name|start
            3: 'end_date',      # {project-name|start|end
            4: 'longitude',     # {project-name|start|end|lon
            5: 'latitude',      # {project-name|start|end|lon|lat
            6: 'scale',         # {project-name|start|end|lon|lat|scale
            7: 'dataset'        # {project-name|start|end|lon|lat|scale|DATASET
        }
        
        return (context_map.get(position, 'none'), position)
    
    def get_columns(self, query_text: str) -> List[str]:
        """Get available columns based on current query context"""
        print(f"[METADATA] get_columns() called")
        
        columns = []
        
        self._parse_query_for_tables(query_text)
        
        print(f"[METADATA] Found {len(self.table_aliases)} table aliases")
        
        if not self.table_aliases:
            print("[METADATA] No table aliases - returning ALL columns")
            for datasource, cols in self.datasource_cache.items():
                columns.extend(cols)
        else:
            for alias, datasource in self.table_aliases.items():
                print(f"[METADATA] Alias '{alias}' -> '{datasource}'")
                if datasource in self.datasource_cache:
                    columns.extend(self.datasource_cache[datasource])
                else:
                    loaded_columns = self.load_datasource_from_file(datasource)
                    if loaded_columns:
                        columns.extend(loaded_columns)
        
        unique_columns = list(set(columns))
        print(f"[METADATA] Returning {len(unique_columns)} unique columns")
        return unique_columns
    
    def get_qualified_columns(self, query_text: str) -> List[str]:
        """Get qualified column names (table.column) for JOIN conditions"""
        self._parse_query_for_tables(query_text)
        
        qualified_columns = []
        
        for alias, datasource in self.table_aliases.items():
            if datasource in self.datasource_cache:
                columns = self.datasource_cache[datasource]
            else:
                columns = self.load_datasource_from_file(datasource) or []
            
            for col in columns:
                qualified_columns.append(f"{alias}.{col}")
        
        return qualified_columns
    
    def get_columns_for_table(self, table_alias: str) -> List[str]:
        """Get columns for a specific table alias"""
        if table_alias not in self.table_aliases:
            return []
        
        datasource = self.table_aliases[table_alias]
        
        if datasource in self.datasource_cache:
            return self.datasource_cache[datasource]
        
        return self.load_datasource_from_file(datasource) or []
    
    def get_datasources(self) -> List[str]:
        """Get list of available datasources"""
        all_datasources = list(self.available_datasources)
        
        for dataset_name in self.KNOWN_DATASETS.keys():
            all_datasources.append(dataset_name)
        
        return list(set(all_datasources))
    
    def get_locations(self) -> List[str]:
        """Get list of common project locations (public examples only)"""
        return self.COMMON_LOCATIONS.copy()
    
    def get_dataset_names(self) -> List[str]:
        """Get list of ALL known dataset names"""
        return list(self.KNOWN_DATASETS.keys())
    
    def add_datasource_suggestion(self, datasource: str):
        """Add a datasource to suggestions without loading columns"""
        self.available_datasources.add(datasource)
    
    def add_location(self, location: str):
        """Add a new location/project name to suggestions"""
        # Only add if not private-looking
        if location and location not in self.COMMON_LOCATIONS:
            if not any(private in location.lower() for private in ['private', 'personal', 'mennawali']):
                self.COMMON_LOCATIONS.append(location)
                self.available_datasources.add(location)
    
    def _parse_query_for_tables(self, query_text: str):
        """
        Parse query to extract table references and aliases
        FORMAT: {location|start|end|lon|lat|scale|dataset}
        """
        self.table_aliases.clear()
        
        pattern = r'\{([^}]+)\}\s*([A-Za-z_]\w*)?'
        
        matches = re.finditer(pattern, query_text, re.IGNORECASE)
        
        for match in matches:
            full_datasource = match.group(1)
            alias = match.group(2)
            
            datasource_parts = full_datasource.split('|')
            
            if len(datasource_parts) >= 7:
                # ORDER: location|start|end|lon|lat|scale|dataset
                location = datasource_parts[0].strip()
                dataset_name = datasource_parts[6].strip()  # Dataset at position 6
                
                if ':' in location:
                    datasource = f"{location.split(':')[0]}:{dataset_name}"
                else:
                    datasource = f"gee:{dataset_name}"
            elif len(datasource_parts) > 1:
                # Partial datasource
                location = datasource_parts[0].strip()
                if len(datasource_parts) > 6:
                    dataset_name = datasource_parts[6].strip()
                else:
                    dataset_name = ""
                
                if dataset_name and ':' in location:
                    datasource = f"{location.split(':')[0]}:{dataset_name}"
                elif dataset_name:
                    datasource = f"gee:{dataset_name}"
                else:
                    datasource = location
            else:
                datasource = full_datasource
            
            if alias:
                self.table_aliases[alias] = datasource
                print(f"[METADATA] Found alias: {alias} -> {datasource}")
            else:
                alias_name = datasource.split(':')[-1].split('/')[-1]
                self.table_aliases[alias_name] = datasource
                print(f"[METADATA] Generated alias: {alias_name} -> {datasource}")


class StaticMetadataProvider(MetadataProvider):
    """Static metadata provider with predefined datasources"""
    
    def __init__(self, predefined_datasources: Dict[str, List[str]] = None):
        super().__init__()
        
        if predefined_datasources:
            for datasource, columns in predefined_datasources.items():
                self.register_datasource(datasource, columns)