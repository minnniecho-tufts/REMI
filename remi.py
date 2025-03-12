from flask import send_file, Flask, request, jsonify
from datetime import datetime
import os
import json
import requests
import re
from urllib.parse import quote

app = Flask(__name__)

# Load API Key from .env file
API_KEY = os.getenv("YELP_API_KEY")
YELP_API_URL = "https://api.yelp.com/v3/businesses/search"

# JSON file to store user sessions
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


### --- RESTAURANT SEARCH FUNCTION --- ###
def search_restaurants(user_session):
    cuisine = user_session["preferences"]["cuisine"]
    budget = user_session["preferences"]["budget"]
    location = user_session["preferences"]["location"]
    radius = user_session["preferences"]["radius"]

    headers = {"Authorization": f"Bearer {API_KEY}", "accept": "application/json"}

    try:
        radius_val = round(int(radius) * 1609.34) if radius else 20000
        if radius_val > 40000:
            radius_val = 40000
    except (ValueError, TypeError):
        radius_val = 20000

    params = {
        "term": cuisine,
        "location": location,
        "price": budget,
        "radius": radius_val,
        "limit": 5,
        "sort_by": "best_match",
    }

    response = requests.get(YELP_API_URL, headers=headers, params=params)

    res = [f"Here are some restaurants for {cuisine} cuisine in {location} within {radius} miles:\n"]
    if response.status_code == 200:
        data = response.json()
        if "businesses" in data and data["businesses"]:
            for i, restaurant in enumerate(data["businesses"], 1):
                name = restaurant["name"]
                address = ", ".join(restaurant["location"]["display_address"])
                rating = restaurant["rating"]
                res.append(f"{i}. **{name}** ({rating}⭐) in {address}\n")

            return ["".join(res), res]
        else:
            return ["⚠️ No matching restaurants found. Try adjusting your search!", []]

    return [f"⚠️ Yelp API error {response.status_code}: {response.text}", []]


### --- GOOGLE CALENDAR INVITE FUNCTION --- ###
def RC_message(user_id, message):
    """Generate a Google Calendar invite link instead of sending a Rocket.Chat message."""

    # Extract reservation details
    event_date = session_dict[user]["res_date"]
    event_time = session_dict[user]["res_time"]
    top_choice = session_dict[user]["top_choice"]

    # Parse restaurant details
    name_match = re.search(r'\*\*(.*?)\*\*', top_choice)
    location_match = re.search(r'in (.*)', top_choice)

    event_name = name_match.group(1).strip() if name_match else "Dinner Reservation"
    location = location_match.group(1).strip() if location_match else "TBD"

    # Format event time for Google Calendar (assumes reservation time is in HH:MM format)
    start_time = f"{event_date}T{event_time}:00"
    end_time = f"{event_date}T{str(int(event_time[:2]) + 1)}:{event_time[3:]}:00"  # Adds 1 hour

    # Construct Google Calendar event URL
    calendar_url = f"https://calendar.google.com/calendar/r/eventedit?text={quote(event_name)}&dates={start_time.replace(':', '')}/{end_time.replace(':', '')}&location={quote(location)}&details={quote(message)}"

    # Return response with the Google Calendar link
    response_obj = {
        "text": f"📅 Click here to add your reservation to Google Calendar: [Add to Calendar]({calendar_url})"
    }

    print(f"📅 Google Calendar Invite URL: {calendar_url}")
    return response_obj


### --- MAIN BOT FUNCTION --- ###
@app.route("/", methods=["POST"])
def main():
    """Handles user messages and manages session storage."""
    data = request.get_json()
    message = data.get("text", "").strip()
    user = data.get("user_name", "Unknown")

    # Load sessions
    global session_dict
    session_dict = load_sessions()

    # Start a new session if needed
    if user not in session_dict:
        session_dict[user] = {
            "session_id": f"{user}-session",
            "api_results": [],
            "top_choice": "",
            "current_search": {},
            "res_date": "",
            "res_time": "",
        }
        save_sessions(session_dict)

    # Process "yes" or "no" responses
    if message.startswith("yes_response_") or message.startswith("no_response_"):
        response = handle_friend_response(user, message, session_dict)

    # Otherwise, process general messages
    else:
        response = restaurant_assistant_llm(message, user, session_dict)

    save_sessions(session_dict)
    return jsonify(response)


### --- HANDLE FRIEND RESPONSE --- ###
def handle_friend_response(user, message, session_dict):
    """Handles a friend's response to an invite (accept or decline)."""
    user_id = message.split("_")[-1]
    response_type = "accepted" if message.startswith("yes_response_") else "declined"

    response_obj = {"text": ""}

    if response_type == "accepted":
        response_obj["text"] = f"🎉 {user_id} has accepted the invitation!"

        # Generate Google Calendar invite
        response_obj["text"] += RC_message(user, "Let's go for dinner!")["text"]
    else:
        response_obj["text"] = f"😢 {user_id} has declined the invitation."

    return response_obj


### --- RESTAURANT RECOMMENDATION FUNCTION --- ###
def restaurant_assistant_llm(message, user, session_dict):
    """Handles user conversation and recommends a restaurant."""
    
    # Simulating response for demonstration purposes
    response_obj = {"text": "Searching for restaurants... 🍽️"}

    # If user selects a top choice
    if "top choice" in message.lower():
        match = re.search(r"top choice[:\s]*(\d+)", message.lower())
        if match:
            index = int(match.group(1).strip())

            if 1 <= index < len(session_dict[user]["api_results"]):
                session_dict[user]["top_choice"] = session_dict[user]["api_results"][index]
                save_sessions(session_dict)
                response_obj["text"] = f"Great! Booking a table at {session_dict[user]['top_choice']}."
    
    return response_obj


### --- FLASK APP RUNNER --- ###
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)







