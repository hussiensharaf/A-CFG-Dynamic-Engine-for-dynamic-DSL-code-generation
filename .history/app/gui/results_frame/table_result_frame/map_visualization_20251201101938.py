import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import folium
from folium import plugins
import tempfile
import os
import webbrowser
from typing import Optional, Dict, List
import pandas as pd
import numpy as np
from datetime import datetime


class MapVisualizationWindow(ctk.CTkToplevel):
    """
    Enhanced popup window for displaying Google Earth Engine data on an interactive map
    with multi-variable layer support and dynamic positioning within collection radius.
    """
    
    # Color schemes for different variables
    VARIABLE_COLORS = {
        'temperature': '#FF4444',      # Red
        'wind_speed': '#4444FF',       # Blue
        'total_precipitation': '#44FF44',  # Green
        'relative_humidity': '#FF44FF',    # Magenta
        'soil_temperature': '#FFAA44',     # Orange
        'evaporation': '#44FFFF',      # Cyan
        'evapotranspiration': '#AA44FF',   # Purple
        'specific_humidity': '#AAFF44',    # Lime
    }
    
    def __init__(self, parent, gee_metadata: Optional[Dict] = None, data: Optional[pd.DataFrame] = None):
        super().__init__(parent)
        
        self.title("Map Visualization - Google Earth Engine Data")
        self.geometry("1000x800")
        
        # Store metadata and data
        self.gee_metadata = gee_metadata
        self.data = data
        self.selected_variables = []  # Multiple variables
        self.is_time_series = False
        
        # Set window properties
        self.transient(parent)
        self.grab_set()
        
        # Check if data is time-series
        if self.data is not None and not self.data.empty:
            has_date_column = 'date' in self.data.columns
            has_many_rows = len(self.data) > 10
            self.is_time_series = has_date_column or has_many_rows
        
        # Create UI
        self.create_widgets()
        
        # Check if we have data
        if self.gee_metadata and self.data is not None and not self.data.empty:
            self.populate_variable_selector()
        else:
            self.show_no_data_message()
        
        # Store map file path
        self.map_file_path = None
    
    def create_widgets(self):
        """Create the window widgets"""
        # Title frame
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=10)
        
        title_label = ctk.CTkLabel(
            title_frame,
            text="🌍 Google Earth Engine Multi-Layer Visualization",
            font=("Arial", 20, "bold")
        )
        title_label.pack(side="left")
        
        # Variable selector frame with scrollable checkboxes
        self.selector_frame = ctk.CTkFrame(self)
        self.selector_frame.pack(fill="both", expand=True, padx=20, pady=5)
        
        selector_title = ctk.CTkLabel(
            self.selector_frame,
            text="📊 Select Variables to Visualize (Multiple Allowed):",
            font=("Arial", 13, "bold")
        )
        selector_title.pack(anchor="w", padx=10, pady=5)
        
        # Scrollable frame for checkboxes
        self.checkbox_frame = ctk.CTkScrollableFrame(
            self.selector_frame,
            height=150
        )
        self.checkbox_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.variable_checkboxes = {}  # Store checkbox references
        
        # Buttons frame
        button_select_frame = ctk.CTkFrame(self.selector_frame, fg_color="transparent")
        button_select_frame.pack(fill="x", padx=10, pady=5)
        
        select_all_btn = ctk.CTkButton(
            button_select_frame,
            text="Select All",
            command=self.select_all_variables,
            width=100,
            height=28
        )
        select_all_btn.pack(side="left", padx=5)
        
        deselect_all_btn = ctk.CTkButton(
            button_select_frame,
            text="Deselect All",
            command=self.deselect_all_variables,
            width=100,
            height=28
        )
        deselect_all_btn.pack(side="left", padx=5)
        
        self.generate_btn = ctk.CTkButton(
            button_select_frame,
            text="🗺️ Generate Map",
            command=self.generate_map_with_selected_variables,
            font=("Arial", 12, "bold"),
            height=32,
            fg_color="#2B7A0B",
            hover_color="#1f5a08",
            width=150
        )
        self.generate_btn.pack(side="right", padx=5)
        
        # Info frame
        self.info_frame = ctk.CTkFrame(self)
        self.info_frame.pack(fill="x", padx=20, pady=5)
        
        self.info_label = ctk.CTkLabel(
            self.info_frame,
            text="Select variables above, then click 'Generate Map' to visualize",
            font=("Arial", 12)
        )
        self.info_label.pack(pady=5)
        
        # Main content frame
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=20, pady=5)
        
        # Left section - Metadata
        left_frame = ctk.CTkFrame(content_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        metadata_title = ctk.CTkLabel(
            left_frame,
            text="📊 Query Information:",
            font=("Arial", 14, "bold")
        )
        metadata_title.pack(anchor="w", padx=10, pady=5)
        
        self.metadata_text = ctk.CTkTextbox(
            left_frame,
            font=("Consolas", 11),
            wrap="word"
        )
        self.metadata_text.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Right section - Legend
        right_frame = ctk.CTkFrame(content_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        legend_title = ctk.CTkLabel(
            right_frame,
            text="🎨 Variable Color Legend:",
            font=("Arial", 14, "bold")
        )
        legend_title.pack(anchor="w", padx=10, pady=5)
        
        self.legend_text = ctk.CTkTextbox(
            right_frame,
            font=("Consolas", 11),
            wrap="word"
        )
        self.legend_text.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Button frame
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=10)
        
        self.show_map_btn = ctk.CTkButton(
            button_frame,
            text="🗺️ Open Map in Browser",
            command=self.open_map_in_browser,
            font=("Arial", 13),
            height=35,
            fg_color="#2B7A0B",
            hover_color="#1f5a08",
            width=200,
            state="disabled"
        )
        self.show_map_btn.pack(side="left", padx=5)
        
        close_btn = ctk.CTkButton(
            button_frame,
            text="Close",
            command=self.destroy,
            font=("Arial", 13),
            height=35,
            fg_color="#B22222",
            hover_color="#8B0000"
        )
        close_btn.pack(side="right", padx=5)
    
    def populate_variable_selector(self):
        """Populate checkboxes with available numeric columns"""
        numeric_cols = self.data.select_dtypes(include=[np.number]).columns.tolist()
        
        if numeric_cols:
            for col in numeric_cols:
                # Get color for this variable
                color = self.get_variable_color(col)
                
                # Create checkbox with colored indicator
                var = tk.BooleanVar(value=False)
                checkbox = ctk.CTkCheckBox(
                    self.checkbox_frame,
                    text=f"{col}",
                    variable=var,
                    font=("Arial", 12),
                    checkbox_width=20,
                    checkbox_height=20
                )
                checkbox.pack(anchor="w", padx=10, pady=3)
                
                self.variable_checkboxes[col] = var
            
            self.display_metadata_and_legend()
        else:
            self.show_no_data_message()
    
    def select_all_variables(self):
        """Select all variable checkboxes"""
        for var in self.variable_checkboxes.values():
            var.set(True)
    
    def deselect_all_variables(self):
        """Deselect all variable checkboxes"""
        for var in self.variable_checkboxes.values():
            var.set(False)
    
    def get_variable_color(self, variable_name):
        """Get color for a variable (case-insensitive match)"""
        var_lower = variable_name.lower()
        for key, color in self.VARIABLE_COLORS.items():
            if key in var_lower:
                return color
        # Default color if not found
        return '#888888'
    
    def generate_map_with_selected_variables(self):
        """Generate map with selected variables"""
        # Get selected variables
        self.selected_variables = [
            col for col, var in self.variable_checkboxes.items() if var.get()
        ]
        
        if not self.selected_variables:
            messagebox.showwarning(
                "No Variables Selected",
                "Please select at least one variable to visualize."
            )
            return
        
        self.info_label.configure(
            text=f"Generating map for {len(self.selected_variables)} variable(s)... Please wait."
        )
        self.update()
        
        # Generate the map
        if self.is_time_series:
            self.generate_multi_layer_map()
        else:
            self.generate_aggregated_map()
        
        self.info_label.configure(
            text=f"Map generated with {len(self.selected_variables)} layers. Click 'Open Map in Browser' to view."
        )
        self.show_map_btn.configure(state="normal")
    
    def show_no_data_message(self):
        """Show message when no GEE data is available"""
        self.metadata_text.insert("1.0", 
            "⚠️ No Google Earth Engine data detected.\n\n"
            "Please execute a GEE query first."
        )
        self.metadata_text.configure(state="disabled")
        self.legend_text.insert("1.0", "No data available.")
        self.legend_text.configure(state="disabled")
        self.generate_btn.configure(state="disabled")
    
    def display_metadata_and_legend(self):
        """Display metadata and color legend"""
        latitude = self.gee_metadata.get('latitude')
        longitude = self.gee_metadata.get('longitude')
        project = self.gee_metadata.get('project')
        start_date = self.gee_metadata.get('start_date')
        end_date = self.gee_metadata.get('end_date')
        scale = self.gee_metadata.get('scale')
        
        data_type = "Time-Series (Animated Layers)" if self.is_time_series else "Aggregated (Summary)"
        
        # Metadata
        metadata_info = f"""📊 Query Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌍 Location:
   • Latitude:  {latitude}°
   • Longitude: {longitude}°

📅 Time Range:
   • Start: {start_date}
   • End:   {end_date}
   • Rows:  {len(self.data)}

🔧 Configuration:
   • Project: {project}
   • Scale:   {scale}m
   • Data points distributed within {scale}m radius

📊 Data Type: {data_type}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 Instructions:
   1. Select one or more variables
   2. Click "Generate Map"
   3. Each variable becomes a layer
   4. Toggle layers on/off in map
"""
        
        self.metadata_text.insert("1.0", metadata_info)
        self.metadata_text.configure(state="disabled")
        
        # Color Legend
        legend_info = "Variable Colors:\n"
        legend_info += "━" * 40 + "\n\n"
        
        numeric_cols = self.data.select_dtypes(include=[np.number]).columns.tolist()
        for col in numeric_cols:
            color = self.get_variable_color(col)
            legend_info += f"● {col}\n"
            legend_info += f"  Color: {color}\n\n"
        
        legend_info += "━" * 40 + "\n"
        legend_info += "Each variable will be:\n"
        legend_info += "• Distributed randomly within\n"
        legend_info += f"  collection radius ({scale}m)\n"
        legend_info += "• Shown as separate layer\n"
        legend_info += "• Toggle-able on/off\n"
        
        self.legend_text.insert("1.0", legend_info)
        self.legend_text.configure(state="disabled")
    
    def generate_random_position_in_radius(self, center_lat, center_lon, max_radius_meters, seed):
        """
        Generate random position within radius using uniform distribution.
        Uses seed for consistent positions per variable.
        """
        np.random.seed(seed)
        
        # Convert radius from meters to degrees (approximate)
        # 1 degree latitude ≈ 111,320 meters
        # 1 degree longitude ≈ 111,320 * cos(latitude) meters
        radius_lat = max_radius_meters / 111320
        radius_lon = max_radius_meters / (111320 * np.cos(np.radians(center_lat)))
        
        # Generate random point within circle
        # Use square root for uniform distribution
        r = np.sqrt(np.random.random()) * min(radius_lat, radius_lon)
        theta = np.random.random() * 2 * np.pi
        
        lat_offset = r * np.cos(theta)
        lon_offset = r * np.sin(theta)
        
        return center_lat + lat_offset, center_lon + lon_offset
    
    def generate_multi_layer_map(self):
        """Generate map with multiple variable layers"""
        try:
            latitude = self.gee_metadata.get('latitude')
            longitude = self.gee_metadata.get('longitude')
            project = self.gee_metadata.get('project')
            start_date = self.gee_metadata.get('start_date')
            end_date = self.gee_metadata.get('end_date')
            scale = self.gee_metadata.get('scale')
            
            # Create folium map
            map_center = [latitude, longitude]
            m = folium.Map(
                location=map_center,
                zoom_start=13,
                tiles="OpenStreetMap",
                prefer_canvas=True
            )
            
            # Add tile layers
            folium.TileLayer('OpenStreetMap', name='Street Map').add_to(m)
            
            has_date_column = 'date' in self.data.columns
            
            # Create a layer for each selected variable
            for var_idx, viz_col in enumerate(self.selected_variables):
                if viz_col not in self.data.columns:
                    continue
                
                variable_color = self.get_variable_color(viz_col)
                min_val = self.data[viz_col].min()
                max_val = self.data[viz_col].max()
                
                # Create feature group for this variable
                layer_name = f"📊 {viz_col.replace('_', ' ').title()}"
                variable_layer = folium.FeatureGroup(name=layer_name, show=True)
                
                # Store positions for heatmap
                heatmap_data = []
                time_series_data = []
                
                # Add markers for each data point
                for idx, row in self.data.iterrows():
                    if has_date_column:
                        date_str = str(row['date'])
                    else:
                        date_str = f"Day {idx + 1}"
                    
                    value = row[viz_col]
                    
                    # Generate unique position for this data point within radius
                    # Seed = variable index * 10000 + row index (ensures consistency)
                    seed = var_idx * 10000 + idx
                    point_lat, point_lon = self.generate_random_position_in_radius(
                        latitude, longitude, scale, seed
                    )
                    
                    # Create popup
                    popup_html = f"""
                    <div style="font-family: Arial; width: 250px; font-size: 13px;">
                        <h4 style="color: {variable_color}; margin: 5px 0;">📅 {date_str}</h4>
                        <hr style="margin: 5px 0;">
                        <p style='margin: 5px 0; background: {variable_color}; padding: 5px; color: white; font-weight: bold; border-radius: 3px;'>
                        {viz_col}: {value:.4f}</p>
                        <hr style="margin: 5px 0;">
                        <p style="margin: 3px 0; font-size: 11px; color: #666;">
                        <strong>Variable:</strong> {viz_col}<br>
                        <strong>Location:</strong> {point_lat:.4f}°, {point_lon:.4f}°
                        </p>
                    </div>
                    """
                    
                    # Add circle marker
                    folium.CircleMarker(
                        location=[point_lat, point_lon],
                        radius=5,
                        popup=folium.Popup(popup_html, max_width=300),
                        tooltip=f"{viz_col}: {value:.2f}",
                        color=variable_color,
                        fill=True,
                        fillColor=variable_color,
                        fillOpacity=0.7,
                        weight=2
                    ).add_to(variable_layer)
                    
                    # Add to heatmap data
                    heatmap_data.append([point_lat, point_lon, value])
                    
                    # For time series animation
                    if has_date_column:
                        date_key = str(row['date']).split()[0]
                    else:
                        date_key = f"Day {idx + 1}"
                    
                    time_series_data.append({
                        'time': date_key,
                        'data': [[point_lat, point_lon, value]]
                    })
                
                variable_layer.add_to(m)
                
                # Add heatmap for this variable
                if len(heatmap_data) > 1:
                    # Group by time for animation
                    time_dict = {}
                    for entry in time_series_data:
                        time_key = entry['time']
                        if time_key not in time_dict:
                            time_dict[time_key] = []
                        time_dict[time_key].extend(entry['data'])
                    
                    sorted_times = sorted(time_dict.keys())
                    heatmap_time_data = [time_dict[t] for t in sorted_times]
                    
                    heatmap_layer = plugins.HeatMapWithTime(
                        heatmap_time_data,
                        index=sorted_times,
                        auto_play=False,
                        max_opacity=0.8,
                        radius=20,
                        blur=15,
                        min_opacity=0.2,
                        name=f"🌡️ {viz_col.title()} Heatmap",
                        gradient={0.0: 'blue', 0.5: variable_color, 1.0: 'red'}
                    )
                    heatmap_layer.add_to(m)
            
            # Add collection area circle
            folium.Circle(
                location=map_center,
                radius=scale,
                color='#0000FF',
                fill=True,
                fillColor='lightblue',
                fillOpacity=0.1,
                weight=2,
                popup=f"Collection Radius: {scale}m",
                name='📏 Collection Area'
            ).add_to(m)
            
            # Add center marker
            folium.Marker(
                location=map_center,
                popup=folium.Popup(f"""
                    <div style="font-family: Arial; width: 250px;">
                        <h4 style="color: #2B7A0B;">📍 GEE Collection Center</h4>
                        <hr>
                        <p><strong>Variables:</strong> {len(self.selected_variables)}</p>
                        <p><strong>Coordinates:</strong><br>Lat: {latitude}°<br>Lon: {longitude}°</p>
                        <p><strong>Date Range:</strong><br>{start_date} to {end_date}</p>
                        <p><strong>Data Points:</strong> {len(self.data)}</p>
                        <p><strong>Radius:</strong> {scale}m</p>
                    </div>
                """, max_width=300),
                tooltip="Collection Center",
                icon=folium.Icon(color='red', icon='info-sign', prefix='glyphicon')
            ).add_to(m)
            
            # Add layer control
            folium.LayerControl(position='topleft', collapsed=False).add_to(m)
            plugins.Fullscreen().add_to(m)
            plugins.MeasureControl(position='bottomleft').add_to(m)
            
            # Save map
            temp_dir = tempfile.gettempdir()
            self.map_file_path = os.path.join(temp_dir, f"gee_multilayer_map.html")
            m.save(self.map_file_path)
            
            self.open_map_in_browser()
            
        except Exception as e:
            messagebox.showerror("Map Generation Error", f"Failed to generate map:\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def generate_aggregated_map(self):
        """Generate simple map for aggregated data"""
        try:
            latitude = self.gee_metadata.get('latitude')
            longitude = self.gee_metadata.get('longitude')
            scale = self.gee_metadata.get('scale')
            
            map_center = [latitude, longitude]
            m = folium.Map(location=map_center, zoom_start=13, tiles="OpenStreetMap")
            
            folium.TileLayer('OpenStreetMap').add_to(m)
            folium.TileLayer('CartoDB positron').add_to(m)
            
            # Create summary popup
            popup_html = f"""
            <div style="font-family: Arial; width: 300px; font-size: 13px;">
                <h4 style="color: #2B7A0B;">📊 Aggregated Data Summary</h4>
                <hr>
            """
            
            for idx, row in self.data.iterrows():
                popup_html += f"<div style='background: #f0f0f0; padding: 5px; margin: 5px 0;'>"
                for col in self.selected_variables:
                    if col in row:
                        color = self.get_variable_color(col)
                        popup_html += f"<p style='margin: 2px 0; color: {color}; font-weight: bold;'>{col}: {row[col]}</p>"
                popup_html += "</div>"
            
            popup_html += "</div>"
            
            folium.Marker(
                location=map_center,
                popup=folium.Popup(popup_html, max_width=350),
                icon=folium.Icon(color='green', icon='th-list', prefix='glyphicon')
            ).add_to(m)
            
            folium.Circle(
                location=map_center,
                radius=scale,
                color='blue',
                fillOpacity=0.2
            ).add_to(m)
            
            folium.LayerControl().add_to(m)
            
            temp_dir = tempfile.gettempdir()
            self.map_file_path = os.path.join(temp_dir, "gee_aggregated_map.html")
            m.save(self.map_file_path)
            
            self.open_map_in_browser()
            
        except Exception as e:
            messagebox.showerror("Map Error", f"Failed to generate map:\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def open_map_in_browser(self):
        """Open the generated map in the default web browser"""
        if self.map_file_path and os.path.exists(self.map_file_path):
            webbrowser.open('file://' + self.map_file_path)
        else:
            messagebox.showwarning("Map Not Available", "Please generate a map first.")
    
    def destroy(self):
        """Clean up and close the window"""
        if self.map_file_path and os.path.exists(self.map_file_path):
            try:
                os.remove(self.map_file_path)
            except:
                pass
        super().destroy()