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

    def save_table_csv(self) -> None:
        data_frame = self.get_table()
        if data_frame.empty:
            messagebox.showwarning("No Data", "There is no table data to save.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Save table as CSV",
            initialfile="query_result.csv",
        )
        if not file_path:
            return

        try:
            data_frame.to_csv(file_path, index=False)
            messagebox.showinfo("Saved", f"Table data saved successfully to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save CSV file:\n{e}")

    def sort_by_selected_column(self) -> None:
        if self.current_view.empty:
            messagebox.showwarning("No Data", "There is no data to sort.")
            return

        column_names = list(self.current_view.columns)
        if not column_names:
            messagebox.showwarning("No Columns", "There are no columns to sort.")
            return

        sort_window = ctk.CTkToplevel(self)
        sort_window.title("Sort Table")
        sort_window.grab_set()

        selected_columns = self.table.sheet.get_selected_columns(get_cells=False, return_tuple=False)
        default_column = column_names[0]
        if selected_columns:
            default_index = next(iter(selected_columns))
            if 0 <= default_index < len(column_names):
                default_column = column_names[default_index]

        ctk.CTkLabel(sort_window, text="Select column to sort by:").pack(padx=10, pady=(10, 4))
        column_var = tk.StringVar(value=default_column)
        ctk.CTkOptionMenu(sort_window, variable=column_var, values=column_names).pack(padx=10, pady=4)

        ascending_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(sort_window, text="Ascending", variable=ascending_var).pack(padx=10, pady=4)

        def apply_sort() -> None:
            column = column_var.get()
            ascending = ascending_var.get()
            try:
                self.current_view = self.current_view.sort_values(by=[column], ascending=ascending)
                self.table.set_data(self.current_view)
                sort_window.destroy()
            except Exception as e:
                messagebox.showerror("Sort Error", f"Could not sort by '{column}':\n{e}")

        ctk.CTkButton(sort_window, text="Sort", command=apply_sort).pack(padx=10, pady=10)

    def delete_selected_column(self) -> None:
        if self.current_view.empty:
            messagebox.showwarning("No Data", "There is no table data to update.")
            return

        selected_columns = self.table.sheet.get_selected_columns(get_cells=False, return_tuple=False)
        if not selected_columns:
            messagebox.showwarning("No Selection", "Select one or more columns to delete.")
            return

        column_indices = sorted(set(selected_columns), reverse=True)
        column_names = list(self.current_view.columns)
        columns_to_remove = []

        for col_idx in column_indices:
            if 0 <= col_idx < len(column_names):
                columns_to_remove.append(column_names[col_idx])

        if not columns_to_remove:
            messagebox.showwarning("No Columns", "No valid selected columns were found.")
            return

        try:
            self.full_data.drop(columns=columns_to_remove, inplace=True)
            self.current_view.drop(columns=columns_to_remove, inplace=True)
            self.table.set_data(self.current_view)
            messagebox.showinfo("Deleted", f"Deleted columns: {', '.join(columns_to_remove)}")
        except Exception as e:
            messagebox.showerror("Delete Error", f"Could not delete selected columns:\n{e}")

    def add_computed_column(self) -> None:
        if self.full_data.empty:
            messagebox.showwarning("No Data", "There is no data to compute from.")
            return

        prompt = (
            "Enter a computed column formula in the form:\n"
            "new_column = expression\n"
            "Example: speed = (u**2 + v**2)**0.5"
        )
        formula = simpledialog.askstring("Computed Column", prompt, parent=self)
        if not formula:
            return

        if "=" not in formula:
            messagebox.showerror("Invalid Formula", "Formula must include '=' and a column name on the left-hand side.")
            return

        new_column, expression = [part.strip() for part in formula.split("=", 1)]
        if not new_column or not expression:
            messagebox.showerror("Invalid Formula", "Provide a valid column name and expression.")
            return

        try:
            self.full_data[new_column] = self.full_data.eval(expression, engine="python")
            self.current_view = self.current_view.copy()
            self.current_view[new_column] = self.full_data.loc[self.current_view.index, new_column]
            self.table.set_data(self.current_view)
            messagebox.showinfo("Computed Column", f"Computed column '{new_column}' added.")
        except Exception as e:
            messagebox.showerror("Compute Error", f"Could not compute new column:\n{e}")

    def set_gee_metadata(self, metadata: Optional[Dict]) -> None:
        """Store Google Earth Engine query metadata and show/hide map button"""
        self.gee_metadata = metadata
        
        # Show map button only if we have GEE metadata
        if metadata is not None:
            # Show the map button
            self.map_button.pack(side="left", padx=5)
        else:
            # Hide the map button for non-GEE queries
            self.map_button.pack_forget()
    
    def show_map(self):
        """Open enhanced map visualization window with data"""
        # Pass both metadata and actual data to the map window
        MapVisualizationWindow(self, self.gee_metadata, self.get_table())

    def change_table_theme(self, theme: str) -> None:
        self.table_theme = theme
        self.table.sheet.change_theme(theme.lower() + " blue")