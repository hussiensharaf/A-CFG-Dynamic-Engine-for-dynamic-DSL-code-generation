"""
Google Earth Engine Map Visualization - Embedded Version
Uses existing table data for consistency, embedded map viewer, OpenStreetMap default.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import folium
from folium import plugins
import tempfile
import os
from typing import Optional, Dict, List, Tuple
import pandas as pd
import numpy as np
from datetime import datetime
import webbrowser


class EmbeddedMapFrame(ctk.CTkFrame):
    """
    Embedded map viewer using iframe in tkinter.
    Uses platform-specific webview for best compatibility.
    """
    
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        self.html_file = None
        self.webview = None
        self.setup_webview()
    
    def setup_webview(self):
        """Setup embedded web view."""
        try:
            # Try platform-specific webview
            import platform
            system = platform.system()
            
            if system == "Windows":
                # Use webview library for Windows
                try:
                    import webview
                    self.use_webview = True
                    self.setup_webview_widget()
                    return
                except ImportError:
                    pass
            
            # Fallback to tkinterweb
            try:
                from tkinterweb import HtmlFrame
                self.webview = HtmlFrame(self, messages_enabled=False)
                self.webview.pack(fill="both", expand=True)
                
                # Suppress scroll events
                self.webview.bind_all("<MouseWheel>", lambda e: None, add="+")
                return
            except ImportError:
                pass
            
            # Final fallback - show instruction
            self.setup_instruction_view()
            
        except Exception as e:
            print(f"Error setting up webview: {e}")
            self.setup_instruction_view()
    
    def setup_webview_widget(self):
        """Setup webview widget (for Windows)."""
        # Container for webview
        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True)
        
        self.webview_container = container
        self.use_webview = True
    
    def setup_instruction_view(self):
        """Show installation instructions."""
        info_frame = ctk.CTkFrame(self, fg_color=("#E8E8E8", "#2B2B2B"))
        info_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(
            info_frame,
            text="🗺️",
            font=("Arial", 60)
        ).pack(pady=(30, 10))
        
        ctk.CTkLabel(
            info_frame,
            text="Map Embedding Not Available",
            font=("Arial", 16, "bold")
        ).pack(pady=10)
        
        ctk.CTkLabel(
            info_frame,
            text="To view maps embedded in the window, install:\n\npip install tkinterweb\n\nor\n\npip install pywebview",
            font=("Arial", 12),
            justify="center"
        ).pack(pady=20)
        
        self.browser_btn = ctk.CTkButton(
            info_frame,
            text="🌍 Open in Browser (Alternative)",
            command=self.open_in_browser,
            height=40,
            fg_color="#2B7A0B",
            hover_color="#1f5a08",
            state="disabled"
        )
        self.browser_btn.pack(pady=20)
    
    def load_html(self, html_file: str):
        """Load HTML file into embedded viewer."""
        self.html_file = html_file
        
        try:
            # Check if using webview
            if hasattr(self, 'use_webview') and self.use_webview:
                self.load_with_webview(html_file)
            # Check if tkinterweb is available
            elif self.webview is not None:
                self.webview.load_file(html_file)
            # Fallback to browser
            else:
                if hasattr(self, 'browser_btn'):
                    self.browser_btn.configure(state="normal")
                # Don't auto-open, let user click
                
        except Exception as e:
            print(f"Error loading HTML: {e}")
            # Fallback to browser
            if hasattr(self, 'browser_btn'):
                self.browser_btn.configure(state="normal")
    
    def load_with_webview(self, html_file: str):
        """Load HTML using pywebview."""
        import webview
        import threading
        
        def create_webview():
            # Create webview in separate thread
            webview.create_window(
                '',
                html_file,
                width=800,
                height=600,
                frameless=False,
                easy_drag=False
            )
            webview.start()
        
        # Run in thread to avoid blocking
        thread = threading.Thread(target=create_webview, daemon=True)
        thread.start()
    
    def open_in_browser(self):
        """Open HTML file in browser (fallback)."""
        if self.html_file and os.path.exists(self.html_file):
            webbrowser.open('file://' + self.html_file)


class MapVisualizationWindow(ctk.CTkToplevel):
    """
    Map visualization window using existing table data for consistency.
    Embedded map view with OpenStreetMap default.
    """
    
    def __init__(self, parent, gee_metadata: Optional[Dict] = None, data: Optional[pd.DataFrame] = None):
        super().__init__(parent)
        
        self.title("Google Earth Engine - Heatmap Visualization")
        self.geometry("1400x900")
        
        # Store metadata and data
        self.gee_metadata = gee_metadata
        self.data = data
        
        # Current state
        self.current_date = None
        self.current_variable = None
        self.available_dates = []
        self.available_variables = []
        
        # Map file path
        self.map_file_path = None
        
        # Set window properties
        self.transient(parent)
        self.grab_set()
        
        # Create UI
        self.create_widgets()
        
        # Initialize
        if self.gee_metadata and self.data is not None and not self.data.empty:
            self.initialize_from_data()
            self.generate_initial_map()
        else:
            self.show_no_data_message()
    
    def initialize_from_data(self):
        """Initialize from existing table data."""
        try:
            # Get available variables (numeric columns except date)
            numeric_cols = self.data.select_dtypes(include=[np.number]).columns.tolist()
            self.available_variables = numeric_cols
            
            # Get available dates
            if 'date' in self.data.columns:
                self.available_dates = self.data['date'].astype(str).tolist()
            else:
                # Generate day indices
                self.available_dates = [f"Day {i+1}" for i in range(len(self.data))]
            
            # Set initial values
            if self.available_variables:
                self.current_variable = self.available_variables[0]
            
            if self.available_dates:
                self.current_date = self.available_dates[len(self.available_dates) // 2]
            
        except Exception as e:
            print(f"Error initializing: {e}")
            messagebox.showerror("Initialization Error", str(e))
    
    def create_widgets(self):
        """Create UI widgets."""
        # Main container with two sections: controls (left) and map (right)
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Left panel - Controls (30% width)
        left_panel = ctk.CTkFrame(main_container)
        left_panel.pack(side="left", fill="both", padx=(0, 5), pady=0)
        left_panel.configure(width=400)
        
        # Title
        title_label = ctk.CTkLabel(
            left_panel,
            text="🌍 GEE Heatmap",
            font=("Arial", 18, "bold")
        )
        title_label.pack(pady=10)
        
        # Variable selector
        var_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        var_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            var_frame,
            text="Variable:",
            font=("Arial", 12, "bold")
        ).pack(anchor="w", pady=2)
        
        self.variable_dropdown = ctk.CTkComboBox(
            var_frame,
            values=["Select variable..."],
            command=self.on_variable_changed,
            width=350
        )
        self.variable_dropdown.pack(fill="x", pady=2)
        
        # Date slider
        date_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        date_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            date_frame,
            text="Date:",
            font=("Arial", 12, "bold")
        ).pack(anchor="w", pady=2)
        
        self.date_label = ctk.CTkLabel(
            date_frame,
            text="",
            font=("Arial", 11)
        )
        self.date_label.pack(anchor="w", pady=2)
        
        self.date_slider = ctk.CTkSlider(
            date_frame,
            from_=0,
            to=100,
            command=self.on_date_changed,
            width=350
        )
        self.date_slider.pack(fill="x", pady=5)
        
        # Update button
        self.update_btn = ctk.CTkButton(
            left_panel,
            text="🔄 Update Map",
            command=self.update_map,
            font=("Arial", 13, "bold"),
            fg_color="#2B7A0B",
            hover_color="#1f5a08",
            height=40
        )
        self.update_btn.pack(padx=10, pady=10, fill="x")
        
        # Info display
        info_label = ctk.CTkLabel(
            left_panel,
            text="📊 Current Data:",
            font=("Arial", 12, "bold")
        )
        info_label.pack(anchor="w", padx=10, pady=(10, 5))
        
        self.info_text = ctk.CTkTextbox(
            left_panel,
            height=300,
            font=("Consolas", 10),
            wrap="word"
        )
        self.info_text.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Close button
        ctk.CTkButton(
            left_panel,
            text="Close",
            command=self.destroy,
            height=35,
            fg_color="#B22222",
            hover_color="#8B0000"
        ).pack(padx=10, pady=10, fill="x")
        
        # Right panel - Embedded map (70% width)
        right_panel = ctk.CTkFrame(main_container)
        right_panel.pack(side="right", fill="both", expand=True, padx=(5, 0), pady=0)
        
        # Map viewer
        self.map_viewer = EmbeddedMapFrame(right_panel)
        self.map_viewer.pack(fill="both", expand=True, padx=5, pady=5)
    
    def show_no_data_message(self):
        """Show message when no data is available."""
        self.info_text.insert("1.0", 
            "⚠️ No data available.\n\n"
            "Please execute a GEE query first."
        )
        self.info_text.configure(state="disabled")
        self.update_btn.configure(state="disabled")
    
    def generate_initial_map(self):
        """Generate the initial map."""
        if not self.available_variables:
            self.show_no_data_message()
            return
        
        # Populate dropdowns
        self.variable_dropdown.configure(values=self.available_variables)
        self.variable_dropdown.set(self.available_variables[0])
        
        # Setup slider
        if self.available_dates:
            self.date_slider.configure(from_=0, to=len(self.available_dates) - 1)
            self.date_slider.set(len(self.available_dates) // 2)
            self.update_date_label()
        
        # Display info
        self.display_info()
        
        # Generate map
        self.update_map()
    
    def update_date_label(self):
        """Update date label from slider."""
        if self.available_dates:
            idx = int(self.date_slider.get())
            idx = max(0, min(idx, len(self.available_dates) - 1))
            self.current_date = self.available_dates[idx]
            
            # Extract just the date part if it's a datetime string
            date_display = str(self.current_date).split()[0]
            self.date_label.configure(text=date_display)
    
    def display_info(self):
        """Display current state information."""
        if not self.gee_metadata:
            return
        
        # Get current row data
        row_data = self.get_current_row_data()
        
        info = f"""Query Information:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌍 Location:
   Lat: {self.gee_metadata.get('latitude')}°
   Lon: {self.gee_metadata.get('longitude')}°

