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
    with heatmap visualization for time-series data or simple markers for aggregated data.
    """
    
    def __init__(self, parent, gee_metadata: Optional[Dict] = None, data: Optional[pd.DataFrame] = None):
        super().__init__(parent)
        
        self.title("Map Visualization - Google Earth Engine Data")
        self.geometry("1000x750")
        
        # Store metadata and data
        self.gee_metadata = gee_metadata
        self.data = data
        self.selected_variable = None
        self.is_time_series = False
        
        # Set window properties
        self.transient(parent)
        self.grab_set()
        
        # Check if data is time-series
        # Time-series: has 'date' column OR many rows (likely daily data)
        if self.data is not None and not self.data.empty:
            has_date_column = 'date' in self.data.columns
            has_many_rows = len(self.data) > 10  # More than 10 rows suggests time-series
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
        
        if self.is_time_series:
            self.info_label.configure(
                text=f"Generating animated heatmap for: {selected}... Please wait."
            )
        else:
            self.info_label.configure(
                text=f"Generating summary map for: {selected}... Please wait."
            )
        
        self.update()
        
        # Generate the map
        if self.is_time_series:
            self.generate_time_series_map()
        else:
            self.generate_aggregated_map()
        
        self.info_label.configure(
            text=f"Map generated for: {selected}. Click 'Open Map in Browser' to view."
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
        
        # Determine data type
        data_type = "Time-Series (Animated Heatmap)" if self.is_time_series else "Aggregated (Summary Markers)"
        
        # Display metadata
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

📊 Data Type:
   • {data_type}

📊 Available Variables:
   • {available_vars}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 How to Use:
   1. Select a variable from dropdown
   2. Click "Generate Map"
   3. View the visualization

🎨 Map Features:
"""
        
        if self.is_time_series:
            metadata_info += """   ✓ Animated heatmap timeline
   ✓ Color-coded daily markers
   ✓ Interactive data popups
   ✓ Multiple map layers
"""
        else:
            metadata_info += """   ✓ Summary data marker
   ✓ Aggregated statistics popup
   ✓ Collection area indicator
   ✓ Multiple map layers
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
        
        # Get numeric columns
        numeric_cols = self.data.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            stats_info += f"📊 {col.upper()}:\n"
            stats_info += f"   • Min:    {self.data[col].min():.4f}\n"
            stats_info += f"   • Max:    {self.data[col].max():.4f}\n"
            stats_info += f"   • Mean:   {self.data[col].mean():.4f}\n"
            stats_info += f"   • Median: {self.data[col].median():.4f}\n"
            stats_info += f"   • Std:    {self.data[col].std():.4f}\n"
            stats_info += "\n"
        
        if 'date' in self.data.columns:
            stats_info += f"📅 Date Range:\n"
            stats_info += f"   • Start: {self.data['date'].min()}\n"
            stats_info += f"   • End:   {self.data['date'].max()}\n"
            stats_info += f"   • Days:  {len(self.data)}\n"
        else:
            stats_info += f"📊 Data Rows: {len(self.data)}\n"
        
        return stats_info
    
    def get_color_for_value(self, value, min_val, max_val):
        """Get color based on value using a gradient"""
        # Normalize value to 0-1 range
        if max_val == min_val:
            normalized = 0.5
        else:
            normalized = (value - min_val) / (max_val - min_val)
        
        # Color gradient: blue (low) -> green -> yellow -> red (high)
        if normalized < 0.25:
            r, g, b = 0, int(normalized * 4 * 255), 255
        elif normalized < 0.5:
            r, g, b = 0, 255, int((0.5 - normalized) * 4 * 255)
        elif normalized < 0.75:
            r, g, b = int((normalized - 0.5) * 4 * 255), 255, 0
        else:
            r, g, b = 255, int((1 - normalized) * 4 * 255), 0
        
        return f'#{r:02x}{g:02x}{b:02x}'
    
    def generate_aggregated_map(self):
        """Generate simple map with summary marker for aggregated data"""
        try:
            latitude = self.gee_metadata.get('latitude')
            longitude = self.gee_metadata.get('longitude')
            project = self.gee_metadata.get('project')
            start_date = self.gee_metadata.get('start_date')
            end_date = self.gee_metadata.get('end_date')
            scale = self.gee_metadata.get('scale')
            
            viz_col = self.selected_variable
            
            if viz_col not in self.data.columns:
                messagebox.showerror("Variable Not Found", f"Selected variable '{viz_col}' not found in data.")
                return
            
            # Create folium map with light theme
            map_center = [latitude, longitude]
            m = folium.Map(
                location=map_center, 
                zoom_start=12, 
                tiles="OpenStreetMap",
                prefer_canvas=True
            )
            
            # Add tile layers (light themes first)
            folium.TileLayer('OpenStreetMap', name='Street Map').add_to(m)
            folium.TileLayer('CartoDB positron', name='Light Map').add_to(m)
            
            # Create summary popup with all data
            popup_html = f"""
            <div style="font-family: Arial; width: 300px; font-size: 13px;">
                <h4 style="color: #2B7A0B; margin: 5px 0;">📊 Aggregated GEE Data Summary</h4>
                <hr style="margin: 5px 0;">
                <p style="margin: 5px 0;"><strong>Selected Variable:</strong> {viz_col}</p>
                <hr style="margin: 5px 0;">
            """
            
            # Add all rows to popup
            for idx, row in self.data.iterrows():
                popup_html += f"<div style='background: #f0f0f0; padding: 5px; margin: 5px 0; border-radius: 3px;'>"
                for col in self.data.columns:
                    value = row[col]
                    if col == viz_col:
                        popup_html += f"<p style='margin: 2px 0; font-weight: bold; color: #2B7A0B;'>{col}: {value}</p>"
                    else:
                        popup_html += f"<p style='margin: 2px 0;'>{col}: {value}</p>"
                popup_html += "</div>"
            
            popup_html += f"""
                <hr style="margin: 5px 0;">
                <p style="font-size: 11px; color: #666;">
                <strong>Location:</strong> {latitude}°, {longitude}°<br>
                <strong>Date Range:</strong> {start_date} to {end_date}<br>
                <strong>Total Rows:</strong> {len(self.data)}
                </p>
            </div>
            """
            
            # Add main marker
            folium.Marker(
                location=map_center,
                popup=folium.Popup(popup_html, max_width=350),
                tooltip=f"GEE Aggregated Data: {len(self.data)} rows",
                icon=folium.Icon(color='green', icon='th-list', prefix='glyphicon')
            ).add_to(m)
            
            # Add scale circle
            folium.Circle(
                location=map_center,
                radius=scale,
                color='blue',
                fill=True,
                fillColor='lightblue',
                fillOpacity=0.2,
                popup=f"Collection Scale: {scale}m radius"
            ).add_to(m)
            
            # Add legend
            min_val = self.data[viz_col].min()
            max_val = self.data[viz_col].max()
            mean_val = self.data[viz_col].mean()
            
            legend_html = f"""
            <div style="position: fixed; top: 10px; right: 10px; width: 220px;
                        background-color: white; border:2px solid grey; z-index:9999;
                        font-size:12px; padding: 10px; border-radius: 5px;">
                <h4 style="margin: 0 0 10px 0;">📊 {viz_col.replace('_', ' ').title()}</h4>
                <p style="margin: 5px 0;"><strong>Min:</strong> {min_val:.4f}</p>
                <p style="margin: 5px 0;"><strong>Max:</strong> {max_val:.4f}</p>
                <p style="margin: 5px 0;"><strong>Mean:</strong> {mean_val:.4f}</p>
                <hr style="margin: 10px 0;">
                <p style="margin: 5px 0; font-size: 10px; color: #666;">
                Aggregated data summary<br>
                Click marker for details
                </p>
            </div>
            """
            m.get_root().html.add_child(folium.Element(legend_html))
            
            folium.LayerControl(position='topleft').add_to(m)
            plugins.Fullscreen().add_to(m)
            
            # Save map
            temp_dir = tempfile.gettempdir()
            self.map_file_path = os.path.join(temp_dir, f"gee_map_{viz_col}_aggregated.html")
            m.save(self.map_file_path)
            
            self.open_map_in_browser()
            
        except Exception as e:
            messagebox.showerror("Map Generation Error", f"Failed to generate map:\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def generate_time_series_map(self):
        """Generate enhanced map with animated heatmap for time-series data"""
        try:
            latitude = self.gee_metadata.get('latitude')
            longitude = self.gee_metadata.get('longitude')
            project = self.gee_metadata.get('project')
            start_date = self.gee_metadata.get('start_date')
            end_date = self.gee_metadata.get('end_date')
            scale = self.gee_metadata.get('scale')
            
            viz_col = self.selected_variable
            
            if viz_col not in self.data.columns:
                messagebox.showerror("Variable Not Found", f"Selected variable '{viz_col}' not found in data.")
                return
            
            min_val = self.data[viz_col].min()
            max_val = self.data[viz_col].max()
            
            # Create folium map
            map_center = [latitude, longitude]
            m = folium.Map(location=map_center, zoom_start=10, tiles="OpenStreetMap")
            
            # Add tile layers
            folium.TileLayer('OpenStreetMap').add_to(m)
            folium.TileLayer('CartoDB positron').add_to(m)
            folium.TileLayer('CartoDB dark_matter').add_to(m)
            
            # Create feature groups
            marker_layer = folium.FeatureGroup(name='📍 Daily Data Points', show=True)
            heatmap_data = []
            
            # Check if we have a date column
            has_date_column = 'date' in self.data.columns
            
            # Add markers for each data point
            for idx, row in self.data.iterrows():
                if has_date_column:
                    date_str = str(row['date'])
                else:
                    # Use row index as "day number" if no date column
                    date_str = f"Day {idx + 1}"
                
                value = row[viz_col]
                color_hex = self.get_color_for_value(value, min_val, max_val)
                
                popup_html = f"""
                <div style="font-family: Arial; width: 280px; font-size: 13px;">
                    <h4 style="color: #2B7A0B; margin: 5px 0;">📅 {date_str}</h4>
                    <hr style="margin: 5px 0;">
                    <p style='margin: 5px 0; background: {color_hex}; padding: 5px; color: white; font-weight: bold; border-radius: 3px;'>
                    {viz_col}: {value:.4f}</p>
                """
                
                for col in self.data.select_dtypes(include=[np.number]).columns:
                    if col != viz_col:
                        col_value = row[col]
                        popup_html += f"<p style='margin: 3px 0;'><strong>{col}:</strong> {col_value:.4f}</p>"
                
                popup_html += f"""
                    <hr style="margin: 5px 0;">
                    <p style="margin: 3px 0; font-size: 11px; color: #666;">
                    <strong>Location:</strong> {latitude}°, {longitude}°
                    </p>
                </div>
                """
                
                # Spread points in a circle pattern for better visualization
                angle = (idx / len(self.data)) * 2 * np.pi  # Full circle
                radius_offset = 0.01  # Larger spread
                lat_offset = np.cos(angle) * radius_offset
                lon_offset = np.sin(angle) * radius_offset
                
                point_location = [latitude + lat_offset, longitude + lon_offset]
                
                folium.CircleMarker(
                    location=point_location,
                    radius=6,
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=f"{date_str}: {viz_col}={value:.2f}",
                    color=color_hex,
                    fill=True,
                    fillColor=color_hex,
                    fillOpacity=0.8,
                    weight=2
                ).add_to(marker_layer)
                
                # Add to heatmap data with spread
                heatmap_data.append([
                    latitude + lat_offset,
                    longitude + lon_offset,
                    value
                ])
            
            marker_layer.add_to(m)
            
            # Add animated heatmap
            if len(heatmap_data) > 0:
                time_series_data = []
                for idx, row in self.data.iterrows():
                    if has_date_column:
                        date_str = str(row['date']).split()[0]
                    else:
                        date_str = f"Day {idx + 1}"
                    
                # Spread heatmap points in circle pattern
                angle = (idx / len(self.data)) * 2 * np.pi
                radius_offset = 0.01
                lat_offset = np.cos(angle) * radius_offset
                lon_offset = np.sin(angle) * radius_offset
                
                time_series_data.append({
                    'time': date_str,
                    'data': [[
                        latitude + lat_offset,
                        longitude + lon_offset,
                        value
                    ]]
                })
                
                # Add time-animated heatmap with better visibility
                heatmap_layer = plugins.HeatMapWithTime(
                    [entry['data'] for entry in time_series_data],
                    index=[entry['time'] for entry in time_series_data],
                    auto_play=True,
                    max_opacity=0.9,
                    radius=30,
                    blur=20,
                    min_opacity=0.3,
                    name=f'🌡️ {viz_col.title()} Heatmap Timeline'
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
            
            # Add main marker
            folium.Marker(
                location=map_center,
                popup=folium.Popup(f"""
                    <div style="font-family: Arial; width: 250px;">
                        <h4 style="color: #2B7A0B;">📍 GEE Data Collection Point</h4>
                        <hr>
                        <p><strong>Visualizing:</strong> {viz_col}</p>
                        <p><strong>Coordinates:</strong><br>Lat: {latitude}°<br>Lon: {longitude}°</p>
                        <p><strong>Date Range:</strong><br>{start_date} to {end_date}</p>
                        <p><strong>Total Days:</strong> {len(self.data)}</p>
                        <p><strong>Project:</strong> {project}</p>
                        <p><strong>Scale:</strong> {scale}m</p>
                    </div>
                """, max_width=300),
                tooltip="Main Collection Point",
                icon=folium.Icon(color='red', icon='info-sign', prefix='glyphicon')
            ).add_to(m)
            
            # Add legend
            legend_html = f"""
            <div style="position: fixed; top: 10px; right: 10px; width: 220px;
                        background-color: white; border:2px solid grey; z-index:9999;
                        font-size:12px; padding: 10px; border-radius: 5px;">
                <h4 style="margin: 0 0 10px 0;">📊 {viz_col.replace('_', ' ').title()}</h4>
                <p style="margin: 5px 0;"><strong>Min:</strong> {min_val:.4f}</p>
                <p style="margin: 5px 0;"><strong>Max:</strong> {max_val:.4f}</p>
                <div style="background: linear-gradient(to right, blue, cyan, green, yellow, red);
                            height: 20px; margin: 10px 0; border: 1px solid #333;"></div>
                <p style="margin: 5px 0; font-size: 10px; color: #666;">
                Markers are color-coded by {viz_col} value
                </p>
            </div>
            """
            m.get_root().html.add_child(folium.Element(legend_html))
            
            folium.LayerControl(position='topleft', collapsed=False).add_to(m)
            plugins.Fullscreen().add_to(m)
            plugins.MeasureControl(position='bottomleft').add_to(m)
            
            # Save map
            temp_dir = tempfile.gettempdir()
            self.map_file_path = os.path.join(temp_dir, f"gee_map_{viz_col}_timeseries.html")
            m.save(self.map_file_path)
            
            self.open_map_in_browser()
            
        except Exception as e:
            messagebox.showerror("Map Generation Error", f"Failed to generate map:\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def open_map_in_browser(self):
        """Open the generated map in the default web browser"""
        if self.map_file_path and os.path.exists(self.map_file_path):
            webbrowser.open('file://' + self.map_file_path)
        else:
            messagebox.showwarning("Map Not Available", "Please generate a map first by selecting a variable and clicking 'Generate Map'.")
    
    def destroy(self):
        """Clean up and close the window"""
        if self.map_file_path and os.path.exists(self.map_file_path):
            try:
                os.remove(self.map_file_path)
            except:
                pass
        super().destroy()