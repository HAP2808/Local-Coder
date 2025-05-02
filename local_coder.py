import sys
import os
import tkinter as tk
from tkinter import scrolledtext, ttk
from PIL import ImageGrab, ImageTk
import keyboard
import ctypes
import threading
import uuid
import win32gui
import win32con
from ai_processor import AIProcessor
import pystray
from PIL import Image, ImageDraw
from win10toast import ToastNotifier

# Windows API constants
WDA_EXCLUDEFROMCAPTURE = 0x00000011
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080

# Load Windows APIs
user32 = ctypes.WinDLL('user32', use_last_error=True)
_set_window_display_affinity = user32.SetWindowDisplayAffinity
_set_window_display_affinity.argtypes = (ctypes.wintypes.HWND, ctypes.wintypes.UINT)
_set_window_display_affinity.restype = ctypes.wintypes.BOOL
_set_window_long = user32.SetWindowLongPtrW
_set_window_long.argtypes = (ctypes.wintypes.HWND, ctypes.c_int, ctypes.wintypes.LONG)
_set_window_long.restype = ctypes.wintypes.LONG
_get_window_long = user32.GetWindowLongPtrW
_get_window_long.argtypes = (ctypes.wintypes.HWND, ctypes.c_int)
_get_window_long.restype = ctypes.wintypes.LONG

def hide_from_capture(hwnd):
    """Hide window from screen capture using SetWindowDisplayAffinity."""
    try:
        if not hwnd:
            print("Invalid window handle")
            return False
        if not _set_window_display_affinity(hwnd, WDA_EXCLUDEFROMCAPTURE):
            error = ctypes.get_last_error()
            print(f"Error hiding from capture: {error}")
            return False
        return True
    except Exception as e:
        print(f"Exception in hide_from_capture: {e}")
        return False

