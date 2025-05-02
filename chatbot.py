import tkinter as tk
from tkinter import ttk
import ctypes
from chat_processor import ChatProcessor
import re
import logging

# Configure logging
logging.basicConfig(
    filename='chatbot.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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
            logging.error("Invalid window handle")
            return False
        if not _set_window_display_affinity(hwnd, WDA_EXCLUDEFROMCAPTURE):
            error = ctypes.get_last_error()
            logging.error(f"Error hiding from capture: {error}")
            return False
        return True
    except Exception as e:
        logging.error(f"Exception in hide_from_capture: {e}")
        return False

class Chatbot:
    def __init__(self, root, app, chat_processor, opacity=0.8):
        self.root = root
        self.app = app
        self.chat_processor = chat_processor
        self.opacity = opacity
        self.chat_window = None
        self.text_input = None
        self.conversation_frame = None
        self.canvas = None
        self.scrollbar = None
        self.move_step = 20
        self.drag_start_x = None
        self.drag_start_y = None

    def show_chat_window(self):
        """Show the chatbot window with input and conversation area."""
        try:
            if self.chat_window and self.chat_window.winfo_exists():
                self.chat_window.destroy()

            # Hide the main window and mark chatbot as open
            self.app.hide_main_window()
            self.app.chatbot_open = True

            self.chat_window = tk.Toplevel(self.root)
            self.chat_window.withdraw()
            self.root.update_idletasks()

            self.chat_window.overrideredirect(True)
            self.chat_window.attributes('-topmost', True)
            self.chat_window.attributes('-alpha', self.opacity)
            self.chat_window.configure(bg='#1e1e1e')

            self.chat_window.transient(self.root)
            hwnd = ctypes.windll.user32.GetParent(self.chat_window.winfo_id())
            current_style = _get_window_long(hwnd, GWL_EXSTYLE)
            _set_window_long(hwnd, GWL_EXSTYLE, current_style | WS_EX_TOOLWINDOW)

            self.chat_window.update_idletasks()
            if not hide_from_capture(hwnd):
                logging.warning("Failed to hide chat window from screen capture")

            # Set window size to 90% of screen
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            window_width = int(screen_width * 0.95)
            window_height = int(screen_height * 0.95)
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            self.chat_window.geometry(f"{window_width}x{window_height}+{x}+{y}")

            main_frame = tk.Frame(self.chat_window, bg='#1e1e1e', padx=5, pady=5)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Header frame
            header_frame = tk.Frame(main_frame, bg='#2d2d2d', bd=1, relief=tk.SOLID)
            header_frame.pack(fill=tk.X, pady=(0, 5))
            tk.Label(
                header_frame, text="🤖 Interview Chatbot", font=("Segoe UI", 14, "bold"),
                fg="#e0e0e0", bg="#2d2d2d", padx=10, pady=5
            ).pack(side=tk.LEFT)
            
            # Dragging support
            header_frame.bind("<ButtonPress-1>", self.start_drag)
            header_frame.bind("<ButtonRelease-1>", self.stop_drag)
            header_frame.bind("<B1-Motion>", self.do_drag)

            # Header buttons
            clear_btn = tk.Button(
                header_frame, text="Clear Chat", font=("Segoe UI", 9), bg="#2d2d2d",
                fg="#0078d7", relief=tk.FLAT, command=self.clear_chat
            )
            clear_btn.pack(side=tk.RIGHT, padx=5)
            clear_btn.bind("<Enter>", lambda e: clear_btn.config(bg="#444444"))
            clear_btn.bind("<Leave>", lambda e: clear_btn.config(bg="#2d2d2d"))

            close_btn = tk.Button(
                header_frame, text="✖", font=("Segoe UI", 10), bg="#2d2d2d",
                fg="#ff5555", relief=tk.FLAT, command=self.close_chat_window
            )
            close_btn.pack(side=tk.RIGHT, padx=5)
            close_btn.bind("<Enter>", lambda e: close_btn.config(bg="#444444"))
            close_btn.bind("<Leave>", lambda e: close_btn.config(bg="#2d2d2d"))

            # Conversation area
            conversation_frame = tk.Frame(main_frame, bg='#1e1e1e', bd=1, relief=tk.SOLID)
            conversation_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
            
            self.canvas = tk.Canvas(conversation_frame, bg='#1e1e1e', highlightthickness=0)
            self.scrollbar = tk.Scrollbar(conversation_frame, orient="vertical", command=self.canvas.yview)
            self.conversation_frame = tk.Frame(self.canvas, bg='#1e1e1e')
            
            self.canvas.configure(yscrollcommand=self.scrollbar.set)
            self.canvas.create_window((0, 0), window=self.conversation_frame, anchor="nw", width=window_width - 30)
            
            def on_frame_configure(event):
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
                self.canvas.update_idletasks()
                content_height = self.conversation_frame.winfo_reqheight()
                canvas_height = self.canvas.winfo_height()
                if content_height > canvas_height:
                    self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                else:
                    self.scrollbar.pack_forget()
            
            self.conversation_frame.bind("<Configure>", on_frame_configure)
            
            def on_mousewheel(event):
                if self.scrollbar.winfo_ismapped():
                    self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
            self.canvas.bind_all("<MouseWheel>", on_mousewheel)
            
            self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            self.scrollbar.config(
                bg="#1e1e1e", troughcolor="#3c3c3c",
                activebackground="#0078d7", highlightbackground="#0078d7", width=8
            )

            # Input area
            input_frame = tk.Frame(main_frame, bg='#2d2d2d', bd=1, relief=tk.SOLID)
            input_frame.pack(fill=tk.X, pady=(0, 5), padx=5)
            
            self.text_input = tk.Entry(
                input_frame, bg="#1a1a1a", fg="#ffffff", font=("Segoe UI", 11),
                insertbackground="white", relief=tk.FLAT, bd=2, highlightthickness=1,
                highlightbackground="#0078d7", highlightcolor="#0078d7"
            )
            self.text_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 5), pady=5)
            self.text_input.bind("<Return>", lambda e: self.submit_question())
            
            submit_btn = tk.Button(
                input_frame, text="Send", bg="#0078d7", fg="white",
                font=("Segoe UI", 10, "bold"), relief=tk.FLAT, padx=10, pady=5,
                command=self.submit_question
            )
            submit_btn.pack(side=tk.RIGHT, padx=(0, 10), pady=5)
            submit_btn.bind("<Enter>", lambda e: submit_btn.config(bg="#005ba1"))
            submit_btn.bind("<Leave>", lambda e: submit_btn.config(bg="#0078d7"))

            self.chat_window.bind("<Escape>", lambda e: self.close_chat_window())
            
            # Bind movement shortcuts
            self.chat_window.bind('<Control-Left>', lambda e: self.move_window(-self.move_step, 0))
            self.chat_window.bind('<Control-Right>', lambda e: self.move_window(self.move_step, 0))
            self.chat_window.bind('<Control-Up>', lambda e: self.move_window(0, -self.move_step))
            self.chat_window.bind('<Control-Down>', lambda e: self.move_window(0, self.move_step))

            self.chat_window.update_idletasks()
            self.chat_window.deiconify()

            self.text_input.config(state='normal')
            self.text_input.focus_set()
            self.text_input.focus_force()
            logging.debug("Chatbot window opened, text input focused")
        
        except Exception as e:
            logging.error(f"Error in show_chat_window: {e}")
            self.append_error(f"Failed to open chatbot: {str(e)}")
            self.app.show_main_window()
            self.app.chatbot_open = False

    def move_window(self, deltax, deltay):
        """Move the chatbot window by delta values."""
        try:
            if self.chat_window and self.chat_window.winfo_exists():
                x = self.chat_window.winfo_x() + deltax
                y = self.chat_window.winfo_y() + deltay
                self.chat_window.geometry(f"+{x}+{y}")
                logging.debug(f"Moved chatbot window to ({x}, {y})")
        except Exception as e:
            logging.error(f"Error moving chatbot window: {e}")

    def start_drag(self, event):
        """Start dragging the window."""
        try:
            self.drag_start_x = event.x_root - self.chat_window.winfo_x()
            self.drag_start_y = event.y_root - self.chat_window.winfo_y()
            logging.debug("Started dragging chatbot window")
        except Exception as e:
            logging.error(f"Error in start_drag: {e}")

    def do_drag(self, event):
        """Drag the window."""
        try:
            x = event.x_root - self.drag_start_x
            y = event.y_root - self.drag_start_y
            self.chat_window.geometry(f"+{x}+{y}")
        except Exception as e:
            logging.error(f"Error in do_drag: {e}")

    def stop_drag(self, event):
        """Stop dragging the window."""
        try:
            self.drag_start_x = None
            self.drag_start_y = None
            logging.debug("Stopped dragging chatbot window")
        except Exception as e:
            logging.error(f"Error in stop_drag: {e}")

    def submit_question(self):
        """Submit the user's question and display the AI response."""
        try:
            user_question = self.text_input.get().strip()
            if not user_question:
                logging.warning("Empty question submitted")
                return

            self.text_input.delete(0, tk.END)
            self.append_message(user_question, is_user=True)
            
            response = self.chat_processor.process_chat_message(user_question)
            if "error" in response:
                self.append_error(response["error"])
            else:
                self.append_message(response["success"], is_user=False)
            
            logging.debug(f"Submitted question: {user_question}")
        
        except Exception as e:
            logging.error(f"Error in submit_question: {e}")
            self.append_error(f"Error processing question: {str(e)}")

    def append_message(self, text, is_user=False):
        """Append a message to the conversation frame."""
        try:
            # Parse markdown-like formatting
            formatted_lines = self.parse_markdown(text)
            
            # Create message frame with bubble style
            msg_frame = tk.Frame(
                self.conversation_frame, bg='#1e1e1e',
                highlightbackground="#0078d7" if is_user else "#444444",
                highlightthickness=1, padx=10, pady=5
            )
            msg_frame.pack(fill=tk.X, pady=5, padx=20, anchor='e' if is_user else 'w')
            
            # Style based on user or AI
            bg_color = '#2d2d2d' if is_user else '#1a1a1a'
            fg_color = '#e0e0e0' if is_user else '#ffffff'
            anchor = 'e' if is_user else 'w'
            
            for line, style in formatted_lines:
                if style.get("is_code"):
                    # Create a subframe for code with copy button
                    code_frame = tk.Frame(msg_frame, bg=bg_color)
                    code_frame.pack(fill=tk.X, anchor=anchor)
                    label = tk.Label(
                        code_frame,
                        text=line,
                        font=("Consolas", 11),
                        fg=fg_color,
                        bg='#333333',
                        wraplength=600,
                        justify='left' if is_user else 'left',
                        anchor=anchor,
                        padx=10,
                        pady=3
                    )
                    label.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    copy_btn = tk.Button(
                        code_frame,
                        text="Copy",
                        bg="#0078d7",
                        fg="white",
                        font=("Segoe UI", 9),
                        relief=tk.FLAT,
                        command=lambda text=line: self.copy_code(text),
                        padx=2,
                        pady=2
                    )
                    copy_btn.pack(side=tk.RIGHT, padx=(5, 0))
                    copy_btn.bind("<Enter>", lambda e: copy_btn.config(bg="#005ba1"))
                    copy_btn.bind("<Leave>", lambda e: copy_btn.config(bg="#0078d7"))
                else:
                    # Normal text or other styles
                    label = tk.Label(
                        msg_frame,
                        text=line,
                        font=style["font"],
                        fg=fg_color,
                        bg=bg_color,
                        wraplength=600,
                        justify='right' if is_user else 'left',
                        anchor=anchor,
                        padx=10,
                        pady=3
                    )
                    label.pack(fill=tk.X, anchor=anchor)
                    if style.get("is_hr"):
                        label.config(text="─" * 80, fg="#0078d7", justify='center', bg='#1e1e1e')
            
            self.canvas.update_idletasks()
            self.canvas.yview_moveto(1.0)
            logging.debug(f"Appended message (is_user={is_user})")
        
        except Exception as e:
            logging.error(f"Error in append_message: {e}")
            self.append_error(f"Error displaying message: {str(e)}")

    def append_error(self, error_message):
        """Append an error message to the conversation frame."""
        try:
            error_frame = tk.Frame(
                self.conversation_frame, bg='#1e1e1e',
                highlightbackground="#ff5555", highlightthickness=1, padx=10, pady=5
            )
            error_frame.pack(fill=tk.X, pady=5, padx=20, anchor='w')
            tk.Label(
                error_frame,
                text=f"Error: {error_message}",
                font=("Segoe UI", 11),
                fg="#ff5555",
                bg='#1a1a1a',
                wraplength=600,
                justify='left',
                anchor='w',
                padx=10,
                pady=3
            ).pack(fill=tk.X, anchor='w')
            self.canvas.update_idletasks()
            self.canvas.yview_moveto(1.0)
            logging.debug(f"Appended error: {error_message}")
        
        except Exception as e:
            logging.error(f"Error in append_error: {e}")

    def parse_markdown(self, text):
        """Parse markdown-like formatting into styled lines."""
        try:
            lines = text.split('\n')
            formatted_lines = []
            in_code_block = False
            
            for line in lines:
                # Separator (--- or ===)
                if re.match(r'^-{3,}$|^={3,}$', line.strip()):
                    formatted_lines.append((line, {"font": ("Segoe UI", 11), "is_hr": True}))
                    continue
                
                # Code block
                if line.strip().startswith('```'):
                    in_code_block = not in_code_block
                    continue
                
                if in_code_block:
                    formatted_lines.append((line, {"font": ("Consolas", 11), "is_code": True}))
                    continue
                
                # Bold (**text**)
                if '**' in line:
                    line = re.sub(r'\*\*(.*?)\*\*', r'\1', line)
                    formatted_lines.append((line, {"font": ("Segoe UI", 11, "bold")}))
                    continue
                
                # Italics (*text*)
                if '*' in line:
                    line = re.sub(r'\*(.*?)\*', r'\1', line)
                    formatted_lines.append((line, {"font": ("Segoe UI", 11, "italic")}))
                    continue
                
                # Normal text
                formatted_lines.append((line, {"font": ("Segoe UI", 11)}))
            
            return formatted_lines
        
        except Exception as e:
            logging.error(f"Error in parse_markdown: {e}")
            return [(text, {"font": ("Segoe UI", 11)})]

    def copy_code(self, code_text):
        """Copy code text to clipboard."""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(code_text)
            logging.debug(f"Copied code to clipboard: {code_text[:50]}...")
        except Exception as e:
            logging.error(f"Error in copy_code: {e}")
            self.append_error(f"Failed to copy code: {str(e)}")

    def clear_chat(self):
        """Clear the chat history and conversation area."""
        try:
            self.chat_processor.reset_chat_history()
            for widget in self.conversation_frame.winfo_children():
                widget.destroy()
            logging.debug("Chat history and conversation area cleared")
        except Exception as e:
            logging.error(f"Error in clear_chat: {e}")
            self.append_error(f"Failed to clear chat: {str(e)}")

    def close_chat_window(self):
        """Close the chatbot window and clean up."""
        try:
            if self.chat_window and self.chat_window.winfo_exists():
                self.chat_window.unbind_all("<MouseWheel>")
                self.chat_window.destroy()
            self.chat_window = None
            self.text_input = None
            self.conversation_frame = None
            self.canvas = None
            self.scrollbar = None
            self.app.show_main_window()
            self.app.chatbot_open = False
            logging.debug("Chatbot window closed and state reset")
        
        except Exception as e:
            logging.error(f"Error in close_chat_window: {e}")
            self.app.show_main_window()
            self.app.chatbot_open = False