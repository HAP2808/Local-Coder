def toggle_screen_sharing_mode(self):
    """
    Toggle screen sharing mode - completely hides the app 
    during screen sharing using techniques that work with Google Meet
    """
    # Toggle screen sharing hidden state
    self.screen_sharing_hidden = not self.screen_sharing_hidden
    
    if self.screen_sharing_hidden:
        # Save current position and size for later restoration
        self.save_pos_x = self.root.winfo_x()
        self.save_pos_y = self.root.winfo_y()
        self.save_width = self.root.winfo_width()
        self.save_height = self.root.winfo_height()
        
        # Method 1: Move window off-screen (outside visible area)
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.root.geometry(f"1x1+{screen_width+100}+{screen_height+100}")
        
        # Method 2: Make fully transparent
        self.root.attributes('-alpha', 0.0)
        
        # Method 3: Make window very small
        self.root.geometry("1x1")
        
        # Method 4: Set window style to make it not visible on screen capture
        try:
            # Windows constants
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_TOOLWINDOW = 0x00000080
            
            # Get the window handle
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            
            # Get current window style
            style = ctypes.windll.user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            
            # Add styles to make the window harder to capture
            style = style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
            
            # Set the new window style
            ctypes.windll.user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)
            
            # Hide window completely (different from withdraw)
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE = 0
        except Exception as e:
            print(f"Error modifying window for screen sharing: {e}")
        
        # Show feedback via system notification
        self.show_notification("LocalCoder is now hidden for screen sharing.\nPress Ctrl+M again to restore.")
    else:
        # Restore window visibility
        self.root.attributes('-alpha', 0.8)
        
        # Restore window size and position
        if hasattr(self, 'save_pos_x') and hasattr(self, 'save_pos_y'):
            self.root.geometry(f"{self.save_width}x{self.save_height}+{self.save_pos_x}+{self.save_pos_y}")
        else:
            # Default if saved position not available
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            window_width = 800
            window_height = 600
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Reset window style to be interactive again
        try:
            # Windows constants
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_TOOLWINDOW = 0x00000080
            
            # Get the window handle
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            
            # Get current window style
            style = ctypes.windll.user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            
            # Remove transparent style but keep layered
            style = style & ~WS_EX_TRANSPARENT
            
            # Set the new window style
            ctypes.windll.user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)
            
            # Show window
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE = 9
        except Exception as e:
            print(f"Error restoring window style: {e}")
        
        # Make sure window is visible
        self.root.deiconify()
        
        # Make it topmost
        self.root.attributes('-topmost', True)
        
        # Make it click-through if that mode was enabled
        self.make_click_through()
        
        # Show feedback message in the app
        self.show_temporary_message("Screen sharing mode disabled - App is now visible") 