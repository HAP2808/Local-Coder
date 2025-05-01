import os
import json
import base64
import logging
from typing import List, Dict, Any, Optional, Callable
from dotenv import load_dotenv
from groq import Groq
import time
import traceback

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class AIProcessor:
    """Singleton class to process screenshots using Groq API for coding problem analysis."""
    _instance = None

    SYSTEM_PROMPT = """You are an expert programming assistant analyzing coding problems from screenshots.
Extract the problem statement and provide a comprehensive solution with explanation, code, and examples.
Format your response as a valid JSON object with these fields:
{
  "question": "Extracted problem statement",
  "explanation": "In-depth explanation of the approach",
  "solution": "Complete solution code (provide the full implementation)",
  "example": "Example usage of the solution",
  "complexity": "Time and space complexity analysis",
  "notes": "Additional notes or edge cases to consider"
}
Ensure all code is fully executable and handles all edge cases mentioned in the problem."""

    USER_PROMPT = "Analyze these screenshots of a coding problem and provide a solution."
    MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct"  # Placeholder; replace with correct Llama Maverick model ID
    MAX_TOKENS = 4096
    MAX_RETRIES = 3

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AIProcessor, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize the processor with configuration values."""
        self.api_key = os.environ.get("GROQ_API_KEY2")
        if not self.api_key:
            config_path = os.path.join(os.path.expanduser("~"), ".localcoder", "config.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r") as f:
                        config = json.load(f)
                        self.api_key = config.get("GROQ_API_KEY2")
                except Exception as e:
                    logger.error(f"Failed to load config: {e}")
        self.client = Groq(api_key=self.api_key) if self.api_key else None
        self.model = self.MODEL

    def set_api_key(self, api_key: str) -> bool:
        """Set and save the API key."""
        try:
            self.api_key = api_key
            self.client = Groq(api_key=self.api_key)
            config_dir = os.path.join(os.path.expanduser("~"), ".localcoder")
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, "config.json")
            config = {"GROQ_API_KEY2": api_key}
            with open(config_path, "w") as f:
                json.dump(config, f)
            return True
        except Exception as e:
            logger.error(f"Failed to set API key: {e}")
            return False

    def check_api_key(self) -> bool:
        """Validate the API key."""
        if not self.api_key or not self.client:
            return False
        try:
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            return True
        except Exception as e:
            logger.error(f"API key validation failed: {e}")
            return False

    def encode_image(self, image_path: str) -> Optional[str]:
        """Encode an image to base64 format."""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to encode image {image_path}: {e}")
            return None

    def process_screenshots(self, screenshot_paths: List[str], callback: Optional[Callable] = None) -> Optional[Dict]:
        """Process screenshots to extract coding problem information."""
        logger.info(f"Processing {len(screenshot_paths)} screenshots")
        default_response = {
            "question": "",
            "explanation": "Error processing screenshots",
            "solution": "# No solution generated",
            "example": "",
            "complexity": "",
            "notes": "An error occurred during processing."
        }

        if not self.check_api_key():
            logger.error("API key not set")
            default_response["notes"] = "Please set your Groq API key."
            if callback:
                callback(default_response)
                return None
            return default_response

        if not screenshot_paths:
            logger.error("No screenshots provided")
            default_response["notes"] = "Please provide at least one screenshot."
            if callback:
                callback(default_response)
                return None
            return default_response

        if callback:
            threading.Thread(target=self._process_thread, args=(screenshot_paths, callback), daemon=True).start()
            return None

        try:
            image_inputs = self._prepare_images(screenshot_paths)
            if not image_inputs:
                default_response["notes"] = "No valid images found."
                return default_response
            return self._process_with_api(image_inputs)
        except Exception as e:
            logger.error(f"Error in synchronous processing: {e}")
            default_response["notes"] = f"Processing error: {str(e)}"
            return default_response

    def _prepare_images(self, screenshot_paths: List[str]) -> List[str]:
        """Prepare images by encoding them in base64 format."""
        logger.info(f"Preparing {len(screenshot_paths)} images")
        image_inputs = []
        for path in screenshot_paths:
            if not os.path.exists(path):
                logger.warning(f"Image file not found: {path}")
                continue
            encoded = self.encode_image(path)
            if encoded:
                image_inputs.append(encoded)
        logger.info(f"Prepared {len(image_inputs)} images")
        return image_inputs

    def _process_with_api(self, images: List[str]) -> Dict[str, Any]:
        """Process images with the Groq API."""
        logger.info(f"Processing {len(images)} images with API")
        default_response = {
            "question": "",
            "explanation": "Could not process screenshots",
            "solution": "# No solution generated",
            "example": "",
            "complexity": "",
            "notes": "Error processing screenshots"
        }

        if not images:
            logger.error("No valid images to process")
            return default_response

        for attempt in range(self.MAX_RETRIES):
            try:
                messages = [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.USER_PROMPT},
                            *[{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}} for img in images]
                        ]
                    }
                ]
                start_time = time.time()
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=self.MAX_TOKENS,
                    response_format={"type": "json_object"}
                )
                # print(response)
                logger.info(f"API response received in {time.time() - start_time:.2f} seconds")

                try:
                    parsed = json.loads(response.choices[0].message.content)
                    required_keys = ["question", "explanation", "solution", "example", "complexity", "notes"]
                    for key in required_keys:
                        parsed.setdefault(key, default_response[key])
                    return parsed
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parsing failed: {e}")
                    if attempt == self.MAX_RETRIES - 1:
                        return default_response
                    time.sleep(1)  # Wait before retrying
            except Exception as e:
                logger.error(f"API processing error (attempt {attempt + 1}): {e}")
                if attempt == self.MAX_RETRIES - 1:
                    return default_response
                time.sleep(1)  # Wait before retrying
        return default_response

    def _process_thread(self, screenshot_paths: List[str], callback: Callable) -> None:
        """Process screenshots in a separate thread."""
        logger.info(f"Starting processing thread for {len(screenshot_paths)} screenshots")
        try:
            image_inputs = self._prepare_images(screenshot_paths)
            result = self._process_with_api(image_inputs) if image_inputs else {
                "question": "",
                "explanation": "No valid images found",
                "solution": "# No solution available",
                "example": "",
                "complexity": "",
                "notes": "Failed to process screenshots."
            }
        except Exception as e:
            logger.error(f"Thread processing error: {e}")
            result = {
                "question": "",
                "explanation": f"Error: {str(e)}",
                "solution": "# Error during processing",
                "example": "",
                "complexity": "",
                "notes": f"Processing error: {str(e)}"
            }
        if callback:
            callback(result)
        logger.info("Thread processing complete")

# Create singleton instance
AIProcessor = AIProcessor()