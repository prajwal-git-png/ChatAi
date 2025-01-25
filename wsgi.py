from app import app
import os

if __name__ == "__main__":
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
