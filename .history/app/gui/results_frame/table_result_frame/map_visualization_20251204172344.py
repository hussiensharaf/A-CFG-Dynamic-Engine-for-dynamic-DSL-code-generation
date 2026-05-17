"""
Google Earth Engine Map Visualization - Complete Interactive Version
Combines perfect heatmap rendering with full interactive controls in browser.
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
from datetime import datetime
import json


class MapVisualizationWindow(ctk.CTkToplevel):
    """
    Complete map visualization with interactive controls and perfect heatmap rendering.
    """
    
    def __init__(self, parent, gee_metadata: Optional[Dict] = None, data: Optional[pd.DataFrame] = None):
        super().__init__(parent)
        
        self.title("Google Earth Engine - Interactive Heatmap Visualization")
        self.geometry("600x750")
        
        # Store metadata and data
        self.gee_metadata = gee_metadata
        self.data = data
        
        # Map file path
        self.map_file_path = None
        
        # Set window properties
        self.transient(parent)
        self.grab_set()
        
        # Create UI
        self.create_widgets()
        
        # Initialize and generate
        if self.gee_metadata and self.data is not None and not self.data.empty:
            self.generate_interactive_map()
        else:
            self.show_no_data_message()
    
    def create_widgets(self):
        """Create UI widgets."""
        # Title
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkLabel(
            title_frame,
            text="🗺️ Interactive GEE Heatmap",
            font=("Arial", 22, "bold")
        ).pack()
        
        # Info section
        info_frame = ctk.CTkFrame(self)
        info_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        ctk.CTkLabel(
            info_frame,
            text="📊 Map Information",
            font=("Arial", 14, "bold")
        ).pack(anchor="w", padx=15, pady=(10, 5))
        
        self.info_text = ctk.CTkTextbox(
            info_frame,
            font=("Consolas", 11),
            wrap="word"
        )
        self.info_text.pack(fill="both", expand=True, padx=15, pady=10)
        
        # Features section
        features_frame = ctk.CTkFrame(self)
        features_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            features_frame,
            text="✨ Interactive Features in Browser:",
            font=("Arial", 13, "bold")
        ).pack(anchor="w", padx=15, pady=(10, 5))
        
        features_text = """
• 📅 Date Slider - Navigate through time
• 📊 Variable Selector - Switch between data types
• 🎨 Live Heatmap - Updates in real-time with smooth gradients
• 📍 Data Marker - Shows exact values for all variables
• 🔍 Zoom & Pan - Explore the map freely
• 📏 Collection Circle - Shows data collection radius
• 🎮 Play/Pause - Animate through dates automatically
• 🔄 Reset - Return to initial state
        """
        
        ctk.CTkLabel(
            features_frame,
            text=features_text,
            font=("Arial", 11),
            justify="left",
            anchor="w"
        ).pack(anchor="w", padx=30, pady=5)
        
        # Buttons
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=15)
        
        self.open_map_btn = ctk.CTkButton(
            button_frame,
            text="🌍 Open Interactive Map",
            command=self.open_map,
            height=45,
            font=("Arial", 14, "bold"),
            fg_color="#2B7A0B",
            hover_color="#1f5a08"
        )
        self.open_map_btn.pack(fill="x", pady=5)
        
        self.regenerate_btn = ctk.CTkButton(
            button_frame,
            text="🔄 Regenerate Map",
            command=self.generate_interactive_map,
            height=35,
            fg_color="#0066CC",
            hover_color="#004499"
        )
        self.regenerate_btn.pack(fill="x", pady=5)
        
        ctk.CTkButton(
            button_frame,
            text="Close",
            command=self.destroy,
            height=35,
            fg_color="#B22222",
            hover_color="#8B0000"
        ).pack(fill="x", pady=5)
    
    def show_no_data_message(self):
        """Show message when no data available."""
        self.info_text.insert("1.0",
            "⚠️ No Google Earth Engine data detected.\n\n"
            "Please execute a GEE query first to visualize data."
        )
        self.info_text.configure(state="disabled")
        self.open_map_btn.configure(state="disabled")
        self.regenerate_btn.configure(state="disabled")
    
    def generate_heatmap_points_for_value(self, center_value: float, lat: float, lon: float, scale: float) -> List[Tuple[float, float, float]]:
        """
        Generate heatmap points with gradient distribution.
        This is the key function from the first code that creates perfect heatmaps.
        """
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
    
    def generate_interactive_map(self):
        """Generate fully interactive HTML map with embedded controls and perfect heatmaps."""
        try:
            self.open_map_btn.configure(state="disabled", text="⏳ Generating...")
            self.update()
            
            lat = self.gee_metadata.get('latitude')
            lon = self.gee_metadata.get('longitude')
            scale = self.gee_metadata.get('scale')
            start_date = self.gee_metadata.get('start_date')
            end_date = self.gee_metadata.get('end_date')
            
            # Display info
            info = f"""Query Information:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌍 Location: ({lat}°, {lon}°)
