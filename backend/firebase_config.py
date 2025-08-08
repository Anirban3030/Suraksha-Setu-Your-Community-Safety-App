import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
# Load environment variables from a .env file
load_dotenv()
# Initialize Firebase only if it's not already initialized
if not firebase_admin._apps:
    try:
        # Retrieve Firebase service account credentials from environment variables
        # FIREBASE_CREDENTIALS is expected to be a JSON string
        firebase_creds = json.loads(os.getenv("FIREBASE_CREDENTIALS"))
         # Create a Firebase credential object from the parsed JSON
        cred = credentials.Certificate(firebase_creds)
         # Initialize the Firebase Admin SDK with the provided credentials
        firebase_admin.initialize_app(cred)
    except Exception as e:
        # Log and raise the error if initialization fails
        print(f"❌ Firebase initialization failed: {e}") 
        raise e
# Create a Firestore database client to perform database operations
db = firestore.client()
