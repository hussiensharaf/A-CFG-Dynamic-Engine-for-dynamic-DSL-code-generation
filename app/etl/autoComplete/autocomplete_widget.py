"""
Autocomplete Widget for CustomTkinter GUI - FIXED VERSION
- Better positioning (below text with proper spacing)
- Fixed text insertion (doesn't delete previous text)
- Better placeholder hints for dates, coordinates, etc.
"""

import customtkinter as ctk
from typing import List, Callable, Optional
from dataclasses import dataclass


@dataclass
class SuggestionItem:
    """Represents a suggestion item in the popup"""
    text: str
    display_text: str
    type: str
    description: Optional[str] = None
    auto_suffix: str = ""  # Auto-added text after selection


class AutocompletePopup(ctk.CTkToplevel):
    """Popup window that displays autocomplete suggestions"""
    
    # Type colors for different suggestion types
    TYPE_COLORS = {
        'keyword': '#569CD6',      # Blue
        'column': '#9CDCFE',       # Light blue
        'function': '#DCDCAA',     # Yellow
        'datasource': '#4EC9B0',   # Cyan
        'wildcard': '#CE9178',     # Orange
        'location': '#C586C0',     # Purple
        'dataset': '#4EC9B0',      # Cyan
        'date': '#CE9178',         # Orange
        'coordinate': '#B5CEA8',   # Green
        'scale': '#B5CEA8',        # Green
        'syntax': '#D4D4D4',       # Gray
    }
    
    def __init__(
        self, 
        parent, 
        suggestions: List[SuggestionItem],
        on_select: Callable[[str], None],
        x: int,
        y: int
    ):
        """
        Initialize autocomplete popup
        
        Args:
            parent: Parent widget (the text box)
            suggestions: List of suggestions to display
            on_select: Callback when user selects a suggestion
            x, y: Position to display popup
        """
        super().__init__(parent)
        
        self.on_select = on_select
        self.suggestions = suggestions
        self.selected_index = 0
        
        # Configure window
        self.withdraw()  # Hide initially
        self.overrideredirect(True)  # Remove window decorations
        self.configure(fg_color="#1E1E1E")
        
        # Create main container with border
        main_container = ctk.CTkFrame(
            self,
            fg_color="#1E1E1E",
            corner_radius=0
        )
        main_container.pack(fill="both", expand=True)
        
        # Create header with close button
        header_frame = ctk.CTkFrame(
            main_container,
            fg_color="#252526",
            height=30,
            corner_radius=0
        )
        header_frame.pack(fill="x", padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        # Title label
        title_label = ctk.CTkLabel(
            header_frame,
            text="💡 Suggestions",
            font=("Consolas", 11, "bold"),
            text_color="#CCCCCC",
            anchor="w"
        )
        title_label.pack(side="left", padx=10, pady=5)
        
        # Close button (X)
        close_btn = ctk.CTkButton(
            header_frame,
            text="✕",
            width=30,
            height=25,
            fg_color="transparent",
            hover_color="#E81123",
            text_color="#CCCCCC",
            font=("Consolas", 16, "bold"),
            corner_radius=0,
            command=self._close_popup
        )
        close_btn.pack(side="right", padx=5, pady=2)
        
        # Create scrollable frame for suggestions
        max_height = min(250, len(suggestions) * 35 + 10)  # More space per item
        self.scroll_frame = ctk.CTkScrollableFrame(
            main_container,
            width=400,  # Wider for better readability
            height=max_height,
            fg_color="#1E1E1E"
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Create suggestion items
        self.suggestion_buttons = []
        for idx, suggestion in enumerate(suggestions):
            self._create_suggestion_item(idx, suggestion)
        
        # Position popup with better spacing (20px below the cursor line)
        self.geometry(f"+{x}+{y + 20}")
        
        # Show popup
        self.deiconify()
        self.lift()
        
        # Highlight first item
        if self.suggestion_buttons:
            self._highlight_item(0)
    
    def _create_suggestion_item(self, idx: int, suggestion: SuggestionItem):
        """Create a single suggestion item button"""
        # Get color for type
        type_color = self.TYPE_COLORS.get(suggestion.type, '#CCCCCC')
        
        # Create frame for item
        item_frame = ctk.CTkFrame(
            self.scroll_frame,
            fg_color="transparent",
            height=32  # Taller for better readability
        )
        item_frame.pack(fill="x", pady=2)
        item_frame.pack_propagate(False)
        
        # Create button for the suggestion
        btn = ctk.CTkButton(
            item_frame,
            text=suggestion.display_text,
            anchor="w",
            fg_color="transparent",
            hover_color="#2D2D30",
            text_color=type_color,
            font=("Consolas", 12),
            command=lambda: self._select_item(idx)
        )
        btn.pack(side="left", fill="both", expand=True, padx=5)
        
        # Add description label if available
        if suggestion.description:
            desc_label = ctk.CTkLabel(
                item_frame,
                text=suggestion.description[:40],  # Truncate long descriptions
                text_color="#808080",
                font=("Consolas", 9),
                anchor="e"
            )
            desc_label.pack(side="right", padx=5)
        
        # Add type badge
        type_badge = ctk.CTkLabel(
            item_frame,
            text=suggestion.type[:3].upper(),  # First 3 letters
            width=35,
            height=25,
            fg_color=type_color,
            text_color="#1E1E1E",
            font=("Consolas", 8, "bold"),
            corner_radius=3
        )
        type_badge.pack(side="right", padx=5)
        
        self.suggestion_buttons.append((btn, item_frame, suggestion))
    
    def _highlight_item(self, index: int):
        """Highlight a suggestion item"""
        # Remove previous highlight
        for btn, frame, _ in self.suggestion_buttons:
            btn.configure(fg_color="transparent")
        
        # Add new highlight
        if 0 <= index < len(self.suggestion_buttons):
            btn, frame, _ = self.suggestion_buttons[index]
            btn.configure(fg_color="#2D2D30")
            self.selected_index = index
            
            # Scroll to item if needed
            frame.update_idletasks()
            self.scroll_frame._parent_canvas.yview_moveto(
                index / len(self.suggestion_buttons)
            )
    
    def _select_item(self, index: int):
        """Select a suggestion item"""
        if 0 <= index < len(self.suggestions):
            suggestion = self.suggestions[index]
            self.on_select(suggestion.text)
            self.destroy()
    
    def _close_popup(self):
        """Close the popup window"""
        self.destroy()
    
    def move_selection_up(self):
        """Move selection up"""
        new_index = max(0, self.selected_index - 1)
        self._highlight_item(new_index)
    
    def move_selection_down(self):
        """Move selection down"""
        new_index = min(len(self.suggestions) - 1, self.selected_index + 1)
        self._highlight_item(new_index)
    
    def select_current(self):
        """Select the currently highlighted item"""
        self._select_item(self.selected_index)


class AutocompleteTextbox:
    """
    Wrapper for CTkTextbox that adds autocomplete functionality
    """
    
    def __init__(
        self,
        textbox: ctk.CTkTextbox,
        autocomplete_engine,
        trigger_chars: str = ".",
        min_chars: int = 0
    ):
        """
        Initialize autocomplete textbox
        
        Args:
            textbox: The CTkTextbox widget to add autocomplete to
            autocomplete_engine: AutocompleteEngine instance
            trigger_chars: Characters that trigger autocomplete
            min_chars: Minimum characters before showing suggestions
        """
        self.textbox = textbox
        self.engine = autocomplete_engine
        self.trigger_chars = trigger_chars
        self.min_chars = min_chars
        self.popup: Optional[AutocompletePopup] = None
        self._autocomplete_after_id = None
        
        # Bind events
        self.textbox.bind('<KeyRelease>', self._on_key_release)
        self.textbox.bind('<Control-space>', self._on_ctrl_space)
        self.textbox.bind('<Escape>', self._on_escape)
        self.textbox.bind('<Button-1>', self._on_click)
        
        # Store original bindings for arrow keys
        self._setup_navigation()
    
    def _setup_navigation(self):
        """Setup keyboard navigation for popup"""
        self.textbox.bind('<Up>', self._on_up_arrow)
        self.textbox.bind('<Down>', self._on_down_arrow)
        self.textbox.bind('<Return>', self._on_return)
        self.textbox.bind('<Tab>', self._on_tab)
    
    def _on_key_release(self, event):
        """Handle key release event"""
        # Ignore navigation and command keys
        if event.keysym in ['Up', 'Down', 'Left', 'Right', 'Return', 'Escape', 'Tab', 'Control_L', 'Control_R', 'Shift_L', 'Shift_R', 'Caps_Lock', 'Alt_L', 'Alt_R']:
            return

        char = event.char
        if char in self.trigger_chars or (char and len(char) == 1 and char.isalnum()):
            self._schedule_autocomplete()
        else:
            self._close_popup()
    
    def _on_ctrl_space(self, event):
        """Handle Ctrl+Space to trigger autocomplete"""
        self._show_autocomplete()
        return "break"

    def _on_click(self, event):
        """Close popup when clicking in the text box"""
        self._close_popup()
    
    def _on_escape(self, event):
        """Handle Escape to close popup"""
        if self.popup:
            self.popup.destroy()
            self.popup = None
            return "break"
    
    def _on_up_arrow(self, event):
        """Handle Up arrow key"""
        if self.popup:
            self.popup.move_selection_up()
            return "break"
    
    def _on_down_arrow(self, event):
        """Handle Down arrow key"""
        if self.popup:
            self.popup.move_selection_down()
            return "break"
    
    def _on_return(self, event):
        """Handle Return/Enter key"""
        if self.popup:
            self.popup.select_current()
            return "break"
    
    def _on_tab(self, event):
        """Handle Tab key"""
        if self.popup:
            self.popup.select_current()
            return "break"

    def _close_popup(self):
        """Close the autocomplete popup if it exists"""
        if self.popup:
            try:
                self.popup.destroy()
            except Exception:
                pass
            self.popup = None
        if self._autocomplete_after_id:
            self.textbox.after_cancel(self._autocomplete_after_id)
            self._autocomplete_after_id = None
    
    def _schedule_autocomplete(self):
        """Debounce autocomplete to keep popup responsive"""
        if self._autocomplete_after_id:
            self.textbox.after_cancel(self._autocomplete_after_id)
        self._autocomplete_after_id = self.textbox.after(75, self._show_autocomplete)

    def _show_autocomplete(self):
        """Show autocomplete popup"""
        self._autocomplete_after_id = None
        # Close existing popup
        if self.popup:
            self.popup.destroy()
            self.popup = None

        # Get current cursor position
        cursor_index = self.textbox.index("insert")
        row, col = map(int, cursor_index.split('.'))

        # Get all text and calculate position
        all_text = self.textbox.get("1.0", "end-1c")
        cursor_pos = self._get_position_from_index(all_text, row - 1, col)

        # Get suggestions
        result = self.engine.get_suggestions(all_text, cursor_pos)
        if not result.suggestions:
            return

        # Convert suggestions to SuggestionItems
        suggestions = [
            SuggestionItem(
                text=s.text,
                display_text=s.display_text,
                type=s.type,
                description=s.description,
                auto_suffix=s.auto_suffix
            )
            for s in result.suggestions[:12]
        ]

        # Calculate popup position
        bbox = self.textbox.bbox(f"{row}.{col}")
        if bbox:
            x = self.textbox.winfo_rootx() + bbox[0]
            y = self.textbox.winfo_rooty() + bbox[1] + bbox[3]

            # Create popup
            self.popup = AutocompletePopup(
                self.textbox,
                suggestions,
                self._insert_suggestion,
                x,
                y
            )
    
    def _insert_suggestion(self, text: str, suggestion_item=None):
        """Insert selected suggestion into textbox - WITH AUTO-SUFFIX SUPPORT"""
        # Get current position
        cursor_index = self.textbox.index("insert")
        row, col = map(int, cursor_index.split('.'))
        
        # Get current line
        line_start = f"{row}.0"
        line_end = f"{row}.end"
        line_text = self.textbox.get(line_start, line_end)
        
        # Find start of current WORD ONLY (not the whole line)
        word_start = col
        
        # Go back to find word boundary, but stop at spaces, braces, pipes
        while word_start > 0:
            prev_char = line_text[word_start - 1]
            # Stop at word boundaries
            if prev_char in ' \t,(){}|':
                break
            word_start -= 1
        
        # Delete ONLY the partial word (not everything before it)
        delete_start = f"{row}.{word_start}"
        delete_end = cursor_index
        
        self.textbox.delete(delete_start, delete_end)
        
        # Insert suggestion at the word start position
        self.textbox.insert(delete_start, text)
        
        # Move cursor to end of inserted text
        new_col = word_start + len(text)
        self.textbox.mark_set("insert", f"{row}.{new_col}")
        
        # Add space after for better UX (except for special chars like }, ;, |)
        if text and text[-1] not in '}|;,':
            self.textbox.insert(f"{row}.{new_col}", " ")
            new_col += 1
            self.textbox.mark_set("insert", f"{row}.{new_col}")
        
        # Close popup
        if self.popup:
            self.popup.destroy()
            self.popup = None
    
    def _get_position_from_index(self, text: str, row: int, col: int) -> int:
        """Convert row/col to absolute position in text"""
        lines = text.split('\n')
        position = 0
        
        for i in range(row):
            if i < len(lines):
                position += len(lines[i]) + 1  # +1 for newline
        
        position += col
        return position