import os
import io
import json
import base64
from PIL import Image
import threading
import requests
import logging
import traceback
from typing import List, Dict, Any, Optional, Tuple, Callable
from dotenv import load_dotenv
import time

# Set up logging
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Check if groq is installed, if not, provide function to install dependencies
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

class AIProcessor:
    """
    A class that processes screenshots using the Groq API to extract code and information.
    This is implemented as a singleton to ensure only one instance exists.
    """
    _instance = None
    
    # Class constants for API prompts
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
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AIProcessor, cls).__new__(cls)
            # Initialize the processor
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the processor with configuration values"""
        # Load API key from environment (from .env file)
        self.api_key = os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            # Check if user has API key stored locally
            config_path = os.path.join(os.path.expanduser("~"), ".localcoder", "config.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r") as f:
                        config = json.load(f)
                        self.api_key = config.get("groq_api_key")
                except:
                    pass
                    
        # Initialize Groq client if API key exists
        self.client = Groq(api_key=self.api_key) if self.api_key else None
        
        # Set default model - using Llama Maverick which supports image inputs
        self.model = "meta-llama/llama-4-maverick-17b-128e-instruct"
        
    def set_api_key(self, api_key):
        """Set the API key and initialize the client"""
        self.api_key = api_key
        self.client = Groq(api_key=self.api_key)
        
        # Save API key to config
        config_dir = os.path.join(os.path.expanduser("~"), ".localcoder")
        os.makedirs(config_dir, exist_ok=True)
        
        config_path = os.path.join(config_dir, "config.json")
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
            except:
                pass
                
        config["groq_api_key"] = api_key
        
        with open(config_path, "w") as f:
            json.dump(config, f)
            
        return True
        
    def check_api_key(self):
        """Check if API key is set and valid"""
        if not self.api_key:
            return False
            
        # Test connection
        try:
            # Send a minimal request to test API key
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            return True
        except Exception as e:
            print(f"API Key validation error: {str(e)}")
            return False
    
    def encode_image(self, image_path):
        """Encode an image to base64 format"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
            
    def process_screenshots(self, screenshot_paths: List[str], callback: Optional[Callable] = None):
        """
        Process screenshots of coding problems to extract information
        
        Args:
            screenshot_paths (List[str]): List of paths to screenshots
            callback (Optional[Callable], optional): Callback function to call with results
            
        Returns:
            Dict: Extracted information or error details if no callback is provided
        """
        print(f"Processing {len(screenshot_paths)} screenshots")
        
        # Check if API key is set
        if not self.check_api_key():
            print("ERROR: API key not set")
            default_response = {
                "question": "",
                "explanation": "API key not set",
                "solution": "# API key not set\n# Please set your API key first",
                "example": "",
                "complexity": "",
                "notes": "No API key found. Please set your API key first."
            }
            
            if callback:
                print("Invoking callback with API key error response")
                callback(default_response)
                return None
            return default_response
        
        # Check if screenshots are provided
        if not screenshot_paths:
            print("ERROR: No screenshots provided")
            default_response = {
                "question": "",
                "explanation": "No screenshots provided",
                "solution": "# No screenshots provided",
                "example": "",
                "complexity": "",
                "notes": "Please provide at least one screenshot of a coding problem."
            }
            
            if callback:
                print("Invoking callback with no screenshots error response")
                callback(default_response)
                return None
            return default_response
            
        print(f"Starting processing of {len(screenshot_paths)} screenshots")
        
        # If callback is provided, process in a separate thread
        if callback:
            print("Callback provided, processing in background thread")
            thread = threading.Thread(target=self._process_thread, args=(screenshot_paths, callback))
            thread.daemon = True
            thread.start()
            print(f"Background thread started (id: {thread.ident})")
            return None
            
        # If no callback, process synchronously
        print("No callback provided, processing synchronously")
        try:
            # Prepare images
            print("Preparing images for processing")
            image_inputs = self._prepare_images(screenshot_paths)
            
            if not image_inputs:
                print("No valid images prepared, returning default response")
                return {
                    "question": "",
                    "explanation": "No valid images found",
                    "solution": "# No solution available",
                    "example": "",
                    "complexity": "",
                    "notes": "Failed to process screenshots. Please ensure the images are valid."
                }
                
            # Process with API
            print("Processing images with API")
            result = self._process_with_api(image_inputs)
            print("API processing complete, returning results")
            return result
            
        except Exception as e:
            print(f"Error in synchronous processing: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "question": "",
                "explanation": f"Error: {str(e)}",
                "solution": "# Error during processing",
                "example": "",
                "complexity": "",
                "notes": f"An error occurred: {str(e)}"
            }
    
    def _prepare_images(self, screenshot_paths: List[str]) -> List[str]:
        """
        Prepare images for processing by encoding them in base64 format
        
        Args:
            screenshot_paths (List[str]): List of file paths to images
            
        Returns:
            List[str]: List of base64 encoded images
        """
        logger.debug(f"Preparing {len(screenshot_paths)} images")
        image_inputs = []
        
        for idx, path in enumerate(screenshot_paths):
            try:
                logger.debug(f"Processing image {idx+1}/{len(screenshot_paths)}: {path}")
                # Check if file exists
                if not os.path.exists(path):
                    logger.warning(f"Image file not found: {path}")
                    continue
                    
                # Read and encode the image
                with open(path, "rb") as file:
                    base64_image = base64.b64encode(file.read()).decode("utf-8")
                    
                # Check if encoding was successful
                if not base64_image:
                    logger.warning(f"Failed to encode image: {path}")
                    continue
                    
                # Add to inputs list
                image_inputs.append(base64_image)
                logger.debug(f"Successfully encoded image {idx+1}")
                
            except Exception as e:
                logger.error(f"Error preparing image {path}: {str(e)}")
                logger.error(traceback.format_exc())
                
        logger.debug(f"Successfully prepared {len(image_inputs)} of {len(screenshot_paths)} images")
        return image_inputs
    
    def _process_with_api(self, images: List[str]) -> Dict[str, Any]:
        """
        Process the screenshot with the LLM API
        
        Args:
            images: List of base64 encoded images
            
        Returns:
            Dict: Response from API containing explanation, code and examples
        """
        logger.debug("Starting API processing")
        
        # Default response structure in case of error
        default_response = {
            "explanation": self.ERROR_MSG_PROCESSING_FAILED,
            "code": self.ERROR_MSG_NO_CODE_GENERATED,
            "examples": [],
            "error": "",
        }
        
        # Check if we have any images to process
        if not images:
            logger.error("No valid images to process")
            default_response["error"] = "No valid images provided"
            return default_response
            
        try:
            logger.debug(f"Processing {len(images)} images with API")
            
            # Prepare the messages for the API
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": self.USER_PROMPT}
                    ]
                }
            ]
            
            # Add each image to the user content
            for img in images:
                messages[1]["content"].append({
                    "type": "image", 
                    "image": img
                })
                
            # Create the API request
            url = f"{self.API_URL}/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.MODEL,
                "messages": messages,
                "max_tokens": self.MAX_TOKENS
            }
            
            logger.debug(f"Sending request to API: {url}")
            response = requests.post(url, headers=headers, json=payload)
            
            # Check if the request was successful
            if response.status_code != 200:
                logger.error(f"API request failed with status {response.status_code}")
                logger.error(f"Response: {response.text}")
                default_response["error"] = f"API request failed: {response.status_code}"
                return default_response
                
            # Parse the response
            response_data = response.json()
            
            # Check if we have the expected keys in the response
            if "choices" not in response_data or not response_data["choices"]:
                logger.error("No choices in API response")
                default_response["error"] = "Invalid API response format"
                return default_response
                
            # Extract the message content
            content = response_data["choices"][0]["message"]["content"]
            
            # Try to parse the JSON content
            try:
                parsed_content = json.loads(content)
                logger.debug("Successfully parsed API response")
                
                # Check for required keys
                required_keys = ["explanation", "code", "examples"]
                missing_keys = [key for key in required_keys if key not in parsed_content]
                
                if missing_keys:
                    logger.warning(f"Missing keys in API response: {missing_keys}")
                    # Add any missing keys with default values
                    for key in missing_keys:
                        if key == "explanation":
                            parsed_content[key] = self.ERROR_MSG_NO_EXPLANATION
                        elif key == "code":
                            parsed_content[key] = self.ERROR_MSG_NO_CODE_GENERATED
                        elif key == "examples":
                            parsed_content[key] = []
                
                return parsed_content
                
            except json.JSONDecodeError:
                logger.error("Failed to parse JSON from API response")
                logger.error(f"Raw content: {content}")
                default_response["error"] = "Invalid JSON in API response"
                return default_response
                
        except Exception as e:
            logger.error(f"Error processing with API: {str(e)}")
            logger.error(traceback.format_exc())
            default_response["error"] = str(e)
            return default_response
    
    @staticmethod
    def install_dependencies():
        """
        Install required dependencies for the AI processor
        
        Returns:
            bool: True if installation was successful, False otherwise
        """
        try:
            import subprocess
            subprocess.check_call(["pip", "install", "groq", "python-dotenv"])
            return True
        except Exception as e:
            print(f"Error installing dependencies: {e}")
            return False

    def _process_thread(self, screenshot_paths: List[str], callback: Callable = None) -> None:
        """Process screenshots in a separate thread and invoke the callback when done"""
        print(f"Starting processing thread for {len(screenshot_paths)} screenshots")
        result = {}
        
        try:
            # Prepare images
            print("Preparing images for processing")
            image_inputs = self._prepare_images(screenshot_paths)
            
            if not image_inputs:
                print("No valid images prepared, returning default response")
                result = {
                    "question": "",
                    "explanation": "No valid images found",
                    "solution": "# No solution available",
                    "example": "",
                    "complexity": "",
                    "notes": "Failed to process screenshots. Please ensure the images are valid."
                }
            else:
                # Process images with API
                print(f"Processing {len(image_inputs)} images with API")
                result = self._process_with_api(image_inputs)
                print("API processing complete")
                
        except Exception as e:
            print(f"Error in processing thread: {str(e)}")
            import traceback
            traceback.print_exc()
            result = {
                "question": "",
                "explanation": f"Error: {str(e)}",
                "solution": "# Error during processing",
                "example": "",
                "complexity": "",
                "notes": f"An error occurred: {str(e)}"
            }
            
        finally:
            # Call the callback with the result if provided
            if callback:
                print("Invoking callback with results")
                callback(result)
            else:
                print("No callback provided, results will not be returned")
                
            print("Thread processing complete")

# Create a singleton instance
ai_processor = AIProcessor() 