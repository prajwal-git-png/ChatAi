from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json
import os
import secrets
import google.generativeai as palm
from chat_manager import ChatManager
from image_generator import ImageGenerator
from dotenv import load_dotenv
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError
from bson import ObjectId
from functools import wraps
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key')

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'
login_manager.login_message = 'Please login to access this page'
login_manager.login_message_category = 'error'

# Local storage for users
USERS_FILE = 'users.json'

def load_users():
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading users: {e}")
        return {}

def save_users(users):
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f)
    except Exception as e:
        print(f"Error saving users: {e}")

# User class
class User(UserMixin):
    def __init__(self, user_id, username, email, password, is_admin=False):
        self.id = user_id
        self.username = username
        self.email = email
        self.password = password
        self.is_admin = is_admin

    def check_password(self, password):
        return check_password_hash(self.password, password)

@login_manager.user_loader
def load_user(user_id):
    users = load_users()
    if user_id in users:
        user_data = users[user_id]
        return User(user_id, user_data['username'], user_data['email'], user_data['password'], user_data.get('is_admin', False))
    return None

def requires_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Access denied. Admin privileges required.')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

try:
    # Initialize chat manager and image generator
    chat_manager = ChatManager(max_history=50)
    image_generator = ImageGenerator()

    # Add some permanent context about the user
    chat_manager.add_permanent_info("bot_personality", "Professional and friendly AI assistant")

except Exception as e:
    print(f"An error occurred while initializing chat manager or image generator: {str(e)}")
    raise

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
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        users = load_users()
        
        # Check if username already exists
        if any(u['username'] == username for u in users.values()):
            flash('Username already exists')
            return redirect(url_for('register'))
        
        # Create new user
        user_id = str(len(users) + 1)
        users[user_id] = {
            'username': username,
            'email': email,
            'password': generate_password_hash(password)
        }
        
        save_users(users)
        
        user = User(user_id, username, email, users[user_id]['password'])
        login_user(user)
        flash('Registration successful!', 'success')
        return redirect(url_for('home'))
        
    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    try:
        username = request.form['username']
        password = request.form['password']
        login_type = request.form.get('login_type', 'user')
        
        users = load_users()
        
        # Find user by username
        user_id = None
        user_data = None
        for uid, data in users.items():
            if data['username'] == username:
                user_id = uid
                user_data = data
                break
        
        if user_data and check_password_hash(user_data['password'], password):
            # Check if admin login attempt
            if login_type == 'admin' and not user_data.get('is_admin', False):
                flash('Invalid admin credentials')
                return redirect(url_for('login_page'))
            
            user = User(user_id, username, user_data['email'], user_data['password'], user_data.get('is_admin', False))
            login_user(user)
            flash('Login successful!', 'success')
            next_page = request.args.get('next')
            
            # Redirect admin to admin dashboard
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            
            return redirect(next_page or url_for('home'))
        
        flash('Invalid username or password')
        return redirect(url_for('login_page'))
    except Exception as e:
        flash(f'An error occurred during login: {str(e)}')
        return redirect(url_for('login_page'))

@app.route('/logout')
@login_required
def logout():
    try:
        logout_user()
        session.clear()
        flash('You have been logged out successfully', 'success')
        return redirect(url_for('login_page'))
    except Exception as e:
        flash(f'An error occurred during logout: {str(e)}')
        return redirect(url_for('home'))

@app.route('/')
@login_required
def home():
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Get user's chat history
    chat_history = chat_manager.get_history(current_user.get_id())
    return render_template('dashboard.html', chat_history=chat_history)

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    try:
        username = request.form.get('username')
        email = request.form.get('email')
        new_password = request.form.get('new_password')
        
        users = load_users()
        
        # Update user data
        if username:
            users[current_user.get_id()]['username'] = username
        if email:
            users[current_user.get_id()]['email'] = email
        if new_password:
            users[current_user.get_id()]['password'] = generate_password_hash(new_password)
        
        save_users(users)
        
        flash('Profile updated successfully!', 'success')
        return jsonify({"success": True})
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/chat/<chat_id>', methods=['DELETE'])
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
        data = request.json
        message = data.get('message')
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return jsonify({'error': 'API key is required'}), 401
        
        # Check if message contains @image tag
        if message.startswith('@image'):
            print(f"Processing image generation request: {message}")
            # Extract the prompt after @image tag
            image_prompt = message[6:].strip()
            print(f"Image prompt: {image_prompt}")
            
            # Generate image
            try:
                print("Calling image generator...")
                image_base64 = image_generator.generate_image(image_prompt)
                print(f"Image generated successfully, base64 length: {len(image_base64)}")
                response_text = f"I've generated an image based on your prompt: {image_prompt}"
                
                # Add to history
                chat_manager.add_to_history(current_user.get_id(), message, response_text)
                
                print("Sending response with image...")
                return jsonify({
                    'response': response_text,
                    'image': image_base64
                })
            except Exception as e:
                error_msg = f"Failed to generate image: {str(e)}"
                print(error_msg)
                return jsonify({'error': error_msg}), 500
        
        # Handle normal text chat
        palm.configure(api_key=api_key)
        model = palm.GenerativeModel('gemini-pro')
        
        context = chat_manager.get_context_for_prompt(current_user.get_id())
        full_prompt = f"{context}\nUser: {message}\nAssistant:"
        
        response = model.generate_content(full_prompt)
        chat_manager.add_to_history(current_user.get_id(), message, response.text)
        
        return jsonify({
            'response': response.text
        })
    except Exception as e:
        print(f"Error in chat route: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/generate_image', methods=['POST'])
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
        palm.configure(api_key=api_key)
        model = palm.GenerativeModel('gemini-pro')
        # Make a simple test request
        response = model.generate_content("Hello")
        return jsonify({'valid': True})
    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)}), 400

@app.route('/admin/dashboard')
@login_required
@requires_admin
def admin_dashboard():
    try:
        users = load_users()
        return render_template('admin_dashboard.html', users=users)
    except Exception as e:
        print(f"Error in admin dashboard: {str(e)}")
        flash('An error occurred while loading the admin dashboard', 'error')
        return redirect(url_for('home'))

@app.route('/admin/delete_user/<user_id>', methods=['DELETE'])
@login_required
@requires_admin
def delete_user(user_id):
    try:
        users = load_users()
        if user_id in users:
            del users[user_id]
            save_users(users)
            return jsonify({"success": True})
        return jsonify({"success": False, "message": "User not found"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/admin/create_admin', methods=['POST'])
@login_required
@requires_admin
def create_admin():
    try:
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        
        if not all([email, password, name]):
            flash('All fields are required')
            return redirect(url_for('admin_dashboard'))
        
        users = load_users()
        user_id = str(len(users) + 1)
        users[user_id] = {
            'username': name,
            'email': email,
            'password': generate_password_hash(password),
            'is_admin': True
        }
        save_users(users)
        
        flash('Admin user created successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        flash(f'An error occurred: {str(e)}')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/user_details/<user_id>')
@login_required
@requires_admin
def user_details(user_id):
    try:
        users = load_users()
        if user_id in users:
            user = User(user_id, users[user_id]['username'], users[user_id]['email'], users[user_id]['password'], users[user_id].get('is_admin', False))
            return render_template('user_details.html', user=user)
        flash('User not found', 'error')
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        print(f"Error in user details: {str(e)}")
        flash('An error occurred while fetching user details', 'error')
        return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)