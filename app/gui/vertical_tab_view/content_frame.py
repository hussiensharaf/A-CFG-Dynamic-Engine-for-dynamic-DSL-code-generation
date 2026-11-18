import sqlparse
import os
import sys
import threading
import re
import datetime


# Add AI Assistant to path
from ai_assistant.GEEQueryAssistant import GEEQueryAssistant

try:
    from ai_assistant.GEEQueryAssistant import GEEQueryAssistant
except ImportError:
    GEEQueryAssistant = None

from typing import Any, Tuple
import customtkinter as ctk
import re


from app.core.result_monad import Success
from app.etl.controllers import compile_to_python, execute_python_code
from app.gui.error_frame.error_frame import ErrorFrame

from app.gui.results_frame.results_frame import ResultsFrame
from app.gui.vertical_tab_view.sql_textbox_colorizer import Colorizer
from tkinter import filedialog, messagebox
import csv


_AREA_NAME_KEYS = {"name", "area", "area name", "areaname", "site", "place", "location", "title", "id"}
_AREA_LON_KEYS = {"longitude", "lon", "lng", "long", "x"}
_AREA_LAT_KEYS = {"latitude", "lat", "y"}


def _read_text_file(file_path):
    """Read a text file whatever its encoding (Excel UTF-8 with BOM, Arabic Windows, etc.)."""
    with open(file_path, "rb") as f:
        raw = f.read()
    for encoding in ("utf-8-sig", "cp1256", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def _to_float(text):
    value = str(text).strip().replace(" ", "")
    if "," in value and "." not in value:
        value = value.replace(",", ".")  # decimal comma, e.g. 30,40
    return float(value)


def parse_areas_csv(file_path):
    """
    Read an areas CSV. Returns (areas, skipped_messages).
    areas = {name: {"longitude": float, "latitude": float}}
    Accepts , ; tab or | separators, any capitalisation, and the column names
    name / longitude / latitude (also lon, lng, lat, ...). The name column is optional.
    Raises ValueError with a plain-English message if the file cannot be used.
    """
    text = _read_text_file(file_path)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("The file is empty.")
    delimiter = max(",;\t|", key=lambda d: lines[0].count(d))
    if lines[0].count(delimiter) == 0:
        delimiter = ","
    rows = list(csv.reader(lines, delimiter=delimiter))
    header = [h.strip().strip("\ufeff").lower() for h in rows[0]]

    def find(keys):
        for i, h in enumerate(header):
            if h in keys:
                return i
        return None

    i_lon, i_lat, i_name = find(_AREA_LON_KEYS), find(_AREA_LAT_KEYS), find(_AREA_NAME_KEYS)
    if i_lon is None or i_lat is None:
        raise ValueError(
            "Could not find the longitude and latitude columns.\n\n"
            "The first row of the file must contain column names such as:\n"
            "name,longitude,latitude\n\n"
            "Columns found: " + ", ".join(h or "(blank)" for h in header)
        )

    areas, skipped = {}, []
    for line_no, row in enumerate(rows[1:], start=2):
        try:
            lon = _to_float(row[i_lon])
            lat = _to_float(row[i_lat])
        except (ValueError, IndexError):
            skipped.append(f"Row {line_no}: longitude or latitude is missing or is not a number")
            continue
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            skipped.append(f"Row {line_no}: coordinates out of range (are longitude and latitude swapped?)")
            continue
        name = row[i_name].strip() if i_name is not None and i_name < len(row) else ""
        name = name or f"Area {len(areas) + 1}"
        base, n = name, 2
        while name in areas:
            name, n = f"{base} ({n})", n + 1
        areas[name] = {"longitude": lon, "latitude": lat}
    if not areas:
        raise ValueError("No usable rows were found.\n\n" + "\n".join(skipped[:8]))
    return areas, skipped


def _fmt_coord(value):
    return f"{value:.6f}".rstrip("0").rstrip(".")


class TabContent(ctk.CTkFrame):
    def __init__(
        self,
        master: Any,
        width: int = 200,
        height: int = 200,
        corner_radius: int | str | None = None,
        border_width: int | str | None = None,
        bg_color: str | Tuple[str] = "transparent",
        fg_color: str | Tuple[str] | None = None,
        border_color: str | Tuple[str] | None = None,
        background_corner_colors: Tuple[str | Tuple[str]] | None = None,
        overwrite_preferred_drawing_method: str | None = None,
        **kwargs,
    ):
        super().__init__(
            master,
            width,
            height,
            corner_radius,
            border_width,
            bg_color,
            fg_color,
            border_color,
            background_corner_colors,
            overwrite_preferred_drawing_method,
            **kwargs,
        )
        self.add_children_widget()

        self.sql_textbox_theme = ctk.get_appearance_mode().lower()
        if self.sql_textbox_theme == "dark":
            self.change_sql_textbox_theme("dark")
        else:
            self.sql_textbox_theme = "light"
        
        # Store the last executed SQL query
        self.last_sql_query = ""

    def add_children_widget(self):
        self.sql_textbox = ctk.CTkTextbox(
            self, fg_color=("#ffffff", "#1e1e1e"), font=("Consolas", 24)
        )
        self.sql_textbox.bind(
            "<KeyRelease>",
            lambda _: Colorizer.highlight_syntax(
                self.sql_textbox, self.sql_textbox_theme
            ),
        )

        # Satellite selector frame
        self.satellite_frame = ctk.CTkFrame(self, fg_color="transparent")

        self.satellite_label = ctk.CTkLabel(
            self.satellite_frame,
            text="Satellite:",
            font=("Consolas", 14, "bold")
        )

        self.satellites = {
            "ERA5 Daily": "ECMWF/ERA5/DAILY",
            "ERA5 Land Daily": "ECMWF/ERA5_LAND/DAILY_AGGR",
            "Sentinel-2": "COPERNICUS/S2_SR_HARMONIZED",
            "Landsat 8": "LANDSAT/LC08/C01/T1_SR",
            "SMAP": "NASA/SMAP/SPL3SMP_E/005",
            "CHIRPS": "UCSB-CHG/CHIRPS/DAILY",
        }

        self.satellite_dropdown = ctk.CTkComboBox(
            self.satellite_frame,
            values=list(self.satellites.keys()),
            command=self.on_satellite_selected,
            width=220,
        )
        self.satellite_dropdown.set("Select Satellite...")

        self.satellite_id_label = ctk.CTkLabel(
            self.satellite_frame,
            text="",
            font=("Consolas", 12),
            text_color=("gray40", "gray60")
        )

        self.insert_satellite_btn = ctk.CTkButton(
            self.satellite_frame,
            text="Insert into Query",
            command=self.insert_satellite_into_query,
            width=140,
            height=28,
            font=("Consolas", 12),
        )

        # Area selector frame
        self.area_frame = ctk.CTkFrame(self, fg_color="transparent")

        self.area_label = ctk.CTkLabel(
            self.area_frame,
            text="Area:",
            font=("Consolas", 14, "bold")
        )

        self.load_areas_btn = ctk.CTkButton(
            self.area_frame,
            text="Load Areas CSV",
            command=self.load_areas_csv,
            width=130,
            height=28,
            font=("Consolas", 12),
        )

        self.area_dropdown = ctk.CTkComboBox(
            self.area_frame,
            values=["No areas loaded..."],
            width=200,
        )
        self.area_dropdown.set("No areas loaded...")

        self.area_mode = ctk.CTkSegmentedButton(
            self.area_frame,
            values=["Circle", "Polygon"],
            width=150,
        )
        self.area_mode.set("Polygon")

        self.insert_area_btn = ctk.CTkButton(
            self.area_frame,
            text="Insert Area",
            command=self.insert_area_into_query,
            width=110,
            height=28,
            font=("Consolas", 12),
        )

        # Store loaded areas data
        self.areas_data = {}

        # Button Frame
        self.btn_frame = ctk.CTkFrame(self, height=40, fg_color="transparent")

        # Execute Button
        self.execute_btn = ctk.CTkButton(
            self.btn_frame,
            text="Execute",
            command=self.execute_python,
            width=80,
            fg_color="#51ab46",
            hover_color="#387731",
        )

        # Compile Button
        self.run_btn = ctk.CTkButton(
            self.btn_frame,
            text="Compile",
            command=self.compile_sql,
            width=80,
        )

        self.results_section = ResultsFrame(self)
        self.error_section = ErrorFrame(
            self,
            border_width=4,
            fg_color=("#f9f9fa", "#1d1e1e"),
            border_color=("#cfcfcf", "#333333"),
            height=50,
        )

        # Pack satellite frame
        self.satellite_frame.pack(fill="x", padx=10, pady=(5, 0))
        self.satellite_label.pack(side="left", padx=5)
        self.satellite_dropdown.pack(side="left", padx=5)
        self.satellite_id_label.pack(side="left", padx=5)
        self.insert_satellite_btn.pack(side="left", padx=5)

        # Pack area frame
        self.area_frame.pack(fill="x", padx=10, pady=(2, 0))
        self.area_label.pack(side="left", padx=5)
        self.load_areas_btn.pack(side="left", padx=5)
        self.area_dropdown.pack(side="left", padx=5)
        self.area_mode.pack(side="left", padx=5)
        self.insert_area_btn.pack(side="left", padx=5)

        # Pack rest
        self.sql_textbox.pack(fill="both", expand=True, padx=10, pady=5)
        self.btn_frame.pack(fill="x", pady=5, padx=10)
        self.execute_btn.pack(side="left", padx=5)
        self.run_btn.pack(side="left", padx=5)
        self.results_section.pack(fill="both", expand=True, pady=5, padx=10)
        self.results_section.pack_propagate(False)
        self.error_section.pack(fill="x", pady=5, padx=10)
        self.error_section.pack_propagate(False)

    def _extract_gee_metadata_area(self, sql_query: str):
        """
        (Unused draft) Extract Google Earth Engine metadata from SQL query.
        Handles both circle and AREA formats.
        """
        try:
            # Check for AREA format first
            area_pattern = r'\{gee:([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|AREA\(\((.+?)\)\)\}'
            area_match = re.search(area_pattern, sql_query)

            if area_match:
                # Parse coordinates from AREA
                coord_str = area_match.group(5)
                pairs = re.findall(r'([\d.+-]+)\s*,\s*([\d.+-]+)', coord_str)
                coords = [[float(lon), float(lat)] for lon, lat in pairs]

                # Calculate center point from polygon
                center_lon = sum(c[0] for c in coords) / len(coords)
                center_lat = sum(c[1] for c in coords) / len(coords)

                return {
                    'project': area_match.group(1),
                    'dataset': area_match.group(2),
                    'start_date': area_match.group(3),
                    'end_date': area_match.group(4),
                    'longitude': center_lon,
                    'latitude': center_lat,
                    'scale': 1000,
                    'is_area': True,
                    'coordinates': coords
                }

            # Old circle format
            circle_pattern = r'\{gee:([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^}]+)\}'
            match = re.search(circle_pattern, sql_query)

            if match:
                return {
                    'project': match.group(1),
                    'dataset': match.group(2),
                    'start_date': match.group(3),
                    'end_date': match.group(4),
                    'longitude': float(match.group(5)),
                    'latitude': float(match.group(6)),
                    'scale': float(match.group(7)),
                    'is_area': False
                }

            return None
        except Exception as e:
            print(f"Error extracting GEE metadata: {e}")
            return None

    def extract_gee_metadata(self, sql: str):
        if not sql:
            return None

        pattern = re.compile(
            r'\{gee:([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^}]+)\}',
            re.IGNORECASE
        )

        matches = pattern.findall(sql)
        if not matches:
            return None

        try:
            datasets = []
            for match in matches:
                datasets.append({
                    "project": match[0],
                    "dataset": match[1],
                    "start_date": match[2],
                    "end_date": match[3],
                    "longitude": float(match[4]),
                    "latitude": float(match[5]),
                    "scale": float(match[6]),
                })
            return datasets if datasets else None
        except Exception as e:
            print(f"Error extracting GEE metadata: {e}")
            return None

    def execute_python(self):
        # Fetch Python code from the text box
        python_code = self.results_section.python_section.code_textbox.get(
            "1.0", "end-1c"
        ).strip()
        if not python_code:
            self.results_section.python_section.clear_code()
            self.results_section.table_section.clear_table()
            self.error_section.clear_error()
            return
        
        execution_result = execute_python_code(python_code)
        
        if isinstance(execution_result, Success):
            # Execution succeeded; display Python code and DataFrame results
            data_frame = execution_result.unwrap()
            self.results_section.table_section.set_table(data_frame)
            self.error_section.clear_error()
            
            # Extract and store GEE metadata if this was a GEE query
            gee_metadata = self.extract_gee_metadata(self.last_sql_query)
            self.results_section.table_section.set_gee_metadata(gee_metadata)
        else:
            # Execution failed; display Python code and error in DataFrame section
            execution_error = execution_result.unwrap_error()
            error_message = f"Python Execution Error:\n{execution_error.message}\nTraceback:\n{execution_error.code}"
            self.results_section.table_section.clear_table()
            self.error_section.set_error(error_message)

    def compile_sql(self):
        # Fetch SQL code from the text box
        sql_query = self.sql_textbox.get("1.0", "end-1c").strip()
        sql_query = sqlparse.format(sql_query, reindent=True, strip_whitespace=True)
        
        # Store the SQL query for later use
        self.last_sql_query = sql_query
        
        # Delete all content
        self.sql_textbox.delete("1.0", "end")
        # Insert text at the beginning (index "1.0")
        self.sql_textbox.insert("1.0", sql_query)
        Colorizer.highlight_syntax(self.sql_textbox, self.sql_textbox_theme)
        if not sql_query:
            self.results_section.python_section.clear_code()
            self.results_section.table_section.clear_table()
            self.error_section.clear_error()
            return

        # Step 1: Compile SQL code to Python
        compilation_result = compile_to_python(sql_query)

        if isinstance(compilation_result, Success):
            python_code = compilation_result.unwrap()
            self.results_section.python_section.set_code(python_code)
            self.error_section.clear_error()
        else:
            # Compilation failed; display error in the Python Code section
            compilation_error = compilation_result.unwrap_error()
            error_message = f"SQL Compilation Error:\n{compilation_error}"
            self.results_section.python_section.clear_code()
            self.error_section.set_error(error_message)
        self.results_section.table_section.clear_table()

    def copy_to_clipboard(self, text: str):
        # Copy the provided text to the clipboard
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

    def _sanitize_query_filename(self, text: str) -> str:
        text = text.strip().replace("\n", " ").replace("\r", " ")
        text = re.sub(r"[\\/:*?\"<>|]+", "_", text)
        text = re.sub(r"\s+", "_", text)
        return text[:120] if len(text) > 120 else text

    def _get_query_save_dir(self) -> str:
        save_dir = os.path.join(os.getcwd(), "saved_queries")
        os.makedirs(save_dir, exist_ok=True)
        return save_dir

    def _extract_gee_info(self, sql_query: str) -> tuple[str | None, str | None, str | None, str | None, str | None]:
        # Updated pattern to match: {gee:project|dataset|start_date|end_date|lon|lat|scale}
        pattern = re.compile(
            r"\{gee:([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^}]+)\}",
            re.IGNORECASE,
        )
        match = pattern.search(sql_query)
        if not match:
            return None, None, None, None, None

        project = match.group(1).strip()  # Not used in filename
        dataset = match.group(2).strip()
        start_date = match.group(3).strip()
        end_date = match.group(4).strip()
        lon = match.group(5).strip()
        lat = match.group(6).strip()
        return dataset, start_date, end_date, lon, lat

    def _extract_select_columns(self, sql_query: str) -> str:
        pattern = re.compile(r"SELECT\s+(.+?)\s*FROM\b", re.IGNORECASE | re.DOTALL)
        match = pattern.search(sql_query)
        if not match:
            return "all"

        columns_part = match.group(1).strip()
        if columns_part == "*":
            return "all"

        columns = [col.strip() for col in columns_part.split(",") if col.strip()]
        cleaned = []
        for col in columns:
            col = re.sub(r"\(|\)", "", col)
            col = re.sub(r"\s+AS\s+.*", "", col, flags=re.IGNORECASE)
            col = col.replace(".", "_")
            col = col.replace(" ", "_")
            cleaned.append(col)
        if not cleaned:
            return "all"

        return "-".join(cleaned[:3])

    def _build_query_filename(self, sql_query: str) -> str:
        dataset, start_date, end_date, lon, lat = self._extract_gee_info(sql_query)
        columns = self._extract_select_columns(sql_query)

        filename_parts = ["GEE_Query"]

        if dataset:
            filename_parts.append(dataset.replace("/", "_"))

        if start_date and end_date:
            filename_parts.append(f"{start_date}_to_{end_date}")

        if lon and lat:
            # Format coordinates as Lon_Lat, round to 2 decimals
            try:
                lon_float = float(lon)
                lat_float = float(lat)
                filename_parts.append(f"{lon_float:.2f}_{lat_float:.2f}")
            except ValueError:
                pass  # Skip if not valid numbers

        if columns and columns != "all":
            filename_parts.append(columns)

        return "_".join(filename_parts)

    def _save_query_to_file(self, sql_query: str = None) -> None:
        if sql_query is None:
            sql_query = self.last_sql_query
        if not sql_query:
            return  # No query to save
        save_dir = self._get_query_save_dir()
        filename_fragment = self._build_query_filename(sql_query)
        filename_fragment = self._sanitize_query_filename(filename_fragment)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if filename_fragment:
            base_name = f"{filename_fragment}.txt"
        else:
            base_name = f"{timestamp}_query.txt"
        file_path = os.path.join(save_dir, base_name)

        counter = 1
        while os.path.exists(file_path):
            if filename_fragment:
                file_path = os.path.join(save_dir, f"{filename_fragment}_{counter}.txt")
            else:
                file_path = os.path.join(save_dir, f"{timestamp}_query_{counter}.txt")
            counter += 1

        with open(file_path, "w", encoding="utf-8") as query_file:
            query_file.write(sql_query)

        # Show confirmation message with the file path
        messagebox.showinfo("Query Saved", f"Query saved successfully to:\n{file_path}")

    def change_sql_textbox_theme(self, theme: str) -> None:
        self.sql_textbox_theme = theme
        Colorizer.highlight_syntax(self.sql_textbox, theme)

    def on_satellite_selected(self, selected_name):
        dataset_id = self.satellites.get(selected_name, "")
        self.satellite_id_label.configure(text=dataset_id)

    def insert_satellite_into_query(self):
        selected_name = self.satellite_dropdown.get()
        dataset_id = self.satellites.get(selected_name, "")
        if not dataset_id:
            return
        self.sql_textbox.insert("insert", dataset_id)
        Colorizer.highlight_syntax(self.sql_textbox, self.sql_textbox_theme)

    def load_areas_csv(self):
        file_path = filedialog.askopenfilename(
            title="Select Areas CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not file_path:
            return
        try:
            areas, skipped = parse_areas_csv(file_path)
        except Exception as e:
            messagebox.showerror("Load Areas CSV", str(e))
            return
        self.areas_data = areas
        names = list(areas.keys())
        self.area_dropdown.configure(values=names)
        self.area_dropdown.set(names[0])
        message = f"Loaded {len(names)} area(s)."
        if skipped:
            message += "\n\nSkipped rows:\n" + "\n".join(skipped[:8])
        messagebox.showinfo("Load Areas CSV", message)

    def insert_area_into_query(self):
        area = self.areas_data.get(self.area_dropdown.get())
        if not area:
            messagebox.showinfo(
                "Insert Area",
                "Click 'Load Areas CSV' first, then choose an area from the list."
            )
            return
        if self.area_mode.get() == "Circle":
            messagebox.showwarning(
                "Circle is not supported yet",
                "Single-point (Circle) queries do not work yet. Please choose Polygon."
            )
            return
        lon = area["longitude"]
        lat = area["latitude"]
        offset = 0.05
        corners = [
            (lon - offset, lat - offset),
            (lon + offset, lat - offset),
            (lon + offset, lat + offset),
            (lon - offset, lat + offset),
        ]
        points = ",".join(f"({_fmt_coord(x)},{_fmt_coord(y)})" for x, y in corners)
        text = f"0|0|0|AREA({points})"
        self.sql_textbox.insert("insert", text)
        Colorizer.highlight_syntax(self.sql_textbox, self.sql_textbox_theme)