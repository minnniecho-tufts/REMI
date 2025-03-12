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

# JSON file to store user sessions
SESSION_FILE = "session_store.json"

# Rocket.Chat API Credentials
ROCKETCHAT_API_URL = "https://chat.genaiconnect.net/api/v1/chat.postMessage"
ROCKETCHAT_AUTH_TOKEN = "NwEWNpYAyj0VjnGIWDqzLG_8JGUN4l2J3-4mQaZm_pF"
ROCKETCHAT_USER_ID = "vuWQsF6j36wS6qxmf"

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

### --- GOOGLE CALENDAR LINK GENERATION --- ###
def generate_google_calendar_link(event_name, location, event_date, event_time):
    """
    Generates a Google Calendar event link.
    """
    base_url = "https://calendar.google.com/calendar/render?action=TEMPLATE"
    formatted_date = event_date.replace("-", "")  
    formatted_time = event_time.replace(":", "") + "00Z"  
    event_datetime = f"{formatted_date}T{formatted_time}"  

    params = {
        "text": event_name,  
        "dates": f"{event_datetime}/{event_datetime}",  
        "details": f"Join me at {event_name} at {location}.",  
        "location": location,  
        "sf": "true",
        "output": "xml"
    }

    return f"{base_url}&{urllib.parse.urlencode(params)}"

### --- HANDLING FRIEND RESPONSES --- ###
def handle_friend_response(user, message, session_dict):    
    """Handles a friend's response to the invitation."""
    user_id = message.split("_")[-1]  
    response_type = "accepted" if message.startswith("yes_response_") else "declined"

    if response_type == "accepted":
        event_date = session_dict[user]["res_date"]
        event_time = session_dict[user]["res_time"]
        top_choice = session_dict[user]["top_choice"]

        name_match = re.search(r'\*\*(.*?)\*\*', top_choice)
        location_match = re.search(r'in (.*)', top_choice)

        if name_match and location_match:
            event_name = name_match.group(1).strip()  
            location = location_match.group(1).strip()  

            # Generate Google Calendar event link
            calendar_link = generate_google_calendar_link(event_name, location, event_date, event_time)

            # Send Google Calendar invite via Rocket.Chat
            RC_message(user_id, f"📅 Your invitation to **{event_name}** at **{event_time}** on **{event_date}** is ready! Click below to add to Google Calendar:\n🔗 [**Add Event**]({calendar_link})")

### --- SENDING MESSAGE TO ROCKET.CHAT --- ###
def RC_message(user_id, message):
    """Sends a message to a user on Rocket.Chat."""
    headers = {
        "Content-Type": "application/json",
        "X-Auth-Token": ROCKETCHAT_AUTH_TOKEN,
        "X-User-Id": ROCKETCHAT_USER_ID
    }

    payload = {
        "channel": f"@{user_id}",
        "text": message
    }

    response = requests.post(ROCKETCHAT_API_URL, json=payload, headers=headers)
    print(response.status_code, response.json())

### --- FLASK ROUTE TO HANDLE USER REQUESTS --- ###
@app.route('/query', methods=['POST'])
def main():
    """Handles incoming user queries and session management dynamically."""
    
    data = request.get_json()
    print("🔍 Incoming request data:", data)  

    message = data.get("text", "").strip().lower()  
    user = data.get("user_name", "Unknown")

    # Load sessions
    session_dict = load_sessions()

    # Restart session when user says "hi" or "restart"
    restart_phrases = ["hi", "hello", "restart", "start over", "new session", "begin again", "reset"]

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

    # Process restaurant assistant LLM
    else:
        response = restaurant_assistant_llm(message, user, session_dict)
        RC_message(user, response["text"])

    save_sessions(session_dict)
    return jsonify({})

### --- LLM CHATBOT HANDLER --- ###
def restaurant_assistant_llm(message, user, session_dict):
    """Handles the chatbot logic and restaurant recommendations."""
    sid = session_dict[user]["session_id"]
    
    response = generate(
        model="4o-mini",
        system="...",
        query=message,
        temperature=0.7,
        lastk=10,
        session_id=sid,
        rag_usage=False
    )
    
    response_text = response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?").strip() if isinstance(response, dict) else response.strip()

    response_obj = {"text": response_text}
    return response_obj

### --- RUN THE FLASK APP --- ###
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)



