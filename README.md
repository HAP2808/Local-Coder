# LocalCoder

LocalCoder is a Windows application designed to assist users during coding interviews. It provides a transparent, user-only UI that remains invisible to interviewers during screen sharing, ensuring discreet assistance.

## Features

- **Transparent Overlay UI**: A see-through interface that overlays other applications, allowing seamless interaction.
- **Click-Through Functionality**: Toggle click-through mode (`Ctrl+F`) to interact with applications behind the overlay.
- **Screenshot Capture**: Capture multiple screenshots of coding questions with `Ctrl+H`, displayed as thumbnails for easy reference.
- **Batch Screenshot Processing**: Process all screenshots together with `Ctrl+Enter` to generate AI-driven responses.
- **Chatbot Integration**: Open an interactive chatbot window (`Ctrl+G`) to ask coding-related questions, receive formatted AI responses with code blocks, and copy code snippets to the clipboard.
- **Window Navigation**: Move the window using `Ctrl+Arrow keys` for precise positioning.
- **Taskbar Hiding**: The application is hidden from the taskbar for a discreet experience.
- **Keyboard Shortcuts Menu**: Access a dropdown menu (`Ctrl+S`) or system tray icon to view all keyboard shortcuts.
- **AI Response Display**: View dummy or AI-generated responses, including question detection, explanations, complexity analysis, dry runs, and code solutions.
- **Clipboard Support**: Copy code solutions or chatbot code snippets to the clipboard with dedicated buttons.
- **Toggle Visibility**: Show or hide the application with the `Esc` key.
- **Application Exit**: Close the application with `Ctrl+Q` or the close button (`✖`).
- **Reset Functionality**: Clear screenshots and reset the UI with `Ctrl+O`.

## Installation

1. Ensure you have Python 3.7+ installed on your Windows machine.
2. Clone this repository or download the files.
3. Install the required dependencies:

```
pip install -r requirements.txt
```

4. Set up the required environment variable for the Grok API key:
   - Create a `.env` file in the project directory or set the variable manually:
     ```
     GROQ_API_KEY2=your_groq_api_key_here
     ```
   - Obtain the API key from [Groq API](https://console.groq.com/keys).

## Usage

1. Run the application:

```
python local_coder.py
```

2. A transparent window with instructions will appear, centered on the screen.
3. Navigate to the coding question you want to analyze.
4. Capture screenshots:
   - Press `Ctrl+H` to take screenshots of coding questions (multiple screenshots are supported).
   - Thumbnails of each screenshot will appear in the main window.
5. Process screenshots:
   - Press `Ctrl+Enter` to process all screenshots and display AI-generated results, including question, explanation, complexity, dry run, and code solution.
   - Click “Copy” buttons to copy code to the clipboard.
   - Press `Esc` or click “Back” to return to the thumbnail view.
6. Use the chatbot:
   - Press `Ctrl+G` to open the chatbot window, which hides the main window.
   - Type questions in the input box and press `Enter` or click “Send” to submit.
   - View AI responses with formatted text and code blocks, each with a “Copy” button for code snippets.
   - Click “Clear Chat” to reset the conversation or `Esc` to close the chatbot and return to the main window.
   - Note: `Ctrl+H` is disabled while the chatbot is open to prevent screenshot capture.
7. Manage the UI:
   - Press `Ctrl+F` to toggle click-through mode.
   - Press `Ctrl+S` to open the settings dialog with all keyboard shortcuts.
   - Press `Ctrl+O` to reset the UI, clearing all screenshots and chat history.
   - Press `Ctrl+Arrow keys` to move the main or chatbot window.
   - Press `Esc` to hide/show the main window.
   - Press `Ctrl+Q` or click the close button (`✖`) to exit the application.
8. Access shortcuts via the system tray:
   - Right-click the “LocalCoder” tray icon to view shortcuts or quit the application.

### Keyboard Shortcuts

- `Ctrl+H`: Capture a screenshot (disabled when chatbot is open).
- `Ctrl+G`: Open the chatbot window.
- `Ctrl+Enter`: Process all screenshots.
- `Ctrl+O`: Reset the UI and clear screenshots/chat history.
- `Ctrl+F`: Toggle click-through mode.
- `Ctrl+S`: Toggle the settings/shortcuts dropdown menu.
- `Ctrl+Q`: Close the application.
- `Esc`: Hide/show the main window or close the chatbot.
- `Ctrl+Arrow keys`: Move the main or chatbot window.

## Future Enhancements

- **Customizable Shortcuts**: Allow users to rebind keyboard shortcuts.
- **Multi-Language Support**: Extend AI responses to support multiple programming languages.
- **Advanced UI Features**: Add resizable windows, pinned thumbnails, or drag-and-drop screenshot reordering.
- **Theme Customization**: Support light/dark themes or custom color schemes.
- **Real-Time AI Enhancements**: Improve chatbot responsiveness with streaming responses or context-aware suggestions.
- **Cross-Platform Support**: Adapt the application for macOS and Linux.

## Notes

- This application is a prototype. The screenshot processing and chatbot currently use a Grok API for AI responses, simulating real-time coding assistance.
- The UI is designed to be excluded from screen capture during screen sharing, ensuring it remains invisible to interviewers.
- Ensure the `GROQ_API_KEY2` environment variable is set correctly, or the AI features will not function.
- Logs are saved to `local_coder.log` and `chatbot.log` for debugging purposes.

WARNING - This is only for learning purpose. Collaborators of this project do not promote cheating or malpractise. 