import customtkinter as ctk
import seaborn as sns
import matplotlib
import matplotlib.pyplot as plt
import mplcursors
 
from tkinter import filedialog, messagebox
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from pandas import DataFrame
 
from app.gui.results_frame.table_result_frame.multi_selection_dropdown import (
    MultiSelectionDropDown,
)
 
# ── Global style applied once at import time ─────────────────────────────────
matplotlib.rcParams.update({
    "font.family":        "DejaVu Sans",
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.titlesize":     13,
    "axes.titleweight":   "bold",
    "axes.labelsize":     11,
    "xtick.labelsize":    9,
    "ytick.labelsize":    9,
    "legend.fontsize":    9,
    "legend.framealpha":  0.85,
    "figure.dpi":         110,
})
 
# Cohesive palette used across every chart
_PALETTE = sns.color_palette("muted", 12)
 
 
# ─────────────────────────────────────────────────────────────────────────────
class DataVisualizer:
    def __init__(self, master_widget, data_frame: DataFrame):
        self.master      = master_widget
        self.data_frame  = data_frame
        self.current_figure = {"fig": None, "canvas": None, "toolbar": None}
        self._error_label   = None          # single reusable error label
        self.create_visualization_window()
 
    # ── Window & tab skeleton ─────────────────────────────────────────────────
    def create_visualization_window(self):
        if self.data_frame is None or self.data_frame.empty:
            return
 
        self.popup = ctk.CTkToplevel(self.master)
        self.popup.title("Data Visualizer")
        self.popup.geometry("760x820")
        self.popup.grab_set()
 
        self.tabview = ctk.CTkTabview(self.popup, height=720)
        self.tabview.pack(expand=True, fill="both", padx=12, pady=6)
 
        self.tab1 = self.tabview.add("📈  Charts")
        self.tab2 = self.tabview.add("📊  Count Plot")
        self.tab3 = self.tabview.add("🔢  Histogram")
 
        self.setup_standard_plots_tab()
        self.setup_count_plot_tab()
        self.setup_histogram_tab()
        self.setup_buttons()
 
    # ── Tab 1 – Scatter / Line / Bar ──────────────────────────────────────────
    def setup_standard_plots_tab(self):
        all_columns     = self.data_frame.columns.tolist()
        numeric_columns = self.data_frame.select_dtypes(include=["number"]).columns.tolist()
        cat_columns     = ["None"] + self.data_frame.select_dtypes(
            include=["object", "category"]
        ).columns.tolist()
 
        # ── Controls panel ────────────────────────────────────────────────────
        self.control_frame = ctk.CTkScrollableFrame(self.tab1, height=200)
        self.control_frame.pack(fill="x", padx=10, pady=(8, 4))
 
        self._make_grid(self.control_frame, columns=3)
 
        # Row 0: Graph type
        self._label(self.control_frame, "Graph Type", 0, 0)
        graph_type_options  = ["Scatterplot", "Line", "Bar"]
        self.graph_type_var = ctk.StringVar(value=graph_type_options[0])
        ctk.CTkOptionMenu(
            self.control_frame, values=graph_type_options,
            variable=self.graph_type_var, width=160
        ).grid(row=1, column=0, padx=8, pady=4, sticky="ew")
 
        # Row 0: Y-axis
        self._label(self.control_frame, "Y-axis  (numeric)", 0, 1)
        self.y_axis_var = ctk.StringVar(
            value=numeric_columns[0] if numeric_columns else ""
        )
        ctk.CTkOptionMenu(
            self.control_frame, values=numeric_columns,
            variable=self.y_axis_var, width=160
        ).grid(row=1, column=1, padx=8, pady=4, sticky="ew")
 
        # Row 0: Hue / colour-by
        self._label(self.control_frame, "Color-by  (hue)", 0, 2)
        self.hue_var = ctk.StringVar(value="None")
        ctk.CTkOptionMenu(
            self.control_frame, values=cat_columns,
            variable=self.hue_var, width=160
        ).grid(row=1, column=2, padx=8, pady=4, sticky="ew")
 
        # Row 2: X-axis multi-select
        self._label(self.control_frame, "X-axis Variables  (multi-select)", 2, 0, colspan=3)
        self.x_axis_widget = MultiSelectionDropDown(
            self.control_frame, values=all_columns
        )
        self.x_axis_widget.grid(row=3, column=0, columnspan=3, padx=8, pady=4, sticky="ew")
 
        # Row 4: Custom title
        self._label(self.control_frame, "Custom Chart Title  (optional)", 4, 0, colspan=3)
        self.chart_title_entry = ctk.CTkEntry(
            self.control_frame, placeholder_text="Leave blank for auto title", width=400
        )
        self.chart_title_entry.grid(row=5, column=0, columnspan=3, padx=8, pady=(4, 8), sticky="ew")
 
        # ── Plot frame ────────────────────────────────────────────────────────
        self.plot_frame = ctk.CTkFrame(self.tab1)
        self.plot_frame.pack(fill="both", expand=True, padx=10, pady=4)
 
    # ── Tab 2 – Count Plot ────────────────────────────────────────────────────
    def setup_count_plot_tab(self):
        all_columns = self.data_frame.columns.tolist()
        cat_columns = ["None"] + self.data_frame.select_dtypes(
            include=["object", "category"]
        ).columns.tolist()
 
        self.countplot_control = ctk.CTkFrame(self.tab2)
        self.countplot_control.pack(fill="x", padx=10, pady=(8, 4))
 
        self._make_grid(self.countplot_control, columns=2)
 
        self._label(self.countplot_control, "X-axis Variable", 0, 0)
        self.countplot_x_axis_var = ctk.StringVar(
            value=all_columns[0] if all_columns else ""
        )
        ctk.CTkOptionMenu(
            self.countplot_control, values=all_columns,
            variable=self.countplot_x_axis_var, width=200
        ).grid(row=1, column=0, padx=8, pady=4, sticky="ew")
 
        self._label(self.countplot_control, "Color-by  (hue)", 0, 1)
        self.countplot_hue_var = ctk.StringVar(value="None")
        ctk.CTkOptionMenu(
            self.countplot_control, values=cat_columns,
            variable=self.countplot_hue_var, width=200
        ).grid(row=1, column=1, padx=8, pady=4, sticky="ew")
 
        self.countplot_frame = ctk.CTkFrame(self.tab2)
        self.countplot_frame.pack(fill="both", expand=True, padx=10, pady=4)
 
    # ── Tab 3 – Histogram ─────────────────────────────────────────────────────
    def setup_histogram_tab(self):
        numeric_columns = self.data_frame.select_dtypes(include=["number"]).columns.tolist()
        cat_columns     = ["None"] + self.data_frame.select_dtypes(
            include=["object", "category"]
        ).columns.tolist()
 
        self.hist_control = ctk.CTkFrame(self.tab3)
        self.hist_control.pack(fill="x", padx=10, pady=(8, 4))
 
        self._make_grid(self.hist_control, columns=3)
 
        self._label(self.hist_control, "Column", 0, 0)
        self.hist_col_var = ctk.StringVar(
            value=numeric_columns[0] if numeric_columns else ""
        )
        ctk.CTkOptionMenu(
            self.hist_control, values=numeric_columns,
            variable=self.hist_col_var, width=180
        ).grid(row=1, column=0, padx=8, pady=4, sticky="ew")
 
        self._label(self.hist_control, "Bins", 0, 1)
        self.hist_bins_var = ctk.StringVar(value="20")
        ctk.CTkOptionMenu(
            self.hist_control,
            values=["5", "10", "15", "20", "30", "50", "100"],
            variable=self.hist_bins_var, width=120
        ).grid(row=1, column=1, padx=8, pady=4, sticky="ew")
 
        self._label(self.hist_control, "Color-by  (hue)", 0, 2)
        self.hist_hue_var = ctk.StringVar(value="None")
        ctk.CTkOptionMenu(
            self.hist_control, values=cat_columns,
            variable=self.hist_hue_var, width=180
        ).grid(row=1, column=2, padx=8, pady=4, sticky="ew")
 
        self.hist_frame = ctk.CTkFrame(self.tab3)
        self.hist_frame.pack(fill="both", expand=True, padx=10, pady=4)
 
    # ── Action buttons ────────────────────────────────────────────────────────
    def setup_buttons(self):
        btn_frame = ctk.CTkFrame(self.popup, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=(4, 10))
 
        ctk.CTkButton(
            btn_frame, text="▶  Generate Plot",
            command=self.generate_graph, width=180,
            fg_color="#2563eb", hover_color="#1d4ed8"
        ).pack(side="left", padx=8)
 
        ctk.CTkButton(
            btn_frame, text="💾  Save Figure",
            command=self.save_figure, width=160,
            fg_color="#16a34a", hover_color="#15803d"
        ).pack(side="left", padx=4)
 
        ctk.CTkButton(
            btn_frame, text="✖  Clear",
            command=self._full_clear, width=120,
            fg_color="#dc2626", hover_color="#b91c1c"
        ).pack(side="right", padx=8)
 
    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _make_grid(frame, columns: int):
        for i in range(columns):
            frame.columnconfigure(i, weight=1)
 
    @staticmethod
    def _label(parent, text: str, row: int, col: int, colspan: int = 1):
        ctk.CTkLabel(
            parent, text=text, anchor="w",
            font=ctk.CTkFont(size=11, weight="bold")
        ).grid(row=row, column=col, columnspan=colspan,
               padx=8, pady=(10, 0), sticky="w")
 
    def _show_error(self, msg: str):
        """Single reusable error label — replaces the old endlessly-stacking labels."""
        if self._error_label and self._error_label.winfo_exists():
            self._error_label.configure(text=f"⚠  {msg}")
        else:
            self._error_label = ctk.CTkLabel(
                self.popup, text=f"⚠  {msg}",
                text_color="#f87171",
                font=ctk.CTkFont(size=11)
            )
            self._error_label.pack(pady=2)
 
    def _hide_error(self):
        if self._error_label and self._error_label.winfo_exists():
            self._error_label.destroy()
            self._error_label = None
 
    def _apply_style(self, ax, fig):
        """Consistent light-mode look for every chart."""
        fig.patch.set_facecolor("#ffffff")
        ax.set_facecolor("#f8fafc")
        ax.title.set_color("#1e293b")
        ax.xaxis.label.set_color("#475569")
        ax.yaxis.label.set_color("#475569")
        ax.tick_params(colors="#475569")
        for spine in ax.spines.values():
            spine.set_edgecolor("#cbd5e1")
        ax.grid(color="#e2e8f0", linewidth=0.7, alpha=0.9)
 
    def _embed_canvas(self, fig, parent_frame):
        """Embed figure + navigation toolbar into a CTkFrame."""
        canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
 
        toolbar_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        toolbar_frame.pack(fill="x")
        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
        toolbar.update()
 
        self.current_figure = {"fig": fig, "canvas": canvas, "toolbar": toolbar}
 
    def _auto_rotate_xticks(self, ax):
        labels = [t.get_text() for t in ax.get_xticklabels()]
        if labels and max(len(l) for l in labels) > 6:
            ax.tick_params(axis="x", rotation=35)
        else:
            ax.tick_params(axis="x", rotation=0)
 
    def _stats_annotation(self, ax, series):
        """Add a tiny stats box (mean / median / std) to the axes."""
        try:
            text = (
                f"mean={series.mean():.2f}   "
                f"median={series.median():.2f}   "
                f"σ={series.std():.2f}"
            )
            ax.annotate(
                text, xy=(0.01, 0.97), xycoords="axes fraction",
                fontsize=8, color="#475569",
                va="top", ha="left",
                bbox=dict(boxstyle="round,pad=0.3", fc="#f1f5f9", alpha=0.9, ec="#cbd5e1")
            )
        except Exception:
            pass
 
    def _resolve_hue(self, hue_var):
        val = hue_var.get()
        return None if val == "None" else val
 
    # ── Clear ─────────────────────────────────────────────────────────────────
    def clear_current_plot(self):
        if self.current_figure["canvas"]:
            self.current_figure["canvas"].get_tk_widget().destroy()
        if self.current_figure.get("toolbar"):
            try:
                self.current_figure["toolbar"].destroy()
            except Exception:
                pass
 
    def _full_clear(self):
        self.clear_current_plot()
        self.current_figure = {"fig": None, "canvas": None, "toolbar": None}
        self._hide_error()
 
    # ── Generate: Count Plot ──────────────────────────────────────────────────
    def generate_count_plot(self):
        x_column = self.countplot_x_axis_var.get()
        if not x_column:
            self._show_error("Please select an X variable for the count plot.")
            return False
 
        hue = self._resolve_hue(self.countplot_hue_var)
 
        fig = Figure(figsize=(7, 4.5))
        ax  = fig.add_subplot(111)
 
        sns.countplot(
            data=self.data_frame, x=x_column, hue=hue,
            ax=ax, palette=_PALETTE
        )
 
        ax.set_xlabel(x_column)
        ax.set_ylabel("Frequency")
        title = f"Count of  {x_column}"
        if hue:
            title += f"  (by {hue})"
        ax.set_title(title)
        self._auto_rotate_xticks(ax)
 
        # Value labels on bars
        for bar in ax.patches:
            h = bar.get_height()
            if h > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2, h + 0.15,
                    f"{int(h)}", ha="center", va="bottom",
                    fontsize=8, color="#1e293b"
                )
 
        self._apply_style(ax, fig)
        fig.tight_layout()
        self._embed_canvas(fig, self.countplot_frame)
        self._hide_error()
        return True
 
    # ── Generate: Histogram ───────────────────────────────────────────────────
    def generate_histogram(self):
        col  = self.hist_col_var.get()
        bins = int(self.hist_bins_var.get())
        hue  = self._resolve_hue(self.hist_hue_var)
 
        if not col:
            self._show_error("Please select a column for the histogram.")
            return False
 
        fig = Figure(figsize=(7, 4.5))
        ax  = fig.add_subplot(111)
 
        sns.histplot(
            data=self.data_frame, x=col, bins=bins, hue=hue,
            kde=True, ax=ax, palette=_PALETTE, alpha=0.75
        )
 
        ax.set_xlabel(col)
        ax.set_ylabel("Frequency")
        title = f"Distribution of  {col}"
        if hue:
            title += f"  (by {hue})"
        ax.set_title(title)
 
        self._stats_annotation(ax, self.data_frame[col].dropna())
        self._apply_style(ax, fig)
        fig.tight_layout()
        self._embed_canvas(fig, self.hist_frame)
        self._hide_error()
        return True
 
    # ── Generate: Scatter / Line / Bar ────────────────────────────────────────
    def generate_standard_plot(self):
        x_columns = self.x_axis_widget.get_selected_values()
        y_column  = self.y_axis_var.get()
        hue       = self._resolve_hue(self.hue_var)
        chart_type = self.graph_type_var.get()
        custom_title = self.chart_title_entry.get().strip()
 
        if not x_columns:
            self._show_error("Please select at least one X variable.")
            return False
        if not y_column:
            self._show_error("Please select a Y variable.")
            return False
 
        fig = Figure(figsize=(7, 4.5))
        ax  = fig.add_subplot(111)
 
        for idx, x_column in enumerate(x_columns):
            color = _PALETTE[idx % len(_PALETTE)]
            x_data = self.data_frame[x_column]
            y_data = self.data_frame[y_column]
 
            if chart_type == "Scatterplot":
                if hue:
                    sns.scatterplot(
                        data=self.data_frame, x=x_column, y=y_column,
                        hue=hue, ax=ax, palette=_PALETTE, alpha=0.8,
                        edgecolor="none", s=55
                    )
                else:
                    sc = ax.scatter(
                        x_data, y_data,
                        label=x_column, color=color,
                        alpha=0.8, edgecolors="none", s=55
                    )
                    mplcursors.cursor(sc, hover=True)
 
            elif chart_type == "Line":
                ax.plot(
                    x_data, y_data,
                    label=x_column, color=color,
                    linewidth=2, alpha=0.9
                )
                ax.fill_between(x_data, y_data, alpha=0.08, color=color)
 
            elif chart_type == "Bar":
                if hue:
                    sns.barplot(
                        data=self.data_frame, x=x_column, y=y_column,
                        hue=hue, ax=ax, palette=_PALETTE,
                        capsize=0.05, errwidth=1.2
                    )
                else:
                    sns.barplot(
                        data=self.data_frame, x=x_column, y=y_column,
                        ax=ax, color=color, label=x_column,
                        capsize=0.05, errwidth=1.2
                    )
 
        ax.set_xlabel(", ".join(x_columns) if len(x_columns) > 1 else x_columns[0])
        ax.set_ylabel(y_column)
 
        if custom_title:
            ax.set_title(custom_title)
        else:
            ax.set_title(f"{chart_type}  —  {y_column}")
 
        self._auto_rotate_xticks(ax)
        if len(x_columns) > 1 or hue:
            ax.legend(loc="best")
 
        # Summary stats annotation for Y
        self._stats_annotation(ax, self.data_frame[y_column].dropna())
        self._apply_style(ax, fig)
        fig.tight_layout()
        self._embed_canvas(fig, self.plot_frame)
        self._hide_error()
        return True
 
    # ── Route to correct generator ────────────────────────────────────────────
    def generate_graph(self):
        self.clear_current_plot()
        tab = self.tabview.get()
        if "Count" in tab:
            self.generate_count_plot()
        elif "Histogram" in tab:
            self.generate_histogram()
        else:
            self.generate_standard_plot()
 
    # ── Save ──────────────────────────────────────────────────────────────────
    def save_figure(self):
        if not self.current_figure["fig"]:
            messagebox.showinfo("No Figure", "Generate a plot first before saving.")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG files",  "*.png"),
                ("JPEG files", "*.jpg"),
                ("PDF files",  "*.pdf"),
                ("SVG files",  "*.svg"),
            ],
        )
        if file_path:
            self.current_figure["fig"].savefig(
                file_path, dpi=150, bbox_inches="tight",
                facecolor="#ffffff"
            )
            messagebox.showinfo("Saved", f"Figure saved to:\n{file_path}")
 
 
# ─────────────────────────────────────────────────────────────────────────────
def visualize(master_widget, data_frame: DataFrame):
    """Opens the enhanced visualization pop-up for the given DataFrame."""
    if data_frame is None or data_frame.empty:
        return
    DataVisualizer(master_widget, data_frame)