📏 Radius: {scale}m
📅 Date Range: {start_date} to {end_date}
📊 Data Points: {len(self.data)} days
📈 Variables: {len(self.data.select_dtypes(include=[np.number]).columns)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ Interactive map with controls
✓ Perfect heatmap rendering
✓ Real-time variable switching
✓ Smooth date animation

Status: Generating map data...
            """
            
            self.info_text.delete("1.0", "end")
            self.info_text.insert("1.0", info)
            self.update()
            
            # Prepare dates
            dates = []
            if 'date' in self.data.columns:
                dates = self.data['date'].astype(str).str.split().str[0].tolist()
            else:
                dates = [f"Day {i+1}" for i in range(len(self.data))]
            
            numeric_cols = self.data.select_dtypes(include=[np.number]).columns.tolist()
            
            # PRE-GENERATE ALL HEATMAP DATA for smooth transitions
            # This is crucial for perfect heatmap rendering
            all_heatmap_data = {}
            
            print("Generating heatmap data...")
            for idx, row in self.data.iterrows():
                date_key = dates[idx]
                all_heatmap_data[date_key] = {}
                
                for var in numeric_cols:
                    value = row[var]
                    if pd.notna(value):
                        # Generate heatmap points for this date/variable combination
                        heatmap_points = self.generate_heatmap_points_for_value(
                            value, lat, lon, scale
                        )
                        # Convert to list of lists for JSON serialization
                        all_heatmap_data[date_key][var] = [[p[0], p[1], p[2]] for p in heatmap_points]
                        if idx == 0 and var == numeric_cols[0]:
                            print(f"Sample heatmap point: {all_heatmap_data[date_key][var][0]}")
                    else:
                        all_heatmap_data[date_key][var] = []
            
            print(f"Generated heatmap data for {len(all_heatmap_data)} dates")
            
            # Create data dictionary for JavaScript
            data_dict = {
                'dates': dates,
                'variables': numeric_cols,
                'values': {},  # Actual data values
                'heatmaps': all_heatmap_data  # Pre-generated heatmap points
            }
            
            # Organize values by date
            for idx, row in self.data.iterrows():
                date_key = dates[idx]
                data_dict['values'][date_key] = {
                    var: float(row[var]) if pd.notna(row[var]) else None
                    for var in numeric_cols
                }
            
            # Create base map
            m = folium.Map(
                location=[lat, lon],
                zoom_start=13,
                tiles="OpenStreetMap"
            )
            
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
            
            # Add center marker (will be updated by JavaScript)
            folium.Marker(
                location=[lat, lon],
                popup="<div id='marker-popup'>Loading...</div>",
                tooltip="Data Point",
                icon=folium.Icon(color='red', icon='info-sign', prefix='glyphicon')
            ).add_to(m)
            
            # Add Leaflet.heat plugin (required for heatmaps)
            heat_plugin = """
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
            <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/leaflet.heat@0.2.0/dist/leaflet-heat.min.js"></script>
            """
            m.get_root().html.add_child(folium.Element(heat_plugin))
            
            # Add custom HTML/CSS/JavaScript for interactive controls
            custom_html = self.create_interactive_controls_html(
                data_dict, lat, lon, scale
            )
            
            # Add to map
            m.get_root().html.add_child(folium.Element(custom_html))
            
            # Add fullscreen
            plugins.Fullscreen().add_to(m)
            
            # Save map
            temp_dir = tempfile.gettempdir()
            self.map_file_path = os.path.join(temp_dir, "gee_interactive_complete_map.html")
            m.save(self.map_file_path)
            
            # Update info
            final_info = info.replace("Status: Generating map data...", "✅ Map ready! Click button to open.")
            self.info_text.delete("1.0", "end")
            self.info_text.insert("1.0", final_info)
            
            # Enable buttons
            self.open_map_btn.configure(state="normal", text="🌍 Open Interactive Map")
            self.regenerate_btn.configure(state="normal")
            
            # Auto-open
            self.open_map()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate map:\n{str(e)}")
            self.open_map_btn.configure(state="normal", text="🌍 Open Interactive Map")
            import traceback
            traceback.print_exc()
    
    def create_interactive_controls_html(self, data_dict, lat, lon, scale):
        """Create HTML with embedded interactive controls and perfect heatmap rendering."""
        
        data_json = json.dumps(data_dict)
        
        html = f"""
        <style>
            .control-panel {{
                position: fixed;
                top: 10px;
                left: 10px;
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.3);
                z-index: 9999;
                width: 320px;
                font-family: Arial, sans-serif;
                max-height: 90vh;
                overflow-y: auto;
            }}
            
            .control-title {{
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 15px;
                color: #2B7A0B;
                display: flex;
                align-items: center;
                gap: 8px;
            }}
            
            .control-group {{
                margin-bottom: 15px;
            }}
            
            .control-label {{
                font-weight: bold;
                margin-bottom: 5px;
                font-size: 13px;
                color: #333;
            }}
            
            .control-select {{
                width: 100%;
                padding: 8px;
                border: 2px solid #2B7A0B;
                border-radius: 5px;
                font-size: 13px;
                background: white;
                cursor: pointer;
            }}
            
            .control-select:hover {{
                background: #f0f0f0;
            }}
            
            .date-display {{
                font-size: 14px;
                font-weight: bold;
                color: #2B7A0B;
                margin-bottom: 8px;
                text-align: center;
                padding: 8px;
                background: #f0f0f0;
                border-radius: 5px;
            }}
            
            .slider-container {{
                width: 100%;
                margin: 10px 0;
            }}
            
            .date-slider {{
                width: 100%;
                height: 8px;
                border-radius: 5px;
                background: #ddd;
                outline: none;
                -webkit-appearance: none;
                cursor: pointer;
            }}
            
            .date-slider::-webkit-slider-thumb {{
                -webkit-appearance: none;
                appearance: none;
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background: #2B7A0B;
                cursor: pointer;
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }}
            
            .date-slider::-moz-range-thumb {{
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background: #2B7A0B;
                cursor: pointer;
                border: none;
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }}
            
            .play-controls {{
                display: flex;
                gap: 10px;
                margin-top: 10px;
            }}
            
            .play-btn {{
                flex: 1;
                padding: 10px;
                background: #2B7A0B;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-weight: bold;
                font-size: 13px;
                transition: background 0.2s;
            }}
            
            .play-btn:hover {{
                background: #1f5a08;
            }}
            
            .play-btn:active {{
                transform: scale(0.98);
            }}
            
            .data-display {{
                margin-top: 15px;
                padding: 12px;
                background: #f8f8f8;
                border-radius: 5px;
                font-size: 12px;
                border: 1px solid #e0e0e0;
            }}
            
            .data-display-title {{
                font-weight: bold;
                margin-bottom: 8px;
                color: #2B7A0B;
            }}
            
            .data-value {{
                margin: 5px 0;
                display: flex;
                justify-content: space-between;
                padding: 3px 0;
            }}
            
            .data-value-label {{
                font-weight: bold;
                color: #555;
            }}
            
            .data-value-number {{
                color: #2B7A0B;
                font-weight: bold;
            }}
            
            .data-value.highlighted {{
                background: #e8f5e9;
                padding: 5px;
                border-radius: 3px;
                margin: 3px -5px;
            }}
            
            .legend {{
                position: fixed;
                bottom: 30px;
                right: 10px;
                background: white;
                padding: 15px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                z-index: 9999;
                font-size: 11px;
                max-width: 200px;
            }}
            
            .legend-title {{
                font-weight: bold;
                margin-bottom: 8px;
                color: #2B7A0B;
            }}
            
            .status-indicator {{
                display: inline-block;
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: #4CAF50;
                margin-right: 5px;
                animation: pulse 2s infinite;
            }}
            
            @keyframes pulse {{
                0%, 100% {{ opacity: 1; }}
                50% {{ opacity: 0.5; }}
            }}
        </style>
        
        <div class="control-panel">
            <div class="control-title">
                🎮 Interactive Controls
            </div>
            
            <div class="control-group">
                <div class="control-label">📊 Variable</div>
                <select id="variable-select" class="control-select">
                </select>
            </div>
            
            <div class="control-group">
                <div class="control-label">📅 Date</div>
                <div class="date-display" id="date-display">Loading...</div>
                <div class="slider-container">
                    <input type="range" id="date-slider" class="date-slider" min="0" max="0" value="0">
                </div>
                <div class="play-controls">
                    <button class="play-btn" id="play-btn" onclick="togglePlay()">▶ Play</button>
                    <button class="play-btn" id="reset-btn" onclick="resetSlider()">↻ Reset</button>
                </div>
            </div>
            
            <div class="data-display">
                <div class="data-display-title">Current Values:</div>
                <div id="data-values"></div>
            </div>
        </div>
        
        <div class="legend">
            <div class="legend-title">📍 Map Info</div>
            <strong>Location:</strong> {lat:.4f}°, {lon:.4f}°<br>
            <strong>Radius:</strong> {scale}m<br>
            <br>
            <span class="status-indicator"></span> <strong>Live Updates</strong><br>
            ✓ Pre-generated heatmaps<br>
            ✓ Smooth transitions
        </div>
        
        <script>
            // Data from Python - includes pre-generated heatmap points
            const DATA = {data_json};
            const CENTER_LAT = {lat};
            const CENTER_LON = {lon};
            const SCALE = {scale};
            
            // State
            let currentDateIndex = 0;
            let currentVariable = null;
            let isPlaying = false;
            let playInterval = null;
            let heatmapLayer = null;
            
            // Initialize
            window.addEventListener('load', function() {{
                console.log('=== MAP INITIALIZATION ===');
                console.log('Initializing interactive map...');
                console.log('Data loaded:', DATA.dates.length, 'dates,', DATA.variables.length, 'variables');
                console.log('First date:', DATA.dates[0]);
                console.log('Variables:', DATA.variables);
                console.log('Sample heatmap data structure:', DATA.heatmaps[DATA.dates[0]]);
                
                // Check if leaflet.heat is loaded
                if (typeof L !== 'undefined' && typeof L.heatLayer !== 'undefined') {{
                    console.log('✓ Leaflet.heat plugin loaded successfully');
                }} else {{
                    console.error('✗ Leaflet.heat plugin NOT loaded!');
                }}
                
                initializeControls();
                updateMap();
            }});
            
            function initializeControls() {{
                // Populate variable selector
                const varSelect = document.getElementById('variable-select');
                DATA.variables.forEach((varName, idx) => {{
                    const option = document.createElement('option');
                    option.value = varName;
                    option.textContent = varName;
                    varSelect.appendChild(option);
                    if (idx === 0) currentVariable = varName;
                }});
                
                varSelect.addEventListener('change', function() {{
                    currentVariable = this.value;
                    console.log('Variable changed to:', currentVariable);
                    updateMap();
                }});
                
                // Setup date slider
                const slider = document.getElementById('date-slider');
                slider.max = DATA.dates.length - 1;
                slider.value = 0;
                
                slider.addEventListener('input', function() {{
                    currentDateIndex = parseInt(this.value);
                    updateMap();
                }});
                
                // Set initial date (middle of range)
                currentDateIndex = Math.floor(DATA.dates.length / 2);
                slider.value = currentDateIndex;
                
                console.log('Controls initialized. Starting at date index:', currentDateIndex);
            }}
            
            function updateMap() {{
                const currentDate = DATA.dates[currentDateIndex];
                const dateValues = DATA.values[currentDate];
                const heatmapPoints = DATA.heatmaps[currentDate][currentVariable];
                
                console.log('=== UPDATE MAP ===');
                console.log('Current date:', currentDate, '(index:', currentDateIndex, ')');
                console.log('Current variable:', currentVariable);
                console.log('Heatmap points:', heatmapPoints ? heatmapPoints.length : 'null', 'points');
                if (heatmapPoints && heatmapPoints.length > 0) {{
                    console.log('First heatmap point:', heatmapPoints[0]);
                }}
                
                // Update date display
                document.getElementById('date-display').textContent = currentDate;
                
                // Update data display
                let dataHTML = '';
                for (const [varName, value] of Object.entries(dateValues)) {{
                    const valueStr = value !== null ? value.toFixed(4) : 'N/A';
                    const isHighlighted = varName === currentVariable;
                    const highlightClass = isHighlighted ? 'highlighted' : '';
                    dataHTML += `
                        <div class="data-value ${{highlightClass}}">
                            <span class="data-value-label">${{varName}}:</span>
                            <span class="data-value-number">${{valueStr}}</span>
                        </div>
                    `;
                }}
                document.getElementById('data-values').innerHTML = dataHTML;
                
                // Update heatmap using PRE-GENERATED points for perfect rendering
                updateHeatmap(heatmapPoints);
                
                // Update marker popup
                updateMarker(currentDate, dateValues);
            }}
            
            function updateHeatmap(heatmapPoints) {{
                // Remove existing heatmap
                if (heatmapLayer) {{
                    window.map.removeLayer(heatmapLayer);
                    heatmapLayer = null;
                }}
                
                // Create new heatmap from pre-generated points
                if (heatmapPoints && heatmapPoints.length > 0) {{
                    console.log('Rendering heatmap with', heatmapPoints.length, 'points');
                    console.log('Sample point:', heatmapPoints[0]);
                    
                    // Ensure we have the Leaflet heat plugin
                    if (typeof L.heatLayer === 'undefined') {{
                        console.error('Leaflet.heat plugin not loaded!');
                        return;
                    }}
                    
                    heatmapLayer = L.heatLayer(heatmapPoints, {{
                        radius: 25,
                        blur: 20,
                        max: 1.0,
                        maxZoom: 17,
                        minOpacity: 0.3,
                        gradient: {{
                            0.0: 'blue',
                            0.3: 'cyan',
                            0.5: 'lime',
                            0.7: 'yellow',
                            1.0: 'red'
                        }}
                    }}).addTo(window.map);
                    
                    console.log('Heatmap layer added successfully');
                }} else {{
                    console.log('No heatmap data for current selection');
                }}
            }}
            
            function updateMarker(date, dateValues) {{
                let popupHTML = `
                    <div style="font-family: Arial; min-width: 250px; max-width: 350px;">
                        <h4 style="color: #2B7A0B; margin: 5px 0;">📍 ${{date}}</h4>
                        <hr style="margin: 8px 0;">
                `;
                
                for (const [varName, value] of Object.entries(dateValues)) {{
                    const valueStr = value !== null ? value.toFixed(4) : 'N/A';
                    const isSelected = varName === currentVariable;
                    const style = isSelected ? 'background: #e8f5e9; padding: 5px; border-radius: 3px; font-weight: bold;' : '';
                    popupHTML += `<p style="margin: 5px 0; ${{style}}"><strong>${{varName}}:</strong> ${{valueStr}}</p>`;
                }}
                
                popupHTML += `
                        <hr style="margin: 8px 0;">
                        <p style="font-size: 11px; color: #666; margin: 3px 0;">
                        <strong>Location:</strong> ${{CENTER_LAT.toFixed(4)}}°, ${{CENTER_LON.toFixed(4)}}°<br>
                        <strong>Radius:</strong> ${{SCALE}}m
                        </p>
                    </div>
                `;
                
                // Update popup content
                const popupDiv = document.getElementById('marker-popup');
                if (popupDiv) {{
                    popupDiv.innerHTML = popupHTML;
                }}
            }}
            
            function togglePlay() {{
                const btn = document.getElementById('play-btn');
                
                if (isPlaying) {{
                    // Stop
                    isPlaying = false;
                    btn.textContent = '▶ Play';
                    if (playInterval) {{
                        clearInterval(playInterval);
                        playInterval = null;
                    }}
                    console.log('Animation stopped');
                }} else {{
                    // Start
                    isPlaying = true;
                    btn.textContent = '⏸ Pause';
                    console.log('Animation started');
                    playInterval = setInterval(() => {{
                        currentDateIndex++;
                        if (currentDateIndex >= DATA.dates.length) {{
                            currentDateIndex = 0;
                        }}
                        document.getElementById('date-slider').value = currentDateIndex;
                        updateMap();
                    }}, 1000);  // Change every 1 second
                }}
            }}
            
            function resetSlider() {{
                currentDateIndex = 0;
                document.getElementById('date-slider').value = 0;
                updateMap();
                
                if (isPlaying) {{
                    togglePlay();  // Stop if playing
                }}
                
                console.log('Reset to first date');
            }}
        </script>
        """
        
        return html
    
    def open_map(self):
        """Open the interactive map in browser."""
        if self.map_file_path and os.path.exists(self.map_file_path):
            webbrowser.open('file://' + self.map_file_path)
        else:
            messagebox.showwarning("No Map", "Map file not found. Please generate the map first.")
    
    def destroy(self):
        """Clean up and close."""
        if self.map_file_path and os.path.exists(self.map_file_path):
            try:
                os.remove(self.map_file_path)
            except:
                pass
        super().destroy()