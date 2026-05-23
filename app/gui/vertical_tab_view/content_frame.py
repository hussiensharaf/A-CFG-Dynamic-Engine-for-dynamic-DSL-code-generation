import sqlparse
import os
import sys
import threading
import re
import datetime
import tkinter.messagebox as messagebox


# Add AI Assistant to path
from ai_assistant.GEEQueryAssistant import GEEQueryAssistant

try:
    from ai_assistant.GEEQueryAssistant import GEEQueryAssistant
except ImportError:
    GEEQueryAssistant = None

from typing import Any, Tuple
import customtkinter as ctk


from app.core.result_monad import Success
from app.etl.controllers import compile_to_python, execute_python_code
from app.gui.error_frame.error_frame import ErrorFrame

from app.gui.results_frame.results_frame import ResultsFrame
from app.gui.vertical_tab_view.sql_textbox_colorizer import Colorizer
from app.gui.vertical_tab_view.input_dialog import SQLGeneratorDialog

# استيراد مكونات Autocomplete
from app.etl.autoComplete.autocomplete_engine import AutocompleteEngine
from app.etl.autoComplete.autocomplete_widget import AutocompleteTextbox
from app.etl.autoComplete.metadat_provider import MetadataProvider


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
        
        # تهيئة Autocomplete قبل إضافة الويدجتس
        self.metadata_provider = MetadataProvider()
        self.autocomplete_engine = AutocompleteEngine(self.metadata_provider)
        
        self.add_children_widget()

        self.sql_textbox_theme = ctk.get_appearance_mode().lower()
        if self.sql_textbox_theme == "dark":
            self.change_sql_textbox_theme("dark")
        else:
            self.sql_textbox_theme = "light"
        
        # ربط Autocomplete بالـ SQL textbox
        self.autocomplete = AutocompleteTextbox(
            self.sql_textbox,
            self.autocomplete_engine,
            trigger_chars=".|{",
            min_chars=0
        )

        # Store the last executed SQL query
        self.last_sql_query = ""

        # AI assistant instance (lazy initialization)
        self.assistant = None


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
        # Button Frame (for Execute, Run, Delete, Up, Down buttons)
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
        # Run Button
        self.run_btn = ctk.CTkButton(
            self.btn_frame,
            text="Compile",
            command=self.compile_sql,
            width=80,
        )

        # Generate SQL Button
        self.generate_sql_btn = ctk.CTkButton(
            self.btn_frame,
            text="Generate SQL",
            command=self.generate_sql,
            width=100,
        )
        
        self.results_section = ResultsFrame(self)
        self.error_section = ErrorFrame(
            self,
            border_width=4,
            fg_color=("#f9f9fa", "#1d1e1e"),
            border_color=("#cfcfcf", "#333333"),
            height=50,
        )
        self.sql_textbox.pack(fill="both", expand=True, padx=10, pady=5)
        self.btn_frame.pack(fill="x", pady=5, padx=10)
        self.execute_btn.pack(side="left", padx=5)
        self.run_btn.pack(side="left", padx=5)
        self.generate_sql_btn.pack(side="left", padx=5)
        self.results_section.pack(fill="both", expand=True, pady=5, padx=10)
        self.results_section.pack_propagate(False)
        self.error_section.pack(fill="x", pady=5, padx=10)
        self.error_section.pack_propagate(False)



    def extract_gee_metadata(self, sql: str):
        if not sql:
            return None

        pattern = re.compile(
            r'\{gee:([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^}]+)\}',
            re.IGNORECASE
        )

        match = pattern.search(sql)
        if not match:
            return None

        try:
            return {
                "project": match.group(1),
                "start_date": match.group(2),
                "end_date": match.group(3),
                "longitude": float(match.group(4)),
                "latitude": float(match.group(5)),
                "scale": float(match.group(6)),
            }
        except Exception as e:
            print("GEE metadata parse error:", e)
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
            print("DEBUG GEE METADATA:", gee_metadata)
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

    def generate_sql(self):
        dialog = SQLGeneratorDialog(self)
        user_input = dialog.get_input()
        
        if user_input:
            # Show loading state
            self.sql_textbox.delete("1.0", "end")
            self.sql_textbox.insert("1.0", "-- Generating SQL... Please wait.")
            self.generate_sql_btn.configure(state="disabled")
            
            # Run in a separate thread
            threading.Thread(target=self._run_generate_sql_thread, args=(user_input,), daemon=True).start()

    def _run_generate_sql_thread(self, user_input):
        try:
            if not GEEQueryAssistant:
                raise ImportError("Could not import GEEQueryAssistant. Check dependencies and paths.")
            
            if not self.assistant:
                # Define paths
                ai_dir = os.path.join(os.getcwd(), "ai_assistant")
                json_path = os.path.join(ai_dir, "GEE_datasets_augmented_threaded.json")
                persist_dir = os.path.join(ai_dir, "chroma_db_v2")
                
                if not os.path.exists(json_path):
                        raise FileNotFoundError(f"Dataset file not found: {json_path}")

                self.assistant = GEEQueryAssistant(
                    json_path=json_path,
                    persist_directory=persist_dir
                )
            
            generated_sql = self.assistant.generate_sql(user_input)
            
            # Update GUI in main thread
            self.after(0, self._update_sql_textbox, generated_sql)
            
        except Exception as e:
            self.after(0, self._handle_generation_error, str(e))

    def _update_sql_textbox(self, sql_query):
        self.sql_textbox.delete("1.0", "end")
        self.sql_textbox.insert("1.0", sql_query)
        Colorizer.highlight_syntax(self.sql_textbox, self.sql_textbox_theme)
        self.error_section.clear_error()
        self.generate_sql_btn.configure(state="normal")

    def _handle_generation_error(self, error_message):
        self.error_section.set_error(f"AI Assistant Error: {error_message}")
        self.sql_textbox.delete("1.0", "end")
        self.generate_sql_btn.configure(state="normal")

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