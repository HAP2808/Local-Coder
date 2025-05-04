import sys
import os
import json
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
from PIL import ImageGrab, ImageTk, Image, ImageDraw
import keyboard
import ctypes
import threading
import uuid
import win32gui
import win32con
from screenshot_processor import ScreenshotProcessor
from chatbot import Chatbot
from chat_processor import ChatProcessor
import pystray
from plyer import notification
import logging
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Configure logging
logging.basicConfig(
    filename='local_coder.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

# Google OAuth configuration
SCOPES = ['https://www.googleapis.com/auth/userinfo.profile', 
          'https://www.googleapis.com/auth/userinfo.email', 
          'openid']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'
USER_DATA_FILE = 'user_data.json'

def hide_from_capture(hwnd):
    """Hide window from screen capture using SetWindowDisplayAffinity."""
    try:
        if not hwnd:
            logger.error("Invalid window handle")
            return False
        if not _set_window_display_affinity(hwnd, WDA_EXCLUDEFROMCAPTURE):
            error = ctypes.get_last_error()
            logger.error(f"Error hiding from capture: {error}")
            return False
        return True
    except Exception as e:
        logger.error(f"Exception in hide_from_capture: {e}")
        return False

class LocalCoderApp:
    def __init__(self, root):
        self.root = root
        self.user_data = {}
        self.credentials = None
        self.click_through_enabled = True
        self.move_step = 20
        self.screenshot_files = []
        self.screenshot_thumbnails = []
        self.opacity = 0.8
        self.settings_dialog = None
        self.chatbot_open = False
        self.tray_icon = None
        self.load_user_data()
        self.load_credentials()
        if self.credentials and 'groq_api_key' in self.user_data and self.validate_api_key():
            self.init_main_ui()
        else:
            self.show_login_window()

    def load_user_data(self):
        """Load user data from user_data.json."""
        if os.path.exists(USER_DATA_FILE):
            try:
                with open(USER_DATA_FILE, 'r') as f:
                    self.user_data = json.load(f)
                logger.info("User data loaded successfully")
            except Exception as e:
                logger.error(f"Error loading user data: {e}")
                self.user_data = {}

    def save_user_data(self):
        """Save user data to user_data.json."""
        try:
            with open(USER_DATA_FILE, 'w') as f:
                json.dump(self.user_data, f, indent=4)
            logger.info("User data saved successfully")
        except Exception as e:
            logger.error(f"Error saving user data: {e}")

    def load_credentials(self):
        """Load or refresh Google OAuth credentials."""
        creds = None
        if os.path.exists(TOKEN_FILE):
            try:
                creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            except Exception as e:
                logger.error(f"Error loading credentials: {e}")
        if creds and creds.valid:
            self.credentials = creds
            return creds
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(TOKEN_FILE, 'w') as token:
                    token.write(creds.to_json())
                self.credentials = creds
                return creds
            except Exception as e:
                logger.error(f"Error refreshing credentials: {e}")
        return None

    def validate_api_key(self):
        """Validate the GROQ API key."""
        try:
            processor = ScreenshotProcessor
            return processor.set_api_key(self.user_data['groq_api_key']) and processor.check_api_key()
        except Exception as e:
            logger.error(f"Invalid API key or error: {e}")
            return False

    def show_login_window(self):
        """Show Tkinter login window with Google Sign-In."""
        self.root.withdraw()
        self.login_window = tk.Toplevel(self.root)
        self.login_window.title("LocalCoder Login")
        self.login_window.geometry("400x300")
        self.login_window.attributes('-topmost', True)
        self.login_window.configure(bg='#f0f0f0')

        try:
            logo_img = Image.open('static/logo.png')
            logo_img = logo_img.resize((200, 100), Image.Resampling.LANCZOS)
            logo_photo = ImageTk.PhotoImage(logo_img)
            tk.Label(self.login_window, image=logo_photo, bg='#f0f0f0').pack(pady=20)
            self.login_window.logo = logo_photo
        except Exception as e:
            logger.error(f"Error loading logo: {e}")
            tk.Label(self.login_window, text="LocalCoder", font=("Arial", 16, "bold"), bg='#f0f0f0').pack(pady=20)

        signin_btn = tk.Button(
            self.login_window,
            text="Sign in with Google",
            font=("Arial", 12),
            bg="#4285F4",
            fg="white",
            relief=tk.FLAT,
            command=self.google_login,
            padx=20,
            pady=10
        )
        signin_btn.pack(pady=20)
        signin_btn.bind("<Enter>", lambda e: signin_btn.config(bg="#357ae8"))
        signin_btn.bind("<Leave>", lambda e: signin_btn.config(bg="#4285F4"))

        self.login_window.protocol("WM_DELETE_WINDOW", self.close_application)
        self.login_window.mainloop()

    def google_login(self):
        """Initiate Google OAuth flow."""
        try:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            self.credentials = creds
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
            
            profile = self.get_google_profile(creds)
            if profile:
                self.user_data['name'] = profile['name']
                self.user_data['email'] = profile['email']
                self.save_user_data()
                logger.info(f"User {profile['name']} logged in successfully")
                self.login_window.destroy()
                if 'groq_api_key' in self.user_data and self.validate_api_key():
                    self.init_main_ui()
                else:
                    self.show_api_key_window()
            else:
                messagebox.showerror("Error", "Failed to fetch Google profile")
        except Exception as e:
            logger.error(f"Error in Google login: {e}")
            messagebox.showerror("Error", f"Login failed: {str(e)}")

    def get_google_profile(self, creds):
        """Fetch user profile from Google."""
        try:
            service = build('people', 'v1', credentials=creds)
            profile = service.people().get(resourceName='people/me', personFields='names,emailAddresses').execute()
            name = profile['names'][0]['displayName']
            email = profile['emailAddresses'][0]['value']
            return {'name': name, 'email': email}
        except Exception as e:
            logger.error(f"Error fetching Google profile: {e}")
            return None

    def show_api_key_window(self):
        """Show Tkinter window for GROQ API key input."""
        self.api_key_window = tk.Toplevel(self.root)
        self.api_key_window.title("Enter GROQ API Key")
        self.api_key_window.geometry("400x500")
        self.api_key_window.attributes('-topmost', True)
        self.api_key_window.configure(bg='#f0f0f0')

        tk.Label(self.api_key_window, text="Enter your GROQ API Key", font=("Arial", 14), bg='#f0f0f0').pack(pady=10)
        
        api_key_entry = tk.Entry(self.api_key_window, width=40, show="*")
        api_key_entry.pack(pady=10)
        
        tk.Label(self.api_key_window, text="Steps to obtain GROQ API Key:", font=("Arial", 12, "bold"), bg='#f0f0f0').pack(pady=10)
        steps = [
            "1. Visit https://x.ai/api and sign in or create an xAI account.",
            "2. Navigate to the API section in your account dashboard.",
            "3. Generate a new API key or copy an existing one.",
            "4. Paste the API key in the field above."
        ]
        for step in steps:
            tk.Label(self.api_key_window, text=step, wraplength=350, justify="left", bg='#f0f0f0').pack(anchor="w", padx=10)
        
        def submit_api_key():
            key = api_key_entry.get().strip()
            if key:
                self.user_data['groq_api_key'] = key
                self.save_user_data()
                if self.validate_api_key():
                    self.api_key_window.destroy()
                    self.init_main_ui()
                else:
                    messagebox.showerror("Error", "Invalid API key. Please try again.")
            else:
                messagebox.showerror("Error", "Please enter a valid API key.")
        
        tk.Button(self.api_key_window, text="Submit", command=submit_api_key, bg="#0078d7", fg="white", font=("Arial", 10)).pack(pady=20)
        self.api_key_window.protocol("WM_DELETE_WINDOW", self.close_application)

    def edit_api_key(self):
        """Show window to edit GROQ API key."""
        edit_window = tk.Toplevel(self.root)
        edit_window.title("Edit GROQ API Key")
        edit_window.geometry("400x200")
        edit_window.attributes('-topmost', True)
        edit_window.configure(bg='#f0f0f0')

        tk.Label(edit_window, text="Enter new GROQ API Key", font=("Arial", 14), bg='#f0f0f0').pack(pady=10)
        api_key_entry = tk.Entry(edit_window, width=40, show="*")
        api_key_entry.pack(pady=10)
        
        def save_new_api_key():
            key = api_key_entry.get().strip()
            if key:
                self.user_data['groq_api_key'] = key
                self.save_user_data()
                if self.validate_api_key():
                    messagebox.showinfo("Success", "API key updated successfully.")
                    edit_window.destroy()
                else:
                    messagebox.showerror("Error", "Invalid API key. Please try again.")
            else:
                messagebox.showerror("Error", "Please enter a valid API key.")
        
        tk.Button(edit_window, text="Save", command=save_new_api_key, bg="#0078d7", fg="white", font=("Arial", 10)).pack(pady=20)

    def logout(self):
        """Clear credentials and restart login process."""
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        if os.path.exists(USER_DATA_FILE):
            os.remove(USER_DATA_FILE)
        self.user_data = {}
        self.credentials = None
        for file in self.screenshot_files:
            if os.path.exists(file):
                os.remove(file)
        keyboard.unhook_all()
        self.root.destroy()
        main()

    def init_main_ui(self):
        """Initialize the main application UI."""
        self.screenshot_processor = ScreenshotProcessor
        self.chat_processor = ChatProcessor(self.user_data['groq_api_key'])
        self.chatbot = Chatbot(self.root, self, self.chat_processor, self.opacity)
        self.root.deiconify()
        self.init_ui()
        self.setup_shortcuts()
        self.root.update_idletasks()
        self.apply_screen_sharing_protection()
        self.create_tray_icon()

    def init_ui(self):
        """Initialize the UI with a professional, minimal design."""
        try:
            self.root.overrideredirect(True)
            self.root.attributes('-alpha', self.opacity)
            self.root.attributes('-topmost', True)

            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            window_width = 570
            window_height = 60
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

            menu_bar = tk.Menu(self.root)
            profile_menu = tk.Menu(menu_bar, tearoff=0)
            profile_menu.add_command(label=f"User: {self.user_data.get('name', 'Unknown')}")
            profile_menu.add_command(label="Edit API Key", command=self.edit_api_key)
            profile_menu.add_command(label="Logout", command=self.logout)
            menu_bar.add_cascade(label="Profile", menu=profile_menu)
            self.root.config(menu=menu_bar)

            self.main_frame = tk.Frame(self.root, bg='#1e1e1e')
            self.main_frame.pack(fill=tk.BOTH, expand=True)

            self.header_frame = tk.Frame(self.main_frame, bg='#1e1e1e')
            self.header_frame.pack(fill=tk.X, padx=2, pady=2)

            self.instruction_label = tk.Label(
                self.header_frame,
                text="Ctrl+H to Capture • Ctrl+G to Chat • Ctrl+Enter to Process • Ctrl+S for Settings",
                font=("Segoe UI", 10),
                fg="#e0e0e0",
                bg="#1e1e1e",
                padx=2,
                pady=2
            )
            self.instruction_label.pack(side=tk.LEFT)

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

            self.thumbnails_frame = tk.Frame(self.main_frame, bg='#1e1e1e')
            self.thumbnails_frame.pack(fill=tk.X, padx=2, pady=2)
            self.thumbnails_container = tk.Frame(self.thumbnails_frame, bg='#1e1e1e')
            self.thumbnails_container.pack(fill=tk.X, pady=2)

            for widget in (self.header_frame, self.instruction_label):
                widget.bind("<ButtonPress-1>", self.start_move)
                widget.bind("<ButtonRelease-1>", self.stop_move)
                widget.bind("<B1-Motion>", self.do_move)
        
        except Exception as e:
            logger.error(f"Error in init_ui: {e}")
            self.show_notification(f"Failed to initialize UI: {str(e)}")

    def hide_main_window(self):
        """Hide the main application window."""
        try:
            self.root.withdraw()
            logger.debug("Main window hidden")
        except Exception as e:
            logger.error(f"Error in hide_main_window: {e}")
            self.show_notification(f"Failed to hide main window: {str(e)}")

    def show_main_window(self):
        """Show the main application window."""
        try:
            self.root.deiconify()
            self.root.attributes('-topmost', True)
            logger.debug("Main window shown")
        except Exception as e:
            logger.error(f"Error in show_main_window: {e}")
            self.show_notification(f"Failed to show main window: {str(e)}")

    def setup_shortcuts(self):
        """Set up global keyboard shortcuts."""
        try:
            keyboard.add_hotkey('ctrl+h', self.take_screenshot, suppress=True)
            keyboard.add_hotkey('ctrl+g', self.chatbot.show_chat_window, suppress=True)
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
        except Exception as e:
            logger.error(f"Error in setup_shortcuts: {e}")
            self.show_notification(f"Failed to set up shortcuts: {str(e)}")

    def apply_screen_sharing_protection(self):
        """Hide the main window from screen capture."""
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hide_from_capture(hwnd):
                self.show_notification("Warning: Could not hide UI from screen capture.")
        except Exception as e:
            logger.error(f"Error in apply_screen_sharing_protection: {e}")
            self.show_notification(f"Screen sharing protection failed: {str(e)}")

    def toggle_settings_dialog(self):
        """Toggle the settings dialog (open if closed, close if open)."""
        try:
            if self.settings_dialog and self.settings_dialog.winfo_exists():
                self.settings_dialog.destroy()
                self.settings_dialog = None
            else:
                self.root.after(50, self.show_settings_dialog)
        except Exception as e:
            logger.error(f"Error in toggle_settings_dialog: {e}")
            self.show_notification(f"Failed to toggle settings: {str(e)}")

    def show_settings_dialog(self):
        """Show a modal dialog with keyboard shortcuts and opacity slider."""
        try:
            self.settings_dialog = tk.Toplevel(self.root)
            self.settings_dialog.withdraw()
            self.root.update_idletasks()

            self.settings_dialog.overrideredirect(True)
            self.settings_dialog.attributes('-topmost', True)
            self.settings_dialog.configure(bg='#2d2d2d')

            self.settings_dialog.transient(self.root)
            hwnd = ctypes.windll.user32.GetParent(self.settings_dialog.winfo_id())
            current_style = _get_window_long(hwnd, GWL_EXSTYLE)
            _set_window_long(hwnd, GWL_EXSTYLE, current_style | WS_EX_TOOLWINDOW)

            self.settings_dialog.update_idletasks()
            if not hide_from_capture(hwnd):
                logger.warning("Failed to hide settings dialog from screen capture")

            dialog_width = 400
            dialog_height = 350
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            x = (screen_width - dialog_width) // 2
            y = (screen_height - dialog_height) // 2
            self.settings_dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

            frame = tk.Frame(self.settings_dialog, bg='#2d2d2d', padx=2, pady=2)
            frame.pack(fill=tk.BOTH, expand=True)
            tk.Label(frame, text="Settings", font=("Segoe UI", 12, "bold"), fg="#e0e0e0", bg="#2d2d2d").pack(pady=2)

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

            tk.Label(frame, text="Keyboard Shortcuts", font=("Segoe UI", 12, "bold"), fg="#e0e0e0", bg="#2d2d2d").pack(pady=2)
            shortcuts = [
                ("Ctrl+H", "Take a screenshot"),
                ("Ctrl+G", "Open chatbot"),
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

            self.settings_dialog.update_idletasks()
            self.settings_dialog.deiconify()
        
        except Exception as e:
            logger.error(f"Error in show_settings_dialog: {e}")
            self.show_notification(f"Failed to show settings: {str(e)}")

    def update_opacity(self, value):
        """Update UI opacity based on slider value."""
        try:
            self.opacity = float(value)
            self.root.attributes('-alpha', self.opacity)
            self.chatbot.opacity = self.opacity
            if self.chatbot.chat_window and self.chatbot.chat_window.winfo_exists():
                self.chatbot.chat_window.attributes('-alpha', self.opacity)
            self.opacity_label.config(text=f"{self.opacity:.1f}")
        except Exception as e:
            logger.error(f"Error in update_opacity: {e}")
            self.show_notification(f"Failed to update opacity: {str(e)}")

    def take_screenshot(self):
        """Capture a screenshot and add it to the UI."""
        try:
            if self.chatbot_open:
                logger.debug("Screenshot capture ignored: chatbot window is open")
                return
            self.root.withdraw()
            self.root.after(500, self._capture_screen)
        except Exception as e:
            logger.error(f"Error in take_screenshot: {e}")
            self.show_notification(f"Failed to take screenshot: {str(e)}")

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
            logger.error(f"Error in _capture_screen: {e}")
            self.root.deiconify()
            self.show_temporary_message("Failed to capture screenshot")
    
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
            self._resize_window_to_fit_content()
        except Exception as e:
            logger.error(f"Error in add_screenshot_thumbnail: {e}")
            self.show_temporary_message(f"Failed to add thumbnail: {str(e)}")
    
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
            logger.error(f"Error in _resize_window_to_fit_content: {e}")
            self.show_notification(f"Failed to resize window: {str(e)}")
    
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
            logger.error(f"Error in remove_screenshot: {e}")
            self.show_temporary_message(f"Failed to remove screenshot: {str(e)}")
    
    def process_all_screenshots(self):
        """Process all screenshots and display results."""
        try:
            if not self.screenshot_files:
                self.show_temporary_message("No screenshots to process. Use Ctrl+H to capture.")
                return
            self.thumbnails_frame.pack_forget()
            if hasattr(self, 'result_frame') and self.result_frame.winfo_exists():
                self.result_frame.destroy()
            self.root.bind("<Escape>", lambda e: self.hide_results())
            threading.Thread(target=self._process_screenshots_thread, daemon=True).start()
        except Exception as e:
            logger.error(f"Error in process_all_screenshots: {e}")
            self.show_temporary_message(f"Failed to process screenshots: {str(e)}")
    
    def _process_screenshots_thread(self):
        """Process screenshots in a background thread."""
        try:
            self.root.after(0, self.show_loading_sections)
            def callback(result):
                logger.debug(f"Callback received result: {result}")
                self.root.after(0, lambda: self.show_professional_results(result))
            self.screenshot_processor.process_screenshots(self.screenshot_files, callback=callback)
        except Exception as e:
            logger.error(f"Error in _process_screenshots_thread: {e}")
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
            logger.error(f"Error in show_loading_sections: {e}")
            self.show_temporary_message(f"Failed to show loading: {str(e)}")
    
    def show_professional_results(self, result):
        """Display AI-generated results in a professional, responsive layout."""
        try:
            logger.debug(f"Displaying results: {json.dumps(result, indent=2)}")
            if hasattr(self, 'result_frame') and self.result_frame.winfo_exists():
                self.result_frame.destroy()
    
            self.result_frame = tk.Frame(self.main_frame, bg='#1e1e1e')
            self.result_frame.pack(fill=tk.BOTH, expand=True)
    
            if not isinstance(result, dict):
                error_msg = "Invalid result format: Expected dictionary"
                logger.error(error_msg)
                self.show_error(error_msg)
                return
            
            required_keys = {"question", "explanation", "solution", "dry_run", "complexity"}
            if not all(key in result for key in required_keys):
                error_msg = f"Result missing required keys: {set(required_keys) - set(result.keys())}"
                logger.error(error_msg)
                self.show_error(error_msg)
                return
            
            if "notes" in result and result["notes"]:
                logger.warning(f"Result contains notes: {result['notes']}")
                self.show_error(result["notes"])
                return
    
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            window_width = int(screen_width * 0.95)
            window_height = int(screen_height * 0.95)
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
            question_height = int(window_height * 0.10)
            column_height = int(window_height * 0.90)
            explanation_height = int(column_height * 0.30)
            complexity_height = int(column_height * 0.25)
            dry_run_height = int(column_height * 0.35)
            code_height = int(column_height * 0.90)
    
            container = tk.Frame(self.result_frame, bg='#1e1e1e')
            container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
    
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
    
            columns_frame = tk.Frame(container, bg='#1e1e1e')
            columns_frame.pack(fill=tk.BOTH, expand=True, pady=2)
    
            left_column = tk.Frame(columns_frame, bg='#2d2d2d', width=int(window_width * 0.6))
            left_column.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 2))
            left_column.pack_propagate(False)
    
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
            logger.info("Results displayed successfully")
        except Exception as e:
            logger.error(f"Error in show_professional_results: {e}")
            self.show_error(f"Error displaying results: {str(e)}")
    
    def _create_collapsible_section(self, parent, title, content, icon, is_code=False, pixel_height=100, wraplength=None):
        """Create a collapsible section with fixed pixel height and styled scrollbar."""
        try:
            logger.debug(f"Creating section: {title} with content: {content[:100]}...")
            frame = tk.Frame(parent, bg='#2d2d2d')
            frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
    
            header = tk.Frame(frame, bg='#2d2d2d')
            header.pack(fill=tk.X)
            tk.Label(header, text=icon, font=("Segoe UI", 12), fg="#0078d7", bg="#2d2d2d").pack(side=tk.LEFT, padx=2)
            tk.Label(header, text=title, font=("Segoe UI", 12, "bold"), fg="#0078d7", bg="#2d2d2d").pack(side=tk.LEFT)
            toggle_btn = tk.Label(header, text="▼", font=("Segoe UI", 10), fg="#e0e0e0", bg="#2d2d2d", cursor="hand2")
            toggle_btn.pack(side=tk.RIGHT, padx=2)
            toggle_btn.bind("<Enter>", lambda e: toggle_btn.config(fg="#ffffff"))
            toggle_btn.bind("<Leave>", lambda e: toggle_btn.config(fg="#e0e0e0"))
    
            content_frame = tk.Frame(frame, bg='#2d2d2d')
            canvas = tk.Canvas(content_frame, bg='#2d2d2d', highlightthickness=0, height=pixel_height)
            scrollbar = tk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)
            inner_frame = tk.Frame(canvas, bg='#2d2d2d')
            canvas.create_window((0, 0), window=inner_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
    
            scrollbar.config(
                bg="#2d2d2d",
                troughcolor="#3c3c3c",
                activebackground="#0078d7",
                highlightbackground="#0078d7",
                width=8
            )
    
            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
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
            logger.debug(f"Section {title} created successfully")
        except Exception as e:
            logger.error(f"Error in _create_collapsible_section: {e}")
            self.show_error(f"Failed to create section: {str(e)}")
    
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
            logger.error(f"Error in show_error: {e}")
            self.show_temporary_message(f"Failed to show error: {str(e)}")
    
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
            logger.error(f"Error in hide_results: {e}")
            self.show_temporary_message(f"Failed to hide results: {str(e)}")
    
    def start_from_scratch(self):
        """Reset the UI for a new question without showing any message."""
        try:
            for file_path, thumb_frame in self.screenshot_thumbnails[:]:
                try:
                    thumb_frame.destroy()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    logger.error(f"Error removing screenshot {file_path}: {e}")
            self.screenshot_files = []
            self.screenshot_thumbnails = []
            if hasattr(self, 'result_frame') and self.result_frame.winfo_exists():
                self.result_frame.destroy()
            self.thumbnails_frame.destroy()
            self.thumbnails_frame = tk.Frame(self.main_frame, bg='#1e1e1e')
            self.thumbnails_frame.pack(fill=tk.X, padx=2, pady=2, after=self.header_frame)
            self.thumbnails_container = tk.Frame(self.thumbnails_frame, bg='#1e1e1e')
            self.thumbnails_container.pack(fill=tk.X, pady=2)
            self.chatbot.close_chat_window()
            self.chat_processor.reset_chat_history()
            self.root.update_idletasks()
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            window_width = 570
            window_height = 60
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
            logger.debug("Application reset successfully with initial window size")
        except Exception as e:
            logger.error(f"Error in start_from_scratch: {e}")
            self.show_temporary_message(f"Failed to reset: {str(e)}")
    
    def copy_specific_code(self, code_text):
        """Copy text to clipboard."""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(code_text)
        except Exception as e:
            logger.error(f"Error in copy_specific_code: {e}")
            self.show_temporary_message(f"Failed to copy code: {str(e)}")
    
    def toggle_visibility(self):
        """Toggle UI visibility."""
        try:
            if self.root.state() == 'normal':
                self.root.withdraw()
            else:
                self.root.deiconify()
                self.root.attributes('-topmost', True)
        except Exception as e:
            logger.error(f"Error in toggle_visibility: {e}")
            self.show_notification(f"Failed to toggle visibility: {str(e)}")
    
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
            logger.error(f"Error in make_click_through: {e}")
            self.show_notification(f"Failed to set click-through: {str(e)}")
    
    def toggle_click_through(self):
        """Toggle click-through state."""
        try:
            self.click_through_enabled = not self.click_through_enabled
            self.make_click_through()
        except Exception as e:
            logger.error(f"Error in toggle_click_through: {e}")
            self.show_notification(f"Failed to toggle click-through: {str(e)}")
    
    def move_window(self, deltax, deltay):
        """Move window by delta values."""
        try:
            x = self.root.winfo_x() + deltax
            y = self.root.winfo_y() + deltay
            self.root.geometry(f"+{x}+{y}")
        except Exception as e:
            logger.error(f"Error in move_window: {e}")
            self.show_notification(f"Failed to move window: {str(e)}")
    
    def start_move(self, event):
        """Start window drag."""
        try:
            self.click_through_enabled = False
            self.make_click_through()
            self.x = event.x
            self.y = event.y
        except Exception as e:
            logger.error(f"Error in start_move: {e}")
            self.show_notification(f"Failed to start drag: {str(e)}")
    
    def stop_move(self, event):
        """Stop window drag."""
        try:
            self.x = None
            self.y = None
            if self.click_through_enabled:
                self.make_click_through()
        except Exception as e:
            logger.error(f"Error in stop_move: {e}")
            self.show_notification(f"Failed to stop drag: {str(e)}")
    
    def do_move(self, event):
        """Perform window drag."""
        try:
            deltax = event.x - self.x
            deltay = event.y - self.y
            x = self.root.winfo_x() + deltax
            y = self.root.winfo_y() + deltay
            self.root.geometry(f"+{x}+{y}")
        except Exception as e:
            logger.error(f"Error in do_move: {e}")
            self.show_notification(f"Failed to drag window: {str(e)}")
    
    def show_temporary_message(self, message, duration=3000):
        """Show a temporary message."""
        try:
            msg_frame = tk.Frame(self.thumbnails_frame, bg="#0078d7", padx=2, pady=2)
            msg_frame.pack(fill=tk.X, pady=2)
            tk.Label(msg_frame, text=message, font=("Segoe UI", 10), fg="white", bg="#0078d7").pack()
            self.root.after(duration, lambda: self.fade_out_message(msg_frame))
        except Exception as e:
            logger.error(f"Error in show_temporary_message: {e}")
            self.show_notification(f"Failed to show message: {str(e)}")
    
    def fade_out_message(self, frame, alpha=1.0, step=0.1):
        """Fade out a message frame."""
        try:
            if alpha <= 0 or not frame.winfo_exists():
                frame.destroy()
                return
            alpha -= step
            frame.after(50, lambda: self.fade_out_message(frame, alpha, step))
        except Exception as e:
            logger.error(f"Error in fade_out_message: {e}")
            if frame.winfo_exists():
                frame.destroy()
    
    def show_notification(self, message):
        """Show a system notification."""
        try:
            notification.notify(
                title="LocalCoder",
                message=message,
                app_name="LocalCoder",
                timeout=5
            )
        except Exception as e:
            logger.error(f"Error in show_notification: {e}")
            print(f"Notification error: {e}")

    def create_tray_icon(self):
        """Create a system tray icon."""
        try:
            image = Image.new('RGB', (64, 64), color=(40, 40, 40))
            draw = ImageDraw.Draw(image)
            draw.text((20, 20), "LC", fill=(0, 120, 215), font_size=32)
            menu = pystray.Menu(
                pystray.MenuItem('Show Shortcuts', self.show_shortcuts),
                pystray.MenuItem('Quit', self.close_application)
            )
            self.tray_icon = pystray.Icon("LocalCoder", image, "LocalCoder", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            logger.error(f"Error in create_tray_icon: {e}")
            self.show_notification(f"Failed to create tray icon: {str(e)}")
    
    def show_shortcuts(self, icon, item):
        """Show shortcuts in a message box."""
        try:
            msg = "\n".join([f"{k}: {d}" for k, d in [
                ("Ctrl+H", "Take a screenshot"),
                ("Ctrl+G", "Open chatbot"),
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
            logger.error(f"Error in show_shortcuts: {e}")
            self.show_notification(f"Failed to show shortcuts: {str(e)}")
    
    def close_application(self):
        """Clean up and exit."""
        try:
            for file in self.screenshot_files:
                if os.path.exists(file):
                    os.remove(file)
            keyboard.unhook_all()
            if self.tray_icon:
                self.tray_icon.stop()
            self.root.destroy()
            sys.exit(0)
        except Exception as e:
            logger.error(f"Error in close_application: {e}")
            sys.exit(1)

def main():
    try:
        root = tk.Tk()
        root.title("LocalCoder")
        app = LocalCoderApp(root)
        root.mainloop()
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()