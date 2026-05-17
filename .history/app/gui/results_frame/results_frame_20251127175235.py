"""
UPDATED results_frame.py
Replace your existing app/gui/results_frame/results_frame.py with this updated version
"""

import customtkinter as ctk
from typing import Any
import pandas as pd

# Import the existing components
from app.gui.results_frame.table_result_frame.table_frame import TableFrame
from app.gui.results_frame.python_frame import PythonFrame

# Import the new map viewer
from app.gui.map_viewer import MapViewerWindow


class ResultsFrame(ctk.CTkFrame):
    """
    Frame that displays query results with Python code and table view
    Now includes "Draw on Map" button for GEE data visualization
    """
    
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        self.current_result = None
        self.current_gee_data = None
        self.configure(fg_color="transparent")
        
        # Main container with two sections
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Top section: Python code
        self.python_frame = PythonFrame(self)
        self.python_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Bottom section: Table results with map button
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.bottom_frame.grid_rowconfigure(1, weight=1)
        self.bottom_frame.grid_columnconfigure(0, weight=1)
        
        # Control buttons frame (includes Draw on Map button)
        self.control_frame = ctk.CTkFrame(self.bottom_frame, height=50)
        self.control_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 5))
        self.control_frame.grid_propagate(False)
        
        # "Draw on Map" button
        self.map_button = ctk.CTkButton(
            self.control_frame,
            text="🗺️ Draw on Map",
            command=self.show_map,
            width=140,
            height=35,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#2D6A4F",
            hover_color="#1B4332"
        )
        self.map_button.pack(side="left", padx=10, pady=7)
        
        # Info label
        self.info_label = ctk.CTkLabel(
            self.control_frame,
            text="Visualize GEE data on interactive map",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.info_label.pack(side="left", padx=10, pady=7)
        
        # Table frame
        self.table_frame = TableFrame(self.bottom_frame)
        self.table_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        
        # Configure grid weights
        self.grid_rowconfigure(1, weight=2)  # Bottom section gets more space
    
    def update_results(self, result: Any, python_code: str = "", gee_data: Any = None):
        """
        Update the display with new results
        
        Args:
            result: Query result (DataFrame, dict, list, etc.)
            python_code: Generated Python code to display
            gee_data: Google Earth Engine data object for map visualization
        """
        self.current_result = result
        self.current_gee_data = gee_data
        
        # Update Python code display
        if python_code:
            self.python_frame.set_code(python_code)
        
        # Update table display
        if result is not None:
            if isinstance(result, pd.DataFrame):
                self.table_frame.load_dataframe(result)
            elif isinstance(result, (list, dict)):
                # Convert to DataFrame for display
                try:
                    df = pd.DataFrame(result) if isinstance(result, list) else pd.DataFrame([result])
                    self.table_frame.load_dataframe(df)
                except:
                    # If conversion fails, show as text
                    self.table_frame.show_message(str(result))
            else:
                self.table_frame.show_message(str(result))
        
        # Enable/disable map button based on GEE data availability
        if gee_data is not None:
            self.map_button.configure(state="normal")
            self.info_label.configure(text="GEE data detected - Click to visualize on map")
        else:
            # Check if result contains GEE-like data
            if self._is_gee_compatible(result):
                self.map_button.configure(state="normal")
                self.info_label.configure(text="Geographic data detected - Click to visualize")
                self.current_gee_data = result
            else:
                self.map_button.configure(state="disabled")
                self.info_label.configure(text="No geographic data available for mapping")
    
    def _is_gee_compatible(self, data: Any) -> bool:
        """
        Check if the data can be visualized on a map
        Returns True if data contains geographic information
        """
        if data is None:
            return False
        
        # Check for GEE objects
        try:
            import ee
            if isinstance(data, (ee.Image, ee.FeatureCollection, ee.Geometry)):
                return True
        except ImportError:
            pass
        
        # Check for GeoJSON structure
        if isinstance(data, dict):
            if 'type' in data and 'features' in data:
                return True
            if 'geometry' in data or 'coordinates' in data:
                return True
        
        # Check for DataFrames with lat/lon columns
        if isinstance(data, pd.DataFrame):
            columns_lower = [col.lower() for col in data.columns]
            lat_cols = ['lat', 'latitude', 'lat_deg', 'y']
            lon_cols = ['lon', 'longitude', 'long', 'lng', 'lon_deg', 'x']
            
            has_lat = any(lat in columns_lower for lat in lat_cols)
            has_lon = any(lon in columns_lower for lon in lon_cols)
            
            return has_lat and has_lon
        
        # Check for list of coordinates
        if isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            if isinstance(first_item, dict):
                if 'lat' in first_item and 'lon' in first_item:
                    return True
                if 'latitude' in first_item and 'longitude' in first_item:
                    return True
            elif isinstance(first_item, (list, tuple)) and len(first_item) >= 2:
                # Assume [lat, lon] format
                return True
        
        return False
    
    def show_map(self):
        """Open the map viewer window with the current GEE data"""
        if self.current_gee_data is not None:
            try:
                # Create and show map viewer
                map_viewer = MapViewerWindow(self, gee_data=self.current_gee_data)
                map_viewer.focus()
            except Exception as e:
                # Show error dialog
                error_window = ctk.CTkToplevel(self)
                error_window.title("Map Viewer Error")
                error_window.geometry("400x150")
                
                error_label = ctk.CTkLabel(
                    error_window,
                    text=f"Error opening map viewer:\n{str(e)}",
                    font=ctk.CTkFont(size=12),
                    wraplength=350
                )
                error_label.pack(expand=True, pady=20)
                
                ok_btn = ctk.CTkButton(
                    error_window,
                    text="OK",
                    command=error_window.destroy
                )
                ok_btn.pack(pady=10)
        else:
            # No data to display
            info_window = ctk.CTkToplevel(self)
            info_window.title("No Data")
            info_window.geometry("300x100")
            
            info_label = ctk.CTkLabel(
                info_window,
                text="No geographic data available to display on map.",
                font=ctk.CTkFont(size=12)
            )
            info_label.pack(expand=True, pady=20)
            
            ok_btn = ctk.CTkButton(
                info_window,
                text="OK",
                command=info_window.destroy
            )
            ok_btn.pack(pady=10)
    
    def clear(self):
        """Clear all displayed results"""
        self.current_result = None
        self.current_gee_data = None
        self.python_frame.clear()
        self.table_frame.clear()
        self.map_button.configure(state="disabled")
        self.info_label.configure(text="Visualize GEE data on interactive map")