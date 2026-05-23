from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum
import re


class AutocompleteContext(Enum):
    """Different contexts where autocomplete can occur"""
    KEYWORD = "keyword"
    SELECT_COLUMNS = "select_columns"
    FROM_DATASOURCE = "from_datasource"
    DATASOURCE_LOCATION = "datasource_location"
    DATASOURCE_DATASET = "datasource_dataset"
    DATASOURCE_START_DATE = "datasource_start_date"
    DATASOURCE_END_DATE = "datasource_end_date"
    DATASOURCE_LONGITUDE = "datasource_longitude"
    DATASOURCE_LATITUDE = "datasource_latitude"
    DATASOURCE_SCALE = "datasource_scale"
    WHERE_CONDITION = "where_condition"
    JOIN_TABLE = "join_table"
    JOIN_CONDITION = "join_condition"
    GROUP_BY_COLUMNS = "group_by_columns"
    ORDER_BY_COLUMNS = "order_by_columns"
    TABLE_ALIAS = "table_alias"
    COLUMN_QUALIFIED = "column_qualified"
    AFTER_LOCATION = "after_location"
    AFTER_SCALE = "after_scale"


@dataclass
class AutocompleteSuggestion:
    """Represents a single autocomplete suggestion"""
    text: str
    display_text: str
    type: str
    description: Optional[str] = None
    score: float = 0.0
    auto_suffix: str = ""


@dataclass
class AutocompleteResult:
    """Result of autocomplete analysis"""
    suggestions: List[AutocompleteSuggestion]
    context: AutocompleteContext
    trigger_position: int
    partial_word: str


