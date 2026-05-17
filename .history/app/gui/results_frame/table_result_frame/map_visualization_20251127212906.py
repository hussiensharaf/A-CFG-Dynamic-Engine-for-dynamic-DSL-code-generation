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


class MapVisualizationWindow(ctk.CTkToplevel):
    """
    Enhanced popup window for displaying Google Earth Engine data on an interactive map
    with heatmap visualization, time slider, and multiple data layers.
    """
    
    def __init__(self, parent, gee_metadata: Optional[Dict] = None, data: Optional[pd.DataFrame] = None):
        super().__init__(parent)
        
        self.title("Map Visualization - Google Earth Engine Data")
        self.geometry("1000x750")
        
        # Store metadata and data
        self.gee_metadata = gee_metadata
        self.data = data
        
        # Set window properties
        self.transient(parent)
        self.grab_set()
        
        # Create UI
        self.create_widgets()
        
        # Generate and display map
        if self.gee_metadata and self.data is not None and not self.data.empty:
            self.generate_enhanced_map()
        else:
            self.show_no_data_message()
    
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
        
        # Info frame
        self.info_frame = ctk.CTkFrame(self)
        self.info_frame.pack(fill="x", padx=20, pady=5)
        
        # Map display info
        info_label = ctk.CTkLabel(
            self.info_frame,
            text="Interactive map with heatmap, timeline, and data layers will open in your browser",
            font=("Arial", 12)
        )
        info_label.pack(pady=5)
        
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
            text="🗺️ Open Interactive Map in Browser",
            command=self.open_map_in_browser,
            font=("Arial", 13),
            height=35,
            fg_color="#2B7A0B",
            hover_color="#1f5a08",
            width=250
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
        
        # Store map file path
        self.map_file_path = None
    
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
        self.show_map_btn.configure(state="disabled")
    
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
    
    def get_color_for_value(self, value, min_val, max_val):
        """Get color based on value using a temperature-like gradient"""
        # Normalize value to 0-1 range
        if max_val == min_val:
            normalized = 0.5
        else:
            normalized = (value - min_val) / (max_val - min_val)
        
        # Color gradient: blue (cold) -> green -> yellow -> red (hot)
        if normalized < 0.25:
            # Blue to Cyan
            r, g, b = 0, int(normalized * 4 * 255), 255
        elif normalized < 0.5:
            # Cyan to Green
            r, g, b = 0, 255, int((0.5 - normalized) * 4 * 255)
        elif normalized < 0.75:
            # Green to Yellow
            r, g, b = int((normalized - 0.5) * 4 * 255), 255, 0
        else:
            # Yellow to Red
            r, g, b = 255, int((1 - normalized) * 4 * 255), 0
        
        return f'#{r:02x}{g:02x}{b:02x}'
    
    def generate_enhanced_map(self):
        """Generate enhanced folium map with heatmap and time series visualization"""
        try:
            # Extract coordinates
            latitude = self.gee_metadata.get('latitude')
            longitude = self.gee_metadata.get('longitude')
            project = self.gee_metadata.get('project')
            start_date = self.gee_metadata.get('start_date')
            end_date = self.gee_metadata.get('end_date')
            scale = self.gee_metadata.get('scale')
            
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

📊 Available Data Layers:
   • Temperature
   • Wind Speed
   • Precipitation
   • Relative Humidity

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 Map Features:
   ✓ Color-coded markers by temperature
   ✓ Interactive popups with daily data
   ✓ Multiple visualization layers
   ✓ Heatmap animation over time
   ✓ Layer control panel
