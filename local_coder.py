import sys
import os
import tkinter as tk
from tkinter import scrolledtext, Toplevel
import uuid
from PIL import ImageGrab, ImageTk
import keyboard
import ctypes
import threading
from ctypes import wintypes
import win32gui
import win32con
from ai_processor import ai_processor  # Import the AI processor singleton

# Load dwmapi.dll for true window cloaking
try:
    dwmapi = ctypes.WinDLL("dwmapi")
    DWMWA_CLOAK = 17  # Undocumented attribute to cloak the window from capture
    DWM_AVAILABLE = True
except Exception:
    DWM_AVAILABLE = False

# Win32 constants for screen capture protection
WDA_MONITOR = 0x00000001  # Normal mode
WDA_EXCLUDEFROMCAPTURE = 0x00000011  # Prevents capture

# Load SetWindowDisplayAffinity API
user32 = ctypes.WinDLL('user32', use_last_error=True)
_set_window_display_affinity = user32.SetWindowDisplayAffinity
_set_window_display_affinity.argtypes = (wintypes.HWND, wintypes.UINT)
_set_window_display_affinity.restype = wintypes.BOOL

def hide_from_capture(hwnd):
    """Hide window from screen capture using SetWindowDisplayAffinity"""
    try:
        if not _set_window_display_affinity(hwnd, WDA_EXCLUDEFROMCAPTURE):
            error = ctypes.get_last_error()
            print(f"Error hiding from capture: {error}")
            return False
        return True
    except Exception as e:
        print(f"Exception in hide_from_capture: {e}")
        return False

def restore_capture(hwnd):
    """Allow window to be captured again"""
    try:
        if not _set_window_display_affinity(hwnd, WDA_MONITOR):
            error = ctypes.get_last_error()
            print(f"Error restoring capture: {error}")
            return False
        return True
    except Exception as e:
        print(f"Exception in restore_capture: {e}")
        return False

