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
from ai_processor import AIProcessor  # Import singleton instance
import pystray
from PIL import Image, ImageDraw
from win10toast import ToastNotifier

# Windows API constants
WDA_EXCLUDEFROMCAPTURE = 0x00000011

# Load Windows APIs
user32 = ctypes.WinDLL('user32', use_last_error=True)
_set_window_display_affinity = user32.SetWindowDisplayAffinity
_set_window_display_affinity.argtypes = (ctypes.wintypes.HWND, ctypes.wintypes.UINT)
_set_window_display_affinity.restype = ctypes.wintypes.BOOL

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
        self.init_ui()
        self.setup_shortcuts()
        self.root.update_idletasks()  # Ensure window is fully realized
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
        self.header_frame.pack(fill=tk.X, padx=5, pady=5)

        # Instruction label
        self.instruction_label = tk.Label(
            self.header_frame,
            text="Ctrl+H to Capture • Ctrl+Enter to Process",
            font=("Segoe UI", 10),
            fg="#e0e0e0",
            bg="#1e1e1e",
            padx=5,
            pady=5
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
            command=self.show_settings_dialog,
            padx=5,
            pady=2
        )
        self.settings_button.pack(side=tk.RIGHT)
        self.settings_button.bind("<Enter>", lambda e: self.settings_button.config(bg="#444444"))
        self.settings_button.bind("<Leave>", lambda e: self.settings_button.config(bg="#2d2d2d"))

        # Thumbnails frame
        self.thumbnails_frame = tk.Frame(self.main_frame, bg='#1e1e1e')
        self.thumbnails_frame.pack(fill=tk.X, padx=10, pady=5)
        self.thumbnails_container = tk.Frame(self.thumbnails_frame, bg='#1e1e1e')
        self.thumbnails_container.pack(fill=tk.X, pady=3)

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
        keyboard.add_hotkey('ctrl+left', lambda: self.move_window(-self.move_step, 0), suppress=True)
        keyboard.add_hotkey('ctrl+right', lambda: self.move_window(self.move_step, 0), suppress=True)
        keyboard.add_hotkey('ctrl+up', lambda: self.move_window(0, -self.move_step), suppress=True)
        keyboard.add_hotkey('ctrl+down', lambda: self.move_window(0, self.move_step), suppress=True)

    def apply_screen_sharing_protection(self):
        """Hide the main window and settings dialog from screen capture."""
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        if not hide_from_capture(hwnd):
            self.show_notification("Warning: Could not hide UI from screen capture.")

    def show_settings_dialog(self):
        """Show a modal dialog with keyboard shortcuts."""
        if hasattr(self, 'settings_dialog') and self.settings_dialog.winfo_exists():
            self.settings_dialog.destroy()

        self.settings_dialog = tk.Toplevel(self.root)
        self.settings_dialog.overrideredirect(True)
        self.settings_dialog.attributes('-topmost', True)
        self.settings_dialog.configure(bg='#2d2d2d')

        # Apply screen capture protection after dialog is realized
        self.settings_dialog.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(self.settings_dialog.winfo_id())
        if not hide_from_capture(hwnd):
            print("Failed to hide settings dialog from screen capture")

        # Center dialog
        dialog_width = 400
        dialog_height = 300
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        self.settings_dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # Dialog content
        frame = tk.Frame(self.settings_dialog, bg='#2d2d2d', padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Keyboard Shortcuts", font=("Segoe UI", 12, "bold"), fg="#e0e0e0", bg="#2d2d2d").pack(pady=5)

        shortcuts = [
            ("Ctrl+H", "Take a screenshot"),
            ("Ctrl+Enter", "Process screenshots"),
            ("Ctrl+O", "Start from scratch"),
            ("Ctrl+F", "Toggle click-through"),
            ("Ctrl+Q", "Quit application"),
            ("Esc", "Hide/Show UI"),
            ("Ctrl+↑↓←→", "Move window"),
        ]

        for key, desc in shortcuts:
            row = tk.Frame(frame, bg="#2d2d2d")
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=key, font=("Segoe UI", 9, "bold"), fg="#0078d7", bg="#2d2d2d", width=12, anchor="w").pack(side=tk.LEFT, padx=5)
            tk.Label(row, text=desc, font=("Segoe UI", 9), fg="#e0e0e0", bg="#2d2d2d", anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(frame, text="Close", bg="#0078d7", fg="white", font=("Segoe UI", 10), command=self.settings_dialog.destroy).pack(pady=10)

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
            thumb_frame = tk.Frame(self.thumbnails_container, bg="#2d2d2d", padx=3, pady=3)
            thumb_frame.pack(side=tk.LEFT, padx=3, pady=3)

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
            tk.Label(loading_frame, text="⏳ Processing...", font=("Segoe UI", 14), fg="#0078d7", bg="#1e1e1e").pack(pady=10)

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
        """Display AI-generated results in a clean, collapsible layout."""
        try:
            if hasattr(self, 'result_frame') and self.result_frame.winfo_exists():
                self.result_frame.destroy()

            self.result_frame = tk.Frame(self.main_frame, bg='#1e1e1e')
            self.result_frame.pack(fill=tk.BOTH, expand=True)

            window_width = self.root.winfo_screenwidth() // 2
            window_height = min(self.root.winfo_screenheight() // 2, 600)
            x = (self.root.winfo_screenwidth() - window_width) // 2
            y = (self.root.winfo_screenheight() - window_height) // 2
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

            canvas = tk.Canvas(self.result_frame, bg='#1e1e1e', highlightthickness=0)
            scrollbar = tk.Scrollbar(self.result_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas, bg='#1e1e1e')

            scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=window_width - 20)
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

            if not result or not isinstance(result, dict):
                self.show_error("Invalid response format received")
                return

            sections = [
                ("Question", result.get("question", ""), "📝", False),
                ("Approach", result.get("explanation", ""), "🔑", False),
                ("Solution Code", result.get("solution", ""), "💻", True),
                ("Example Usage", result.get("example", ""), "🔄", True),
                ("Complexity Analysis", result.get("complexity", ""), "⏱️", False),
                ("Notes", result.get("notes", ""), "📋", False),
            ]

            for title, content, icon, is_code in sections:
                if content:
                    self._create_collapsible_section(scrollable_frame, title, content, icon, is_code)

            tk.Button(
                scrollable_frame, text="Close", bg="#d70000", fg="white", font=("Segoe UI", 10),
                command=self.hide_results, padx=10, pady=5
            ).pack(pady=10)
        except Exception as e:
            print(f"Error showing results: {e}")
            self.show_error(f"Error displaying results: {str(e)}")

    def _create_collapsible_section(self, parent, title, content, icon, is_code=False):
        """Create a collapsible section for results."""
        frame = tk.Frame(parent, bg='#1e1e1e')
        frame.pack(fill=tk.X, pady=5, padx=10)

        header = tk.Frame(frame, bg='#2d2d2d')
        header.pack(fill=tk.X)
        tk.Label(header, text=icon, font=("Segoe UI", 12), fg="#0078d7", bg="#2d2d2d").pack(side=tk.LEFT, padx=5)
        tk.Label(header, text=title, font=("Segoe UI", 12, "bold"), fg="#0078d7", bg="#2d2d2d").pack(side=tk.LEFT)
        toggle_btn = tk.Label(header, text="▼", font=("Segoe UI", 10), fg="#e0e0e0", bg="#2d2d2d")
        toggle_btn.pack(side=tk.RIGHT, padx=5)

        content_frame = tk.Frame(frame, bg='#1e1e1e')
        if is_code:
            text_widget = scrolledtext.ScrolledText(
                content_frame, height=8, bg="#2d2d2d", fg="#e0e0e0", font=("Consolas", 10), wrap=tk.NONE
            )
            text_widget.insert(tk.END, content)
            text_widget.config(state=tk.DISABLED)
            text_widget.pack(fill=tk.X, pady=5)
            tk.Button(
                content_frame, text="Copy", bg="#0078d7", fg="white", font=("Segoe UI", 9),
                command=lambda: self.copy_specific_code(content), padx=5, pady=2
            ).pack(side=tk.RIGHT)
        else:
            tk.Label(
                content_frame, text=content, font=("Segoe UI", 10), fg="#e0e0e0", bg="#1e1e1e",
                wraplength=self.root.winfo_width() - 50, justify=tk.LEFT
            ).pack(fill=tk.X, pady=5, padx=10)

        def toggle():
            if content_frame.winfo_ismapped():
                content_frame.pack_forget()
                toggle_btn.config(text="▶")
            else:
                content_frame.pack(fill=tk.X)
                toggle_btn.config(text="▼")
        toggle_btn.bind("<Button-1>", lambda e: toggle())
        content_frame.pack(fill=tk.X)

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
            tk.Label(error_frame, text="Error", font=("Segoe UI", 16, "bold"), fg="#e0e0e0", bg="#1e1e1e").pack(pady=10)
            tk.Label(error_frame, text=error_message, font=("Segoe UI", 12), fg="#e0e0e0", bg="#1e1e1e", wraplength=300).pack(pady=10)
            tk.Button(error_frame, text="Back", bg="#0078d7", fg="white", font=("Segoe UI", 10), command=self.hide_results).pack(pady=10)
        except Exception as e:
            print(f"Error displaying error message: {e}")

    def hide_results(self):
        """Hide results and show thumbnail view."""
        try:
            if hasattr(self, 'result_frame') and self.result_frame.winfo_exists():
                self.result_frame.destroy()
            self.root.unbind_all("<MouseWheel>")
            self.thumbnails_frame.pack(fill=tk.X, padx=10, pady=5, after=self.header_frame)
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
            self.thumbnails_frame.pack(fill=tk.X, padx=10, pady=5, after=self.header_frame)
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
            msg_frame = tk.Frame(self.thumbnails_frame, bg="#0078d7", padx=10, pady=5)
            msg_frame.pack(fill=tk.X, pady=5)
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