"""
            
            self.metadata_text.insert("1.0", metadata_info)
            self.metadata_text.configure(state="disabled")
            
            # Calculate and display statistics
            stats_info = self.calculate_statistics()
            self.stats_text.insert("1.0", stats_info)
            self.stats_text.configure(state="disabled")
            
            # Create folium map
            map_center = [latitude, longitude]
            m = folium.Map(
                location=map_center,
                zoom_start=10,
                tiles="OpenStreetMap"
            )
            
            # Add different tile layers
            folium.TileLayer('OpenStreetMap').add_to(m)
            folium.TileLayer('Stamen Terrain').add_to(m)
            folium.TileLayer('Stamen Toner').add_to(m)
            folium.TileLayer('CartoDB positron').add_to(m)
            
            # Prepare data for visualization
            if 'temperature' in self.data.columns:
                temp_col = 'temperature'
            else:
                # Use first numeric column
                temp_col = self.data.select_dtypes(include=[np.number]).columns[0]
            
            min_temp = self.data[temp_col].min()
            max_temp = self.data[temp_col].max()
            
            # Create feature groups for different layers
            marker_layer = folium.FeatureGroup(name='📍 Daily Data Points', show=True)
            heatmap_data = []
            
            # Add markers for each data point
            for idx, row in self.data.iterrows():
                date_str = str(row['date'])
                temp_value = row[temp_col]
                
                # Get color based on temperature
                color_hex = self.get_color_for_value(temp_value, min_temp, max_temp)
                
                # Create detailed popup
                popup_html = f"""
                <div style="font-family: Arial; width: 280px; font-size: 13px;">
                    <h4 style="color: #2B7A0B; margin: 5px 0;">📅 {date_str}</h4>
                    <hr style="margin: 5px 0;">
                """
                
                # Add all numeric columns to popup
                for col in self.data.select_dtypes(include=[np.number]).columns:
                    value = row[col]
                    popup_html += f"<p style='margin: 3px 0;'><strong>{col}:</strong> {value:.4f}</p>"
                
                popup_html += f"""
                    <hr style="margin: 5px 0;">
                    <p style="margin: 3px 0; font-size: 11px; color: #666;">
                    <strong>Location:</strong> {latitude}°, {longitude}°
                    </p>
                </div>
                """
                
                # Add marker
                folium.CircleMarker(
                    location=map_center,
                    radius=8,
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=f"{date_str}: {temp_value:.2f}",
                    color=color_hex,
                    fill=True,
                    fillColor=color_hex,
                    fillOpacity=0.7,
                    weight=2
                ).add_to(marker_layer)
                
                # Add to heatmap data (using temperature intensity)
                # Offset markers slightly to show distribution
                offset = 0.001
                heatmap_data.append([
                    latitude + (idx - len(self.data)/2) * offset,
                    longitude + (idx - len(self.data)/2) * offset,
                    temp_value
                ])
            
            marker_layer.add_to(m)
            
            # Add heatmap with time animation
            if len(heatmap_data) > 0:
                # Create time series data for heatmap animation
                time_series_data = []
                for idx, row in self.data.iterrows():
                    date_str = str(row['date']).split()[0]  # Get just the date part
                    temp_value = row[temp_col]
                    offset = 0.001
                    time_series_data.append({
                        'time': date_str,
                        'data': [[
                            latitude + (idx - len(self.data)/2) * offset,
                            longitude + (idx - len(self.data)/2) * offset,
                            temp_value
                        ]]
                    })
                
                # Add time-animated heatmap
                heatmap_layer = plugins.HeatMapWithTime(
                    [entry['data'] for entry in time_series_data],
                    index=[entry['time'] for entry in time_series_data],
                    auto_play=True,
                    max_opacity=0.8,
                    radius=25,
                    name='🌡️ Temperature Heatmap Timeline'
                )
                heatmap_layer.add_to(m)
            
            # Add scale circle
            folium.Circle(
                location=map_center,
                radius=scale,
                color='blue',
                fill=True,
                fillColor='lightblue',
                fillOpacity=0.2,
                popup=f"Collection Scale: {scale}m radius",
                name='📏 Collection Area'
            ).add_to(m)
            
            # Add main location marker
            folium.Marker(
                location=map_center,
                popup=folium.Popup(f"""
                    <div style="font-family: Arial; width: 250px;">
                        <h4 style="color: #2B7A0B;">📍 GEE Data Collection Point</h4>
                        <hr>
                        <p><strong>Coordinates:</strong><br>
                        Lat: {latitude}°<br>
                        Lon: {longitude}°</p>
                        <p><strong>Date Range:</strong><br>
                        {start_date} to {end_date}</p>
                        <p><strong>Total Days:</strong> {len(self.data)}</p>
                        <p><strong>Project:</strong> {project}</p>
                        <p><strong>Scale:</strong> {scale}m</p>
                    </div>
                """, max_width=300),
                tooltip="Main Collection Point",
                icon=folium.Icon(color='red', icon='info-sign', prefix='glyphicon')
            ).add_to(m)
            
            # Add legend for temperature colors
            legend_html = f"""
            <div style="position: fixed; 
                        top: 10px; right: 10px; 
                        width: 200px; height: auto;
                        background-color: white; 
                        border:2px solid grey; 
                        z-index:9999; 
                        font-size:12px;
                        padding: 10px;
                        border-radius: 5px;">
                <h4 style="margin: 0 0 10px 0;">🌡️ Temperature Scale</h4>
                <p style="margin: 5px 0;"><strong>Min:</strong> {min_temp:.2f}°C</p>
                <p style="margin: 5px 0;"><strong>Max:</strong> {max_temp:.2f}°C</p>
                <div style="background: linear-gradient(to right, 
                            blue, cyan, green, yellow, red); 
                            height: 20px; 
                            margin: 10px 0;
                            border: 1px solid #333;"></div>
                <p style="margin: 5px 0; font-size: 10px; color: #666;">
                    Markers are color-coded by temperature value
                </p>
            </div>
            """
            m.get_root().html.add_child(folium.Element(legend_html))
            
            # Add layer control
            folium.LayerControl(position='topleft', collapsed=False).add_to(m)
            
            # Add fullscreen button
            plugins.Fullscreen().add_to(m)
            
            # Add measure control
            plugins.MeasureControl(position='bottomleft').add_to(m)
            
            # Save map to temporary HTML file
            temp_dir = tempfile.gettempdir()
            self.map_file_path = os.path.join(temp_dir, "gee_enhanced_map_visualization.html")
            m.save(self.map_file_path)
            
            # Automatically open the map
            self.open_map_in_browser()
            
        except Exception as e:
            messagebox.showerror(
                "Map Generation Error",
                f"Failed to generate enhanced map:\n{str(e)}"
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
                "The map file is not available. Please try again."
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