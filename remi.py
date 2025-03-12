from flask import Flask, request, jsonify
import os
import json
import re
import urllib.parse
import requests

app = Flask(__name__)

# Load API Key from .env file
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
    """
    Generates a Google Calendar event link.
    """
    base_url = "https://calendar.google.com/calendar/render?action=TEMPLATE"

    # Convert time to Google Calendar format (YYYYMMDDTHHMMSSZ)
    formatted_date = event_date.replace("-", "")  # Remove dashes
    formatted_time = event_time.replace(":", "") + "00Z"  # Convert HH:MM to HHMMSSZ
    event_datetime = f"{formatted_date}T{formatted_time}"  # Final format

    params = {
        "text": event_name,  # Event title
        "dates": f"{event_datetime}/{event_datetime}",  # Event duration (start = end time)
        "details": f"Join me at {event_name} at {location}.",  # Description
        "location": location,  # Event location
        "sf": "true",
        "output": "xml"
    }

    return f"{base_url}&{urllib.parse.urlencode(params)}"

### --- HANDLING FRIEND RESPONSES --- ###
def handle_friend_response(user, message, session_dict):    
    """Handles a friend's response to the invitation."""
    user_id = message.split("_")[-1]  # Extract user ID
    response_type = "accepted" if message.startswith("yes_response_") else "declined"

    print(f"📩 User {user_id} has {response_type} the invitation.")

    response_obj = {"text": ""}

    if response_type == "accepted":
        response_obj["text"] = f"🎉 Great! {user_id} has accepted the invitation!" 
        
        # Retrieve event details from the session
        event_date = session_dict[user]["res_date"]
        event_time = session_dict[user]["res_time"]
        top_choice = session_dict[user]["top_choice"]

        # Extract restaurant name and location
        name_match = re.search(r'\*\*(.*?)\*\*', top_choice)
        location_match = re.search(r'in (.*)', top_choice)

        if name_match and location_match:
            event_name = name_match.group(1).strip()  # Restaurant name
            location = location_match.group(1).strip()  # Address

            # Generate Google Calendar event link
            calendar_link = generate_google_calendar_link(event_name, location, event_date, event_time)

            # Send Google Calendar invite via Rocket.Chat
            RC_message(user_id, f"📅 Your invitation to **{event_name}** at **{event_time}** on **{event_date}** is ready! Click below to add to Google Calendar:\n🔗 [**Add Event**]({calendar_link})")

            # Confirm message was sent
            response_obj["text"] += f"\n✅ Google Calendar invite sent to {user_id}."
    else:
        response_obj["text"] = f"😢 {user_id} has declined the invitation."

    return response_obj

### --- SENDING MESSAGE TO ROCKET.CHAT --- ###
def RC_message(user_id, message):
    """Sends a message to a user on Rocket.Chat."""
    url = "https://chat.genaiconnect.net/api/v1/chat.postMessage"  # Replace with your Rocket.Chat server

    headers = {
        "Content-Type": "application/json",
        "X-Auth-Token": "NwEWNpYAyj0VjnGIWDqzLG_8JGUN4l2J3-4mQaZm_pF",
        "X-User-Id": "vuWQsF6j36wS6qxmf"
    }

    payload = {
        "channel": f"@{user_id}",  # Rocket.Chat username
        "text": message
    }

    response = requests.post(url, json=payload, headers=headers)

    print(response.status_code)
    print(response.json())
    return response.json()

### --- FLASK ROUTE TO HANDLE USER REQUESTS --- ###
@app.route('/', methods=['POST'])
def main():
    """Handles incoming user queries and session management."""
    
    # Print the full request payload for debugging
    data = request.get_json()
    print("🔍 Incoming request data:", data)  # Debug log
    
    message = data.get("text", "").strip()
    user = data.get("user_name", "Unknown")

    # Load sessions
    session_dict = load_sessions()

    # Initialize session if user is new
    if user not in session_dict:
        session_dict[user] = {
            "session_id": f"{user}-session",
            "api_results": [],
            "top_choice": "",
            "current_search": {},
            "res_date": "",
            "res_time": ""
        }
        save_sessions(session_dict)

    # Handle different message types
    if message.startswith("yes_response_") or message.startswith("no_response_"):
        response = handle_friend_response(user, message, session_dict)
    else:
        response = {"text": f"⚠ Unknown request format: {message}"}

    # Save session changes
    save_sessions(session_dict)
    return jsonify(response)
### --- RUN THE FLASK APP --- ###
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)

