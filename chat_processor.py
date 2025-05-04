import os
import json
import logging
from groq import Groq, APIError
import requests

# Configure logging
logging.basicConfig(
    filename='chatbot.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class ChatProcessor:
    def __init__(self, api_key):
        if not api_key:
            logging.error("GROQ API key not provided")
            raise ValueError("GROQ API key not provided")
        self.client = Groq(api_key=api_key)
        self.chat_history = []

    def process_chat_message(self, user_message):
        """Process a user message and return the AI response."""
        try:
            if not user_message.strip():
                return {"error": "Empty message provided"}
            
            self.chat_history.append({"role": "user", "content": user_message})
            system_prompt = (
                "You are an expert software engineer assisting a student preparing for a technical interview. "
                "Provide clear, concise, and accurate answers to their questions. "
                "Focus on software engineering concepts, coding problems, system design, or interview strategies. "
                "Use examples, code snippets, or step-by-step explanations where appropriate."
            )
            messages = [{"role": "system", "content": system_prompt}] + self.chat_history
            response = self.client.chat.completions.create(
                model=os.getenv("GROQ_MODEL", "meta-llama/llama-4-maverick-17b-128e-instruct"),
                messages=messages,
                temperature=0.7,
                stream=False
            )
            assistant_message = response.choices[0].message.content
            self.chat_history.append({"role": "assistant", "content": assistant_message})
            return {"success": assistant_message}
        
        except APIError as e:
            logging.error(f"Groq API error: {str(e)}")
            return {"error": f"API error: {str(e)}. Please try again."}
        except requests.ConnectionError:
            logging.error("Network connection error")
            return {"error": "Network error: Unable to connect to the AI server. Please check your internet connection."}
        except Exception as e:
            logging.error(f"Unexpected error in process_chat_message: {str(e)}")
            return {"error": f"Unexpected error: {str(e)}. Please try again or contact support."}

    def reset_chat_history(self):
        """Clear the chat history."""
        try:
            self.chat_history = []
        except Exception as e:
            logging.error(f"Error resetting chat history: {str(e)}")
            raise