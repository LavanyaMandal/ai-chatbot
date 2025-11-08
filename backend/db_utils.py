# db_utils.py
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)
db = client["ai_chatbot"]  # database name
chat_collection = db["chat_history"]

def save_message(role, message):
    chat_collection.insert_one({
        "role": role,
        "message": message
    })

def get_all_messages():
    return list(chat_collection.find({}, {"_id": 0}))
