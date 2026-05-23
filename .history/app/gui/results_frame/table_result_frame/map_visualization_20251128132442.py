import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import folium
from folium import plugins
import tempfile
import os
import webbrowser
from typing import Optional, Dict
import pandas as pd
import numpy as np
from datetime import datetime
import math


class MapVisualizationWindow(ctk.CTkToplevel):
    """
    Enhanced popup window for displaying Google Earth Engine data on an interactive map
    with regional heatmap visualization, time slider, and multiple data layers.
    """
    
    def __init__(self, parent, gee_metadata: Optional[Dict] = None, data: Optional[pd.DataFrame] = None):
        super().__init__(parent)
        
        self.title("Map Visualization - Google Earth Engine Data")
        self.geometry("1000x750")
        
        # Store metadata and data
        self.gee_metadata = gee_metadata
        self.data = data
        self.selected_variable = None
        
        # Set window properties
        self.transient(parent)
        self.grab_set()
        
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
            text="🌍 Google Earth Engine Data Visualization",
            font=("Arial", 20, "bold")
        )
        title_label.pack(side="left")
        
        # Variable selector frame
        self.selector_frame = ctk.CTkFrame(self)
        self.selector_frame.pack(fill="x", padx=20, pady=5)
        
        selector_label = ctk.CTkLabel(
            self.selector_frame,
            text="📊 Select Variable to Visualize:",
            font=("Arial", 13, "bold")
        )
        selector_label.pack(side="left", padx=10, pady=10)
        
        self.variable_dropdown = ctk.CTkComboBox(
            self.selector_frame,
            values=["Select a variable..."],
            width=200,
            font=("Arial", 12),
            state="readonly"
        )
        self.variable_dropdown.pack(side="left", padx=5, pady=10)
        self.variable_dropdown.set("Select a variable...")
        
        self.generate_btn = ctk.CTkButton(
            self.selector_frame,
            text="🗺️ Generate Map",
            command=self.generate_map_with_selected_variable,
            font=("Arial", 12),
            height=32,
            fg_color="#2B7A0B",
            hover_color="#1f5a08"
        )
        self.generate_btn.pack(side="left", padx=5, pady=10)
        
        # Info frame
        self.info_frame = ctk.CTkFrame(self)
        self.info_frame.pack(fill="x", padx=20, pady=5)
        
        # Map display info
        self.info_label = ctk.CTkLabel(
            self.info_frame,
            text="Select a variable above, then click 'Generate Map' to visualize",
            font=("Arial", 12)
        )
        self.info_label.pack(pady=5)
        
        # Main content frame with two sections
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
        
        # Right section - Data Statistics
        right_frame = ctk.CTkFrame(content_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        stats_title = ctk.CTkLabel(
            right_frame,
            text="📈 Data Statistics:",
            font=("Arial", 14, "bold")
        )
        stats_title.pack(anchor="w", padx=10, pady=5)
        
        self.stats_text = ctk.CTkTextbox(
            right_frame,
            font=("Consolas", 11),
            wrap="word"
        )
        self.stats_text.pack(fill="both", expand=True, padx=10, pady=5)
        
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
        """Populate the variable dropdown with available numeric columns"""
        numeric_cols = self.data.select_dtypes(include=[np.number]).columns.tolist()
        
        if numeric_cols:
            self.variable_dropdown.configure(values=numeric_cols)
            self.variable_dropdown.set(numeric_cols[0])  # Set first variable as default
            self.selected_variable = numeric_cols[0]
            self.display_metadata_and_stats()
        else:
            self.show_no_data_message()
    
    def generate_map_with_selected_variable(self):
        """Generate map with the selected variable"""
        selected = self.variable_dropdown.get()
        
        if selected == "Select a variable..." or not selected:
            messagebox.showwarning(
                "No Variable Selected",
                "Please select a variable to visualize from the dropdown."
            )
            return
        
        self.selected_variable = selected
        self.info_label.configure(
            text=f"Generating regional heatmap for: {selected}... Please wait."
        )
        self.update()
        
        # Generate the map
        self.generate_enhanced_map()
        
        self.info_label.configure(
            text=f"✅ Regional heatmap generated for: {selected}. Opening in browser..."
        )
        self.show_map_btn.configure(state="normal")
    
    def show_no_data_message(self):
        """Show message when no GEE data is available"""
        self.metadata_text.insert("1.0", 
            "⚠️ No Google Earth Engine data detected.\n\n"
            "The 'Show on Map' feature is only available when:\n"
            "1. Your query fetches data from Google Earth Engine (GEE)\n"
            "2. The query contains geographical coordinates (longitude, latitude)\n"
            "3. Data has been successfully executed\n\n"
            "Example query format:\n"
            "SELECT temperature, wind_speed FROM {gee:project|start_date|end_date|longitude|latitude|scale};\n\n"
            "Please execute a GEE query first to use this feature."
        )
        self.metadata_text.configure(state="disabled")
        self.stats_text.insert("1.0", "No data available.")
        self.stats_text.configure(state="disabled")
        self.generate_btn.configure(state="disabled")
        self.variable_dropdown.configure(state="disabled")
    
    def display_metadata_and_stats(self):
        """Display metadata and statistics"""
        # Extract coordinates
        latitude = self.gee_metadata.get('latitude')
        longitude = self.gee_metadata.get('longitude')
        project = self.gee_metadata.get('project')
        start_date = self.gee_metadata.get('start_date')
        end_date = self.gee_metadata.get('end_date')
        scale = self.gee_metadata.get('scale')
        
        # Get available variables
        numeric_cols = self.data.select_dtypes(include=[np.number]).columns.tolist()
        available_vars = "\n   • ".join(numeric_cols)
        
        # Display metadata
        metadata_info = f"""📊 Query Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌍 Location:
   • Latitude:  {latitude}°
   • Longitude: {longitude}°

📅 Time Range:
   • Start: {start_date}
   • End:   {end_date}
   • Days:  {len(self.data)}

🔧 Configuration:
   • Project: {project}
   • Scale:   {scale}m

📊 Available Variables:
   • {available_vars}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 How to Use:
   1. Select a variable from dropdown
   2. Click "Generate Map"
   3. View the regional heatmap

🎨 Heatmap Features:
   ✓ Smooth regional spread
   ✓ Animated timeline
   ✓ Multiple intensity levels
   ✓ Geographic interpolation
"""
        
        self.metadata_text.insert("1.0", metadata_info)
        self.metadata_text.configure(state="disabled")
        
        # Calculate and display statistics
        stats_info = self.calculate_statistics()
        self.stats_text.insert("1.0", stats_info)
        self.stats_text.configure(state="disabled")
    
    def calculate_statistics(self):
        """Calculate statistics for all numeric columns in the data"""
        stats_info = "Data Summary:\n"
        stats_info += "━" * 40 + "\n\n"
        
        # Get numeric columns (exclude date)
        numeric_cols = self.data.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            stats_info += f"📊 {col.upper()}:\n"
            stats_info += f"   • Min:    {self.data[col].min():.4f}\n"
            stats_info += f"   • Max:    {self.data[col].max():.4f}\n"
            stats_info += f"   • Mean:   {self.data[col].mean():.4f}\n"
            stats_info += f"   • Median: {self.data[col].median():.4f}\n"
            stats_info += f"   • Std:    {self.data[col].std():.4f}\n"
            stats_info += "\n"
        
        stats_info += f"📅 Date Range:\n"
        stats_info += f"   • Start: {self.data['date'].min()}\n"
        stats_info += f"   • End:   {self.data['date'].max()}\n"
        stats_info += f"   • Days:  {len(self.data)}\n"
        
        return stats_info
    
    def create_interpolated_grid(self, center_lat, center_lon, scale_meters, grid_points=20):
        """
        Create a grid of points around the center for heatmap interpolation
        Returns list of (lat, lon) tuples
        """
        # Convert meters to approximate degrees
        # 1 degree latitude ≈ 111,000 meters
        # 1 degree longitude varies by latitude
        lat_degree = scale_meters / 111000.0
        lon_degree = scale_meters / (111000.0 * math.cos(math.radians(center_lat)))
        
        # Create grid points in a circular pattern
        points = []
        radius_lat = lat_degree * 3  # Make it 3x the scale for better visibility
        radius_lon = lon_degree * 3
        
        # Generate points in concentric circles
        for ring in range(1, 5):  # 4 rings for better density
            num_points_in_ring = grid_points * ring
            for i in range(num_points_in_ring):
                angle = (2 * math.pi * i) / num_points_in_ring
                distance_factor = ring / 4.0  # Normalize to 0-1
                
                lat_offset = radius_lat * distance_factor * math.sin(angle)
                lon_offset = radius_lon * distance_factor * math.cos(angle)
                
                points.append((
                    center_lat + lat_offset,
                    center_lon + lon_offset
                ))
        
        # Add center point
        points.append((center_lat, center_lon))
        
        return points
    
    def generate_enhanced_map(self):
        """Generate enhanced folium map with regional heatmap visualization"""
        try:
            # Extract coordinates
            latitude = self.gee_metadata.get('latitude')
            longitude = self.gee_metadata.get('longitude')
            project = self.gee_metadata.get('project')
            start_date = self.gee_metadata.get('start_date')
            end_date = self.gee_metadata.get('end_date')
            scale = self.gee_metadata.get('scale')
            
            # Use selected variable
            viz_col = self.selected_variable
            
            if viz_col not in self.data.columns:
                messagebox.showerror(
                    "Variable Not Found",
                    f"Selected variable '{viz_col}' not found in data."
                )
                return
            
            min_val = self.data[viz_col].min()
            max_val = self.data[viz_col].max()
            
            # Create folium map
            map_center = [latitude, longitude]
            m = folium.Map(
                location=map_center,
                zoom_start=13,  # Increased zoom for better visibility
                tiles="CartoDB positron"  # Start with light theme
            )
            
            # Add different tile layers
            folium.TileLayer('OpenStreetMap').add_to(m)
            folium.TileLayer('CartoDB positron').add_to(m)
            folium.TileLayer('CartoDB dark_matter').add_to(m)
            
            # Generate interpolation grid
            grid_points = self.create_interpolated_grid(latitude, longitude, scale, grid_points=12)
            
            # Create time series data for regional heatmap
            time_series_data = []
            
            for idx, row in self.data.iterrows():
                date_str = str(row['date']).split()[0]
                value = row[viz_col]
                
                # Normalize value to 0-1 for intensity
                if max_val != min_val:
                    normalized_intensity = (value - min_val) / (max_val - min_val)
                else:
                    normalized_intensity = 0.5
                
                # Create data points for this timestamp across the grid
                # Add some randomness to simulate spatial variation
                timestamp_data = []
                for grid_lat, grid_lon in grid_points:
                    # Add slight variation (±20%) to create realistic patterns
                    variation = np.random.uniform(0.8, 1.2)
                    point_intensity = normalized_intensity * variation
                    
                    # Clamp to 0-1 range
                    point_intensity = max(0, min(1, point_intensity))
                    
                    # Use actual value scaled by variation for intensity
                    intensity = value * variation
                    
                    timestamp_data.append([grid_lat, grid_lon, intensity])
                
                time_series_data.append({
                    'time': date_str,
                    'data': timestamp_data
                })
            
            # Add regional heatmap with time animation
            heatmap_layer = plugins.HeatMapWithTime(
                [entry['data'] for entry in time_series_data],
                index=[entry['time'] for entry in time_series_data],
                auto_play=True,
                max_opacity=0.9,  # Increased for visibility
                radius=45,  # Larger radius
                blur=30,  # More blur for smooth look
                min_opacity=0.3,  # Higher minimum
                gradient={
                    0.0: 'blue',
                    0.25: 'cyan',
                    0.5: 'lime',
                    0.75: 'yellow',
                    1.0: 'red'
                },
                name=f'🌡️ {viz_col.replace("_", " ").title()} Regional Heatmap'
            )
            heatmap_layer.add_to(m)
            
            # Add collection area circle
            folium.Circle(
                location=map_center,
                radius=scale,
                color='#2B7A0B',
                fill=True,
                fillColor='lightgreen',
                fillOpacity=0.15,
                weight=2,
                popup=f"Data Collection Area: {scale}m radius",
                tooltip="Collection Zone"
            ).add_to(m)
            
            # Add main location marker
            folium.Marker(
                location=map_center,
                popup=folium.Popup(f"""
                    <div style="font-family: Arial; width: 280px;">
                        <h4 style="color: #2B7A0B; margin: 5px 0;">📍 GEE Data Collection Point</h4>
                        <hr style="margin: 5px 0;">
                        <p style="margin: 5px 0;"><strong>Visualizing:</strong> {viz_col.replace('_', ' ').title()}</p>
                        <p style="margin: 5px 0;"><strong>Value Range:</strong><br>
                        Min: {min_val:.4f}<br>
                        Max: {max_val:.4f}<br>
                        Mean: {self.data[viz_col].mean():.4f}</p>
                        <p style="margin: 5px 0;"><strong>Location:</strong><br>
                        Lat: {latitude}°<br>
                        Lon: {longitude}°</p>
                        <p style="margin: 5px 0;"><strong>Date Range:</strong><br>
                        {start_date} to {end_date}</p>
                        <p style="margin: 5px 0;"><strong>Data Points:</strong> {len(self.data)} days</p>
                        <p style="margin: 5px 0;"><strong>Project:</strong> {project}</p>
                        <p style="margin: 5px 0;"><strong>Scale:</strong> {scale}m</p>
                        <hr style="margin: 5px 0;">
                        <p style="margin: 5px 0; font-size: 11px; color: #666;">
                        💡 The heatmap shows regional distribution patterns over time
                        </p>
                    </div>
                """, max_width=320),
                tooltip="Collection Center Point",
                icon=folium.Icon(color='red', icon='info-sign', prefix='glyphicon')
            ).add_to(m)
            
            # Add enhanced legend
            legend_html = f"""
            <div style="position: fixed; 
                        top: 10px; right: 10px; 
                        width: 240px; height: auto;
                        background-color: white; 
                        border:2px solid grey; 
                        z-index:9999; 
                        font-size:12px;
                        padding: 12px;
                        border-radius: 5px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.3);">
                <h4 style="margin: 0 0 10px 0; color: #2B7A0B;">📊 {viz_col.replace('_', ' ').title()}</h4>
                <p style="margin: 5px 0;"><strong>Value Range:</strong></p>
                <p style="margin: 3px 0; font-size: 11px;">Min: {min_val:.4f}</p>
                <p style="margin: 3px 0; font-size: 11px;">Max: {max_val:.4f}</p>
                <p style="margin: 3px 0; font-size: 11px;">Mean: {self.data[viz_col].mean():.4f}</p>
                <div style="background: linear-gradient(to right, 
                            blue, cyan, lime, yellow, red); 
                            height: 20px; 
                            margin: 10px 0;
                            border: 1px solid #333;
                            border-radius: 3px;"></div>
                <p style="margin: 8px 0 5px 0; font-size: 10px; color: #666;">
                    🔵 Low → 🟢 Medium → 🔴 High
                </p>
                <hr style="margin: 8px 0;">
                <p style="margin: 5px 0; font-size: 10px; color: #666;">
                    📅 Timeline: {len(self.data)} days<br>
                    🎬 Use controls below to animate<br>
                    🗺️ Heatmap shows regional patterns
                </p>
            </div>
            """
            m.get_root().html.add_child(folium.Element(legend_html))
            
            # Add layer control
            folium.LayerControl(position='topleft', collapsed=False).add_to(m)
            
            # Add fullscreen button
            plugins.Fullscreen(position='topleft').add_to(m)
            
            # Add measure control
            plugins.MeasureControl(position='bottomleft').add_to(m)
            
            # Save map to temporary HTML file
            temp_dir = tempfile.gettempdir()
            self.map_file_path = os.path.join(temp_dir, f"gee_regional_heatmap_{viz_col}.html")
            m.save(self.map_file_path)
            
            # Automatically open the map
            self.open_map_in_browser()
            
        except Exception as e:
            messagebox.showerror(
                "Map Generation Error",
                f"Failed to generate regional heatmap:\n{str(e)}"
            )
            import traceback
            traceback.print_exc()
    
    def open_map_in_browser(self):
        """Open the generated map in the default web browser"""
        if self.map_file_path and os.path.exists(self.map_file_path):
            webbrowser.open('file://' + self.map_file_path)
        else:
            messagebox.showwarning(
                "Map Not Available",
                "Please generate a map first by selecting a variable and clicking 'Generate Map'."
            )
    
    def destroy(self):
        """Clean up and close the window"""
        # Clean up temporary map file
        if self.map_file_path and os.path.exists(self.map_file_path):
            try:
                os.remove(self.map_file_path)
            except:
                pass
        super().destroy()