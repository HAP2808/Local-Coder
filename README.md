# LocalCoder

LocalCoder is a Windows application designed to help users during coding interviews. It provides a see-through UI that is only visible to the user and not to the interviewer when screen sharing.

## Features

- Transparent UI that overlays on top of other applications
- Click-through functionality allowing interaction with applications behind the overlay
- Take multiple screenshots of coding questions with Ctrl+H
- Display thumbnails of captured screenshots for easy reference
- Process all screenshots together with Ctrl+Enter
- Move window with arrow keys (Ctrl + Arrow keys)
- Hide application from taskbar
- Quick access dropdown menu for keyboard shortcuts
- Display dummy AI responses (question detection, explanation, and code solution)
- Copy code solutions to clipboard
- Toggle visibility with ESC key
- Close application with Ctrl+Q or close button

## Installation

1. Ensure you have Python 3.7+ installed on your Windows machine.
2. Clone this repository or download the files.
3. Install the required dependencies:

```
pip install -r requirements.txt
```

## Usage

1. Run the application:

```
python local_coder.py
```

2. The application will show a transparent window with instructions.
3. Navigate to the coding question you want to analyze.
4. Press Ctrl+H to take screenshots of the questions. You can take multiple screenshots.
5. Each screenshot will appear as a thumbnail in the application.
6. When ready to process the screenshots, press Ctrl+Enter.
7. The application will process the screenshots and display results.
8. Use the following keyboard shortcuts:
   - Ctrl+H: Take a screenshot
   - Ctrl+Enter: Process all screenshots
   - Ctrl+F: Toggle click-through mode (enable/disable clicking through the overlay)
   - Ctrl+S: Toggle shortcuts dropdown menu
   - Ctrl+Q: Close application
   - Esc: Hide/Show the application
   - Ctrl+Arrow keys: Move window in the corresponding direction
9. Click the settings button (⚙️) to view the dropdown menu with all keyboard shortcuts.
10. Click the close button (✖) to exit the application.
11. Click "Copy Code" to copy the solution to your clipboard.
12. Click "Close Results" to hide the results panel.

## Future Enhancements

- Integration with AI for real-time coding assistance
- Customizable keyboard shortcuts
- Multiple language support
- More advanced UI with additional features
- Theme customization

## Notes

This is a prototype application. In a real scenario, the screenshots would be processed by an AI to generate responses. 