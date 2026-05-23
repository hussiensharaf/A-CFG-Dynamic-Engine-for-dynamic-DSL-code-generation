"""
Map Viewer for Google Earth Engine Data Visualization
Place this file in: app/gui/map_viewer.py
"""

import customtkinter as ctk
import tkinter as tk
from tkinterweb import HtmlFrame
import folium
from folium import plugins
import tempfile
import os
import json
import ee

class MapViewerWindow(ctk.CTkToplevel):
    """
    A popup window that displays Google Earth Engine data on an interactive map
    """
    
    def __init__(self, parent, gee_data=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        self.title("GEE Data Map Viewer")
        self.geometry("1200x800")
        
        # Make window modal
        self.transient(parent)
        self.grab_set()
        
        self.gee_data = gee_data
        self.temp_html_path = None
        
        self._setup_ui()
        self._render_map()
        
    def _setup_ui(self):
        """Setup the UI components"""
        
        # Control panel at top
        control_frame = ctk.CTkFrame(self, height=60)
        control_frame.pack(fill="x", padx=10, pady=5)
        control_frame.pack_propagate(False)
        
        # Title
        title_label = ctk.CTkLabel(
            control_frame, 
            text="Google Earth Engine Map Viewer",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title_label.pack(side="left", padx=20, pady=10)
        
        # Refresh button
        refresh_btn = ctk.CTkButton(
            control_frame,
            text="Refresh Map",
            command=self._render_map,
            width=120
        )
        refresh_btn.pack(side="right", padx=10, pady=10)
        
        # Export button
        export_btn = ctk.CTkButton(
            control_frame,
            text="Export HTML",
            command=self._export_map,
            width=120
        )
        export_btn.pack(side="right", padx=5, pady=10)
        
        # Map display frame
        map_frame = ctk.CTkFrame(self)
        map_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # HTML viewer for the map
        try:
            self.html_viewer = HtmlFrame(map_frame, messages_enabled=False)
            self.html_viewer.pack(fill="both", expand=True)
        except Exception as e:
            # Fallback to text display if tkinterweb is not available
            error_label = ctk.CTkLabel(
                map_frame,
                text=f"Map viewer not available. Install tkinterweb: pip install tkinterweb\nError: {str(e)}",
                font=ctk.CTkFont(size=12)
            )
            error_label.pack(expand=True)
            self.html_viewer = None
    
    def _render_map(self):
        """Render the GEE data on a folium map"""
        
        if self.gee_data is None:
            self._show_empty_map()
            return
        
        try:
            # Create folium map
            m = folium.Map(
                location=[0, 0],  # Will be updated based on data
                zoom_start=2,
                tiles='OpenStreetMap'
            )
            
            # Add additional tile layers
            folium.TileLayer('Stamen Terrain').add_to(m)
            folium.TileLayer('Stamen Toner').add_to(m)
            folium.TileLayer('CartoDB positron').add_to(m)
            
            # Process GEE data
            self._add_gee_data_to_map(m)
            
            # Add layer control
            folium.LayerControl().add_to(m)
            
            # Add fullscreen button
            plugins.Fullscreen().add_to(m)
            
            # Add mouse position
            plugins.MousePosition().add_to(m)
            
            # Save to temporary HTML file
            if self.temp_html_path and os.path.exists(self.temp_html_path):
                os.remove(self.temp_html_path)
            
            fd, self.temp_html_path = tempfile.mkstemp(suffix='.html')
            os.close(fd)
            m.save(self.temp_html_path)
            
            # Display in HTML viewer
            if self.html_viewer:
                self.html_viewer.load_file(self.temp_html_path)
            
        except Exception as e:
            self._show_error_map(str(e))
    
    def _add_gee_data_to_map(self, folium_map):
        """Add GEE data to the folium map"""
        
        # Handle different types of GEE data
        if isinstance(self.gee_data, ee.Image):
            self._add_image_to_map(folium_map, self.gee_data)
        elif isinstance(self.gee_data, ee.FeatureCollection):
            self._add_feature_collection_to_map(folium_map, self.gee_data)
        elif isinstance(self.gee_data, ee.Geometry):
            self._add_geometry_to_map(folium_map, self.gee_data)
        elif isinstance(self.gee_data, dict):
            self._add_dict_data_to_map(folium_map, self.gee_data)
        elif isinstance(self.gee_data, list):
            self._add_list_data_to_map(folium_map, self.gee_data)
        else:
            # Try to convert to GeoJSON
            self._add_geojson_to_map(folium_map, self.gee_data)
    
    def _add_image_to_map(self, folium_map, image):
        """Add EE Image to map"""
        try:
            # Get image thumbnail URL
            vis_params = {
                'min': 0,
                'max': 3000,
                'palette': ['blue', 'green', 'red']
            }
            
            map_id = image.getMapId(vis_params)
            
            # Add tile layer
            folium.TileLayer(
                tiles=map_id['tile_fetcher'].url_format,
                attr='Google Earth Engine',
                name='EE Image Layer',
                overlay=True,
                control=True
            ).add_to(folium_map)
            
            # Center map on image bounds
            bounds = image.geometry().bounds().getInfo()['coordinates'][0]
            folium_map.fit_bounds([[bounds[0][1], bounds[0][0]], 
                                   [bounds[2][1], bounds[2][0]]])
            
        except Exception as e:
            print(f"Error adding image: {e}")
            # Add a marker to show there's data
            folium.Marker([0, 0], popup=f"EE Image (visualization error: {e})").add_to(folium_map)
    
    def _add_feature_collection_to_map(self, folium_map, fc):
        """Add EE FeatureCollection to map"""
        try:
            # Convert to GeoJSON
            geojson = fc.getInfo()
            
            # Add GeoJSON to map
            folium.GeoJson(
                geojson,
                name='Feature Collection',
                style_function=lambda x: {
                    'fillColor': 'blue',
                    'color': 'darkblue',
                    'weight': 2,
                    'fillOpacity': 0.4
                },
                highlight_function=lambda x: {
                    'fillColor': 'red',
                    'color': 'darkred',
                    'weight': 3,
                    'fillOpacity': 0.7
                },
                tooltip=folium.GeoJsonTooltip(fields=list(geojson['features'][0]['properties'].keys()) if geojson['features'] else [])
            ).add_to(folium_map)
            
            # Fit bounds
            if geojson['features']:
                coords = []
                for feature in geojson['features']:
                    if feature['geometry']['type'] == 'Point':
                        coords.append(feature['geometry']['coordinates'][::-1])
                    elif feature['geometry']['type'] in ['Polygon', 'MultiPolygon']:
                        geom_coords = feature['geometry']['coordinates']
                        if feature['geometry']['type'] == 'Polygon':
                            for coord in geom_coords[0]:
                                coords.append(coord[::-1])
                        else:
                            for poly in geom_coords:
                                for coord in poly[0]:
                                    coords.append(coord[::-1])
                
                if coords:
                    folium_map.fit_bounds(coords)
            
        except Exception as e:
            print(f"Error adding feature collection: {e}")
            folium.Marker([0, 0], popup=f"Feature Collection (error: {e})").add_to(folium_map)
    
    def _add_geometry_to_map(self, folium_map, geometry):
        """Add EE Geometry to map"""
        try:
            geojson = geometry.getInfo()
            
            folium.GeoJson(
                geojson,
                name='Geometry',
                style_function=lambda x: {
                    'fillColor': 'green',
                    'color': 'darkgreen',
                    'weight': 2,
                    'fillOpacity': 0.3
                }
            ).add_to(folium_map)
            
            # Center on geometry
            bounds = geometry.bounds().getInfo()['coordinates'][0]
            folium_map.fit_bounds([[bounds[0][1], bounds[0][0]], 
                                   [bounds[2][1], bounds[2][0]]])
            
        except Exception as e:
            print(f"Error adding geometry: {e}")
    
    def _add_dict_data_to_map(self, folium_map, data):
        """Add dictionary data (likely GeoJSON format)"""
        try:
            # Check if it's GeoJSON format
            if 'type' in data and 'features' in data:
                folium.GeoJson(
                    data,
                    name='GeoJSON Data',
                    style_function=lambda x: {
                        'fillColor': 'orange',
                        'color': 'darkorange',
                        'weight': 2,
                        'fillOpacity': 0.4
                    }
                ).add_to(folium_map)
            else:
                # Try to display as JSON popup
                folium.Marker(
                    [0, 0],
                    popup=folium.Popup(f"<pre>{json.dumps(data, indent=2)}</pre>", max_width=400)
                ).add_to(folium_map)
        except Exception as e:
            print(f"Error adding dict data: {e}")
    
    def _add_list_data_to_map(self, folium_map, data):
        """Add list data (likely coordinates or feature list)"""
        try:
            for idx, item in enumerate(data):
                if isinstance(item, dict):
                    if 'lat' in item and 'lon' in item:
                        folium.Marker(
                            [item['lat'], item['lon']],
                            popup=f"Point {idx}: {item}"
                        ).add_to(folium_map)
                    elif 'latitude' in item and 'longitude' in item:
                        folium.Marker(
                            [item['latitude'], item['longitude']],
                            popup=f"Point {idx}: {item}"
                        ).add_to(folium_map)
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    folium.Marker(
                        [item[0], item[1]],
                        popup=f"Point {idx}"
                    ).add_to(folium_map)
        except Exception as e:
            print(f"Error adding list data: {e}")
    
    def _add_geojson_to_map(self, folium_map, data):
        """Try to add data as GeoJSON"""
        try:
            folium.GeoJson(data, name='Data Layer').add_to(folium_map)
        except Exception as e:
            print(f"Error adding GeoJSON: {e}")
            self._show_empty_map()
    
    def _show_empty_map(self):
        """Show an empty map when no data is available"""
        m = folium.Map(location=[0, 0], zoom_start=2)
        folium.Marker(
            [0, 0],
            popup="No GEE data to display",
            icon=folium.Icon(color='red')
        ).add_to(m)
        
        if self.temp_html_path and os.path.exists(self.temp_html_path):
            os.remove(self.temp_html_path)
        
        fd, self.temp_html_path = tempfile.mkstemp(suffix='.html')
        os.close(fd)
        m.save(self.temp_html_path)
        
        if self.html_viewer:
            self.html_viewer.load_file(self.temp_html_path)
    
    def _show_error_map(self, error_msg):
        """Show error on map"""
        m = folium.Map(location=[0, 0], zoom_start=2)
        folium.Marker(
            [0, 0],
            popup=f"Error rendering map: {error_msg}",
            icon=folium.Icon(color='red')
        ).add_to(m)
        
        if self.temp_html_path and os.path.exists(self.temp_html_path):
            os.remove(self.temp_html_path)
        
        fd, self.temp_html_path = tempfile.mkstemp(suffix='.html')
        os.close(fd)
        m.save(self.temp_html_path)
        
        if self.html_viewer:
            self.html_viewer.load_file(self.temp_html_path)
    
    def _export_map(self):
        """Export the map to an HTML file"""
        try:
            from tkinter import filedialog
            
            file_path = filedialog.asksaveasfilename(
                defaultextension=".html",
                filetypes=[("HTML files", "*.html"), ("All files", "*.*")]
            )
            
            if file_path and self.temp_html_path:
                import shutil
                shutil.copy(self.temp_html_path, file_path)
                
                # Show success message
                success_window = ctk.CTkToplevel(self)
                success_window.title("Export Successful")
                success_window.geometry("300x100")
                
                label = ctk.CTkLabel(
                    success_window,
                    text=f"Map exported successfully!\n{os.path.basename(file_path)}",
                    font=ctk.CTkFont(size=12)
                )
                label.pack(expand=True, pady=20)
                
                ok_btn = ctk.CTkButton(
                    success_window,
                    text="OK",
                    command=success_window.destroy
                )
                ok_btn.pack(pady=10)
                
        except Exception as e:
            print(f"Export error: {e}")
    
    def destroy(self):
        """Clean up temporary files when closing"""
        if self.temp_html_path and os.path.exists(self.temp_html_path):
            try:
                os.remove(self.temp_html_path)
            except:
                pass
        super().destroy()