class AutocompleteEngine:
    """Enhanced autocomplete engine with comprehensive attribute support"""
    
    # All SQL keywords
    KEYWORDS = [
        "SELECT", "DISTINCT", "FROM", "WHERE", "GROUP", "BY", 
        "ORDER", "ASC", "DESC", "LIMIT", "TAIL", "INTO",
        "INNER", "JOIN", "LEFT", "RIGHT", "OUTER", "FULL", 
        "CROSS", "ON", "AND", "OR", "NOT", "LIKE", "IN",
        "BETWEEN", "IS", "NULL", "AS", "UNION", "INTERSECT",
        "EXCEPT", "HAVING", "EXISTS", "CASE", "WHEN", "THEN",
        "ELSE", "END"
    ]
    
    # Aggregation functions
    AGG_FUNCTIONS = [
        "sum", "mean", "median", "min", "max", "count", "nunique",
        "std", "var", "first", "last", "prod", "sem", "size", 
        "quantile", "avg", "mode", "skew", "kurt", "cumsum",
        "cumprod", "cummin", "cummax"
    ]
    
    # ALL Earth observation and climate attributes
    COMMON_ATTRIBUTES = [
        # Temperature attributes
        "temperature", "temp", "temperature_2m", "temperature_2m_max", "temperature_2m_min",
        "surface_temperature", "air_temperature", "land_surface_temperature", "LST",
        "minimum_temperature", "min_temp", "maximum_temperature", "max_temp", 
        "mean_temperature", "avg_temperature", "skin_temperature",
        "dewpoint_temperature", "dewpoint_temperature_2m", "dewpoint",
        "soil_temperature", "soil_temperature_level_1", "soil_temperature_level_2",
        "soil_temperature_level_3", "soil_temperature_level_4",
        "LST_Day_1km", "LST_Night_1km",
        
        # Precipitation attributes
        "precipitation", "precip", "total_precipitation", "rainfall", "rain",
        "precipitation_rate", "snow", "snowfall", "snow_depth", "snow_cover",
        "total_precipitation_sum", "convective_precipitation",
        
        # Humidity and moisture
        "humidity", "relative_humidity", "specific_humidity", "absolute_humidity",
        "soil_moisture", "volumetric_soil_water", "volumetric_soil_water_layer_1",
        "volumetric_soil_water_layer_2", "volumetric_soil_water_layer_3",
        "volumetric_soil_water_layer_4", "surface_soil_moisture",
        "water_vapor", "total_column_water_vapour",
        
        # Wind attributes
        "wind_speed", "wind_speed_10m", "wind_speed_100m",
        "wind_direction", "wind_direction_10m", "wind_direction_100m",
        "u_component_of_wind", "u_component_of_wind_10m", "u_component_of_wind_100m",
        "v_component_of_wind", "v_component_of_wind_10m", "v_component_of_wind_100m",
        "u_wind", "v_wind", "wind_gust", "surface_wind",
        
        # Pressure
        "pressure", "surface_pressure", "sea_level_pressure",
        "atmospheric_pressure", "mean_sea_level_pressure",
        
        # Radiation
        "solar_radiation", "net_radiation", "shortwave_radiation",
        "longwave_radiation", "surface_solar_radiation",
        "surface_solar_radiation_downwards", "surface_solar_radiation_downward_clear_sky",
        "surface_thermal_radiation_downwards", "surface_net_solar_radiation",
        "surface_net_thermal_radiation", "top_net_solar_radiation",
        
        # Vegetation Indices
        "NDVI", "EVI", "EVI2", "SAVI", "MSAVI", "MSAVI2",
        "NDWI", "NDMI", "NBR", "NBR2", "NDSI",
        "GCI", "ARVI", "SIPI", "BSI",
        "vegetation_index", "greenness", "leaf_area_index", "LAI",
        
        # Evapotranspiration
        "evaporation", "evapotranspiration", "potential_evapotranspiration",
        "ET", "PET", "actual_evapotranspiration", "AET",
        "evaporation_from_bare_soil", "evaporation_from_vegetation_transpiration",
        "evaporation_from_open_water_surfaces_and_sea_ice",
        
        # Cloud and atmospheric properties
        "cloud_cover", "total_cloud_cover", "low_cloud_cover", 
        "medium_cloud_cover", "high_cloud_cover",
        "aerosol_optical_depth", "AOD", "aerosol_optical_thickness",
        
        # Sentinel-2 Spectral Bands (all bands)
        "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A",
        "B9", "B10", "B11", "B12",
        
        # Landsat Bands (all versions)
        "SR_B1", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7",
        "ST_B10", "ST_B6",
        "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10", "B11",
        
        # MODIS Bands
        "sur_refl_b01", "sur_refl_b02", "sur_refl_b03", "sur_refl_b04",
        "sur_refl_b05", "sur_refl_b06", "sur_refl_b07",
        
        # Generic band names
        "blue", "green", "red", "red_edge", "red_edge_1", "red_edge_2", "red_edge_3",
        "nir", "nir_narrow", "swir", "swir1", "swir2", "pan", "cirrus",
        "coastal_aerosol", "water_vapour",
        
        # Coordinates and Time
        "latitude", "longitude", "lat", "lon", "x", "y",
        "date", "time", "timestamp", "datetime",
        "year", "month", "day", "doy", "hour", "minute",
        "julian_day", "system:time_start", "system:time_end",
        
        # Quality and Masks
        "quality", "QA", "QA60", "QA_PIXEL", "QA_RADSAT",
        "cloud_mask", "pixel_qa", "quality_flag",
        "QC_Day", "QC_Night", "Emis_31", "Emis_32",
        
        # Angular properties
        "ViewZenith", "SolarZenith", "RelativeAzimuth",
        "view_zenith_angle", "solar_zenith_angle", "relative_azimuth_angle",
        "sun_azimuth", "sun_elevation", "view_azimuth",
        
        # Albedo and reflectance
        "albedo", "surface_albedo", "reflectance",
        "blue_reflectance", "green_reflectance", "red_reflectance", "nir_reflectance",
        
        # Elevation and terrain
        "elevation", "altitude", "DEM", "slope", "aspect", "hillshade",
        
        # Land cover and classification
        "land_cover", "landcover", "classification", "label",
        
        # Population and urban
        "population", "population_count", "population_density",
        "nightlights", "nighttime_lights",
        
        # Other climate variables
        "runoff", "surface_runoff", "subsurface_runoff",
        "forecast_albedo", "lake_cover", "lake_depth",
        "boundary_layer_height", "convective_available_potential_energy",
    ]
    
    def __init__(self, metadata_provider=None):
        self.metadata_provider = metadata_provider
    
    def get_suggestions(self, query: str, cursor_position: int) -> AutocompleteResult:
        """Get autocomplete suggestions with full context awareness"""
        text_before_cursor = query[:cursor_position]
        context = self._determine_context(text_before_cursor)
        partial_word = self._extract_partial_word(text_before_cursor)
        
        suggestions = self._get_suggestions_for_context(
            context, partial_word, text_before_cursor
        )
        
        return AutocompleteResult(
            suggestions=suggestions,
            context=context,
            trigger_position=cursor_position - len(partial_word),
            partial_word=partial_word
        )
    
    def _determine_context(self, text_before_cursor: str) -> AutocompleteContext:
        """Determine what context the cursor is in"""
        text = text_before_cursor.strip().upper()
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        
        if not text or text.endswith(';'):
            return AutocompleteContext.KEYWORD
        
        # Check if inside datasource {...}
        # ORDER: {location|start_date|end_date|longitude|latitude|scale|dataset}
        datasource_match = re.search(r'\{([^}]*)$', text_before_cursor)
        if datasource_match:
            content = datasource_match.group(1)
            parts = content.split('|')
            
            if len(parts) == 1:
                if ':' in parts[0]:
                    return AutocompleteContext.AFTER_LOCATION
                return AutocompleteContext.DATASOURCE_LOCATION
            elif len(parts) == 2:
                return AutocompleteContext.DATASOURCE_START_DATE
            elif len(parts) == 3:
                return AutocompleteContext.DATASOURCE_END_DATE
            elif len(parts) == 4:
                return AutocompleteContext.DATASOURCE_LONGITUDE
            elif len(parts) == 5:
                return AutocompleteContext.DATASOURCE_LATITUDE
            elif len(parts) == 6:
                return AutocompleteContext.DATASOURCE_SCALE
            elif len(parts) == 7:
                return AutocompleteContext.DATASOURCE_DATASET
            elif len(parts) == 8:
                return AutocompleteContext.AFTER_SCALE
        
        # Check for qualified column (table.column)
        if re.search(r'\b[A-Za-z_]\w*\.$', text_before_cursor):
            return AutocompleteContext.COLUMN_QUALIFIED
        
        # Check for ORDER BY
        if re.search(r'\bORDER\s+BY\s+', text):
            if not re.search(r'\bORDER\s+BY\s+.+\b(LIMIT|TAIL)\b', text):
                return AutocompleteContext.ORDER_BY_COLUMNS
        
        # Check for GROUP BY
        if re.search(r'\bGROUP\s+BY\s+', text):
            if not re.search(r'\bGROUP\s+BY\s+.+\b(ORDER|LIMIT|TAIL)\b', text):
                return AutocompleteContext.GROUP_BY_COLUMNS
        
        # Check for JOIN conditions
        if re.search(r'\b(INNER|LEFT|RIGHT|OUTER|FULL|CROSS)?\s*JOIN\s+\{[^}]+\}(\s+\w+)?\s+ON\s+', text):
            return AutocompleteContext.JOIN_CONDITION
        
        # Check for JOIN table
        if re.search(r'\b(INNER|LEFT|RIGHT|OUTER|FULL|CROSS)?\s*JOIN\s+(?!\{.*ON)', text):
            if not re.search(r'\b(INNER|LEFT|RIGHT|OUTER|FULL|CROSS)?\s*JOIN\s+.+\bON\b', text):
                return AutocompleteContext.JOIN_TABLE
        
        # Check for WHERE clause
        if re.search(r'\bWHERE\s+', text):
            if not re.search(r'\bWHERE\s+.+\b(GROUP|ORDER|LIMIT|TAIL)\b', text):
                return AutocompleteContext.WHERE_CONDITION
        
        # Check for table alias after datasource
        if re.search(r'\bFROM\s+\{[^}]+\}\s*$', text_before_cursor):
            return AutocompleteContext.TABLE_ALIAS
        
        # Check for FROM datasource
        if re.search(r'\bFROM\s+(?!\{)', text):
            if not re.search(r'\bFROM\s+\{[^}]+\}', text):
                return AutocompleteContext.FROM_DATASOURCE
        
        # Check for SELECT columns
        if re.search(r'\bSELECT\b', text):
            from_match = re.search(r'\bFROM\b', text)
            if not from_match:
                return AutocompleteContext.SELECT_COLUMNS
        
        return AutocompleteContext.KEYWORD
    
    def _extract_partial_word(self, text: str) -> str:
        """Extract the partial word being typed"""
        match = re.search(r'[\w.{}:/-]*$', text)
        return match.group(0) if match else ""
    
    def _get_suggestions_for_context(
        self, 
        context: AutocompleteContext, 
        partial_word: str,
        text_before_cursor: str
    ) -> List[AutocompleteSuggestion]:
        """Get suggestions based on context"""
        suggestions = []
        
        if context == AutocompleteContext.KEYWORD:
            suggestions.extend(self._create_keyword_suggestions(partial_word))
        
        elif context == AutocompleteContext.SELECT_COLUMNS:
            # Wildcard
            if self._fuzzy_match('*', partial_word):
                suggestions.append(AutocompleteSuggestion('*', '*', 'wildcard', 'Select all columns', 100.0))
            
            # Functions
            suggestions.extend(self._create_function_suggestions(partial_word))
            
            # Common attributes (ALL climate/earth observation attributes)
            suggestions.extend(self._create_attribute_suggestions(partial_word))
            
            # Columns from metadata
            if self.metadata_provider:
                columns = self.metadata_provider.get_columns(text_before_cursor)
                suggestions.extend(self._create_column_suggestions(columns, partial_word))
        
        elif context == AutocompleteContext.FROM_DATASOURCE:
            suggestions.append(AutocompleteSuggestion(
                '{gee:', '{gee:project|start|end|lon|lat|scale|dataset}', 'syntax',
                '💡 Start datasource with gee: prefix', 100.0
            ))
        
        elif context == AutocompleteContext.DATASOURCE_LOCATION:
            # Suggest gee: prefix
            if not partial_word.startswith('gee:'):
                suggestions.append(AutocompleteSuggestion(
                    'gee:', 'gee:project-name', 'location',
                    '💡 Add gee: prefix for your project', 100.0
                ))
            
            suggestions.append(AutocompleteSuggestion(
                'gee:your-project', 'gee:your-project', 'location',
                '💡 Enter your GEE project name', 95.0
            ))
            
            # Get locations from metadata (public only)
            if self.metadata_provider:
                locations = self.metadata_provider.get_locations()
                for loc in locations:
                    full_loc = f"gee:{loc}" if not loc.startswith('gee:') else loc
                    if self._fuzzy_match(full_loc, partial_word):
                        score = self._calculate_score(full_loc, partial_word)
                        suggestions.append(AutocompleteSuggestion(
                            full_loc, full_loc, 'location',
                            f'Project: {loc}', score
                        ))
        
        elif context == AutocompleteContext.AFTER_LOCATION:
            suggestions.append(AutocompleteSuggestion(
                '|', '|start_date', 'syntax',
                '💡 Add | then start date', 100.0
            ))
        
        elif context == AutocompleteContext.DATASOURCE_START_DATE:
            suggestions.extend([
                AutocompleteSuggestion(
                    '2024-01-01', '2024-01-01', 'date',
                    '💡 Format: YYYY-MM-DD (Start date)', 100.0
                ),
                AutocompleteSuggestion(
                    '2023-01-01', '2023-01-01', 'date',
                    'Start: January 1, 2023', 95.0
                ),
                AutocompleteSuggestion(
                    '2024-06-01', '2024-06-01', 'date',
                    'Start: June 1, 2024', 90.0
                ),
            ])
        
        elif context == AutocompleteContext.DATASOURCE_END_DATE:
            suggestions.extend([
                AutocompleteSuggestion(
                    '2024-12-31', '2024-12-31', 'date',
                    '💡 Format: YYYY-MM-DD (End date)', 100.0
                ),
                AutocompleteSuggestion(
                    '2023-12-31', '2023-12-31', 'date',
                    'End: December 31, 2023', 95.0
                ),
                AutocompleteSuggestion(
                    '2024-12-31', '2024-12-31', 'date',
                    'End: December 31, 2024', 90.0
                ),
            ])
        
        elif context == AutocompleteContext.DATASOURCE_LONGITUDE:
            suggestions.extend([
                AutocompleteSuggestion(
                    '30.5', '30.5', 'coordinate',
                    '💡 Longitude in decimal degrees', 100.0
                ),
                AutocompleteSuggestion(
                    '31.2357', '31.2357', 'coordinate',
                    'Example: 31.2357°E', 95.0
                ),
                AutocompleteSuggestion(
                    'longitude', 'longitude', 'column',
                    'Use column name', 85.0
                ),
            ])
        
        elif context == AutocompleteContext.DATASOURCE_LATITUDE:
            suggestions.extend([
                AutocompleteSuggestion(
                    '26.8', '26.8', 'coordinate',
                    '💡 Latitude in decimal degrees', 100.0
                ),
                AutocompleteSuggestion(
                    '30.0444', '30.0444', 'coordinate',
                    'Example: 30.0444°N', 95.0
                ),
                AutocompleteSuggestion(
                    'latitude', 'latitude', 'column',
                    'Use column name', 85.0
                ),
            ])
        
        elif context == AutocompleteContext.DATASOURCE_SCALE:
            suggestions.extend([
                AutocompleteSuggestion(
                    '30', '30', 'scale',
                    '💡 30m resolution', 100.0
                ),
                AutocompleteSuggestion(
                    '10', '10', 'scale',
                    '10m resolution (high detail)', 98.0
                ),
                AutocompleteSuggestion(
                    '250', '250', 'scale',
                    '250m resolution', 95.0
                ),
                AutocompleteSuggestion(
                    '500', '500', 'scale',
                    '500m resolution', 90.0
                ),
                AutocompleteSuggestion(
                    '1000', '1000', 'scale',
                    '1km resolution', 85.0
                ),
                AutocompleteSuggestion(
                    '100', '100', 'scale',
                    '100m resolution', 80.0
                ),
            ])
        
        elif context == AutocompleteContext.DATASOURCE_DATASET:
            suggestions.append(AutocompleteSuggestion(
                'ERA5_LAND}', 'ERA5_LAND}', 'dataset',
                '💡 Choose dataset (auto-closes })', 100.0
            ))
            
            # Get all datasets from metadata
            if self.metadata_provider:
                datasets = self.metadata_provider.get_dataset_names()
                for ds in datasets:
                    if self._fuzzy_match(ds, partial_word):
                        score = self._calculate_score(ds, partial_word)
                        # Auto-close with }
                        suggestions.append(AutocompleteSuggestion(
                            ds + '}', ds + '}', 'dataset',
                            f'Dataset: {ds} (auto-closes)', score
                        ))
        
        elif context == AutocompleteContext.AFTER_SCALE:
            suggestions.append(AutocompleteSuggestion(
                '}', '}', 'syntax',
                '💡 Close datasource definition', 100.0
            ))
        
        elif context == AutocompleteContext.WHERE_CONDITION:
            # Add ALL attributes
            suggestions.extend(self._create_attribute_suggestions(partial_word))
            
            if self.metadata_provider:
                columns = self.metadata_provider.get_columns(text_before_cursor)
                suggestions.extend(self._create_column_suggestions(columns, partial_word))
            
            for kw in ['AND', 'OR', 'NOT', 'LIKE', 'IN', 'BETWEEN', 'IS', 'NULL']:
                if self._fuzzy_match(kw, partial_word):
                    score = self._calculate_score(kw, partial_word)
                    suggestions.append(AutocompleteSuggestion(kw, kw, 'keyword', score=score))
        
        elif context == AutocompleteContext.JOIN_TABLE:
            suggestions.append(AutocompleteSuggestion(
                '{gee:', '{gee:project|start|end|lon|lat|scale|dataset}', 'syntax',
                'Start datasource with gee:', 100.0
            ))
        
        elif context == AutocompleteContext.JOIN_CONDITION:
            if self.metadata_provider:
                qualified_cols = self.metadata_provider.get_qualified_columns(text_before_cursor)
                suggestions.extend(self._create_column_suggestions(qualified_cols, partial_word))
        
        elif context == AutocompleteContext.COLUMN_QUALIFIED:
            table_match = re.search(r'([A-Za-z_]\w*)\.$', text_before_cursor)
            if table_match and self.metadata_provider:
                table_alias = table_match.group(1)
                columns = self.metadata_provider.get_columns_for_table(table_alias)
                suggestions.extend(self._create_column_suggestions(columns, partial_word))
        
        elif context in [AutocompleteContext.GROUP_BY_COLUMNS, AutocompleteContext.ORDER_BY_COLUMNS]:
            # Add ALL attributes
            suggestions.extend(self._create_attribute_suggestions(partial_word))
            
            if self.metadata_provider:
                columns = self.metadata_provider.get_columns(text_before_cursor)
                suggestions.extend(self._create_column_suggestions(columns, partial_word))
            
            if context == AutocompleteContext.ORDER_BY_COLUMNS:
                for kw in ['ASC;', 'DESC;']:
                    if self._fuzzy_match(kw, partial_word):
                        score = self._calculate_score(kw, partial_word)
                        suggestions.append(AutocompleteSuggestion(
                            kw, kw, 'keyword', 
                            f'{kw[:-1]} (auto-adds ;)', score
                        ))
        
        suggestions.sort(key=lambda s: s.score, reverse=True)
        return suggestions
    
    def _create_keyword_suggestions(self, partial: str) -> List[AutocompleteSuggestion]:
        """Create keyword suggestions"""
        suggestions = []
        for kw in self.KEYWORDS:
            if self._fuzzy_match(kw, partial):
                score = self._calculate_score(kw, partial)
                suggestions.append(AutocompleteSuggestion(kw, kw, 'keyword', score=score))
        return suggestions
    
    def _create_function_suggestions(self, partial: str) -> List[AutocompleteSuggestion]:
        """Create function suggestions"""
        suggestions = []
        for fn in self.AGG_FUNCTIONS:
            if self._fuzzy_match(fn, partial):
                score = self._calculate_score(fn, partial)
                suggestions.append(AutocompleteSuggestion(
                    f"{fn}(", 
                    f"{fn}(column)", 
                    'function',
                    f"Aggregation: {fn}",
                    score
                ))
        return suggestions
    
    def _create_attribute_suggestions(self, partial: str) -> List[AutocompleteSuggestion]:
        """Create common attribute suggestions - ALL climate/EO attributes"""
        suggestions = []
        for attr in self.COMMON_ATTRIBUTES:
            if self._fuzzy_match(attr, partial):
                score = self._calculate_score(attr, partial)
                suggestions.append(AutocompleteSuggestion(
                    attr, attr, 'attribute',
                    f'Climate/EO attribute: {attr}',
                    score
                ))
        return suggestions
    
    def _create_column_suggestions(self, columns: List[str], partial: str) -> List[AutocompleteSuggestion]:
        """Create column suggestions"""
        suggestions = []
        for col in columns:
            if self._fuzzy_match(col, partial):
                score = self._calculate_score(col, partial)
                suggestions.append(AutocompleteSuggestion(col, col, 'column', score=score))
        return suggestions
    
    def _fuzzy_match(self, text: str, partial: str) -> bool:
        """Check if partial matches text using fuzzy logic"""
        if not partial:
            return True
        
        text_lower = text.lower()
        partial_lower = partial.lower()
        
        if text_lower.startswith(partial_lower):
            return True
        
        if partial_lower in text_lower:
            return True
        
        text_idx = 0
        for char in partial_lower:
            text_idx = text_lower.find(char, text_idx)
            if text_idx == -1:
                return False
            text_idx += 1
        
        return True
    
    def _calculate_score(self, text: str, partial: str) -> float:
        """Calculate relevance score for a suggestion"""
        if not partial:
            return 50.0
        
        text_lower = text.lower()
        partial_lower = partial.lower()
        score = 0.0
        
        if text_lower.startswith(partial_lower):
            score = 100.0
            score += (len(partial_lower) / len(text_lower)) * 50
        elif partial_lower in text_lower:
            score = 50.0
            pos = text_lower.index(partial_lower)
            score += (1.0 - pos / len(text_lower)) * 25
        else:
            score = 10.0
        
        length_bonus = 1.0 / (1.0 + len(text) / 10.0)
        score += length_bonus * 10
        
        return score
