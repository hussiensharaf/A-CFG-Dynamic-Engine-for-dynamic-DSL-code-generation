"""
Google Earth Engine Map Visualization with Real-Time Heatmap
Production-grade implementation with GEE integration, dynamic date slider, and embedded map view.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import folium
from folium import plugins
import tempfile
import os
import webbrowser
from typing import Optional, Dict, List, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ee
import json


class GEEHeatmapGenerator:
    """
    Handles Google Earth Engine data fetching and heatmap generation.
    Optimized for efficient data retrieval and caching.
    """
    
    def __init__(self, collection_id: str, start_date: str, end_date: str, 
                 latitude: float, longitude: float, scale: float):
        """
        Initialize GEE heatmap generator.
        
        Args:
            collection_id: Earth Engine ImageCollection ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            latitude: Center latitude
            longitude: Center longitude
            scale: Radius in meters
        """
        self.collection_id = collection_id
        self.start_date = start_date
        self.end_date = end_date
        self.latitude = latitude
        self.longitude = longitude
        self.scale = scale
        
        # Create region of interest (circle)
        self.center_point = ee.Geometry.Point([longitude, latitude])
        self.roi = self.center_point.buffer(scale)
        
        # Cache for fetched data
        self.data_cache = {}
        
    def get_available_bands(self) -> List[str]:
        """Get available bands from the ImageCollection."""
        try:
            dataset = ee.ImageCollection(self.collection_id).filterDate(
                self.start_date, self.end_date
            ).first()
            
            band_names = dataset.bandNames().getInfo()
            return band_names
        except Exception as e:
            print(f"Error getting bands: {e}")
            return []
    
    def generate_sample_grid(self, num_points: int = 100) -> List[Tuple[float, float]]:
        """
        Generate a grid of sample points within the circular ROI.
        
        Args:
            num_points: Number of sample points to generate
            
        Returns:
            List of (lat, lon) tuples
        """
        points = []
        
        # Convert scale to degrees (approximate)
        lat_offset = self.scale / 111320  # 1 degree lat ≈ 111,320 meters
        lon_offset = self.scale / (111320 * np.cos(np.radians(self.latitude)))
        
        # Generate points in circular pattern
        for i in range(num_points):
            # Use uniform distribution in circle
            r = np.sqrt(np.random.random()) * min(lat_offset, lon_offset)
            theta = np.random.random() * 2 * np.pi
            
            lat = self.latitude + r * np.cos(theta)
            lon = self.longitude + r * np.sin(theta)
            points.append((lat, lon))
        
        return points
    
    def fetch_heatmap_data(self, date: str, band_name: str) -> List[Tuple[float, float, float]]:
        """
        Fetch real GEE data for heatmap generation.
        
        Args:
            date: Date string (YYYY-MM-DD)
            band_name: Band/variable name to fetch
            
        Returns:
            List of (lat, lon, value) tuples for heatmap
        """
        cache_key = f"{date}_{band_name}"
        
        # Check cache first
        if cache_key in self.data_cache:
            return self.data_cache[cache_key]
        
        try:
            # Filter ImageCollection to specific date
            dataset = ee.ImageCollection(self.collection_id).filterDate(
                date, 
                (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
            ).select(band_name).first()
            
            # Generate sample points
            sample_points = self.generate_sample_grid(100)
            
            # Create FeatureCollection from sample points
            features = [
                ee.Feature(ee.Geometry.Point([lon, lat])) 
                for lat, lon in sample_points
            ]
            sample_fc = ee.FeatureCollection(features)
            
            # Sample the image at these points
            sampled = dataset.sampleRegions(
                collection=sample_fc,
                scale=self.scale / 10,  # Higher resolution sampling
                geometries=True
            )
            
            # Get the data
            sampled_data = sampled.getInfo()
            
            # Extract values
            heatmap_data = []
            for feature in sampled_data['features']:
                coords = feature['geometry']['coordinates']
                value = feature['properties'].get(band_name)
                
                if value is not None:
                    heatmap_data.append((coords[1], coords[0], float(value)))
            
            # Cache the result
            self.data_cache[cache_key] = heatmap_data
            
            return heatmap_data
            
        except Exception as e:
            print(f"Error fetching GEE data: {e}")
            # Return empty list on error
            return []
    
    def get_center_point_value(self, date: str, band_name: str) -> Optional[float]:
        """
        Get the exact value at the center point for a specific date and band.
        
        Args:
            date: Date string (YYYY-MM-DD)
            band_name: Band/variable name
            
        Returns:
            Value at center point or None
        """
        try:
            dataset = ee.ImageCollection(self.collection_id).filterDate(
                date,
                (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
            ).select(band_name).first()
            
            # Sample at center point
            value = dataset.reduceRegion(
                reducer=ee.Reducer.first(),
                geometry=self.center_point,
                scale=self.scale
            ).get(band_name).getInfo()
            
            return float(value) if value is not None else None
            
        except Exception as e:
            print(f"Error getting center value: {e}")
            return None
    
    def get_all_band_values(self, date: str, bands: List[str]) -> Dict[str, float]:
        """
        Get values for all bands at center point for a specific date.
        
        Args:
            date: Date string (YYYY-MM-DD)
            bands: List of band names
            
        Returns:
            Dictionary of {band_name: value}
        """
        try:
            dataset = ee.ImageCollection(self.collection_id).filterDate(
                date,
                (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
            ).select(bands).first()
            
            values = dataset.reduceRegion(
                reducer=ee.Reducer.first(),
                geometry=self.center_point,
                scale=self.scale
            ).getInfo()
            
            return {k: float(v) if v is not None else None for k, v in values.items()}
            
        except Exception as e:
            print(f"Error getting all band values: {e}")
            return {}


class MapVisualizationWindow(ctk.CTkToplevel):
    """
    Main map visualization window with embedded Folium map and interactive controls.
    """
    
    def __init__(self, parent, gee_metadata: Optional[Dict] = None, data: Optional[pd.DataFrame] = None):
        super().__init__(parent)
        
        self.title("Google Earth Engine - Real-Time Heatmap Visualization")
        self.geometry("1200x900")
        
        # Store metadata and data
        self.gee_metadata = gee_metadata
        self.data = data
        
        # Initialize GEE generator
        self.gee_generator = None
        
        # Current state
        self.current_date = None
        self.current_variable = None
        self.available_dates = []
        self.available_bands = []
        
        # Map file path
        self.map_file_path = None
        
        # Set window properties
        self.transient(parent)
        self.grab_set()
        
        # Initialize
        if self.gee_metadata:
            self.initialize_gee_generator()
            self.create_widgets()
            self.generate_initial_map()
        else:
            self.create_widgets()
            self.show_no_data_message()
    
    def initialize_gee_generator(self):
        """Initialize the GEE heatmap generator with query parameters."""
        try:
            # Extract parameters from metadata
            project = self.gee_metadata.get('project')
            start_date = self.gee_metadata.get('start_date')
            end_date = self.gee_metadata.get('end_date')
            latitude = self.gee_metadata.get('latitude')
            longitude = self.gee_metadata.get('longitude')
            scale = self.gee_metadata.get('scale')
            
            # Create GEE generator
            collection_id = f"ECMWF/ERA5_LAND/DAILY_AGGR"  # Default collection
            self.gee_generator = GEEHeatmapGenerator(
                collection_id, start_date, end_date,
                latitude, longitude, scale
            )
            
            # Generate date range
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            self.available_dates = [
                (start + timedelta(days=x)).strftime('%Y-%m-%d')
                for x in range((end - start).days + 1)
            ]
            
            # Set initial date to middle of range
            self.current_date = self.available_dates[len(self.available_dates) // 2]
            
            # Get available bands from data
            if self.data is not None:
                numeric_cols = self.data.select_dtypes(include=[np.number]).columns.tolist()
                
                # Map data columns to GEE band names
                band_mapping = {
                    'temperature': 'temperature_2m',
                    'wind_speed': 'u_component_of_wind_10m',
                    'total_precipitation': 'total_precipitation_sum',
                    'relative_humidity': 'dewpoint_temperature_2m',
                    'soil_temperature': 'soil_temperature_level_1',
                }
                
                self.available_bands = []
                for col in numeric_cols:
                    for key, gee_band in band_mapping.items():
                        if key in col.lower():
                            self.available_bands.append((col, gee_band))
                            break
                
                # Set initial variable
                if self.available_bands:
                    self.current_variable = self.available_bands[0]
            
        except Exception as e:
            print(f"Error initializing GEE generator: {e}")
            messagebox.showerror("Initialization Error", f"Failed to initialize GEE: {str(e)}")
    
    def create_widgets(self):
        """Create UI widgets."""
        # Top control panel
        control_frame = ctk.CTkFrame(self)
        control_frame.pack(fill="x", padx=20, pady=10)
        
        # Title
        title_label = ctk.CTkLabel(
            control_frame,
            text="🌍 Google Earth Engine Real-Time Heatmap",
            font=("Arial", 18, "bold")
        )
        title_label.pack(pady=5)
        
        # Variable selector
        var_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        var_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(
            var_frame,
            text="Variable:",
            font=("Arial", 12, "bold")
        ).pack(side="left", padx=5)
        
        self.variable_dropdown = ctk.CTkComboBox(
            var_frame,
            values=["Select variable..."],
            command=self.on_variable_changed,
            width=250
        )
        self.variable_dropdown.pack(side="left", padx=5)
        
        # Date slider frame
        slider_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        slider_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(
            slider_frame,
            text="Date:",
            font=("Arial", 12, "bold")
        ).pack(side="left", padx=5)
        
        self.date_label = ctk.CTkLabel(
            slider_frame,
            text="",
            font=("Arial", 12)
        )
        self.date_label.pack(side="left", padx=10)
        
        self.date_slider = ctk.CTkSlider(
            slider_frame,
            from_=0,
            to=100,
            command=self.on_date_changed,
            width=400
        )
        self.date_slider.pack(side="left", padx=10, fill="x", expand=True)
        
        # Update button
        self.update_btn = ctk.CTkButton(
            control_frame,
            text="🔄 Update Map",
            command=self.update_map,
            font=("Arial", 12, "bold"),
            fg_color="#2B7A0B",
            hover_color="#1f5a08",
            height=35
        )
        self.update_btn.pack(pady=5)
        
        # Info display
        info_frame = ctk.CTkFrame(self)
        info_frame.pack(fill="x", padx=20, pady=5)
        
        self.info_text = ctk.CTkTextbox(
            info_frame,
            height=100,
            font=("Consolas", 11)
        )
        self.info_text.pack(fill="x", padx=10, pady=10)
        
        # Map display instruction
        map_frame = ctk.CTkFrame(self)
        map_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.map_label = ctk.CTkLabel(
            map_frame,
            text="🗺️ Interactive map will open in your browser\nUse controls above to update the heatmap in real-time",
            font=("Arial", 13)
        )
        self.map_label.pack(expand=True)
        
        # Bottom buttons
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=10)
        
        self.open_map_btn = ctk.CTkButton(
            button_frame,
            text="🗺️ Open Map in Browser",
            command=self.open_map_in_browser,
            height=35,
            fg_color="#2B7A0B",
            hover_color="#1f5a08"
        )
        self.open_map_btn.pack(side="left", padx=5)
        
        ctk.CTkButton(
            button_frame,
            text="Close",
            command=self.destroy,
            height=35,
            fg_color="#B22222",
            hover_color="#8B0000"
        ).pack(side="right", padx=5)
    
    def show_no_data_message(self):
        """Show message when no GEE data is available."""
        self.info_text.insert("1.0", 
            "⚠️ No Google Earth Engine data detected.\n\n"
            "Please execute a GEE query first to use this feature."
        )
        self.info_text.configure(state="disabled")
        self.update_btn.configure(state="disabled")
        self.variable_dropdown.configure(state="disabled")
        self.date_slider.configure(state="disabled")
    
    def generate_initial_map(self):
        """Generate the initial map with default settings."""
        if not self.available_bands:
            self.show_no_data_message()
            return
        
        # Populate variable dropdown
        var_names = [display_name for display_name, _ in self.available_bands]
        self.variable_dropdown.configure(values=var_names)
        self.variable_dropdown.set(var_names[0])
        
        # Setup date slider
        if self.available_dates:
            self.date_slider.configure(from_=0, to=len(self.available_dates) - 1)
            self.date_slider.set(len(self.available_dates) // 2)
            self.update_date_label()
        
        # Display info
        self.display_info()
        
        # Generate initial map
        self.update_map()
    
    def update_date_label(self):
        """Update the date label based on slider position."""
        if self.available_dates:
            idx = int(self.date_slider.get())
            self.current_date = self.available_dates[idx]
            self.date_label.configure(text=self.current_date)
    
    def display_info(self):
        """Display metadata and current state information."""
        info = f"""📊 Query Information:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌍 Location: ({self.gee_metadata.get('latitude')}°, {self.gee_metadata.get('longitude')}°)
