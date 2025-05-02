import os
import logging
from groq import Groq, APIError
from dotenv import load_dotenv
import requests

# Configure logging
logging.basicConfig(
    filename='screenshot.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class ScreenshotProcessor:
    def __init__(self):
        load_dotenv()
        api_key = os.getenv("GROQ_API_KEY2")
        if not api_key:
            logging.error("GROQ_API_KEY2 environment variable not set")
            raise ValueError("GROQ_API_KEY2 environment variable not set")
        self.client = Groq(api_key=api_key)

    def process_screenshots(self, screenshot_files, callback=None):
        """Process screenshots to generate structured output."""
        try:
            if not screenshot_files:
                logging.error("No screenshot files provided")
                return {"error": "No screenshots provided"}
            
            prompt = (
                "You are an expert software engineer preparing a student for a technical interview. "
                "Analyze the provided screenshots containing code or technical questions. "
                "Generate a structured response with the following sections:\n"
                "- **Question**: Summarize the question or problem statement.\n"
                "- **Explanation**: Provide a detailed explanation of the solution or concept.\n"
                "- **Complexity**: Analyze time and space complexity (if applicable).\n"
                "- **Example Dry Run**: Step-by-step dry run of the solution (if applicable).\n"
                "- **Code**: Provide the complete, correct code solution (if applicable).\n"
                "Ensure the response is clear, concise, and tailored for a software engineering interview context."
            )
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Analyze the screenshots: {', '.join(screenshot_files)}"}
            ]
            response = self.client.chat.completions.create(
                model="meta-llama/llama-4-maverick-17b-128e-instruct",
                messages=messages,
                temperature=0.7,
                stream=False
            )
            content = response.choices[0].message.content
            sections = {
                "question": "",
                "explanation": "",
                "complexity": "",
                "dry_run": "",
                "solution": ""
            }
            current_section = None
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("**Question**:"):
                    current_section = "question"
                    sections[current_section] = line.replace("**Question**:", "").strip()
                elif line.startswith("**Explanation**:"):
                    current_section = "explanation"
                    sections[current_section] = line.replace("**Explanation**:", "").strip()
                elif line.startswith("**Complexity**:"):
                    current_section = "complexity"
                    sections[current_section] = line.replace("**Complexity**:", "").strip()
                elif line.startswith("**Example Dry Run**:"):
                    current_section = "dry_run"
                    sections[current_section] = line.replace("**Example Dry Run**:", "").strip()
                elif line.startswith("**Code**:"):
                    current_section = "solution"
                    sections[current_section] = line.replace("**Code**:", "").strip()
                elif current_section and line:
                    sections[current_section] += "\n" + line
            return sections
        
        except APIError as e:
            logging.error(f"Groq API error: {str(e)}")
            return {"error": f"API error: {str(e)}. Please try again."}
        except requests.ConnectionError:
            logging.error("Network connection error")
            return {"error": "Network error: Unable to connect to the AI server. Please check your internet connection."}
        except Exception as e:
            logging.error(f"Unexpected error in process_screenshots: {str(e)}")
            return {"error": f"Unexpected error: {str(e)}. Please try again or contact support."}