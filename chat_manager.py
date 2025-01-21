from typing import List, Dict
import json
import os
from datetime import datetime
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

class ChatManager:
    def __init__(self, max_history: int = 50):
        self.max_history = max_history
        self.permanent_context = {}
        self._init_mongo()
        self.load_permanent_context()
    
    def _init_mongo(self):
        """Initialize MongoDB connection with error handling"""
        mongo_uri = os.getenv('MONGODB_URI')
        if not mongo_uri:
            raise ValueError("MONGODB_URI environment variable is not set")
        
        try:
            # Set a shorter timeout for faster error detection
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            # Verify the connection
            self.client.admin.command('ping')
            print("Successfully connected to MongoDB!")
            
            self.db = self.client.get_database('chatbot')
            self.conversations: Collection = self.db.conversations
            
            # Create indexes
            self.conversations.create_index([("user_id", 1)])
            self.conversations.create_index([("timestamp", -1)])
            
        except ConnectionFailure:
            print("Failed to connect to MongoDB. Server not available")
            raise
        except ServerSelectionTimeoutError:
            print("Failed to connect to MongoDB. Timeout error")
            raise
        except Exception as e:
            print(f"An error occurred while connecting to MongoDB: {str(e)}")
            raise
    
    def _ensure_connection(self):
        """Ensure MongoDB connection is alive"""
        try:
            self.client.admin.command('ping')
        except:
            self._init_mongo()
    
    def load_permanent_context(self):
        # Load from environment variables
        context_str = os.getenv('PERMANENT_CONTEXT', '{}')
        try:
            self.permanent_context = json.loads(context_str)
        except json.JSONDecodeError:
            self.permanent_context = {}
    
    def save_permanent_context(self):
        # Save to environment variable
        context_str = json.dumps(self.permanent_context)
        os.environ['PERMANENT_CONTEXT'] = context_str
    
    def add_permanent_info(self, key: str, value: str):
        self.permanent_context[key] = value
        self.save_permanent_context()
    
    def add_to_history(self, user_id: str, message: str, response: str):
        """Add a message to user's conversation history with error handling"""
        try:
            self._ensure_connection()
            
            # Insert new conversation
            self.conversations.insert_one({
                'user_id': user_id,
                'message': message,
                'response': response,
                'timestamp': datetime.utcnow()
            })
            
            # Get count of user's conversations
            count = self.conversations.count_documents({'user_id': user_id})
            
            # If exceeded max_history, delete oldest conversations
            if count > self.max_history:
                # Find the oldest conversations to delete
                to_delete = count - self.max_history
                oldest = self.conversations.find(
                    {'user_id': user_id},
                    sort=[('timestamp', 1)]
                ).limit(to_delete)
                
                # Delete them
                self.conversations.delete_many({
                    '_id': {'$in': [doc['_id'] for doc in oldest]}
                })
                
        except Exception as e:
            print(f"Error adding to history: {str(e)}")
            raise
    
    def get_context_for_prompt(self, user_id: str) -> str:
        """Get context including user-specific conversation history with error handling"""
        try:
            self._ensure_connection()
            
            context = "Permanent Context:\n"
            for key, value in self.permanent_context.items():
                context += f"{key}: {value}\n"
            
            context += "\nRecent Conversation History:\n"
            # Get last 5 conversations
            recent_conversations = self.conversations.find(
                {'user_id': user_id},
                sort=[('timestamp', -1)]
            ).limit(5)
            
            # Convert to list and reverse to get chronological order
            conversations = list(recent_conversations)
            conversations.reverse()
            
            for conv in conversations:
                context += f"User: {conv['message']}\nAssistant: {conv['response']}\n"
            
            return context
            
        except Exception as e:
            print(f"Error getting context: {str(e)}")
            return "Error retrieving conversation history"
    
    def clear_user_history(self, user_id: str):
        """Clear conversation history for a specific user with error handling"""
        try:
            self._ensure_connection()
            result = self.conversations.delete_many({'user_id': user_id})
            print(f"Deleted {result.deleted_count} conversations for user {user_id}")
        except Exception as e:
            print(f"Error clearing history: {str(e)}")
            raise 