📏 Radius: {self.gee_metadata.get('scale')}m

📅 Date Range:
   {self.gee_metadata.get('start_date')} to
   {self.gee_metadata.get('end_date')}

🎯 Current Selection:
   Date: {str(self.current_date).split()[0]}
   Variable: {self.current_variable}

📊 Values at this point:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        if row_data is not None:
            for var in self.available_variables:
                if var in row_data:
                    value = row_data[var]
                    if pd.notna(value):
                        info += f"   {var}: {value:.4f}\n"
        else:
            info += "   No data for selected date\n"
        
        info += "\n💡 Tip: Use slider to change date\n"
        info += "        Select variable from dropdown"
        
        self.info_text.delete("1.0", "end")
        self.info_text.insert("1.0", info)
    
    def on_variable_changed(self, selected_var):
        """Handle variable change."""
        self.current_variable = selected_var
        self.display_info()
    
    def on_date_changed(self, value):
        """Handle date slider change."""
        self.update_date_label()
        self.display_info()
    
    def get_current_row_data(self) -> Optional[pd.Series]:
        """Get the row data for current date."""
        try:
            if 'date' in self.data.columns:
                # Match by date
                current_date_str = str(self.current_date).split()[0]
                mask = self.data['date'].astype(str).str.startswith(current_date_str)
                matching_rows = self.data[mask]
                
                if not matching_rows.empty:
                    return matching_rows.iloc[0]
            else:
                # Match by index
                idx = self.available_dates.index(self.current_date)
                if 0 <= idx < len(self.data):
                    return self.data.iloc[idx]
            
            return None
        except Exception as e:
            print(f"Error getting row data: {e}")
            return None
    
    def generate_heatmap_data(self) -> List[Tuple[float, float, float]]:
        """
        Generate heatmap points distributed within the circle.
        Uses current variable values interpolated spatially.
        """
        lat = self.gee_metadata.get('latitude')
        lon = self.gee_metadata.get('longitude')
        scale = self.gee_metadata.get('scale')
        
        # Get current value
        row_data = self.get_current_row_data()
        if row_data is None or self.current_variable not in row_data:
            return []
        
        center_value = row_data[self.current_variable]
        if pd.isna(center_value):
            return []
        
        # Convert scale to degrees
        lat_offset = scale / 111320
        lon_offset = scale / (111320 * np.cos(np.radians(lat)))
        
        # Generate points with gradient (stronger at center)
        heatmap_data = []
        num_points = 100
        
        for i in range(num_points):
            # Random point in circle
            r = np.sqrt(np.random.random())
            theta = np.random.random() * 2 * np.pi
            
            point_lat = lat + r * lat_offset * np.cos(theta)
            point_lon = lon + r * lon_offset * np.sin(theta)
            
            # Gradient: value decreases with distance from center
            # Add some randomness for natural look
            distance_factor = 1 - (r * 0.3)  # 30% decrease at edge
            noise = np.random.normal(0, 0.05)  # 5% noise
            point_value = center_value * distance_factor * (1 + noise)
            
            heatmap_data.append((point_lat, point_lon, point_value))
        
        return heatmap_data
    
    def update_map(self):
        """Update the map with current settings."""
        if not self.current_variable or self.current_date is None:
            return
        
        try:
            self.update_btn.configure(state="disabled", text="Generating...")
            self.update()
            
            # Generate map
            self.generate_folium_map()
            
            self.update_btn.configure(state="normal", text="🔄 Update Map")
            
        except Exception as e:
            messagebox.showerror("Map Error", f"Failed to update map:\n{str(e)}")
            self.update_btn.configure(state="normal", text="🔄 Update Map")
            import traceback
            traceback.print_exc()
    
    def generate_folium_map(self):
        """Generate Folium map using table data."""
        try:
            lat = self.gee_metadata.get('latitude')
            lon = self.gee_metadata.get('longitude')
            scale = self.gee_metadata.get('scale')
            
            # Get current row data
            row_data = self.get_current_row_data()
            if row_data is None:
                messagebox.showwarning("No Data", "No data available for selected date.")
                return
            
            # Create map - OpenStreetMap only, no CartoDB
            m = folium.Map(
                location=[lat, lon],
                zoom_start=13,
                tiles="OpenStreetMap"
            )
            
            # Generate heatmap data
            heatmap_data = self.generate_heatmap_data()
            
            # Add heatmap
            if heatmap_data:
                plugins.HeatMap(
                    heatmap_data,
                    min_opacity=0.2,
                    max_opacity=0.8,
                    radius=25,
                    blur=20,
                    name=f'{self.current_variable} Heatmap'
                ).add_to(m)
            
            # Get value for current variable
            center_value = row_data[self.current_variable] if self.current_variable in row_data else None
            center_value_str = f"{center_value:.4f}" if pd.notna(center_value) else "N/A"
            
            # Create popup with ALL variable values from table
            popup_html = f"""
            <div style="font-family: Arial; width: 300px; font-size: 13px;">
                <h4 style="color: #2B7A0B; margin: 5px 0;">📍 Data Point</h4>
                <hr>
                <p><strong>Location:</strong> ({lat:.4f}°, {lon:.4f}°)</p>
                <p><strong>Date:</strong> {str(self.current_date).split()[0]}</p>
                <hr>
                <h5 style="color: #2B7A0B;">Selected Variable:</h5>
                <p style="background: #2B7A0B; color: white; padding: 5px; border-radius: 3px;">
                <strong>{self.current_variable}:</strong> {center_value_str}
                </p>
                <hr>
                <h5>All Variables (from table):</h5>
            """
            
            for var in self.available_variables:
                if var in row_data:
                    value = row_data[var]
                    value_str = f"{value:.4f}" if pd.notna(value) else "N/A"
                    popup_html += f"<p><strong>{var}:</strong> {value_str}</p>"
            
            popup_html += "</div>"
            
            # Add center marker
            tooltip_text = f"{self.current_variable}: {center_value_str}"
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
            center_value_legend = f"{center_value:.4f}" if pd.notna(center_value) else "N/A"
            legend_html = f"""
            <div style="position: fixed; top: 10px; right: 10px; width: 250px;
                        background-color: white; border: 2px solid grey; z-index: 9999;
                        padding: 10px; border-radius: 5px; font-size: 12px;">
                <h4 style="margin: 0 0 10px 0;">📊 Current View</h4>
                <p><strong>Variable:</strong> {self.current_variable}</p>
                <p><strong>Date:</strong> {str(self.current_date).split()[0]}</p>
                <p><strong>Value:</strong> {center_value_legend}</p>
                <p><strong>Heatmap Points:</strong> {len(heatmap_data)}</p>
                <hr>
                <p style="font-size: 10px; color: #666;">
                ✓ Data from table<br>
                ✓ {scale}m radius<br>
                ✓ Hover marker for details
                </p>
            </div>
            """
            m.get_root().html.add_child(folium.Element(legend_html))
            
            # Add fullscreen
            plugins.Fullscreen().add_to(m)
            
            # Save map
            temp_dir = tempfile.gettempdir()
            self.map_file_path = os.path.join(
                temp_dir,
                f"gee_map_{self.current_date}_{self.current_variable}.html"
            )
            m.save(self.map_file_path)
            
            # Load in embedded viewer
            self.map_viewer.load_html(self.map_file_path)
            
        except Exception as e:
            print(f"Error generating map: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def destroy(self):
        """Clean up and close."""
        if self.map_file_path and os.path.exists(self.map_file_path):
            try:
                os.remove(self.map_file_path)
            except:
                pass
        super().destroy()