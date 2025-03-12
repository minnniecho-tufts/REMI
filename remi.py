from flask import Flask, request, jsonify, send_file
from datetime import datetime
import os
import json
import requests
import re
import urllib.parse
from llmproxy import generate

app = Flask(__name__)

# Load API Key from .env file
API_KEY = os.getenv("YELP_API_KEY")   
YELP_API_URL = "https://api.yelp.com/v3/businesses/search"
SESSION_FILE = "session_store.json"

### --- SESSION MANAGEMENT FUNCTIONS --- ###
def load_sessions():
    """Load stored sessions from a JSON file."""
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return {}
    return {}

def save_sessions(session_dict):
    """Save sessions to a JSON file."""
    with open(SESSION_FILE, "w") as file:
        json.dump(session_dict, file, indent=4)

### --- FIX `POST /` REQUESTS: HANDLE THEM AS `/query` --- ###
@app.route('/', methods=['POST'])
def handle_root_post():
    """Automatically forwards misplaced POST requests to /query."""
    data = request.get_json()
    print(f"🔄 Redirecting misplaced request to /query: {data}")
    return process_request(data)

@app.route('/', methods=['GET'])
def health_check():
    """Health check route for Koyeb deployment."""
    return "Flask app is running!", 200

### --- FLASK ROUTE TO HANDLE USER REQUESTS --- ###
@app.route('/query', methods=['POST'])
def main():
    """Handles user messages and session management dynamically."""
    data = request.get_json()
    return process_request(data)

def process_request(data):
    """Handles user queries, whether they come from `/` or `/query`."""
    
    if not data or "text" not in data:
        print("⚠️ Received malformed request:", data)
        return jsonify({"error": "Malformed request"}), 400

    message = data.get("text", "").strip().lower()
    user = data.get("user_name", "Unknown")

    # Load sessions
    session_dict = load_sessions()

    # Restart phrases dynamically
    restart_phrases = ["hi", "hello", "restart", "start over", "new session", "begin again", "reset"]

    # Restart session automatically if a user greets or requests restart
    if any(re.search(rf"\b{phrase}\b", message) for phrase in restart_phrases):
        session_dict[user] = {
            "session_id": f"{user}-session",
            "api_results": [],
            "top_choice": "",
            "current_search": {},
            "res_date": "",
            "res_time": ""
        }
        save_sessions(session_dict)

        # Send restart message directly to Rocket.Chat
        RC_message(user, "🔄 Your session has been restarted! Let's start fresh. How can I help you today?")
        return jsonify({})  

    # Handle invitation responses dynamically
    elif re.search(r"yes_response_|no_response_", message):
        handle_friend_response(user, message, session_dict)

    # If message is unrecognized, respond with the restaurant assistant logic
    else:
        response = restaurant_assistant_llm(message, user, session_dict)
        RC_message(user, response["text"])

    # Save session changes
    save_sessions(session_dict)
    return jsonify({})

### --- SENDING MESSAGE TO ROCKET.CHAT --- ###
def RC_message(user_id, message):
    """Sends a message to a user on Rocket.Chat."""
    url = "https://chat.genaiconnect.net/api/v1/chat.postMessage"

    headers = {
        "Content-Type": "application/json",
        "X-Auth-Token": "NwEWNpYAyj0VjnGIWDqzLG_8JGUN4l2J3-4mQaZm_pF",
        "X-User-Id": "vuWQsF6j36wS6qxmf"
    }

    payload = {
        "channel": f"@{user_id}",
        "text": message
    }

    response = requests.post(url, json=payload, headers=headers)
    print(response.status_code, response.json())

### --- MAIN CHATBOT LOGIC --- ###
def restaurant_assistant_llm(message, user, session_dict):
    """Handles restaurant recommendation and reservation logic."""
    sid = session_dict[user]["session_id"]
    
    response = generate(
        model="4o-mini",
        system="Your system prompt here...",
        query=message,
        temperature=0.7,
        lastk=10,
        session_id=sid,
        rag_usage=False
    )

    response_text = response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?").strip()

    return {"text": response_text}

### --- RUN THE FLASK APP --- ###
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)






