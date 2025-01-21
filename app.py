from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import os
import secrets
import google.generativeai as palm
from chat_manager import ChatManager
from image_generator import ImageGenerator
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError
from bson import ObjectId
from functools import wraps
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from user import User



# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
if not app.secret_key:
    app.secret_key = secrets.token_hex(32)
    print("Warning: Using randomly generated secret key")

# Initialize LoginManager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'
login_manager.login_message = 'Please login to access this page'
login_manager.login_message_category = 'error'

def requires_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Access denied. Admin privileges required.')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

try:
    # Initialize MongoDB
    mongo_uri = os.getenv('MONGODB_URI')
    if not mongo_uri:
        raise ValueError("MONGODB_URI environment variable is not set")

    # Ensure the URI has the necessary parameters
    if '?' not in mongo_uri:
        mongo_uri += '?retryWrites=true&w=majority&tls=true'
    
    mongo_client = MongoClient(
        mongo_uri,
        serverSelectionTimeoutMS=30000,
        connectTimeoutMS=20000,
        socketTimeoutMS=20000,
        connect=True,
        retryWrites=True,
        tls=True
    )
    # Test the connection
    mongo_client.server_info()
    db = mongo_client.get_database('chatbot')
    print("Successfully connected to MongoDB")
except (PyMongoError, ServerSelectionTimeoutError) as e:
    print(f"Failed to connect to MongoDB: {str(e)}")
    raise
except Exception as e:
    print(f"An error occurred while connecting to MongoDB: {str(e)}")
    raise

# Initialize chat manager and image generator
chat_manager = ChatManager(max_history=50)
image_generator = ImageGenerator()

# Add some permanent context about the user
chat_manager.add_permanent_info("bot_personality", "Professional and friendly AI assistant")

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.get_user(db, user_id)
    except Exception as e:
        print(f"Error loading user: {str(e)}")
        return None

@app.route('/login_page')
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
        
    if request.method == 'GET':
        return render_template('register.html')
        
    try:
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        
        if not all([email, password, name]):
            flash('All fields are required')
            return redirect(url_for('register'))

        # Check if user already exists
        if User.get_user_by_email(db, email):
            flash('Email already registered')
            return redirect(url_for('register'))

        # Create new user
        user = User.create_user(db, name=name, email=email, password=password)
        if user:
            login_user(user)
            flash('Registration successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Registration failed')
            return redirect(url_for('register'))
            
    except Exception as e:
        print(f"Registration error: {str(e)}")
        flash('An error occurred during registration')
        return redirect(url_for('register'))