📅 Date Range: {self.gee_metadata.get('start_date')} to {self.gee_metadata.get('end_date')}
📏 Collection Radius: {self.gee_metadata.get('scale')}m
🎯 Current Date: {self.current_date}
📊 Current Variable: {self.current_variable[0] if self.current_variable else 'None'}

💡 How to use:
   1. Select a variable from the dropdown
   2. Use the slider to change the date
   3. Click "Update Map" to refresh the heatmap
   4. The map shows REAL Google Earth Engine data within the circle
"""
        
        self.info_text.delete("1.0", "end")
        self.info_text.insert("1.0", info)
        self.info_text.configure(state="disabled")
    
    def on_variable_changed(self, selected_var):
        """Handle variable selection change."""
        for display_name, gee_band in self.available_bands:
            if display_name == selected_var:
                self.current_variable = (display_name, gee_band)
                break
        self.display_info()
    
    def on_date_changed(self, value):
        """Handle date slider change."""
        self.update_date_label()
        self.display_info()
    
    def update_map(self):
        """Update the map with current settings."""
        if not self.gee_generator or not self.current_variable:
            return
        
        try:
            self.update_btn.configure(state="disabled", text="Generating...")
            self.update()
            
            # Generate map
            self.generate_folium_map()
            
            self.update_btn.configure(state="normal", text="🔄 Update Map")
            
            # Auto-open map
            self.open_map_in_browser()
            
        except Exception as e:
            messagebox.showerror("Map Error", f"Failed to update map:\n{str(e)}")
            self.update_btn.configure(state="normal", text="🔄 Update Map")
    
    def generate_folium_map(self):
        """Generate Folium map with real GEE heatmap data."""
        try:
            lat = self.gee_metadata.get('latitude')
            lon = self.gee_metadata.get('longitude')
            scale = self.gee_metadata.get('scale')
            
            display_name, gee_band = self.current_variable
            
            # Create map
            m = folium.Map(
                location=[lat, lon],
                zoom_start=13,
                tiles="OpenStreetMap"
            )
            
            # Add tile layers
            folium.TileLayer('OpenStreetMap', name='Street Map').add_to(m)
            folium.TileLayer('CartoDB positron', name='Light Map').add_to(m)
            
            # Fetch real GEE heatmap data
            print(f"Fetching GEE data for {self.current_date}, band: {gee_band}")
            heatmap_data = self.gee_generator.fetch_heatmap_data(
                self.current_date, 
                gee_band
            )
            
            # Add heatmap if data exists
            if heatmap_data:
                plugins.HeatMap(
                    heatmap_data,
                    min_opacity=0.2,
                    max_opacity=0.8,
                    radius=25,
                    blur=20,
                    name=f'{display_name} Heatmap'
                ).add_to(m)
            
            # Get center point value and all band values
            center_value = self.gee_generator.get_center_point_value(
                self.current_date, 
                gee_band
            )
            
            # Get all band values for popup
            all_gee_bands = [band for _, band in self.available_bands]
            all_values = self.gee_generator.get_all_band_values(
                self.current_date,
                all_gee_bands
            )
            
            # Format center value
            center_value_str = f"{center_value:.4f}" if center_value is not None else "N/A"
            
            # Create popup content
            popup_html = f"""
            <div style="font-family: Arial; width: 300px; font-size: 13px;">
                <h4 style="color: #2B7A0B; margin: 5px 0;">📍 GEE Data Point</h4>
                <hr>
                <p><strong>Location:</strong> ({lat:.4f}°, {lon:.4f}°)</p>
                <p><strong>Date:</strong> {self.current_date}</p>
                <hr>
                <h5 style="color: #2B7A0B;">Selected Variable:</h5>
                <p style="background: #2B7A0B; color: white; padding: 5px; border-radius: 3px;">
                <strong>{display_name}:</strong> {center_value_str}
                </p>
                <hr>
                <h5>All Variables at this point:</h5>
            """
            
            for display_name_all, gee_band_all in self.available_bands:
                value = all_values.get(gee_band_all)
                value_str = f"{value:.4f}" if value is not None else "N/A"
                popup_html += f"<p><strong>{display_name_all}:</strong> {value_str}</p>"
            
            popup_html += "</div>"
            
            # Add center marker
            tooltip_text = f"{display_name}: {center_value_str}"
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=350),
                tooltip=tooltip_text,
                icon=folium.Icon(color='red', icon='info-sign', prefix='glyphicon')
            ).add_to(m)
            
            # Add collection circle
            folium.Circle(
                location=[lat, lon],
                radius=scale,
                color='#0066FF',
                fill=True,
                fillColor='#ADD8E6',
                fillOpacity=0.2,
                weight=2,
                popup=f"Collection Radius: {scale}m"
            ).add_to(m)
            
            # Add legend
            center_value_legend = f"{center_value:.4f}" if center_value is not None else "N/A"
            legend_html = f"""
            <div style="position: fixed; top: 10px; right: 10px; width: 250px;
                        background-color: white; border: 2px solid grey; z-index: 9999;
                        padding: 10px; border-radius: 5px; font-size: 12px;">
                <h4 style="margin: 0 0 10px 0;">📊 Current View</h4>
                <p><strong>Variable:</strong> {display_name}</p>
                <p><strong>Date:</strong> {self.current_date}</p>
                <p><strong>Center Value:</strong> {center_value_legend}</p>
                <p><strong>Heatmap Points:</strong> {len(heatmap_data)}</p>
                <hr>
                <p style="font-size: 10px; color: #666;">
                ✓ Real GEE data<br>
                ✓ {scale}m radius<br>
                ✓ Hover marker for details
                </p>
            </div>
            """
            m.get_root().html.add_child(folium.Element(legend_html))
            
            # Add layer control
            folium.LayerControl(position='topleft').add_to(m)
            plugins.Fullscreen().add_to(m)
            
            # Save map
            temp_dir = tempfile.gettempdir()
            self.map_file_path = os.path.join(
                temp_dir, 
                f"gee_heatmap_{self.current_date}_{display_name}.html"
            )
            m.save(self.map_file_path)
            
        except Exception as e:
            print(f"Error generating map: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def open_map_in_browser(self):
        """Open the generated map in the default web browser."""
        if self.map_file_path and os.path.exists(self.map_file_path):
            webbrowser.open('file://' + self.map_file_path)
        else:
            messagebox.showwarning(
                "Map Not Available",
                "Please generate a map first by clicking 'Update Map'."
            )
    
    def destroy(self):
        """Clean up and close window."""
        if self.map_file_path and os.path.exists(self.map_file_path):
            try:
                os.remove(self.map_file_path)
            except:
                pass
        super().destroy()