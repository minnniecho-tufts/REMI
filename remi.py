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

### --- GOOGLE CALENDAR LINK GENERATION --- ###
def generate_google_calendar_link(event_name, location, event_date, event_time):
    """Generates a Google Calendar event link."""
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

    print(f"📩 User {user_id} has {response_type} the invitation.")

    if response_type == "accepted":
        # Retrieve event details
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
            RC_message(user_id, f"📅 Your invitation to **{event_name}** at **{event_time}** on **{event_date}** is ready!\n🔗 [**Add to Google Calendar**]({calendar_link})")

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

### --- FIX `404` ERROR: HANDLE ROOT REQUESTS --- ###
@app.route('/', methods=['POST'])
def handle_root_post():
    """Redirects misplaced POST requests to the correct /query endpoint."""
    return jsonify({"error": "Invalid endpoint. Use /query instead."}), 400

@app.route('/', methods=['GET'])
def health_check():
    """Health check route for Koyeb deployment."""
    return "Flask app is running!", 200

### --- FLASK ROUTE TO HANDLE USER REQUESTS --- ###
@app.route('/query', methods=['POST'])
def main():
    """Handles user messages and session management dynamically."""
    
    # Print the full request payload for debugging
    data = request.get_json()
    print("🔍 Incoming request data:", data)  

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

    # Handle reservation details
    if "Reservation date:" in response_text:
        match_date = re.search(r'Reservation date:\s*(\w+\s\d{1,2}(?:st|nd|rd|th)?)', response_text)
        if match_date:
            reservation_date_str = match_date.group(1)
            session_dict[user]["res_date"] = datetime.strptime(reservation_date_str + " 2025", "%B %d %Y").strftime("%Y-%m-%d")
            save_sessions(session_dict)

    if "Reservation time:" in response_text:
        match_time = re.search(r'Reservation time:\s*(\d{1,2} (AM|PM))', response_text)
        if match_time:
            reservation_time_str = match_time.group(1)
            session_dict[user]["res_time"] = datetime.strptime(reservation_time_str, "%I %p").strftime("%H:%M")
            save_sessions(session_dict)

    return {"text": response_text}

### --- RUN THE FLASK APP --- ###
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)




