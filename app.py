from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_session import Session
import os
import json
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai
import secrets
import tempfile
from pathlib import Path
from image_generator import ImageGenerator
from chat_manager import ChatManager

# Initialize Flask app
app = Flask(__name__)

# Auto-generate secret key
app.secret_key = secrets.token_hex(32)

# Session configuration for Vercel
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_FILE_DIR'] = tempfile.gettempdir()

# Initialize Flask-Session
Session(app)

# Configure paths for Vercel deployment
def get_data_dir():
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

# Initialize data files
DATA_DIR = get_data_dir()
USERS_FILE = DATA_DIR / 'users.json'
CHATS_FILE = DATA_DIR / 'chats.json'

def ensure_data_files():
    """Ensure data files exist with default structure"""
    if not USERS_FILE.exists():
        with open(USERS_FILE, 'w') as f:
            json.dump({"users": []}, f)
    
    if not CHATS_FILE.exists():
        with open(CHATS_FILE, 'w') as f:
            json.dump({"chats": []}, f)

ensure_data_files()

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

# User class for Flask-Login
class User:
    def __init__(self, user_data):
        self.id = str(user_data.get('id'))
        self.email = user_data.get('email')
        self.name = user_data.get('name')
        self.password_hash = user_data.get('password')
        self.is_admin = user_data.get('is_admin', False)

    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    @staticmethod
    def get(user_id):
        with open(USERS_FILE, 'r') as f:
            users_data = json.load(f)
            for user in users_data.get('users', []):
                if str(user.get('id')) == str(user_id):
                    return User(user)
        return None

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# Initialize chat manager and image generator
try:
    chat_manager = ChatManager()
    image_generator = ImageGenerator()
except Exception as e:
    print(f"An error occurred while initializing chat manager or image generator: {str(e)}")
    raise

# Initialize AI models
def init_ai_models():
    try:
        gemini_key = os.environ.get('GOOGLE_API_KEY')
        if gemini_key:
            genai.configure(api_key=gemini_key)
    except Exception as e:
        print(f"Warning: Could not initialize Gemini model: {str(e)}")

init_ai_models()

@app.route('/login_page')
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        try:
            name = request.form['name']
            email = request.form['email']
            password = request.form['password']
            confirm_password = request.form['confirm_password']

            if password != confirm_password:
                flash('Passwords do not match.', 'error')
                return redirect(url_for('register'))

            users = json.load(open(USERS_FILE, 'r'))
            
            # Check if email already exists
            if any(u['email'] == email for u in users.get('users', [])):
                flash('Email already registered.', 'error')
                return redirect(url_for('register'))

            # Create new user
            user_id = str(len(users.get('users', [])) + 1)
            users['users'].append({
                'id': user_id,
                'name': name,
                'email': email,
                'password': generate_password_hash(password),
                'is_admin': False
            })
            
            with open(USERS_FILE, 'w') as f:
                json.dump(users, f)
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login_page'))

        except Exception as e:
            flash(f'An error occurred during registration: {str(e)}', 'error')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    try:
        email = request.form['email']
        password = request.form['password']
        login_type = request.form.get('login_type', 'user')

        users = json.load(open(USERS_FILE, 'r'))
        # Find user by email in the users dictionary
        user = None
        for user_data in users.get('users', []):
            if user_data['email'] == email:
                user = user_data
                break

        if user and check_password_hash(user['password'], password):
            if login_type == 'admin' and not user.get('is_admin', False):
                flash('Access denied. Admin privileges required.', 'error')
                return redirect(url_for('login_page'))

            user_obj = User(user)
            login_user(user_obj)
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password.', 'error')
            return redirect(url_for('login_page'))

    except Exception as e:
        flash(f'An error occurred during login: {str(e)}', 'error')
        return redirect(url_for('login_page'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Successfully logged out.', 'success')
    return redirect(url_for('login_page'))

@app.route('/')
@login_required
def home():
    return render_template('index.html')

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    try:
        username = request.form.get('username')
        email = request.form.get('email')
        new_password = request.form.get('new_password')
        
        users = json.load(open(USERS_FILE, 'r'))
        
        # Update user data
        for user in users.get('users', []):
            if user['id'] == current_user.get_id():
                if username:
                    user['name'] = username
                if email:
                    user['email'] = email
                if new_password:
                    user['password'] = generate_password_hash(new_password)
        
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f)
        
        flash('Profile updated successfully!', 'success')
        return jsonify({"success": True})
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/delete_chat/<chat_id>', methods=['DELETE'])
@login_required
def delete_chat(chat_id):
    try:
        chat_manager.delete_from_history(current_user.get_id(), chat_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    try:
        message = request.json.get('message', '')
        api_key = request.json.get('api_key')
        hf_api_key = request.json.get('hf_api_key')

        if not message:
            return jsonify({'error': 'No message provided'}), 400

        # Configure AI models with provided keys
        if api_key:
            genai.configure(api_key=api_key)
        if hf_api_key:
            image_generator.set_api_key(hf_api_key)

        # Check if message is for image generation
        if message.startswith('@image'):
            image_prompt = message[6:].strip()
            try:
                image_base64 = image_generator.generate_image(image_prompt)
                response_text = f"I've generated an image based on your prompt: {image_prompt}"
                return jsonify({
                    'response': response_text,
                    'image': image_base64
                })
            except ValueError as e:
                return jsonify({'error': str(e)}), 400
            except Exception as e:
                return jsonify({'error': f"Failed to generate image: {str(e)}"}), 500

        # Process regular chat message
        response = chat_manager.process_message(message, current_user.get_id())
        return jsonify({
            'response': response,
            'error': None
        })

    except Exception as e:
        print(f"Error in chat: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/generate-image', methods=['POST'])
@login_required
def generate_image():
    try:
        prompt = request.json.get('prompt', '')
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400

        # Generate image using the image generator
        image_url = image_generator.generate(prompt)
        
        return jsonify({'image_url': image_url})
    except Exception as e:
        print(f"Error generating image: {str(e)}")
        return jsonify({'error': 'An error occurred while generating the image'}), 500

@app.route('/clear_history', methods=['POST'])
@login_required
def clear_history():
    try:
        chat_manager.clear_history(current_user.get_id())
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/verify_api_key', methods=['POST'])
@login_required
def verify_api_key():
    try:
        api_key = request.json.get('api_key')
        if not api_key:
            return jsonify({'valid': False, 'error': 'API key is required'}), 400
        
        # Try to configure and make a simple test request
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        # Make a simple test request
        response = model.generate_content("Hello")
        return jsonify({'valid': True})
    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)}), 400

# Vercel serverless configuration
if __name__ == '__main__':
    # Get port from environment variable or default to 3000
    port = int(os.environ.get('PORT', 3000))
    
    # Check if running on Vercel
    if os.environ.get('VERCEL_ENV'):
        # In Vercel, we don't run the app directly
        # Vercel will use the app object
        pass
    else:
        # Local development
        app.run(host='0.0.0.0', port=port)