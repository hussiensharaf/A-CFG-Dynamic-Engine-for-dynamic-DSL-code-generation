from typing import Any, Tuple
from tksheet import Sheet
from pandas import DataFrame
import customtkinter as ctk


class TableWidget(ctk.CTkFrame):
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
        self.data = DataFrame()
        self.sheet = Sheet(self)
        self.sheet.enable_bindings("all")
        self.sheet.pack(fill="both", expand=True)

    def set_data(self, data: DataFrame) -> None:
        self.reset_data()
        self.data = data
        self.sheet.set_data(data=self.data.values.tolist())
        self.sheet.set_header_data(list(self.data.columns))

    def get_data(self) -> DataFrame:
        total_columns = self.sheet.total_columns()
        if not total_columns:
            return DataFrame()

        headers = [self.sheet.get_header_data(c) for c in range(total_columns)]
        rows = self.sheet.get_sheet_data(get_displayed=False, get_header=False)
        if not rows:
            return DataFrame(columns=headers)
        return DataFrame(rows, columns=headers)

    def reset_data(self) -> None:
        self.data = DataFrame()
        self.sheet.reset()
