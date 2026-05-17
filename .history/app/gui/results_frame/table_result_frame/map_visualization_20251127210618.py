import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import folium
import tempfile
import os
import webbrowser
from typing import Optional, Dict


class MapVisualizationWindow(ctk.CTkToplevel):
    """
    A popup window for displaying Google Earth Engine data on an interactive map.
    """
    
    def __init__(self, parent, gee_metadata: Optional[Dict] = None):
        super().__init__(parent)
        
        self.title("Map Visualization - Google Earth Engine Data")
        self.geometry("900x700")
        
        # Store metadata
        self.gee_metadata = gee_metadata
        
        # Set window properties
        self.transient(parent)
        self.grab_set()
        
        # Create UI
        self.create_widgets()
        
        # Generate and display map
        if self.gee_metadata:
            self.generate_map()
        else:
            self.show_no_data_message()
    
    def create_widgets(self):
        """Create the window widgets"""
        # Title frame
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=10)
        
        title_label = ctk.CTkLabel(
            title_frame,
            text="🌍 Google Earth Engine Data Location",
            font=("Arial", 20, "bold")
        )
        title_label.pack(side="left")
        
        # Info frame
        self.info_frame = ctk.CTkFrame(self)
        self.info_frame.pack(fill="x", padx=20, pady=5)
        
        # Map display info
        info_label = ctk.CTkLabel(
            self.info_frame,
            text="The map will open in your default web browser",
            font=("Arial", 12)
        )
        info_label.pack(pady=5)
        
        # Metadata display frame
        self.metadata_frame = ctk.CTkFrame(self)
        self.metadata_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        metadata_title = ctk.CTkLabel(
            self.metadata_frame,
            text="Query Information:",
            font=("Arial", 14, "bold")
        )
        metadata_title.pack(anchor="w", padx=10, pady=5)
        
        # Scrollable text for metadata
        self.metadata_text = ctk.CTkTextbox(
            self.metadata_frame,
            font=("Consolas", 12),
            wrap="word"
        )
        self.metadata_text.pack(fill="both", expand=True, padx=10, pady=5)
        
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
            hover_color="#1f5a08"
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
            "2. The query contains geographical coordinates (longitude, latitude)\n\n"
            "Example query format:\n"
            "SELECT temperature, evaporation FROM {gee:project|start_date|end_date|longitude|latitude|scale};\n\n"
            "Please execute a GEE query first to use this feature."
        )
        self.metadata_text.configure(state="disabled")
        self.show_map_btn.configure(state="disabled")
    
    def generate_map(self):
        """Generate the folium map and display metadata"""
        try:
            # Extract coordinates
            latitude = self.gee_metadata.get('latitude')
            longitude = self.gee_metadata.get('longitude')
            project = self.gee_metadata.get('project')
            start_date = self.gee_metadata.get('start_date')
            end_date = self.gee_metadata.get('end_date')
            scale = self.gee_metadata.get('scale')
            
            # Display metadata
            metadata_info = f"""📊 Google Earth Engine Query Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌍 Location:
   • Latitude:  {latitude}°
   • Longitude: {longitude}°

📅 Time Range:
   • Start Date: {start_date}
   • End Date:   {end_date}

🔧 Configuration:
   • Project:    {project}
   • Scale:      {scale}m

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 The marker on the map shows the exact location where 
   the weather/climate data was collected.

📍 Click "Open Map in Browser" to view the interactive map.
"""
            
            self.metadata_text.insert("1.0", metadata_info)
            self.metadata_text.configure(state="disabled")
            
            # Create folium map
            map_center = [latitude, longitude]
            m = folium.Map(
                location=map_center,
                zoom_start=10,
                tiles="OpenStreetMap"
            )
            
            # Add marker with popup
            popup_html = f"""
            <div style="font-family: Arial; width: 250px;">
                <h4 style="color: #2B7A0B; margin-bottom: 10px;">📍 GEE Data Collection Point</h4>
                <hr style="margin: 5px 0;">
                <p><strong>Coordinates:</strong><br>
                Lat: {latitude}°<br>
                Lon: {longitude}°</p>
                <p><strong>Date Range:</strong><br>
                {start_date} to {end_date}</p>
                <p><strong>Project:</strong> {project}</p>
                <p><strong>Scale:</strong> {scale}m</p>
            </div>
            """
            
            folium.Marker(
                location=map_center,
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"GEE Data Point: {latitude}, {longitude}",
                icon=folium.Icon(color='green', icon='info-sign')
            ).add_to(m)
            
            # Add a circle to show the scale area
            folium.Circle(
                location=map_center,
                radius=scale,
                color='blue',
                fill=True,
                fillColor='lightblue',
                fillOpacity=0.3,
                popup=f"Collection Scale: {scale}m radius"
            ).add_to(m)
            
            # Save map to temporary HTML file
            temp_dir = tempfile.gettempdir()
            self.map_file_path = os.path.join(temp_dir, "gee_map_visualization.html")
            m.save(self.map_file_path)
            
            # Automatically open the map
            self.open_map_in_browser()
            
        except Exception as e:
            messagebox.showerror(
                "Map Generation Error",
                f"Failed to generate map:\n{str(e)}"
            )
    
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