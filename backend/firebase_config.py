import os, json
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()
# Initialize Firebase Admin SDK
firebase_creds = os.getenv("FIREBASE_CREDENTIALS","serviceAccountKey.json")
cred = credentials.Certificate(firebase_creds)
firebase_admin.initialize_app(cred)

# Get Firestore client
db = firestore.client()