class LocalCoderApp:
    def __init__(self, root):
        self.root = root
        self.click_through_enabled = True
        self.move_step = 20  # Pixels to move per arrow key press
        self.screenshot_files = []  # List to store screenshot filenames
        self.screenshot_thumbnails = []  # List to store thumbnail widgets
        self.screen_sharing_hidden = True  # Start with app hidden from screen capture by default
        self.init_ui()
        self.setup_shortcuts()
        self.hide_from_taskbar()
        self.make_click_through()
        self.settings_dropdown = None
        self.dropdown_visible = False
        
        # Apply screen sharing protection by default
        self.apply_screen_sharing_protection()
        
    def init_ui(self):
        # Set window attributes
        self.root.overrideredirect(True)  # Remove window decorations
        self.root.attributes('-alpha', 0.8)  # Make window transparent
        self.root.attributes('-topmost', True)  # Keep window on top
        
        # Set window position to center of screen
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = 800
        window_height = 600
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Configure main frame
        self.main_frame = tk.Frame(self.root, bg='#1e1e1e')
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header frame with instruction and settings button
        self.header_frame = tk.Frame(self.main_frame, bg='#1e1e1e')
        self.header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Instruction label
        self.instruction_label = tk.Label(
            self.header_frame, 
            text="Take a screenshot of the question with Ctrl+H\nCtrl+F to toggle click-through\nCtrl+Enter to process screenshots\nCtrl+O to start a new question\nCtrl+M to toggle screen capture visibility (hidden by default)",
            font=("Arial", 14, "bold"),
            fg="white",
            bg="#1e1e1e",
            padx=10,
            pady=10
        )
        self.instruction_label.pack(side=tk.LEFT, pady=10)
        
        # Buttons frame for settings and close
        self.buttons_container = tk.Frame(self.header_frame, bg="#1e1e1e")
        self.buttons_container.pack(side=tk.RIGHT, padx=10)
        
        # Settings button
        self.settings_button = tk.Button(
            self.buttons_container,
            text="⚙️",
            font=("Arial", 14),
            bg="#1e1e1e",
            fg="white",
            relief=tk.FLAT,
            padx=10,
            command=self.toggle_settings_dropdown
        )
        self.settings_button.pack(side=tk.LEFT, padx=5)
        
        # Close button
        self.close_app_button = tk.Button(
            self.buttons_container,
            text="✖",
            font=("Arial", 14),
            bg="#1e1e1e",
            fg="#ff5555",
            relief=tk.FLAT,
            padx=10,
            command=self.close_application
        )
        self.close_app_button.pack(side=tk.LEFT, padx=5)
        
        # Screenshots container (to display thumbnails of taken screenshots)
        self.thumbnails_frame = tk.Frame(self.main_frame, bg='#1e1e1e')
        self.thumbnails_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Screenshot counter label
        self.screenshot_counter = tk.Label(
            self.thumbnails_frame,
            text="Screenshots: 0",
            font=("Arial", 12),
            fg="white",
            bg="#1e1e1e",
            pady=5
        )
        self.screenshot_counter.pack(anchor=tk.W)
        
        # Frame for screenshot thumbnails
        self.thumbnails_container = tk.Frame(self.thumbnails_frame, bg='#1e1e1e')
        self.thumbnails_container.pack(fill=tk.X, pady=5)
        
        # Process button
        self.process_button = tk.Button(
            self.thumbnails_frame,
            text="Process Screenshots (Ctrl+Enter)",
            bg="#0078d7",
            fg="white",
            font=("Arial", 10),
            command=self.process_all_screenshots,
            padx=10,
            pady=5
        )
        self.process_button.pack(pady=10)
        
        # Result frame (initially hidden)
        self.result_frame = tk.Frame(self.main_frame, bg='#2d2d2d', padx=20, pady=20)
        
        # Question section
        self.question_label = tk.Label(
            self.result_frame,
            text="Question detected:",
            font=("Arial", 12, "bold"),
            fg="white",
            bg="#2d2d2d",
            anchor="w"
        )
        self.question_label.pack(fill=tk.X, pady=(0, 5))
        
        self.question_text = scrolledtext.ScrolledText(
            self.result_frame,
            height=5,
            bg="#3d3d3d",
            fg="white",
            font=("Arial", 10)
        )
        self.question_text.pack(fill=tk.X, pady=(0, 10))
        self.question_text.config(state=tk.DISABLED)
        
        # Explanation section
        self.explanation_label = tk.Label(
            self.result_frame,
            text="Answer explanation:",
            font=("Arial", 12, "bold"),
            fg="white",
            bg="#2d2d2d",
            anchor="w"
        )
        self.explanation_label.pack(fill=tk.X, pady=(0, 5))
        
        self.explanation_text = scrolledtext.ScrolledText(
            self.result_frame,
            height=7,
            bg="#3d3d3d",
            fg="white",
            font=("Arial", 10)
        )
        self.explanation_text.pack(fill=tk.X, pady=(0, 10))
        self.explanation_text.config(state=tk.DISABLED)
        
        # Code section
        self.code_label = tk.Label(
            self.result_frame,
            text="Code solution:",
            font=("Arial", 12, "bold"),
            fg="white",
            bg="#2d2d2d",
            anchor="w"
        )
        self.code_label.pack(fill=tk.X, pady=(0, 5))
        
        self.code_text = scrolledtext.ScrolledText(
            self.result_frame,
            height=10,
            bg="#3d3d3d",
            fg="white",
            font=("Consolas", 10)
        )
        self.code_text.pack(fill=tk.X, pady=(0, 10))
        self.code_text.config(state=tk.DISABLED)
        
        # Buttons frame
        self.buttons_frame = tk.Frame(self.result_frame, bg="#2d2d2d")
        self.buttons_frame.pack(fill=tk.X)
        
        self.copy_button = tk.Button(
            self.buttons_frame,
            text="Copy Code",
            bg="#0078d7",
            fg="white",
            font=("Arial", 10),
            command=self.copy_code,
            padx=10,
            pady=5
        )
        self.copy_button.pack(side=tk.LEFT, padx=5)
        
        self.close_button = tk.Button(
            self.buttons_frame,
            text="Close Results",
            bg="#d70000",
            fg="white",
            font=("Arial", 10),
            command=self.hide_results,
            padx=10,
            pady=5
        )
        self.close_button.pack(side=tk.RIGHT, padx=5)
        
        # Make window draggable
        self.header_frame.bind("<ButtonPress-1>", self.start_move)
        self.header_frame.bind("<ButtonRelease-1>", self.stop_move)
        self.header_frame.bind("<B1-Motion>", self.do_move)
        self.instruction_label.bind("<ButtonPress-1>", self.start_move)
        self.instruction_label.bind("<ButtonRelease-1>", self.stop_move)
        self.instruction_label.bind("<B1-Motion>", self.do_move)
        
        # Bind click event to close dropdown when clicking elsewhere
        self.root.bind("<Button-1>", self.close_dropdown_on_click)
        
    def setup_shortcuts(self):
        # Set up global hotkey for screenshot capture
        keyboard.add_hotkey('ctrl+h', self.take_screenshot, suppress=True)
        
        # Set up Escape key to toggle visibility
        keyboard.add_hotkey('esc', self.toggle_visibility, suppress=True)
        
        # Set up Ctrl+F to toggle click-through mode
        keyboard.add_hotkey('ctrl+f', self.toggle_click_through, suppress=True)
        
        # Set up Ctrl+S to toggle settings dropdown
        keyboard.add_hotkey('ctrl+s', self.toggle_settings_dropdown, suppress=True)
        
        # Set up Ctrl+Q to close application
        keyboard.add_hotkey('ctrl+q', self.close_application, suppress=True)
        
        # Set up Ctrl+Enter to process all screenshots
        keyboard.add_hotkey('ctrl+enter', self.process_all_screenshots, suppress=True)
        
        # Set up Ctrl+O to start from scratch (clear all screenshots)
        keyboard.add_hotkey('ctrl+o', self.start_from_scratch, suppress=True)
        
        # Set up Ctrl+M to toggle screen sharing mode
        keyboard.add_hotkey('ctrl+m', self.toggle_screen_sharing_mode, suppress=True)
        
        # Set up arrow keys for movement
        keyboard.add_hotkey('ctrl+left', lambda: self.move_window(-self.move_step, 0), suppress=True)
        keyboard.add_hotkey('ctrl+right', lambda: self.move_window(self.move_step, 0), suppress=True)
        keyboard.add_hotkey('ctrl+up', lambda: self.move_window(0, -self.move_step), suppress=True)
        keyboard.add_hotkey('ctrl+down', lambda: self.move_window(0, self.move_step), suppress=True)
        
    def close_application(self):
        """Close the application and clean up resources"""
        try:
            # Clean up any resources or temporary files
            for file in self.screenshot_files:
                try:
                    if os.path.exists(file):
                        os.remove(file)
                except Exception as e:
                    print(f"Error removing temporary file {file}: {e}")
            
            # Clean up keyboard hooks
            keyboard.unhook_all()
            
            # Destroy main window
            self.root.destroy()
            
            # Exit the application
            sys.exit(0)
        except Exception as e:
            print(f"Error closing application: {e}")
            sys.exit(1)
        
    def move_window(self, deltax, deltay):
        """Move the window by the specified delta values"""
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")
        
    def toggle_settings_dropdown(self):
        """Toggle the settings dropdown menu"""
        # Temporarily disable click-through
        was_click_through = self.click_through_enabled
        if self.click_through_enabled:
            self.click_through_enabled = False
            self.make_click_through()
            
        if self.dropdown_visible:
            self.close_settings_dropdown()
        else:
            self.show_settings_dropdown()
            
    def show_settings_dropdown(self):
        """Show the settings dropdown menu with shortcuts"""
        if self.settings_dropdown:
            return
            
        # Create dropdown frame within the main window
        self.settings_dropdown = tk.Frame(self.main_frame, bg="#2d2d2d", relief=tk.RAISED, bd=1)
        self.settings_dropdown.place(x=self.root.winfo_width() - 370, y=60, width=350, height=350)
        
        # Title
        title_label = tk.Label(
            self.settings_dropdown,
            text="Keyboard Shortcuts",
            font=("Arial", 12, "bold"),
            fg="white",
            bg="#2d2d2d",
            pady=10
        )
        title_label.pack(fill=tk.X)
        
        # Create frame for shortcuts
        shortcuts_frame = tk.Frame(
            self.settings_dropdown,
            bg="#2d2d2d",
            padx=10,
            pady=5
        )
        shortcuts_frame.pack(fill=tk.BOTH, expand=True)
        
        # Define shortcuts to display
        shortcuts = [
            ("Ctrl + H", "Take a screenshot"),
            ("Ctrl + Enter", "Process all screenshots"),
            ("Ctrl + O", "Start from scratch (new question)"),
            ("Ctrl + M", "Toggle screen capture visibility"),
            ("Ctrl + F", "Toggle click-through mode"),
            ("Ctrl + S", "Toggle shortcuts menu"),
            ("Ctrl + Q", "Close application"),
            ("Esc", "Hide/Show LocalCoder"),
            ("Ctrl + Left", "Move window left"),
            ("Ctrl + Right", "Move window right"),
            ("Ctrl + Up", "Move window up"),
            ("Ctrl + Down", "Move window down"),
        ]
        
        # Create a label for each shortcut
        for i, (key, description) in enumerate(shortcuts):
            shortcut_frame = tk.Frame(shortcuts_frame, bg="#2d2d2d")
            shortcut_frame.pack(fill=tk.X, pady=2)
            
            key_label = tk.Label(
                shortcut_frame,
                text=key,
                font=("Arial", 10, "bold"),
                fg="#00BFFF",
                bg="#2d2d2d",
                width=12,
                anchor="w"
            )
            key_label.pack(side=tk.LEFT, padx=5)
            
            desc_label = tk.Label(
                shortcut_frame,
                text=description,
                font=("Arial", 10),
                fg="white",
                bg="#2d2d2d",
                anchor="w"
            )
            desc_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
        # Bottom padding
        padding = tk.Frame(self.settings_dropdown, height=10, bg="#2d2d2d")
        padding.pack(fill=tk.X)
        
        # Add close button in the dropdown
        close_btn = tk.Button(
            self.settings_dropdown,
            text="Close",
            bg="#0078d7",
            fg="white",
            font=("Arial", 10),
            padx=10,
            pady=5,
            command=self.close_settings_dropdown
        )
        close_btn.pack(pady=10)
        
        self.dropdown_visible = True
        
    def close_settings_dropdown(self):
        """Close the settings dropdown menu"""
        if self.settings_dropdown:
            self.settings_dropdown.destroy()
            self.settings_dropdown = None
            self.dropdown_visible = False
            
        # Restore click-through if it was enabled before
        if self.click_through_enabled:
            self.make_click_through()
            
    def close_dropdown_on_click(self, event):
        """Close the dropdown when clicking elsewhere"""
        if self.dropdown_visible:
            # Check if click is outside the dropdown
            if self.settings_dropdown and not self.settings_dropdown.winfo_containing(event.x_root, event.y_root) and event.widget != self.settings_button:
                self.close_settings_dropdown()
        
    def make_click_through(self):
        # Set window as click-through using Windows API
        try:
            # Windows constants
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            
            # Get the window handle
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            
            # Get current window style
            current_style = ctypes.windll.user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            
            if self.click_through_enabled:
                # Add transparent style to make mouse events pass through
                new_style = current_style | WS_EX_LAYERED | WS_EX_TRANSPARENT
            else:
                # Remove transparent style to capture mouse events
                new_style = current_style & ~WS_EX_TRANSPARENT
                
            # Set the new window style
            ctypes.windll.user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, new_style)
            
            # Update the window frame to apply changes
            self.root.update_idletasks()
            
        except Exception as e:
            print(f"Error setting click-through: {e}")
            
    def toggle_click_through(self):
        # Toggle click-through mode
        self.click_through_enabled = not self.click_through_enabled
        self.make_click_through()
        
        # Don't modify appearance if app is hidden for screen sharing
        if self.screen_sharing_hidden:
            return
            
        # Provide visual feedback about the mode
        if self.click_through_enabled:
            self.root.attributes('-alpha', 0.7)  # More transparent in click-through mode
        else:
            self.root.attributes('-alpha', 0.9)  # Less transparent in normal mode
        
        # Update instruction text
        click_status = "ENABLED" if self.click_through_enabled else "DISABLED"
        self.instruction_label.config(
            text=f"Take a screenshot of the question with Ctrl+H\nCtrl+F to toggle click-through ({click_status})\nCtrl+Enter to process screenshots\nCtrl+O to start a new question\nCtrl+M to toggle screen capture visibility (hidden by default)"
        )
        
    def hide_from_taskbar(self):
        # Hide window from taskbar using Windows API
        try:
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            style = ctypes.windll.user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            style = style | WS_EX_TOOLWINDOW
            ctypes.windll.user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)
        except Exception as e:
            print(f"Error hiding from taskbar: {e}")
        
    def take_screenshot(self):
        # Close any open dropdowns before taking screenshot
        if self.dropdown_visible:
            self.close_settings_dropdown()
            
        # Temporarily hide the window to take the screenshot
        self.root.withdraw()
        self.root.after(500, self._capture_screen)
        
    def _capture_screen(self):
        # Capture the entire screen
        screenshot = ImageGrab.grab()
        
        # Save the screenshot to a file
        file_name = f"screenshot_{uuid.uuid4().hex[:8]}.png"
        screenshot.save(file_name)
        
        # Add to screenshot list
        self.screenshot_files.append(file_name)
        
        # Show the window again
        self.root.deiconify()
        
        # Update the screenshot counter
        self.screenshot_counter.config(text=f"Screenshots: {len(self.screenshot_files)}")
        
        # Add thumbnail to UI
        self.add_screenshot_thumbnail(file_name)
        
    def add_screenshot_thumbnail(self, file_path):
        """Add a thumbnail of the screenshot to the UI"""
        try:
            # Open the image
            img = ImageTk.PhotoImage(file=file_path)
            
            # Create a frame for this thumbnail
            thumb_frame = tk.Frame(self.thumbnails_container, bg="#2d2d2d", padx=5, pady=5)
            thumb_frame.pack(side=tk.LEFT, padx=5, pady=5)
            
            # Calculate thumbnail size
            img_width = img.width()
            img_height = img.height()
            max_size = 100
            scale = min(max_size / img_width, max_size / img_height)
            
            # Create a reduced version
            img_reduced = ImageTk.PhotoImage(
                ImageGrab.Image.open(file_path).resize(
                    (int(img_width * scale), int(img_height * scale))
                )
            )
            
            # Create label to display the thumbnail
            img_label = tk.Label(thumb_frame, image=img_reduced, bg="#2d2d2d")
            img_label.image = img_reduced  # Keep a reference to prevent garbage collection
            img_label.pack()
            
            # Add delete button
            delete_btn = tk.Button(
                thumb_frame,
                text="✖",
                font=("Arial", 8),
                bg="#2d2d2d",
                fg="#ff5555",
                relief=tk.FLAT,
                command=lambda: self.remove_screenshot(file_path, thumb_frame)
            )
            delete_btn.pack(anchor=tk.NE, padx=0, pady=0)
            
            # Store thumbnail widget for later reference
            self.screenshot_thumbnails.append((file_path, thumb_frame))
            
        except Exception as e:
            print(f"Error creating thumbnail: {e}")
            
    def remove_screenshot(self, file_path, thumbnail_frame):
        """Remove a screenshot from the list and UI"""
        try:
            # Remove from list
            if file_path in self.screenshot_files:
                self.screenshot_files.remove(file_path)
                
            # Remove thumbnail from UI
            thumbnail_frame.destroy()
            
            # Remove from thumbnails list
            self.screenshot_thumbnails = [(f, t) for f, t in self.screenshot_thumbnails if f != file_path]
            
            # Update counter
            self.screenshot_counter.config(text=f"Screenshots: {len(self.screenshot_files)}")
            
            # Delete the file
            if os.path.exists(file_path):
                os.remove(file_path)
                
        except Exception as e:
            print(f"Error removing screenshot: {e}")
            
    def process_all_screenshots(self):
        """Process all screenshots (Ctrl+Enter handler)"""
        if not self.screenshot_files:
            # No screenshots to process
            return
            
        # Hide the thumbnail section during results display
        self.thumbnails_frame.pack_forget()
        
        # Clear any previous results
        if hasattr(self, 'result_frame') and self.result_frame.winfo_ismapped():
            self.result_frame.pack_forget()
        
        # Show loading indicator
        self.show_loading_indicator()
        
        # Process screenshots in background thread
        threading.Thread(target=self._process_screenshots_thread, daemon=True).start()
    
    def _process_screenshots_thread(self):
        """Process screenshots in a background thread"""
        try:
            # Debug log
            print(f"Starting to process {len(self.screenshot_files)} screenshots")
            print(f"Screenshots: {self.screenshot_files}")
            
            # Process screenshots with AI processor
            result = ai_processor.process_screenshots(self.screenshot_files)
            
            # Debug log
            print(f"Processing completed, result: {type(result)}")
            
            # Update UI on main thread with proper error handling
            def safe_update_ui():
                try:
                    self.show_ai_results(result)
                except Exception as ex:
                    print(f"Error updating UI with results: {ex}")
                    # Show a simplified error message instead
                    self.show_error(f"Error displaying results: {str(ex)}")
            
            # Schedule UI update safely on main thread
            self.root.after(0, safe_update_ui)
            
        except Exception as e:
            # Store the error message
            error_message = str(e)
            print(f"Error processing screenshots: {error_message}")
            print(f"Error type: {type(e)}")
            import traceback
            traceback.print_exc()
            
            # Show error message safely on main thread
            def safe_show_error():
                try:
                    self.show_error(error_message)
                except Exception as ex:
                    print(f"Error showing error message: {ex}")
                    # Last resort - reset the UI to a clean state
                    if hasattr(self, 'loading_frame') and self.loading_frame.winfo_exists():
                        self.loading_frame.destroy()
                    self.thumbnails_frame.pack(fill=tk.X, padx=20, pady=10, after=self.header_frame)
            
            # Schedule error display safely on main thread
            self.root.after(0, safe_show_error)
    
    def show_loading_indicator(self):
        """Show a loading indicator while processing screenshots"""
        # Create loading frame
        self.loading_frame = tk.Frame(self.main_frame, bg='#171717')
        self.loading_frame.pack(fill=tk.BOTH, expand=True)
        
        # Center loading content
        loading_content = tk.Frame(self.loading_frame, bg='#171717')
        loading_content.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Loading message
        loading_label = tk.Label(
            loading_content,
            text="Processing screenshots...",
            font=("Segoe UI", 16, "bold"),
            fg="#e0e0e0",
            bg="#171717"
        )
        loading_label.pack(pady=20)
        
        # Loading animation (simple text-based animation)
        self.loading_dots_label = tk.Label(
            loading_content,
            text="",
            font=("Segoe UI", 16),
            fg="#0078d7",
            bg="#171717"
        )
        self.loading_dots_label.pack()
        
        # Animate the dots
        self._animate_loading_dots()
    
    def _animate_loading_dots(self, dot_count=0):
        """Animate loading dots"""
        if not hasattr(self, 'loading_dots_label') or not self.loading_dots_label.winfo_exists():
            return
            
        dots = "." * (dot_count % 4)
        self.loading_dots_label.config(text=dots)
        
        # Schedule next animation frame
        self.root.after(500, lambda: self._animate_loading_dots(dot_count + 1))
    
    def show_error(self, error_message):
        """Show error message with safe UI handling"""
        try:
            # Remove loading indicator safely
            if hasattr(self, 'loading_frame') and self.loading_frame.winfo_exists():
                try:
                    self.loading_frame.destroy()
                except Exception as e:
                    print(f"Error destroying loading frame: {e}")
                    self.loading_frame = None
            
            # Remove any existing error frame
            for child in self.main_frame.winfo_children():
                if child != self.header_frame and child != self.thumbnails_frame:
                    try:
                        child.destroy()
                    except Exception:
                        pass
                        
            # Create error frame
            error_frame = tk.Frame(self.main_frame, bg='#171717')
            error_frame.pack(fill=tk.BOTH, expand=True)
            
            # Center error content
            error_content = tk.Frame(error_frame, bg='#171717')
            error_content.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
            
            # Error icon
            error_icon = tk.Label(
                error_content,
                text="❌",
                font=("Segoe UI", 24),
                fg="#ff4d4d",
                bg="#171717"
            )
            error_icon.pack(pady=(0, 10))
            
            # Error title
            error_title = tk.Label(
                error_content,
                text="Error Processing Screenshots",
                font=("Segoe UI", 16, "bold"),
                fg="#e0e0e0",
                bg="#171717"
            )
            error_title.pack(pady=(0, 20))
            
            # Error message
            error_msg = tk.Label(
                error_content,
                text=str(error_message),
                font=("Segoe UI", 12),
                fg="#e0e0e0",
                bg="#171717",
                wraplength=600
            )
            error_msg.pack(pady=(0, 30))
            
            # Back button
            back_btn = tk.Button(
                error_content,
                text="Back to Screenshots",
                font=("Segoe UI", 12),
                bg="#333333",
                fg="white",
                padx=20,
                pady=10,
                relief=tk.FLAT,
                activebackground="#444444",
                activeforeground="white",
                command=self.hide_results
            )
            back_btn.pack()
            
            # Store reference to prevent garbage collection
            self.error_frame = error_frame
            
        except Exception as e:
            print(f"Fatal error in show_error: {e}")
            # Try one last recovery attempt
            try:
                # Reset the UI to a basic state
                for child in self.main_frame.winfo_children():
                    if child != self.header_frame:
                        child.destroy()
                        
                # Show thumbnails frame
                self.thumbnails_frame.pack(fill=tk.X, padx=20, pady=10, after=self.header_frame)
            except Exception:
                # Cannot recover UI state, just print error
                pass
    
    def show_ai_results(self, result):
        """Display AI-generated results"""
        try:
            # Hide loading indicator safely
            if hasattr(self, 'loading_frame') and self.loading_frame.winfo_exists():
                try:
                    self.loading_frame.destroy()
                except Exception as e:
                    print(f"Error destroying loading frame: {e}")
                    # Set to None to prevent further access attempts
                    self.loading_frame = None
            
            # Validate result structure before showing
            if not result or not isinstance(result, dict):
                self.show_error("Invalid response format received")
                return
                
            # Create a new full-screen results display
            self.show_professional_results(result)
            
        except Exception as e:
            print(f"Error in show_ai_results: {e}")
            # Show error and reset UI to a clean state
            try:
                self.show_error(f"Error displaying results: {str(e)}")
            except Exception:
                # Last resort - reset to clean state
                if hasattr(self, 'loading_frame') and self.loading_frame.winfo_exists():
                    self.loading_frame.destroy()
                self.thumbnails_frame.pack(fill=tk.X, padx=20, pady=10, after=self.header_frame)
    
    def show_professional_results(self, result=None):
        """Display a professional looking UI with all AI-generated content"""
        try:
            # When showing results, disable click-through to allow interaction
            old_click_through = self.click_through_enabled
            if self.click_through_enabled:
                self.click_through_enabled = False
                self.make_click_through()
                
            # Calculate window dimensions to use 80% of screen
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            window_width = int(screen_width * 0.8)
            window_height = int(screen_height * 0.8)
            
            # Center the window
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            
            # Resize the root window temporarily to 80% of screen
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
                
            # Create a modern, professional result UI
            
            # Main results container with a cleaner background
            self.result_frame = tk.Frame(self.main_frame, bg='#171717')
            self.result_frame.pack(fill=tk.BOTH, expand=True)
            
            # Simple toolbar with just a close button
            toolbar_frame = tk.Frame(self.result_frame, bg='#171717', padx=20, pady=10)
            toolbar_frame.pack(fill=tk.X)
            
            # Right-aligned close button
            close_btn_container = tk.Frame(toolbar_frame, bg='#171717')
            close_btn_container.pack(side=tk.RIGHT)
            
            close_btn = tk.Button(
                close_btn_container,
                text="✕",
                font=("Segoe UI", 12),
                bg="#171717",
                fg="#888888",
                relief=tk.FLAT,
                padx=10,
                activebackground="#333333",
                activeforeground="white",
                bd=0,
                command=self.hide_results
            )
            close_btn.pack(side=tk.RIGHT)
            
            # Content area with sections
            content_frame = tk.Frame(self.result_frame, bg='#171717', padx=int(window_width * 0.05), pady=20)
            content_frame.pack(fill=tk.BOTH, expand=True)
            
            # Create a canvas with scrollbar for scrollable content
            canvas_frame = tk.Frame(content_frame, bg='#171717')
            canvas_frame.pack(fill=tk.BOTH, expand=True)
            
            # Create a scrollbar with modern styling
            scrollbar = tk.Scrollbar(canvas_frame, width=12)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Configure the canvas for scrolling
            canvas = tk.Canvas(
                canvas_frame, 
                bg='#171717', 
                bd=0, 
                highlightthickness=0,
                yscrollcommand=scrollbar.set
            )
            canvas.pack(fill=tk.BOTH, expand=True)
            
            scrollbar.config(command=canvas.yview)
            
            # Inner frame for content sections
            inner_frame = tk.Frame(canvas, bg='#171717')
            canvas_window = canvas.create_window((0, 0), window=inner_frame, anchor=tk.NW, width=window_width * 0.9)
            
            # Store references to widgets to prevent garbage collection
            self.scrollbar_ref = scrollbar
            self.canvas_ref = canvas
            self.inner_frame_ref = inner_frame
            
            if result:
                # Use actual AI results
                
                # SECTION 1: Question Detection
                if 'question' in result:
                    self.create_section(
                        inner_frame, 
                        "Question Detected", 
                        result['question']
                    )
                
                # SECTION 2: Approach Explanation
                if 'explanation' in result:
                    self.create_section(
                        inner_frame,
                        "Approach",
                        result['explanation']
                    )
                
                # SECTION 3: Solution Code
                if 'solution' in result:
                    code_solution = result['solution']
                    code_section = self.create_section(
                        inner_frame,
                        "Solution Code",
                        "",
                        include_text_widget=True
                    )
                    
                    # Create syntax highlighted code display
                    code_display = scrolledtext.ScrolledText(
                        code_section,
                        height=12,
                        bg="#1e1e1e",
                        fg="#d4d4d4",
                        font=("Consolas", 12),
                        padx=15,
                        pady=15,
                        insertbackground="#d4d4d4"
                    )
                    code_display.pack(fill=tk.X, pady=(10, 5))
                    code_display.insert(tk.END, code_solution)
                    code_display.config(state=tk.DISABLED)
                    
                    # Apply syntax highlighting (simulated)
                    self.apply_syntax_highlighting(code_display, "#569cd6", ["def", "if", "else", "elif", "return", "import", "from", "class", "for", "while", "try", "except", "with", "as", "in", "not", "and", "or", "True", "False", "None"])
                    self.apply_syntax_highlighting(code_display, "#4ec9b0", ["ValueError", "Exception", "TypeError"])
                    self.apply_syntax_highlighting(code_display, "#ce9178", ["\"", "'"])
                    self.apply_syntax_highlighting(code_display, "#b5cea8", ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"])
                    
                    # Add a rounded border to code display with modern styling
                    code_display.config(borderwidth=1, relief=tk.SOLID)
                    
                    # Code actions frame 
                    code_actions = tk.Frame(code_section, bg='#171717')
                    code_actions.pack(fill=tk.X, pady=(0, 10))
                    
                    # Copy code button with improved styling
                    copy_btn = tk.Button(
                        code_actions,
                        text="Copy Code",
                        bg="#2d2d2d",
                        fg="white",
                        font=("Segoe UI", 10),
                        padx=12,
                        pady=6,
                        relief=tk.FLAT,
                        activebackground="#444444",
                        activeforeground="white",
                        command=lambda: self.copy_specific_code(code_solution)
                    )
                    copy_btn.pack(side=tk.LEFT)
                
                # SECTION 4: Example Usage
                if 'example' in result:
                    example_code = result['example']
                    example_section = self.create_section(
                        inner_frame,
                        "Example Usage",
                        "",
                        include_text_widget=True
                    )
                    
                    # Example code widget with better styling
                    example_display = scrolledtext.ScrolledText(
                        example_section,
                        height=10,
                        bg="#1e1e1e",
                        fg="#d4d4d4",
                        font=("Consolas", 12),
                        padx=15,
                        pady=15
                    )
                    example_display.pack(fill=tk.X, pady=(10, 5))
                    example_display.insert(tk.END, example_code)
                    example_display.config(state=tk.DISABLED, borderwidth=1, relief=tk.SOLID)
                    
                    # Apply syntax highlighting (simulated)
                    self.apply_syntax_highlighting(example_display, "#6a9955", [line.strip() for line in example_code.split('\n') if line.strip().startswith('#')])
                    self.apply_syntax_highlighting(example_display, "#569cd6", ["print", "for", "in", "if", "else", "elif", "return", "import", "from", "class", "while", "try", "except", "with", "as", "not", "and", "or", "True", "False", "None"])
                    self.apply_syntax_highlighting(example_display, "#b5cea8", ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"])
                    self.apply_syntax_highlighting(example_display, "#ce9178", ["\"", "'"])
                    
                    # Code actions frame 
                    example_actions = tk.Frame(example_section, bg='#171717')
                    example_actions.pack(fill=tk.X, pady=(0, 10))
                    
                    # Copy code button with improved styling
                    example_copy_btn = tk.Button(
                        example_actions,
                        text="Copy Example",
                        bg="#2d2d2d",
                        fg="white",
                        font=("Segoe UI", 10),
                        padx=12,
                        pady=6,
                        relief=tk.FLAT,
                        activebackground="#444444",
                        activeforeground="white",
                        command=lambda: self.copy_specific_code(example_code)
                    )
                    example_copy_btn.pack(side=tk.LEFT)
                    
                # SECTION 5: Complexity Analysis
                if 'complexity' in result:
                    self.create_section(
                        inner_frame,
                        "Complexity Analysis",
                        result['complexity']
                    )
                    
                # SECTION 6: Additional Notes
                if 'notes' in result:
                    self.create_section(
                        inner_frame,
                        "Additional Notes",
                        result['notes']
                    )
            else:
                # Demo mode - show placeholder content
                # SECTION 1: Question Detection
                self.create_section(
                    inner_frame, 
                    "Question Detected", 
                    "Write a function to find the nth Fibonacci number using dynamic programming.\n\n"
                    "The Fibonacci sequence starts with 0 and 1, where each subsequent number is the sum of the two "
                    "preceding ones: 0, 1, 1, 2, 3, 5, 8, 13, 21, ...\n\n"
                    "Implement the function efficiently to handle large values of n."
                )
                
                # ... rest of demo content
            
            # Update the canvas scroll region after adding content
            inner_frame.update_idletasks()
            canvas.config(scrollregion=canvas.bbox("all"))
            
            # Ensure canvas width matches inner frame
            inner_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            
            # Enable mouse wheel scrolling
            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            
        except Exception as e:
            print(f"Error showing professional results: {e}")
    
    def create_section(self, parent, title, content, include_text_widget=False):
        """Create a styled section in the results display"""
        section = tk.Frame(parent, bg='#171717', padx=10, pady=10)
        section.pack(fill=tk.X, pady=10)
        
        # Add a subtle divider above each section (except first one)
        if parent.winfo_children():
            divider = tk.Frame(section, height=1, bg="#333333")
            divider.pack(fill=tk.X, pady=(0, 15))
        
        # Section title with accent color and icon
        title_frame = tk.Frame(section, bg='#171717')
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Add an icon based on section type
        icon = "🔍"  # Default icon
        if "Question" in title:
            icon = "❓"
        elif "Approach" in title:
            icon = "🔑"
        elif "Solution" in title:
            icon = "💻"
        elif "Example" in title:
            icon = "🔄"
        elif "Complexity" in title:
            icon = "⏱️"
        elif "Additional" in title:
            icon = "📝"
        
        icon_label = tk.Label(
            title_frame,
            text=icon,
            font=("Segoe UI", 14),
            bg="#171717",
            fg="#0078d7"
        )
        icon_label.pack(side=tk.LEFT, padx=(0, 10))
        
        title_label = tk.Label(
            title_frame,
            text=title,
            font=("Segoe UI", 14, "bold"),
            fg="#0078d7",
            bg="#171717",
            anchor="w"
        )
        title_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        if not include_text_widget:
            # Regular content with improved readability
            content_label = tk.Label(
                section,
                text=content,
                font=("Segoe UI", 11),
                fg="#e0e0e0",
                bg="#171717",
                justify=tk.LEFT,
                anchor="w",
                wraplength=800
            )
            content_label.pack(fill=tk.X, padx=35)
        
        return section
        
    def apply_syntax_highlighting(self, text_widget, color, keywords):
        """Apply syntax highlighting to specific keywords in a text widget"""
        content = text_widget.get("1.0", tk.END)
        for keyword in keywords:
            start_idx = "1.0"
            while True:
                start_idx = text_widget.search(keyword, start_idx, tk.END)
                if not start_idx:
                    break
                end_idx = f"{start_idx}+{len(keyword)}c"
                text_widget.tag_add(keyword, start_idx, end_idx)
                text_widget.tag_config(keyword, foreground=color)
                start_idx = end_idx
                
    def copy_specific_code(self, code_text):
        """Copy specific code to clipboard"""
        self.root.clipboard_clear()
        self.root.clipboard_append(code_text)
        
    def hide_results(self):
        """Hide the results and show the thumbnail view again"""
        try:
            # Unbind the mousewheel event to prevent conflicts
            try:
                self.root.unbind_all("<MouseWheel>")
            except Exception:
                pass
                
            if hasattr(self, 'result_frame') and self.result_frame.winfo_exists():
                self.result_frame.destroy()
            
            # Clear references to widgets that might cause issues
            for attr in ['scrollbar_ref', 'canvas_ref', 'inner_frame_ref']:
                if hasattr(self, attr):
                    setattr(self, attr, None)
            
            # Reset window to original size if needed
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            window_width = 800
            window_height = 600
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
            # Show thumbnails again
            self.thumbnails_frame.pack(fill=tk.X, padx=20, pady=10, after=self.header_frame)
            
            # Restore click-through state
            if self.click_through_enabled:
                self.make_click_through()
        
        except Exception as e:
            print(f"Error hiding results: {e}")
            # Try to recover gracefully
            try:
                self.thumbnails_frame.pack(fill=tk.X, padx=20, pady=10, after=self.header_frame)
            except:
                pass
        
    def toggle_visibility(self):
        # Close any open dropdowns
        if self.dropdown_visible:
            self.close_settings_dropdown()
            
        if self.root.state() == 'normal':
            self.root.withdraw()
        else:
            self.root.deiconify()
            self.root.attributes('-topmost', True)
            
    def start_move(self, event):
        # Close any open dropdowns
        if self.dropdown_visible:
            self.close_settings_dropdown()
            
        # Temporarily disable click-through when dragging
        old_click_through = self.click_through_enabled
        if self.click_through_enabled:
            self.click_through_enabled = False
            self.make_click_through()
            
        self.x = event.x
        self.y = event.y
        
    def stop_move(self, event):
        self.x = None
        self.y = None
        
        # Restore click-through state after dragging
        if self.click_through_enabled:
            self.make_click_through()
        
    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def copy_code(self):
        # Backwards compatibility for old code
        if hasattr(self, 'code_text') and self.code_text.winfo_exists():
            self.root.clipboard_clear()
            self.root.clipboard_append(self.code_text.get(1.0, tk.END))
        else:
            # Default code if code_text widget doesn't exist
            default_code = """def fibonacci(n):
    if n <= 1:
        return n
    fib = [0, 1]
    for i in range(2, n + 1):
        fib.append(fib[i-1] + fib[i-2])
    return fib[n]"""
            self.copy_specific_code(default_code)

    def start_from_scratch(self):
        """Clear all screenshots and reset the application to start a new coding question"""
        try:
            # Close any open results or loading frames
            if hasattr(self, 'result_frame') and self.result_frame.winfo_exists():
                self.result_frame.destroy()
                
            if hasattr(self, 'loading_frame') and self.loading_frame.winfo_exists():
                self.loading_frame.destroy()
            
            # Delete all screenshot files
            for file_path in self.screenshot_files:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    print(f"Error removing file {file_path}: {e}")
            
            # Clear thumbnails from UI
            for _, thumbnail_frame in self.screenshot_thumbnails:
                if thumbnail_frame.winfo_exists():
                    thumbnail_frame.destroy()
            
            # Reset lists and counter
            self.screenshot_files = []
            self.screenshot_thumbnails = []
            self.screenshot_counter.config(text="Screenshots: 0")
            
            # Make sure thumbnails frame is visible
            if not self.thumbnails_frame.winfo_ismapped():
                self.thumbnails_frame.pack(fill=tk.X, padx=20, pady=10, after=self.header_frame)
                
            # Show feedback message
            self.show_temporary_message("Ready for a new code question! (Ctrl+H to take screenshots)")
            
            # Reset window to original size if needed
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            window_width = 800
            window_height = 600
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
        except Exception as e:
            print(f"Error starting from scratch: {e}")
    
    def show_temporary_message(self, message, duration=3000):
        """Show a temporary message that disappears after a few seconds"""
        # Create a floating message frame
        msg_frame = tk.Frame(self.thumbnails_frame, bg="#0078d7", padx=15, pady=10)
        msg_frame.pack(fill=tk.X, pady=10)
        
        # Message text
        msg_label = tk.Label(
            msg_frame,
            text=message,
            font=("Segoe UI", 12),
            fg="white",
            bg="#0078d7"
        )
        msg_label.pack()
        
        # Schedule the message to disappear
        self.root.after(duration, lambda: self.fade_out_message(msg_frame))
    
    def fade_out_message(self, frame, alpha=1.0, step=0.1):
        """Gradually fade out a message frame"""
        try:
            if alpha <= 0 or not frame.winfo_exists():
                if frame.winfo_exists():
                    frame.destroy()
                return
            
            # Reduce alpha and schedule next step
            alpha -= step
            self.root.after(50, lambda: self.fade_out_message(frame, alpha, step))
        except Exception as e:
            # If any error occurs, just try to destroy the frame
            try:
                if frame.winfo_exists():
                    frame.destroy()
            except:
                pass

    def toggle_screen_sharing_mode(self):
        """
        Toggle screen sharing mode - uses SetWindowDisplayAffinity API to prevent
        the window from being captured during screen sharing.
        """
        # Toggle screen sharing hidden state
        self.screen_sharing_hidden = not self.screen_sharing_hidden
        
        # Get the window handle for Tkinter window
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        
        if self.screen_sharing_hidden:
            # Method 1: Use SetWindowDisplayAffinity to prevent screen capture
            success = hide_from_capture(hwnd)
            
            if not success:
                print("SetWindowDisplayAffinity failed, trying fallback methods")
            
            # Show feedback message
            self.show_temporary_message("App is now hidden from screen sharing")
        else:
            # Method 1: Allow screen capture again
            restore_capture(hwnd)
            
            # Show feedback message
            self.show_temporary_message("App is now visible in screen sharing (Warning!)")
    
    def show_notification(self, message):
        """
        Shows a Windows notification since the app window is hidden
        """
        try:
            # Import necessary modules
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            # Show Windows notification
            toaster.show_toast(
                "LocalCoder",
                message,
                duration=5,
                threaded=True,
                icon_path=None  # Could add an app icon path here
            )
        except Exception:
            # Fall back to a simple message box if toast notifications aren't available
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, message, "LocalCoder", 0)
            except:
                # Last resort - print to console
                print(message)

    def set_window_cloak(self, hwnd, enable=True):
        """
        Cloak or uncloak a window from screen capture using DWM API
        This is a powerful technique that works with most screen sharing applications
        """
        if not DWM_AVAILABLE:
            return False
            
        try:
            value = wintypes.BOOL(enable)
            result = dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_CLOAK,
                ctypes.byref(value),
                ctypes.sizeof(value)
            )
            return result == 0  # S_OK is 0
        except Exception as e:
            print(f"Error setting window cloak: {e}")
            return False
            
    def make_window_layered(self, hwnd, alpha=255):
        """Make the window layered to further control its visibility"""
        try:
            # Set WS_EX_LAYERED attribute
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style | win32con.WS_EX_LAYERED)
            # Set transparency (255 is fully opaque, 0 is transparent)
            win32gui.SetLayeredWindowAttributes(hwnd, 0, alpha, win32con.LWA_ALPHA)
            return True
        except Exception as e:
            print(f"Error making window layered: {e}")
            return False

    def apply_screen_sharing_protection(self):
        """
        Apply screen sharing protection by default - uses SetWindowDisplayAffinity API to prevent
        the window from being captured during screen sharing.
        """
        # Get the window handle for Tkinter window
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        
        # Method 1: Use SetWindowDisplayAffinity to prevent screen capture
        success = hide_from_capture(hwnd)
        
        if not success:
            print("SetWindowDisplayAffinity failed, trying fallback methods")
            
        # No need to make the window invisible since we still want the user to see it
        # We just want to prevent it from being captured in screen sharing
        
        # Show feedback via system notification
        print("Application is hidden from screen capture by default.")

if __name__ == "__main__":
    root = tk.Tk()
    root.title("LocalCoder")
    app = LocalCoderApp(root)
    root.mainloop() 