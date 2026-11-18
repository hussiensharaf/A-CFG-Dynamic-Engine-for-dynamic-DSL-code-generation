from typing import Any, Tuple, Optional, Dict
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import tkinter.simpledialog as simpledialog
import customtkinter as ctk
from pandas import DataFrame

from app.gui.results_frame.table_result_frame.table_widget import TableWidget
from app.gui.results_frame.table_result_frame.visualization import visualize
from app.gui.results_frame.table_result_frame.map_visualization import MapVisualizationWindow


class TableResultFrame(ctk.CTkFrame):
    def __init__(
        self,
        master: Any,
        width: int = 200,
        height: int = 200,
        corner_radius: int | str | None = None,
        border_width: int | str | None = None,
        bg_color: str | Tuple[str, str] = "transparent",
        fg_color: str | Tuple[str, str] | None = None,
        border_color: str | Tuple[str, str] | None = None,
        background_corner_colors: Tuple[str | Tuple[str, str]] | None = None,
        overwrite_preferred_drawing_method: str | None = None,
        **kwargs
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
            **kwargs
        )

        self.label = ctk.CTkLabel(
            self,
            text="Table",
        )
        
        # Label for GEE datasets info
        self.datasets_label = ctk.CTkLabel(
            self,
            text="",
            text_color="gray",
            font=("Arial", 9)
        )
        
        self.table = TableWidget(self)
        
        # Button frame for visualization buttons and table actions
        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")

        self.sort_button = ctk.CTkButton(
            self.button_frame,
            text="Sort",
            command=self.sort_by_selected_column,
            width=100,
        )
        self.delete_column_button = ctk.CTkButton(
            self.button_frame,
            text="Delete Column",
            command=self.delete_selected_column,
            width=120,
            fg_color="#B03E3E",
            hover_color="#862C2C",
        )
        self.compute_column_button = ctk.CTkButton(
            self.button_frame,
            text="Compute Column",
            command=self.add_computed_column,
            width=150,
        )
        
        # Add "Show Visualization" button
        self.visualize_button = ctk.CTkButton(
            self.button_frame,
            text="Show Visualization",
            command=lambda: visualize(self, self.get_table()),
            width=150,
        )
        
        # Add "Save CSV" button
        self.save_csv_button = ctk.CTkButton(
            self.button_frame,
            text="Save CSV",
            command=self.save_table_csv,
            width=120,
            fg_color="#3E6BB0",
            hover_color="#2C5186"
        )

        # Add "Show on Map" button with enhanced styling
        self.map_button = ctk.CTkButton(
            self.button_frame,
            text="Show on Map",
            command=self.show_map,
            width=150,
            fg_color="#2B7A0B",
            hover_color="#1f5a08"
        )
        
        # Store table data for filtering and sorting
        self.full_data: DataFrame = DataFrame()
        self.current_view: DataFrame = DataFrame()
        self.gee_metadata: Optional[Dict] = None
        
        self.table_theme = ""
        self.label.pack(pady=5)
        self.datasets_label.pack(pady=2)
        self.table.pack(fill="both", expand=True, padx=5)
        self.table.pack_propagate(False)
        
        # Pack buttons side by side
        self.button_frame.pack(pady=5)
        self.sort_button.pack(side="left", padx=4)
        self.delete_column_button.pack(side="left", padx=4)
        self.compute_column_button.pack(side="left", padx=4)
        self.visualize_button.pack(side="left", padx=4)
        self.save_csv_button.pack(side="left", padx=4)
        self.map_button.pack(side="left", padx=4)
        
        # Initially hide the map button (will show only for GEE queries)
        self.map_button.pack_forget()
        
        if ctk.get_appearance_mode().lower() == "dark":
            self.change_table_theme("dark")
        else:
            self.table_theme = "light"

    def set_table(self, data_frame: DataFrame) -> None:
        self.full_data = data_frame.copy()
        self.current_view = data_frame.copy()
        self.table.set_data(self.current_view)

    def get_table(self) -> DataFrame:
        return self.table.get_data()

    def clear_table(self) -> None:
        self.table.reset_data()
        self.full_data = DataFrame()
        self.current_view = DataFrame()
        # Clear GEE metadata when table is cleared
        self.gee_metadata = None
        # Hide map button when table is cleared
        self.map_button.pack_forget()

    def set_gee_metadata(self, metadata: Optional[Dict]) -> None:
        """Store Google Earth Engine query metadata and show/hide map button"""
        self.gee_metadata = metadata
        
        # Show map button only if we have GEE metadata
        if metadata is not None:
            # Format metadata for display
            if isinstance(metadata, list):
                dataset_names = ", ".join([m['dataset'] for m in metadata])
                self.datasets_label.configure(text=f"Datasets: {dataset_names}")
                print(f"DEBUG GEE DATASETS: {dataset_names}")
            else:
                self.datasets_label.configure(text=f"Dataset: {metadata['dataset']}")
                print(f"DEBUG GEE DATASET: {metadata['dataset']}")
            
            # Show the map button
            self.map_button.pack(side="left", padx=5)
        else:
            # Hide the datasets label and map button for non-GEE queries
            self.datasets_label.configure(text="")
            self.map_button.pack_forget()
    
    def show_map(self):
        """Open enhanced map visualization window with data"""
        # Pass both metadata and actual data to the map window
        MapVisualizationWindow(self, self.gee_metadata, self.get_table())

    def change_table_theme(self, theme: str) -> None:
        self.table_theme = theme
        self.table.sheet.change_theme(theme.lower() + " blue")

    # ------------------------------------------------------------------
    # Table actions (Sort / Delete Column / Compute Column / Save CSV)
    # ------------------------------------------------------------------
    def _get_selected_column(self) -> Optional[int]:
        """Return the index of the selected column (or the column of the
        selected cell), or None if nothing is selected."""
        sheet = self.table.sheet
        try:
            columns = sorted(sheet.get_selected_columns())
            if columns:
                return int(columns[0])
            current = sheet.get_currently_selected()
            column = getattr(current, "column", None)
            if column is not None:
                return int(column)
        except Exception:
            pass
        return None

    def _require_table_and_column(self) -> Optional[Tuple[DataFrame, int]]:
        """Shared checks: table has data and a column is selected."""
        df = self.get_table()
        if df.empty and len(df.columns) == 0:
            messagebox.showinfo("No data", "The table is empty.", parent=self)
            return None
        index = self._get_selected_column()
        if index is None or index >= len(df.columns):
            messagebox.showinfo(
                "Select a column",
                "Click a column header (or any cell in the column) first.",
                parent=self,
            )
            return None
        return df, index

    def sort_by_selected_column(self) -> None:
        checked = self._require_table_and_column()
        if checked is None:
            return
        df, index = checked
        name = df.columns[index]
        ascending = messagebox.askyesnocancel(
            "Sort",
            f"Sort by '{name}'.\n\nYes = ascending\nNo = descending",
            parent=self,
        )
        if ascending is None:
            return
        try:
            sorted_df = df.sort_values(
                by=df.columns[index], ascending=ascending, kind="stable", na_position="last"
            )
        except TypeError:
            # Mixed types in the column: fall back to sorting as text
            sorted_df = df.sort_values(
                by=df.columns[index],
                ascending=ascending,
                kind="stable",
                key=lambda col: col.astype(str),
            )
        self.set_table(sorted_df.reset_index(drop=True))

    def delete_selected_column(self) -> None:
        checked = self._require_table_and_column()
        if checked is None:
            return
        df, index = checked
        name = df.columns[index]
        if not messagebox.askyesno(
            "Delete column", f"Delete column '{name}' from the table?", parent=self
        ):
            return
        keep = [i for i in range(len(df.columns)) if i != index]
        self.set_table(df.iloc[:, keep].copy())

    def add_computed_column(self) -> None:
        df = self.get_table()
        if len(df.columns) == 0:
            messagebox.showinfo("No data", "The table is empty.", parent=self)
            return
        new_name = simpledialog.askstring(
            "Compute column", "Name of the new column:", parent=self
        )
        if not new_name or not new_name.strip():
            return
        new_name = new_name.strip()
        if new_name in df.columns:
            if not messagebox.askyesno(
                "Column exists",
                f"'{new_name}' already exists. Overwrite it?",
                parent=self,
            ):
                return
        expression = simpledialog.askstring(
            "Compute column",
            "Expression using existing columns, e.g.  price * quantity\n"
            "(wrap names containing spaces in backticks: `unit price` * 2)",
            parent=self,
        )
        if not expression or not expression.strip():
            return
        try:
            result = df.eval(expression.strip())
            df = df.copy()
            df[new_name] = result
        except Exception as e:
            messagebox.showerror(
                "Compute column", f"Could not evaluate the expression:\n{e}", parent=self
            )
            return
        self.set_table(df)

    def save_table_csv(self) -> None:
        df = self.get_table()
        if len(df.columns) == 0:
            messagebox.showinfo("No data", "There is no table to save.", parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Save table as CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            df.to_csv(path, index=False, encoding="utf-8-sig")
        except Exception as e:
            messagebox.showerror("Save CSV", f"Could not save the file:\n{e}", parent=self)
            return
        messagebox.showinfo("Save CSV", f"Saved {len(df)} rows to:\n{path}", parent=self)