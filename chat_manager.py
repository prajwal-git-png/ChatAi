import json
import os
from datetime import datetime
import google.generativeai as genai
from pathlib import Path
import tempfile

class ChatManager:
    def __init__(self):
        self.data_dir = self._get_data_dir()
        self.chats_file = self.data_dir / 'chats.json'
        self._ensure_chats_file()

    def _get_data_dir(self):
        """Get the appropriate data directory for the environment"""
        if os.environ.get('VERCEL_ENV'):
            # Use /tmp directory in Vercel
            base_dir = Path(tempfile.gettempdir())
        else:
            # Use local directory in development
            base_dir = Path(__file__).parent
        
        data_dir = base_dir / 'data'
        data_dir.mkdir(exist_ok=True)
        return data_dir

    def _ensure_chats_file(self):
        """Ensure chats file exists with default structure"""
        if not self.chats_file.exists():
            with open(self.chats_file, 'w') as f:
                json.dump({"chats": {}}, f)

    def get_user_chats(self, user_id: str) -> list:
        """Get all chats for a user"""
        try:
            with open(self.chats_file, 'r') as f:
                chats_data = json.load(f)
                return chats_data.get("chats", {}).get(user_id, [])
        except Exception as e:
            print(f"Error getting user chats: {e}")
            return []

    def add_to_history(self, user_id: str, message: str, response: str):
        """Add a message and response to the chat history"""
        try:
            # Create a new file if it doesn't exist
            if not self.chats_file.exists():
                self._ensure_chats_file()

            try:
                with open(self.chats_file, 'r') as f:
                    chats_data = json.load(f)
            except json.JSONDecodeError:
                chats_data = {"chats": {}}

            if user_id not in chats_data["chats"]:
                chats_data["chats"][user_id] = []

            chat_entry = {
                "timestamp": datetime.now().isoformat(),
                "message": message,
                "response": response
            }

            chats_data["chats"][user_id].append(chat_entry)

            with open(self.chats_file, 'w') as f:
                json.dump(chats_data, f)

        except Exception as e:
            print(f"Error adding to history: {e}")

    def get_context_for_prompt(self, user_id: str, max_messages: int = 5) -> str:
        """Get the conversation context for the next prompt"""
        chats = self.get_user_chats(user_id)
        if not chats:
            return ""

        recent_chats = chats[-max_messages:]
        context = []
        for chat in recent_chats:
            context.append(f"User: {chat['message']}")
            context.append(f"Assistant: {chat['response']}")

        return "\n".join(context)

    def process_message(self, message: str, user_id: str) -> str:
        """Process a message using Gemini model"""
        try:
            # Get conversation context
            context = self.get_context_for_prompt(user_id)
            full_prompt = f"{context}\nUser: {message}\nAssistant:"

            # Use Gemini model for text generation
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(full_prompt)
            
            # Save to history
            self.add_to_history(user_id, message, response.text)
            
            return response.text

        except Exception as e:
            print(f"Error processing message: {str(e)}")
            raise

    def clear_history(self, user_id: str):
        """Clear chat history for a user"""
        try:
            if not self.chats_file.exists():
                return

            try:
                with open(self.chats_file, 'r') as f:
                    chats_data = json.load(f)
            except json.JSONDecodeError:
                chats_data = {"chats": {}}

            if user_id in chats_data["chats"]:
                chats_data["chats"][user_id] = []

            with open(self.chats_file, 'w') as f:
                json.dump(chats_data, f)

        except Exception as e:
            print(f"Error clearing history: {e}")