from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from bson import ObjectId

class User(UserMixin):
    def __init__(self, user_data):
        self.user_data = user_data
        
    def get_id(self):
        return str(self.user_data.get('_id'))
    
    @property
    def is_active(self):
        return not self.user_data.get('is_blocked', False)
    
    @property
    def email(self):
        return self.user_data.get('email')
    
    @property
    def username(self):
        return self.user_data.get('username', self.email.split('@')[0])
    
    @property
    def name(self):
        return self.user_data.get('name')
    
    @property
    def is_admin(self):
        return self.user_data.get('is_admin', False)
    
    @property
    def api_key(self):
        return self.user_data.get('api_key')
    
    @property
    def is_blocked(self):
        return self.user_data.get('is_blocked', False)
    
    @property
    def last_activity(self):
        return self.user_data.get('last_activity')
    
    @property
    def created_at(self):
        return self.user_data.get('created_at', datetime.now())
    
    @classmethod
    def create_user(cls, db, name, email, password, is_admin=False):
        if db.users.find_one({"email": email}):
            raise ValueError("Email already exists")
        
        user_data = {
            "name": name,
            "email": email,
            "password": generate_password_hash(password, method='pbkdf2:sha256'),
            "is_admin": is_admin,
            "created_at": datetime.now(),
            "is_blocked": False,
            "api_key": None,
            "last_activity": None
        }
        
        result = db.users.insert_one(user_data)
        user_data['_id'] = result.inserted_id
        return cls(user_data)

    @classmethod
    def create_admin_user(cls, db, email, password, name):
        try:
            # Check if admin already exists
            if db.users.find_one({"email": email}):
                return None, "Email already registered"
            
            # Create new admin user
            user_data = {
                "email": email,
                "password": generate_password_hash(password, method='pbkdf2:sha256'),
                "name": name,
                "created_at": datetime.now(),
                "is_admin": True,
                "is_blocked": False,
                "api_key": None,
                "last_activity": None
            }
            
            result = db.users.insert_one(user_data)
            user_data['_id'] = result.inserted_id
            
            return cls(user_data), None
            
        except Exception as e:
            return None, str(e)
    
    @staticmethod
    def get_user(db, user_id):
        """Get user by ID"""
        try:
            user_data = db.users.find_one({'_id': ObjectId(user_id)})
            return User(user_data) if user_data else None
        except Exception:
            return None
    
    @staticmethod
    def get_user_by_email(db, email):
        user_data = db.users.find_one({"email": email})
        return User(user_data) if user_data else None
    
    def check_password(self, password):
        """Check if password is correct"""
        stored_hash = self.user_data.get('password')
        if not stored_hash:
            return False
        return check_password_hash(stored_hash, password)
    
    def update_profile(self, username=None, email=None, password=None):
        updates = {}
        if username:
            updates['username'] = username
        if email:
            updates['email'] = email
        if password:
            updates['password'] = generate_password_hash(password, method='pbkdf2:sha256')
        return updates

    def update_last_activity(self, db):
        db.users.update_one(
            {"_id": ObjectId(self.get_id())},
            {"$set": {"last_activity": datetime.now()}}
        )