@app.route('/login', methods=['POST'])
def login():
    try:
        email = request.form.get('email')
        password = request.form.get('password')
        login_type = request.form.get('login_type', 'user')
        
        if not all([email, password]):
            flash('Email and password are required')
            return redirect(url_for('login_page'))
        
        user = User.get_user_by_email(db, email)
        
        if user and user.check_password(password):
            # Check if admin login attempt
            if login_type == 'admin' and not user.is_admin:
                flash('Invalid admin credentials')
                return redirect(url_for('login_page'))
            
            login_user(user)
            flash('Login successful!', 'success')
            next_page = request.args.get('next')
            
            # Redirect admin to admin dashboard
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            
            return redirect(next_page or url_for('home'))
        
        flash('Invalid email or password')
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
    chat_history = db.conversations.find({"user_id": ObjectId(current_user.get_id())}).sort("timestamp", -1)
    return render_template('dashboard.html', chat_history=chat_history)

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    try:
        username = request.form.get('username')
        email = request.form.get('email')
        new_password = request.form.get('new_password')
        
        # Get updates from user model
        updates = current_user.update_profile(
            username=username,
            email=email,
            password=new_password if new_password else None
        )
        
        if updates:
            # Update user in database
            db.users.update_one(
                {"_id": ObjectId(current_user.get_id())},
                {"$set": updates}
            )
            flash('Profile updated successfully!', 'success')
            return jsonify({"success": True})
        
        return jsonify({"success": False, "message": "No changes to update"})
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/chat/<chat_id>', methods=['DELETE'])
@login_required
def delete_chat(chat_id):
    try:
        result = db.conversations.delete_one({
            "_id": ObjectId(chat_id),
            "user_id": ObjectId(current_user.get_id())
        })
        return jsonify({"success": result.deleted_count > 0})
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
        
        # Store the conversation in MongoDB
        conversation = {
            'user_id': current_user.get_id(),
            'user_message': message,
            'bot_response': response.text,
            'timestamp': datetime.utcnow(),
            'user_email': current_user.email,
            'user_name': current_user.name
        }
        db.conversations.insert_one(conversation)

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
        
        # Store the image generation in MongoDB
        image_record = {
            'user_id': current_user.get_id(),
            'prompt': prompt,
            'image_url': image_url,
            'timestamp': datetime.utcnow(),
            'user_email': current_user.email,
            'user_name': current_user.name
        }
        db.generated_images.insert_one(image_record)

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
        # Get all users and convert MongoDB ObjectIds to strings
        users = []
        for user_doc in db.users.find():
            user_doc['_id'] = str(user_doc['_id'])
            # Ensure datetime fields are properly handled
            if 'created_at' not in user_doc:
                user_doc['created_at'] = datetime.utcnow()
            if 'last_activity' not in user_doc:
                user_doc['last_activity'] = None
            users.append(user_doc)
        
        # Get user statistics
        total_users = len(users)
        total_admins = sum(1 for user in users if user.get('is_admin', False))
        
        # Get conversation statistics
        conversations = []
        for conv in db.conversations.find().sort("timestamp", -1):
            conv['_id'] = str(conv['_id'])
            if 'timestamp' not in conv:
                conv['timestamp'] = datetime.utcnow()
            conversations.append(conv)
        total_conversations = len(conversations)
        
        # Get message statistics per day (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        daily_messages = db.conversations.aggregate([
            {
                "$match": {
                    "timestamp": {"$gte": seven_days_ago}
                }
            },
            {
                "$project": {
                    "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                    "message_count": 1
                }
            },
            {
                "$group": {
                    "_id": "$date",
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"_id": 1}
            }
        ])
        
        # Format data for charts
        dates = []
        message_counts = []
        for stat in daily_messages:
            dates.append(stat['_id'])
            message_counts.append(stat['count'])
        
        # Get image generation statistics
        generated_images = []
        for img in db.generated_images.find().sort("timestamp", -1).limit(10):
            img['_id'] = str(img['_id'])
            if 'timestamp' not in img:
                img['timestamp'] = datetime.utcnow()
            generated_images.append(img)
        total_images = db.generated_images.count_documents({})
        
        # Get active users (users with activity in last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        active_users = db.conversations.aggregate([
            {
                "$match": {
                    "timestamp": {"$gte": yesterday}
                }
            },
            {
                "$group": {
                    "_id": "$user_id",
                    "last_activity": {"$max": "$timestamp"}
                }
            }
        ])
        active_users_count = len(list(active_users))
        
        return render_template('admin_dashboard.html',
                             users=users,
                             conversations=conversations,
                             total_users=total_users,
                             total_admins=total_admins,
                             total_conversations=total_conversations,
                             total_images=total_images,
                             active_users_count=active_users_count,
                             dates=dates,
                             message_counts=message_counts,
                             generated_images=generated_images)
    except Exception as e:
        print(f"Error in admin dashboard: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        flash('An error occurred while loading the admin dashboard', 'error')
        return redirect(url_for('home'))

@app.route('/admin/delete_image/<image_id>', methods=['DELETE'])
@login_required
@requires_admin
def delete_image(image_id):
    try:
        result = db.generated_images.delete_one({"_id": ObjectId(image_id)})
        return jsonify({"success": result.deleted_count > 0})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/admin/delete_conversation/<conversation_id>', methods=['DELETE'])
@login_required
@requires_admin
def delete_conversation(conversation_id):
    try:
        result = db.conversations.delete_one({"_id": ObjectId(conversation_id)})
        return jsonify({
            "success": result.deleted_count > 0,
            "message": "Conversation deleted successfully" if result.deleted_count > 0 else "Conversation not found"
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/admin/user_activity/<user_id>')
@login_required
@requires_admin
def user_activity(user_id):
    try:
        user = User.get_user(db, user_id)
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('admin_dashboard'))

        # Get user's conversations and images
        conversations = list(db.conversations.find({'user_id': user_id}).sort('timestamp', -1))
        images = list(db.generated_images.find({'user_id': user_id}).sort('timestamp', -1))

        return render_template('user_activity.html', 
                             user=user,
                             conversations=conversations,
                             images=images)
    except Exception as e:
        print(f"Error in user activity: {str(e)}")
        flash('An error occurred while fetching user activity', 'error')
        return redirect(url_for('admin_dashboard'))

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
        
        user, error = User.create_admin_user(db, email, password, name)
        if error:
            flash(error)
        else:
            flash('Admin user created successfully!', 'success')
        
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        flash(f'An error occurred: {str(e)}')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle_user_block/<user_id>', methods=['POST'])
@login_required
@requires_admin
def toggle_user_block(user_id):
    try:
        user = db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"success": False, "message": "User not found"})
        
        # Toggle blocked status
        new_status = not user.get('is_blocked', False)
        db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"is_blocked": new_status}}
        )
        
        return jsonify({
            "success": True,
            "message": f"User {'blocked' if new_status else 'unblocked'} successfully",
            "is_blocked": new_status
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/admin/manage_api_key/<user_id>', methods=['POST'])
@login_required
@requires_admin
def manage_api_key(user_id):
    try:
        action = request.json.get('action')  # 'generate' or 'revoke'
        user = db.users.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            return jsonify({"success": False, "message": "User not found"})
        
        if action == 'generate':
            # Generate new API key
            api_key = secrets.token_urlsafe(32)
            db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"api_key": api_key}}
            )
            return jsonify({
                "success": True,
                "message": "API key generated successfully",
                "api_key": api_key
            })
        elif action == 'revoke':
            # Revoke API key
            db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"api_key": None}}
            )
            return jsonify({
                "success": True,
                "message": "API key revoked successfully"
            })
        else:
            return jsonify({
                "success": False,
                "message": "Invalid action"
            })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/admin/user_details/<user_id>')