class LocalCoderApp:
    def __init__(self, root):
        self.root = root
        self.click_through_enabled = True
        self.move_step = 20
        self.screenshot_files = []
        self.screenshot_thumbnails = []
        self.opacity = 0.8
        self.settings_dialog = None
        self.init_ui()
        self.setup_shortcuts()
        self.root.update_idletasks()
        self.apply_screen_sharing_protection()
        self.create_tray_icon()

    def init_ui(self):
        """Initialize the UI with a professional, minimal design."""
        self.root.overrideredirect(True)
        self.root.attributes('-alpha', self.opacity)
        self.root.attributes('-topmost', True)

        # Center window with minimal size
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = 400
        window_height = 60
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Main frame with dark theme
        self.main_frame = tk.Frame(self.root, bg='#1e1e1e')
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Header frame
        self.header_frame = tk.Frame(self.main_frame, bg='#1e1e1e')
        self.header_frame.pack(fill=tk.X, padx=2, pady=2)

        # Instruction label
        self.instruction_label = tk.Label(
            self.header_frame,
            text="Ctrl+H to Capture • Ctrl+Enter to Process • Ctrl+S for Settings",
            font=("Segoe UI", 10),
            fg="#e0e0e0",
            bg="#1e1e1e",
            padx=2,
            pady=2
        )
        self.instruction_label.pack(side=tk.LEFT)

        # Settings button
        self.settings_button = tk.Button(
            self.header_frame,
            text="⚙",
            font=("Segoe UI", 10, "bold"),
            bg="#2d2d2d",
            fg="#0078d7",
            relief=tk.FLAT,
            command=self.toggle_settings_dialog,
            padx=2,
            pady=2
        )
        self.settings_button.pack(side=tk.RIGHT)
        self.settings_button.bind("<Enter>", lambda e: self.settings_button.config(bg="#444444"))
        self.settings_button.bind("<Leave>", lambda e: self.settings_button.config(bg="#2d2d2d"))

        # Thumbnails frame
        self.thumbnails_frame = tk.Frame(self.main_frame, bg='#1e1e1e')
        self.thumbnails_frame.pack(fill=tk.X, padx=2, pady=2)
        self.thumbnails_container = tk.Frame(self.thumbnails_frame, bg='#1e1e1e')
        self.thumbnails_container.pack(fill=tk.X, pady=2)

        # Make window draggable
        for widget in (self.header_frame, self.instruction_label):
            widget.bind("<ButtonPress-1>", self.start_move)
            widget.bind("<ButtonRelease-1>", self.stop_move)
            widget.bind("<B1-Motion>", self.do_move)

    def setup_shortcuts(self):
        """Set up global keyboard shortcuts."""
        keyboard.add_hotkey('ctrl+h', self.take_screenshot, suppress=True)
        keyboard.add_hotkey('esc', self.toggle_visibility, suppress=True)
        keyboard.add_hotkey('ctrl+f', self.toggle_click_through, suppress=True)
        keyboard.add_hotkey('ctrl+q', self.close_application, suppress=True)
        keyboard.add_hotkey('ctrl+enter', self.process_all_screenshots, suppress=True)
        keyboard.add_hotkey('ctrl+o', self.start_from_scratch, suppress=True)
        keyboard.add_hotkey('ctrl+s', self.toggle_settings_dialog, suppress=True)
        keyboard.add_hotkey('ctrl+left', lambda: self.move_window(-self.move_step, 0), suppress=True)
        keyboard.add_hotkey('ctrl+right', lambda: self.move_window(self.move_step, 0), suppress=True)
        keyboard.add_hotkey('ctrl+up', lambda: self.move_window(0, -self.move_step), suppress=True)
        keyboard.add_hotkey('ctrl+down', lambda: self.move_window(0, self.move_step), suppress=True)

    def apply_screen_sharing_protection(self):
        """Hide the main window from screen capture."""
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        if not hide_from_capture(hwnd):
            self.show_notification("Warning: Could not hide UI from screen capture.")

    def toggle_settings_dialog(self):
        """Toggle the settings dialog (open if closed, close if open)."""
        if self.settings_dialog and self.settings_dialog.winfo_exists():
            self.settings_dialog.destroy()
            self.settings_dialog = None
        else:
            # Schedule dialog creation to avoid flicker
            self.root.after(50, self.show_settings_dialog)

    def show_settings_dialog(self):
        """Show a modal dialog with keyboard shortcuts and opacity slider."""
        # Create Toplevel and immediately hide it
        self.settings_dialog = tk.Toplevel(self.root)
        self.settings_dialog.withdraw()  # Hide to prevent flicker
        self.root.update_idletasks()  # Ensure main window is stable

        # Configure window attributes
        self.settings_dialog.overrideredirect(True)
        self.settings_dialog.attributes('-topmost', True)
        self.settings_dialog.configure(bg='#2d2d2d')

        # Make the dialog transient to the main window
        self.settings_dialog.transient(self.root)

        # Apply tool window style to hide from taskbar
        hwnd = ctypes.windll.user32.GetParent(self.settings_dialog.winfo_id())
        current_style = _get_window_long(hwnd, GWL_EXSTYLE)
        _set_window_long(hwnd, GWL_EXSTYLE, current_style | WS_EX_TOOLWINDOW)

        # Apply screen capture protection
        self.settings_dialog.update_idletasks()
        if not hide_from_capture(hwnd):
            print("Failed to hide settings dialog from screen capture")

        # Center dialog
        dialog_width = 400
        dialog_height = 350
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        self.settings_dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # Dialog content
        frame = tk.Frame(self.settings_dialog, bg='#2d2d2d', padx=2, pady=2)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Settings", font=("Segoe UI", 12, "bold"), fg="#e0e0e0", bg="#2d2d2d").pack(pady=2)

        # Opacity slider
        opacity_frame = tk.Frame(frame, bg="#2d2d2d")
        opacity_frame.pack(fill=tk.X, pady=5)
        tk.Label(opacity_frame, text="Opacity:", font=("Segoe UI", 9, "bold"), fg="#0078d7", bg="#2d2d2d", width=12, anchor="w").pack(side=tk.LEFT, padx=2)
        self.opacity_label = tk.Label(opacity_frame, text=f"{self.opacity:.1f}", font=("Segoe UI", 9), fg="#e0e0e0", bg="#2d2d2d", width=4)
        self.opacity_label.pack(side=tk.LEFT, padx=2)
        opacity_slider = ttk.Scale(
            opacity_frame,
            from_=0.1,
            to=1.0,
            orient=tk.HORIZONTAL,
            command=self.update_opacity
        )
        opacity_slider.set(self.opacity)
        opacity_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # Shortcuts section
        tk.Label(frame, text="Keyboard Shortcuts", font=("Segoe UI", 12, "bold"), fg="#e0e0e0", bg="#2d2d2d").pack(pady=2)

        shortcuts = [
            ("Ctrl+H", "Take a screenshot"),
            ("Ctrl+Enter", "Process screenshots"),
            ("Ctrl+O", "Start from scratch"),
            ("Ctrl+S", "Toggle settings"),
            ("Ctrl+F", "Toggle click-through"),
            ("Ctrl+Q", "Quit application"),
            ("Esc", "Hide/Show UI"),
            ("Ctrl+↑↓←→", "Move window"),
        ]

        for key, desc in shortcuts:
            row = tk.Frame(frame, bg="#2d2d2d")
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=key, font=("Segoe UI", 9, "bold"), fg="#0078d7", bg="#2d2d2d", width=12, anchor="w").pack(side=tk.LEFT, padx=2)
            tk.Label(row, text=desc, font=("Segoe UI", 9), fg="#e0e0e0", bg="#2d2d2d", anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Show the dialog after full configuration
        self.settings_dialog.update_idletasks()
        self.settings_dialog.deiconify()

    def update_opacity(self, value):
        """Update UI opacity based on slider value."""
        try:
            self.opacity = float(value)
            self.root.attributes('-alpha', self.opacity)
            self.opacity_label.config(text=f"{self.opacity:.1f}")
        except Exception as e:
            print(f"Error updating opacity: {e}")

    def take_screenshot(self):
        """Capture a screenshot and add it to the UI."""
        self.root.withdraw()
        self.root.after(500, self._capture_screen)

    def _capture_screen(self):
        """Save and display a screenshot."""
        try:
            screenshot = ImageGrab.grab()
            file_name = f"screenshot_{uuid.uuid4().hex[:8]}.png"
            screenshot.save(file_name)
            self.screenshot_files.append(file_name)
            self.root.deiconify()
            self.add_screenshot_thumbnail(file_name)
            self._resize_window_to_fit_content()
        except Exception as e:
            print(f"Error capturing screenshot: {e}")
            self.root.deiconify()
            self.show_temporary_message("Failed to capture screenshot.")

    def add_screenshot_thumbnail(self, file_path):
        """Add a thumbnail for a screenshot."""
        try:
            img = ImageTk.PhotoImage(file=file_path)
            thumb_frame = tk.Frame(self.thumbnails_container, bg="#2d2d2d", padx=2, pady=2)
            thumb_frame.pack(side=tk.LEFT, padx=2, pady=2)

            img_width, img_height = img.width(), img.height()
            max_size = 80
            scale = min(max_size / img_width, max_size / img_height)
            img_reduced = ImageTk.PhotoImage(Image.open(file_path).resize((int(img_width * scale), int(img_height * scale))))

            img_label = tk.Label(thumb_frame, image=img_reduced, bg="#2d2d2d")
            img_label.image = img_reduced
            img_label.pack()

            delete_btn = tk.Button(
                thumb_frame, text="✖", font=("Segoe UI", 7), bg="#2d2d2d", fg="#ff5555", relief=tk.FLAT,
                command=lambda: self.remove_screenshot(file_path, thumb_frame)
            )
            delete_btn.pack(anchor=tk.NE)
            self.screenshot_thumbnails.append((file_path, thumb_frame))
        except Exception as e:
            print(f"Error creating thumbnail: {e}")

    def _resize_window_to_fit_content(self):
        """Resize window to fit thumbnails."""
        try:
            self.root.update_idletasks()
            required_height = self.main_frame.winfo_reqheight() + 10
            window_width = self.root.winfo_width()
            screen_height = self.root.winfo_screenheight()
            new_height = min(required_height, int(screen_height * 0.7))
            x = (self.root.winfo_screenwidth() - window_width) // 2
            y = (screen_height - new_height) // 2
            self.root.geometry(f"{window_width}x{new_height}+{x}+{y}")
        except Exception as e:
            print(f"Error resizing window: {e}")

    def remove_screenshot(self, file_path, thumbnail_frame):
        """Remove a screenshot and update UI."""
        try:
            if file_path in self.screenshot_files:
                self.screenshot_files.remove(file_path)
            thumbnail_frame.destroy()
            self.screenshot_thumbnails = [(f, t) for f, t in self.screenshot_thumbnails if f != file_path]
            if os.path.exists(file_path):
                os.remove(file_path)
            self._resize_window_to_fit_content()
        except Exception as e:
            print(f"Error removing screenshot: {e}")

    def process_all_screenshots(self):
        """Process all screenshots and display results."""
        if not self.screenshot_files:
            self.show_temporary_message("No screenshots to process. Use Ctrl+H to capture.")
            return
        self.thumbnails_frame.pack_forget()
        if hasattr(self, 'result_frame') and self.result_frame.winfo_exists():
            self.result_frame.destroy()
        self.root.bind("<Escape>", lambda e: self.hide_results())
        threading.Thread(target=self._process_screenshots_thread, daemon=True).start()

    def _process_screenshots_thread(self):
        """Process screenshots in a background thread."""
        try:
            self.root.after(0, self.show_loading_sections)
            result = AIProcessor.process_screenshots(self.screenshot_files, callback=None)
            self.root.after(0, lambda: self.show_professional_results(result))
        except Exception as e:
            print(f"Error in screenshot processing thread: {e}")
            self.root.after(0, lambda: self.show_error(f"Processing failed: {str(e)}"))

    def show_loading_sections(self):
        """Display a loading indicator."""
        try:
            self.click_through_enabled = False
            self.make_click_through()

            window_width = self.root.winfo_width()
            window_height = min(self.root.winfo_screenheight() // 2, 400)
            self.root.geometry(f"{window_width}x{window_height}+{self.root.winfo_x()}+{self.root.winfo_y()}")

            self.result_frame = tk.Frame(self.main_frame, bg='#1e1e1e')
            self.result_frame.pack(fill=tk.BOTH, expand=True)

            loading_frame = tk.Frame(self.result_frame, bg='#1e1e1e')
            loading_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
            tk.Label(loading_frame, text="⏳ Processing...", font=("Segoe UI", 14), fg="#0078d7", bg="#1e1e1e").pack(pady=2)

            def animate():
                if not loading_frame.winfo_exists():
                    return
                label = loading_frame.winfo_children()[0]
                text = label.cget("text")
                label.config(text=text + "." if len(text) < 20 else "⏳ Processing...")
                self.root.after(500, animate)
            animate()
        except Exception as e:
            print(f"Error showing loading sections: {e}")

    def show_professional_results(self, result):
        """Display AI-generated results in a professional, responsive layout."""
        try:
            if hasattr(self, 'result_frame') and self.result_frame.winfo_exists():
                self.result_frame.destroy()

            self.result_frame = tk.Frame(self.main_frame, bg='#1e1e1e')
            self.result_frame.pack(fill=tk.BOTH, expand=True)

            # Use 95% of screen with margins
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            window_width = int(screen_width * 0.95)
            window_height = int(screen_height * 0.95)
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

            # Calculate section heights
            question_height = int(window_height * 0.10)  # 10%
            column_height = int(window_height * 0.90)    # 90% for columns
            explanation_height = int(column_height * 0.30)  # 30%
            complexity_height = int(column_height * 0.25)   # 25%
            dry_run_height = int(column_height * 0.35)      # 35%
            code_height = int(column_height * 0.90)         # 90%

            # Main container
            container = tk.Frame(self.result_frame, bg='#1e1e1e')
            container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

            # Question section (full width, 10% height)
            question_frame = tk.Frame(container, bg='#2d2d2d', bd=1, relief=tk.SOLID)
            question_frame.pack(fill=tk.X, pady=2)
            self._create_collapsible_section(
                question_frame,
                "Question",
                result.get("question", ""),
                "📝",
                is_code=False,
                pixel_height=question_height,
                wraplength=window_width - 20
            )

            # Two-column layout
            columns_frame = tk.Frame(container, bg='#1e1e1e')
            columns_frame.pack(fill=tk.BOTH, expand=True, pady=2)

            # Left column: Explanation, Complexity, Example Dry Run (60% width)
            left_column = tk.Frame(columns_frame, bg='#2d2d2d', width=int(window_width * 0.6))
            left_column.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 2))
            left_column.pack_propagate(False)

            # Explanation (30% of column)
            explanation_frame = tk.Frame(left_column, bg='#2d2d2d', bd=1, relief=tk.SOLID)
            explanation_frame.pack(fill=tk.X, pady=(0, 2))
            self._create_collapsible_section(
                explanation_frame,
                "Explanation",
                result.get("explanation", ""),
                "🔑",
                is_code=False,
                pixel_height=explanation_height,
                wraplength=int(window_width * 0.6) - 20
            )

            # Complexity (25% of column)
            complexity_frame = tk.Frame(left_column, bg='#2d2d2d', bd=1, relief=tk.SOLID)
            complexity_frame.pack(fill=tk.X, pady=(0, 2))
            self._create_collapsible_section(
                complexity_frame,
                "Complexity",
                result.get("complexity", ""),
                "⏱️",
                is_code=False,
                pixel_height=complexity_height,
                wraplength=int(window_width * 0.6) - 20
            )

            # Example Dry Run (35% of column)
            dry_run_frame = tk.Frame(left_column, bg='#2d2d2d', bd=1, relief=tk.SOLID)
            dry_run_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 2))
            self._create_collapsible_section(
                dry_run_frame,
                "Example Dry Run",
                result.get("dry_run", ""),
                "🔄",
                is_code=True,
                pixel_height=dry_run_height
            )

            # Right column: Code (40% width, 90% height)
            code_frame = tk.Frame(columns_frame, bg='#2d2d2d', bd=1, relief=tk.SOLID)
            code_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(2, 0))
            self._create_collapsible_section(
                code_frame,
                "Code",
                result.get("solution", ""),
                "💻",
                is_code=True,
                pixel_height=code_height
            )

        except Exception as e:
            print(f"Error showing results: {e}")
            self.show_error(f"Error displaying results: {str(e)}")

    def _create_collapsible_section(self, parent, title, content, icon, is_code=False, pixel_height=100, wraplength=None):
        """Create a collapsible section with fixed pixel height and styled scrollbar."""
        frame = tk.Frame(parent, bg='#2d2d2d')
        frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Header
        header = tk.Frame(frame, bg='#2d2d2d')
        header.pack(fill=tk.X)
        tk.Label(header, text=icon, font=("Segoe UI", 12), fg="#0078d7", bg="#2d2d2d").pack(side=tk.LEFT, padx=2)
        tk.Label(header, text=title, font=("Segoe UI", 12, "bold"), fg="#0078d7", bg="#2d2d2d").pack(side=tk.LEFT)
        toggle_btn = tk.Label(header, text="▼", font=("Segoe UI", 10), fg="#e0e0e0", bg="#2d2d2d", cursor="hand2")
        toggle_btn.pack(side=tk.RIGHT, padx=2)
        toggle_btn.bind("<Enter>", lambda e: toggle_btn.config(fg="#ffffff"))
        toggle_btn.bind("<Leave>", lambda e: toggle_btn.config(fg="#e0e0e0"))

        # Content area
        content_frame = tk.Frame(frame, bg='#2d2d2d')
        canvas = tk.Canvas(content_frame, bg='#2d2d2d', highlightthickness=0, height=pixel_height)
        scrollbar = tk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)
        inner_frame = tk.Frame(canvas, bg='#2d2d2d')
        canvas.create_window((0, 0), window=inner_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Style scrollbar
        scrollbar.config(
            bg="#2d2d2d",
            troughcolor="#3c3c3c",
            activebackground="#0078d7",
            highlightbackground="#0078d7",
            width=8
        )

        # Mouse wheel binding
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Check if scrollbar is needed
        def _configure_canvas(event):
            canvas.update_idletasks()
            content_height = inner_frame.winfo_reqheight()
            canvas_height = canvas.winfo_height()
            canvas.configure(scrollregion=canvas.bbox("all"))
            if content_height <= canvas_height:
                scrollbar.pack_forget()
            else:
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        inner_frame.bind("<Configure>", _configure_canvas)

        if is_code:
            text_widget = scrolledtext.ScrolledText(
                inner_frame, height=pixel_height//15, bg="#1a1a1a", fg="#ffffff", font=("Consolas", 10),
                wrap=tk.NONE, insertbackground="white", borderwidth=0
            )
            text_widget.insert(tk.END, content)
            text_widget.config(state=tk.DISABLED)
            text_widget.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
            copy_btn = tk.Button(
                inner_frame, text="Copy", bg="#0078d7", fg="white", font=("Segoe UI", 9),
                command=lambda: self.copy_specific_code(content), padx=2, pady=2
            )
            copy_btn.pack(side=tk.RIGHT, padx=2, pady=2)
            copy_btn.bind("<Enter>", lambda e: copy_btn.config(bg="#005ba1"))
            copy_btn.bind("<Leave>", lambda e: copy_btn.config(bg="#0078d7"))
        else:
            tk.Label(
                inner_frame, text=content, font=("Segoe UI", 10), fg="#e0e0e0", bg="#2d2d2d",
                wraplength=wraplength or (parent.winfo_screenwidth() // 5), justify=tk.LEFT
            ).pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        content_frame.pack(fill=tk.BOTH, expand=True)

        def toggle():
            if content_frame.winfo_ismapped():
                content_frame.pack_forget()
                toggle_btn.config(text="▶")
            else:
                content_frame.pack(fill=tk.BOTH, expand=True)
                toggle_btn.config(text="▼")
        toggle_btn.bind("<Button-1>", lambda e: toggle())

    def show_error(self, error_message):
        """Display an error message."""
        try:
            if hasattr(self, 'result_frame') and self.result_frame.winfo_exists():
                self.result_frame.destroy()
            self.result_frame = tk.Frame(self.main_frame, bg='#1e1e1e')
            self.result_frame.pack(fill=tk.BOTH, expand=True)
            error_frame = tk.Frame(self.result_frame, bg='#1e1e1e')
            error_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
            tk.Label(error_frame, text="❌", font=("Segoe UI", 24), fg="#ff4d4d", bg="#1e1e1e").pack()
            tk.Label(error_frame, text="Error", font=("Segoe UI", 16, "bold"), fg="#e0e0e0", bg="#1e1e1e").pack(pady=2)
            tk.Label(error_frame, text=error_message, font=("Segoe UI", 12), fg="#e0e0e0", bg="#1e1e1e", wraplength=300).pack(pady=2)
            tk.Button(error_frame, text="Back", bg="#0078d7", fg="white", font=("Segoe UI", 10), command=self.hide_results).pack(pady=2)
        except Exception as e:
            print(f"Error displaying error message: {e}")

    def hide_results(self):
        """Hide results and show thumbnail view."""
        try:
            if hasattr(self, 'result_frame') and self.result_frame.winfo_exists():
                self.result_frame.destroy()
            self.root.unbind_all("<MouseWheel>")
            self.thumbnails_frame.pack(fill=tk.X, padx=2, pady=2, after=self.header_frame)
            self._resize_window_to_fit_content()
            if self.click_through_enabled:
                self.make_click_through()
        except Exception as e:
            print(f"Error hiding results: {e}")

    def start_from_scratch(self):
        """Reset the UI for a new question."""
        try:
            for file_path, thumb_frame in self.screenshot_thumbnails:
                thumb_frame.destroy()
                if os.path.exists(file_path):
                    os.remove(file_path)
            self.screenshot_files = []
            self.screenshot_thumbnails = []
            if hasattr(self, 'result_frame') and self.result_frame.winfo_exists():
                self.result_frame.destroy()
            self.thumbnails_frame.pack(fill=tk.X, padx=2, pady=2, after=self.header_frame)
            self._resize_window_to_fit_content()
            self.show_temporary_message("Started a new question. Use Ctrl+H to capture.")
        except Exception as e:
            print(f"Error in start_from_scratch: {e}")

    def copy_specific_code(self, code_text):
        """Copy text to clipboard."""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(code_text)
        except Exception as e:
            print(f"Error copying code: {e}")

    def toggle_visibility(self):
        """Toggle UI visibility."""
        try:
            if self.root.state() == 'normal':
                self.root.withdraw()
            else:
                self.root.deiconify()
                self.root.attributes('-topmost', True)
        except Exception as e:
            print(f"Error toggling visibility: {e}")

    def make_click_through(self):
        """Toggle click-through mode."""
        try:
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            current_style = ctypes.windll.user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            new_style = current_style | WS_EX_LAYERED | WS_EX_TRANSPARENT if self.click_through_enabled else current_style & ~WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, new_style)
            self.root.update_idletasks()
        except Exception as e:
            print(f"Error setting click-through: {e}")

    def toggle_click_through(self):
        """Toggle click-through state."""
        self.click_through_enabled = not self.click_through_enabled
        self.make_click_through()

    def move_window(self, deltax, deltay):
        """Move window by delta values."""
        try:
            x = self.root.winfo_x() + deltax
            y = self.root.winfo_y() + deltay
            self.root.geometry(f"+{x}+{y}")
        except Exception as e:
            print(f"Error moving window: {e}")

    def start_move(self, event):
        """Start window drag."""
        self.click_through_enabled = False
        self.make_click_through()
        self.x = event.x
        self.y = event.y

    def stop_move(self, event):
        """Stop window drag."""
        self.x = None
        self.y = None
        if self.click_through_enabled:
            self.make_click_through()

    def do_move(self, event):
        """Perform window drag."""
        try:
            deltax = event.x - self.x
            deltay = event.y - self.y
            x = self.root.winfo_x() + deltax
            y = self.root.winfo_y() + deltay
            self.root.geometry(f"+{x}+{y}")
        except Exception as e:
            print(f"Error dragging window: {e}")

    def show_temporary_message(self, message, duration=3000):
        """Show a temporary message."""
        try:
            msg_frame = tk.Frame(self.thumbnails_frame, bg="#0078d7", padx=2, pady=2)
            msg_frame.pack(fill=tk.X, pady=2)
            tk.Label(msg_frame, text=message, font=("Segoe UI", 10), fg="white", bg="#0078d7").pack()
            self.root.after(duration, lambda: self.fade_out_message(msg_frame))
        except Exception as e:
            print(f"Error showing temporary message: {e}")

    def fade_out_message(self, frame, alpha=1.0, step=0.1):
        """Fade out a message frame."""
        try:
            if alpha <= 0 or not frame.winfo_exists():
                frame.destroy()
                return
            alpha -= step
            frame.after(50, lambda: self.fade_out_message(frame, alpha, step))
        except:
            if frame.winfo_exists():
                frame.destroy()

    def show_notification(self, message):
        """Show a system notification."""
        try:
            toaster = ToastNotifier()
            toaster.show_toast("LocalCoder", message, duration=5, threaded=True)
        except Exception as e:
            print(f"Notification error: {e}")

    def create_tray_icon(self):
        """Create a system tray icon."""
        try:
            image = Image.new('RGB', (64, 64), color=(40, 40, 40))
            d = ImageDraw.Draw(image)
            d.text((20, 20), "LC", fill=(0, 120, 215), font_size=32)
            menu = pystray.Menu(
                pystray.MenuItem('Show Shortcuts', self.show_shortcuts),
                pystray.MenuItem('Quit', self.close_application)
            )
            self.tray_icon = pystray.Icon("LocalCoder", image, "LocalCoder", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            print(f"Error creating tray icon: {e}")

    def show_shortcuts(self, icon, item):
        """Show shortcuts in a message box."""
        try:
            msg = "\n".join([f"{k}: {d}" for k, d in [
                ("Ctrl+H", "Take a screenshot"),
                ("Ctrl+Enter", "Process screenshots"),
                ("Ctrl+O", "Start from scratch"),
                ("Ctrl+S", "Toggle settings"),
                ("Ctrl+F", "Toggle click-through"),
                ("Ctrl+Q", "Quit"),
                ("Esc", "Hide/Show UI"),
                ("Ctrl+Arrows", "Move window"),
            ]])
            ctypes.windll.user32.MessageBoxW(0, msg, "LocalCoder Shortcuts", 0)
        except Exception as e:
            print(f"Error showing shortcuts: {e}")

    def close_application(self):
        """Clean up and exit."""
        try:
            for file in self.screenshot_files:
                if os.path.exists(file):
                    os.remove(file)
            keyboard.unhook_all()
            self.root.destroy()
            sys.exit(0)
        except Exception as e:
            print(f"Error closing application: {e}")
            sys.exit(1)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("LocalCoder")
    app = LocalCoderApp(root)
    root.mainloop()