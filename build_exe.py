import os
import subprocess
import shutil
import sys

def build_executable():
    print("Building LocalCoder executable...")
    
    # Name of the executable
    app_name = "LocalCoder"
    
    # Clean up previous builds if they exist
    if os.path.exists("dist"):
        print("Cleaning up previous builds...")
        shutil.rmtree("dist", ignore_errors=True)
    
    if os.path.exists("build"):
        shutil.rmtree("build", ignore_errors=True)
    
    # Build command with all the necessary options
    cmd = [
        "pyinstaller",
        "--name", app_name,
        "--windowed",  # GUI mode, no console
        "--onefile",   # Package everything into a single executable
        "--clean",     # Clean PyInstaller cache
        "--add-data", "LICENSE;.",  # Include license if you have one
        "--icon", "icon.ico" if os.path.exists("icon.ico") else "",  # Add icon if available
        "--hidden-import", "PIL._tkinter_finder",  # Required for PIL/Pillow
        "--hidden-import", "groq",  # Required for Groq API
        "local_coder.py"  # Main script
    ]
    
    # Remove empty icon path if no icon exists
    if not os.path.exists("icon.ico"):
        cmd.pop(10)  # Remove the empty icon path
        cmd.pop(9)   # Remove the --icon parameter
    
    # Check for LICENSE file
    if not os.path.exists("LICENSE"):
        cmd.pop(8)  # Remove the LICENSE path
        cmd.pop(7)  # Remove the --add-data parameter
    
    # Build the executable
    print("Running PyInstaller with command:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    
    print(f"\nBuild completed! Executable is in the 'dist' folder: dist/{app_name}.exe")
    print("You can now distribute this standalone executable.")

if __name__ == "__main__":
    build_executable() 