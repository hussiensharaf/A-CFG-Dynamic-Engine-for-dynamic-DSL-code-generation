"""
Google Earth Engine Map Visualization - Interactive Browser Version
All controls embedded in the HTML map for seamless interaction.
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
    Map visualization window that generates interactive HTML with embedded controls.
    """
    
    def __init__(self, parent, gee_metadata: Optional[Dict] = None, data: Optional[pd.DataFrame] = None):
        super().__init__(parent)
        
        self.title("Google Earth Engine - Interactive Map Generator")
        self.geometry("600x700")
        
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
• 🎨 Live Heatmap - Updates in real-time
• 📍 Data Marker - Shows exact values
• 🔍 Zoom & Pan - Explore the map
• 📏 Collection Circle - Shows data radius
• 🎮 Play/Pause - Animate through dates
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
            "Please execute a GEE query first."
        )
        self.info_text.configure(state="disabled")
        self.open_map_btn.configure(state="disabled")
    
    def generate_interactive_map(self):
        """Generate fully interactive HTML map with embedded controls."""
        try:
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

✓ Interactive map generated!
✓ All controls embedded in browser
✓ Real-time updates enabled

Click "Open Interactive Map" to view
            """
            
            self.info_text.insert("1.0", info)
            self.info_text.configure(state="disabled")
            
            # Prepare data for JavaScript
            dates = []
            if 'date' in self.data.columns:
                dates = self.data['date'].astype(str).str.split().str[0].tolist()
            else:
                dates = [f"Day {i+1}" for i in range(len(self.data))]
            
            numeric_cols = self.data.select_dtypes(include=[np.number]).columns.tolist()
            
            # Create data dictionary for JavaScript
            data_dict = {
                'dates': dates,
                'variables': numeric_cols,
                'data': {}
            }
            
            # Organize data by date
            for idx, row in self.data.iterrows():
                date_key = dates[idx]
                data_dict['data'][date_key] = {
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
            self.map_file_path = os.path.join(temp_dir, "gee_interactive_map.html")
            m.save(self.map_file_path)
            
            # Enable button
            self.open_map_btn.configure(state="normal")
            
            # Auto-open
            self.open_map()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate map:\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def create_interactive_controls_html(self, data_dict, lat, lon, scale):
        """Create HTML with embedded interactive controls and JavaScript logic."""
        
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
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                z-index: 9999;
                width: 320px;
                font-family: Arial, sans-serif;
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
            }}
            
            .date-display {{
                font-size: 14px;
                font-weight: bold;
                color: #2B7A0B;
                margin-bottom: 8px;
                text-align: center;
                padding: 5px;
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
            }}
            
            .date-slider::-webkit-slider-thumb {{
                -webkit-appearance: none;
                appearance: none;
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background: #2B7A0B;
                cursor: pointer;
            }}
            
            .date-slider::-moz-range-thumb {{
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background: #2B7A0B;
                cursor: pointer;
                border: none;
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
            }}
            
            .play-btn:hover {{
                background: #1f5a08;
            }}
            
            .data-display {{
                margin-top: 15px;
                padding: 10px;
                background: #f8f8f8;
                border-radius: 5px;
                font-size: 12px;
            }}
            
            .data-value {{
                margin: 5px 0;
                display: flex;
                justify-content: space-between;
            }}
            
            .data-value-label {{
                font-weight: bold;
                color: #555;
            }}
            
            .data-value-number {{
                color: #2B7A0B;
                font-weight: bold;
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
            
            <div class="data-display" id="data-display">
                <strong>Current Values:</strong>
                <div id="data-values"></div>
            </div>
        </div>
        
        <div class="legend">
            <strong>📍 Location:</strong> {lat}°, {lon}°<br>
            <strong>📏 Radius:</strong> {scale}m<br>
            <strong>✓</strong> Data from table<br>
            <strong>✓</strong> Real-time updates
        </div>
        
        <script>
            // Data from Python
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
            let markerLayer = null;
            
            // Initialize
            window.addEventListener('load', function() {{
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
                
                // Set initial date
                currentDateIndex = Math.floor(DATA.dates.length / 2);
                slider.value = currentDateIndex;
            }}
            
            function updateMap() {{
                const currentDate = DATA.dates[currentDateIndex];
                const dateData = DATA.data[currentDate];
                
                // Update date display
                document.getElementById('date-display').textContent = currentDate;
                
                // Update data display
                let dataHTML = '';
                for (const [varName, value] of Object.entries(dateData)) {{
                    const valueStr = value !== null ? value.toFixed(4) : 'N/A';
                    const highlight = varName === currentVariable ? 'color: #2B7A0B; font-weight: bold;' : '';
                    dataHTML += `
                        <div class="data-value" style="${{highlight}}">
                            <span class="data-value-label">${{varName}}:</span>
                            <span class="data-value-number">${{valueStr}}</span>
                        </div>
                    `;
                }}
                document.getElementById('data-values').innerHTML = dataHTML;
                
                // Update heatmap
                updateHeatmap(currentDate, currentVariable, dateData[currentVariable]);
                
                // Update marker popup
                updateMarker(currentDate, dateData);
            }}
            
            function updateHeatmap(date, variable, centerValue) {{
                if (centerValue === null || centerValue === undefined) return;
                
                // Remove existing heatmap
                if (heatmapLayer) {{
                    window.map.removeLayer(heatmapLayer);
                }}
                
                // Generate heatmap points
                const heatmapData = generateHeatmapPoints(centerValue);
                
                // Create new heatmap
                heatmapLayer = L.heatLayer(heatmapData, {{
                    radius: 25,
                    blur: 20,
                    maxZoom: 17,
                    max: 1.0,
                    minOpacity: 0.2,
                    gradient: {{0.0: 'blue', 0.5: 'lime', 1.0: 'red'}}
                }}).addTo(window.map);
            }}
            
            function generateHeatmapPoints(centerValue) {{
                const points = [];
                const numPoints = 100;
                const latOffset = SCALE / 111320;
                const lonOffset = SCALE / (111320 * Math.cos(CENTER_LAT * Math.PI / 180));
                
                for (let i = 0; i < numPoints; i++) {{
                    const r = Math.sqrt(Math.random());
                    const theta = Math.random() * 2 * Math.PI;
                    
                    const lat = CENTER_LAT + r * latOffset * Math.cos(theta);
                    const lon = CENTER_LON + r * lonOffset * Math.sin(theta);
                    
                    // Gradient: stronger at center
                    const distanceFactor = 1 - (r * 0.3);
                    const noise = (Math.random() - 0.5) * 0.1;
                    const intensity = Math.max(0, distanceFactor + noise);
                    
                    points.push([lat, lon, intensity]);
                }}
                
                return points;
            }}
            
            function updateMarker(date, dateData) {{
                let popupHTML = `
                    <div style="font-family: Arial; min-width: 200px;">
                        <h4 style="color: #2B7A0B; margin: 5px 0;">📍 ${{date}}</h4>
                        <hr style="margin: 5px 0;">
                `;
                
                for (const [varName, value] of Object.entries(dateData)) {{
                    const valueStr = value !== null ? value.toFixed(4) : 'N/A';
                    popupHTML += `<p style="margin: 3px 0;"><strong>${{varName}}:</strong> ${{valueStr}}</p>`;
                }}
                
                popupHTML += `
                        <hr style="margin: 5px 0;">
                        <p style="font-size: 11px; color: #666;">
                        Location: ${{CENTER_LAT.toFixed(4)}}°, ${{CENTER_LON.toFixed(4)}}°
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
                }} else {{
                    // Start
                    isPlaying = true;
                    btn.textContent = '⏸ Pause';
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
            }}
        </script>
        """
        
        return html
    
    def open_map(self):
        """Open the interactive map in browser."""
        if self.map_file_path and os.path.exists(self.map_file_path):
            webbrowser.open('file://' + self.map_file_path)
        else:
            messagebox.showwarning("No Map", "Map file not found. Please generate again.")
    
    def destroy(self):
        """Clean up and close."""
        if self.map_file_path and os.path.exists(self.map_file_path):
            try:
                os.remove(self.map_file_path)
            except:
                pass
        super().destroy()