@login_required
@requires_admin
def user_details(user_id):
    try:
        print(f"Fetching user details for user_id: {user_id}")
        
        # Get user document directly from MongoDB
        user_doc = db.users.find_one({"_id": ObjectId(user_id)})
        if not user_doc:
            print(f"User not found with id: {user_id}")
            flash('User not found', 'error')
            return redirect(url_for('admin_dashboard'))

        print(f"Found user document: {user_doc}")

        # Create User instance
        user = User(user_doc)
        print(f"Created user instance with email: {user.email}")

        try:
            # Get user statistics
            total_conversations = db.conversations.count_documents({'user_id': user_id})
            print(f"Total conversations: {total_conversations}")
            
            total_images = db.generated_images.count_documents({'user_id': user_id})
            print(f"Total images: {total_images}")
            
            last_conversation = db.conversations.find_one({'user_id': user_id}, sort=[('timestamp', -1)])
            print(f"Last conversation: {last_conversation}")

            # Get last active time from either last conversation or user document
            last_active = last_conversation['timestamp'] if last_conversation else user_doc.get('last_activity', 'Never')
            print(f"Last active: {last_active}")

            created_at = user_doc.get('created_at', 'Unknown')
            print(f"Account created: {created_at}")

            stats = {
                'total_conversations': total_conversations,
                'total_images': total_images,
                'last_active': last_active,
                'account_created': created_at,
                'account_status': 'Blocked' if user_doc.get('is_blocked', False) else 'Active',
                'api_key_status': 'Active' if user_doc.get('api_key') else 'Not Set'
            }
            print(f"Generated stats: {stats}")

            return render_template('user_details.html', user=user, stats=stats)
            
        except Exception as stats_error:
            print(f"Error while gathering user statistics: {str(stats_error)}")
            print(f"Error type: {type(stats_error)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            raise stats_error

    except Exception as e:
        print(f"Error in user details: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        flash('An error occurred while fetching user details', 'error')
        return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)