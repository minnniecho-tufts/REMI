
from flask import send_file
from datetime import datetime
import os
import json
import requests
from flask import Flask, request, jsonify, Response
from llmproxy import generate
import re
import urllib.parse

app = Flask(__name__)

# Load API Key from .env file
API_KEY = os.getenv("YELP_API_KEY")   
YELP_API_URL = "https://api.yelp.com/v3/businesses/search"

# JSON file to store user sessions
SESSION_FILE = "session_store.json"

add_friends_button = [
    {
        "title": "User Options",
        "text": "Would you like to add anyone to your reservation?",
        "actions": [
            {
                "type": "button",
                "text": "✅ Add friends",
                "msg": "yes_clicked",
                "msg_in_chat_window": True,
                "msg_processing_type": "sendMessage",
                "button_id": "yes_button"
            },
            {
                "type": "button",
                "text": "❌ No, thank you!",
                "msg": "no_clicked",
                "msg_in_chat_window": True,
                "msg_processing_type": "sendMessage"
            }
        ]
    }
]


### --- SESSION MANAGEMENT FUNCTIONS --- ###
def load_sessions():
    """Load stored sessions from a JSON file."""
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as file:
            try:
                session_data = json.load(file)
                print(f"Loaded session data: {session_data}")
                return session_data
            except json.JSONDecodeError:
                print("Error loading session data, returning empty dict.")
                return {}  # If file is corrupted, return an empty dict
    print("No session file found. Returning empty dictionary.")
    return {}

def save_sessions(session_dict):
    """Save sessions to a JSON file."""
    print(f"Saving session data: {session_dict}")
    with open(SESSION_FILE, "w") as file:
        json.dump(session_dict, file, indent=4)
    print("Session data saved.")


### --- MAIN BOT FUNCTION --- ###
def restaurant_assistant_llm(message, user, session_dict):
    print(f"in res LLM. user input: {message}")
    """Handles the full conversation and recommends a restaurant."""
    sid = session_dict[user]["session_id"]
    
    response = generate(
        model="4o-mini",
        system=f"""
            You are a friendly restaurant assistant named REMI 🍽️. Your job is to help the user find a place to eat.
            You always use a lot of **emojis** and are **fun and quirky** in all of your responses.
            
            - The first message should be:  
              **FEEEELING HUNGRY?** REMI 🧑🏻‍🍳 IS HERE TO HELP YOU!  
              Tell us what you're looking for, and we'll help you **find and book a restaurant!**  
              What type of food are you in the mood for?  
            
            - FIRST: Ask the user for their **cuisine preference** in a natural way.
            - SECOND: Ask the user for their **budget** in a natural way.
               - Store the **budget as a number (1-4)** according to this scale:  
              "cheap": "1", "mid-range": "2", "expensive": "3", "fine dining": "4"
            - THIRD:  Ask the user for their **location** in a natural way (acceptable inputs include city, state, and zip code).
            - FOURTH: Ask the user what their preferred search radius is. The search radius cannot be greater than 20 miles.
            - Ask the user for the **occasion** to make it more engaging.

            - After the user has provided all four parameters of cuisine, budget, location, AND search radius, 
            you must respond with the following in a bulleted list format:
                "Cuisine noted: [cuisine]\nLocation noted: [location]\nBudget noted: [budget (1-4)]\nSearch radius noted: [radius (in meters)]"
            and then say, "Thank you! Now searching..."
            
            - When the user provides a **reservation date and time , in a format similar to this 03/05/2025**, remember these details and respond with the following in a bulleted list format:
                "Reservation time: [time]\nReservation date: [date]\n
            - If the user tags a friend using '@' (e.g., "@john_doe"), generate a friendly **personalized invitation message** including:
                - The **name of the restaurant** from {session_dict[user]["top_choice"]}
                - The **reservation date**
                - The **reservation time**
                - Request for the friend to confirm if they will attend
            - Ask the user to confirm if they'd like to send the message. If they affirm, respond with
            "RC_message(user_id, message)" with the parameters filled in appropriately.
            Example usage: RC_message("@anika.kapoor", "join me for dinner")
        """,

        query=message,
        temperature=0.7,
        lastk=10,
        session_id=sid,
        rag_usage=False
    )
    response_text = response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?").strip() if isinstance(response, dict) else response.strip()

    # Initialize an object for suser preferences
    user_session = {
            "state": "conversation",
            "preferences": {"cuisine": None, "budget": None, "location": None, "radius": None}
    }

    
    # Extract information from LLM response
    if "Cuisine noted:" in response_text:
        ascii_text = re.sub(r"[^\x00-\x7F]+", "", response_text)  # Remove non-ASCII characters
        match = re.search(r"Cuisine noted[:*\s]*(\S.*)", ascii_text)  # Capture actual text after "*Cuisine noted:*"
        if match:
            user_session["preferences"]["cuisine"] = match.group(1).strip()  # Remove extra spaces
            # Store in session for persistence
            if "current_search" not in session_dict[user]:
                session_dict[user]["current_search"] = {}
            session_dict[user]["current_search"]["cuisine"] = match.group(1).strip()

    if "Budget noted:" in response_text:
        ascii_text = re.sub(r"[^\x00-\x7F]+", "", response_text)  # Remove non-ASCII characters
        match = re.search(r"Budget noted[:*\s]*(\d+)", ascii_text)  # Extract only the number
        if match:
            user_session["preferences"]["budget"] = match.group(1)  # Store as string (convert if needed)
            if "current_search" not in session_dict[user]:
                session_dict[user]["current_search"] = {}
            session_dict[user]["current_search"]["budget"] = match.group(1)
        else:
            user_session["preferences"]["budget"] = None  # Handle cases where no number is found
    
    if "Location noted:" in response_text:
        ascii_text = re.sub(r"[^\x00-\x7F]+", "", response_text)  # Remove non-ASCII characters
        match = re.search(r"Location noted[:*\s]*(\S.*)", ascii_text)  # Capture actual text after "*Location noted:*"
        if match:
            user_session["preferences"]["location"] = match.group(1).strip()  # Remove extra spaces
            if "current_search" not in session_dict[user]:
                session_dict[user]["current_search"] = {}
            session_dict[user]["current_search"]["location"] = match.group(1).strip()
    
    if "Search radius noted:" in response_text:
        ascii_text = re.sub(r"[^\x00-\x7F]+", "", response_text)  # Remove non-ASCII characters
        match = re.search(r"Search radius noted[:*\s]*(\d+)", ascii_text)  # Extract only the number
        if match:
            user_session["preferences"]["radius"] = match.group(1)
            if "current_search" not in session_dict[user]:
                session_dict[user]["current_search"] = {}
            session_dict[user]["current_search"]["radius"] = match.group(1)
        else:
            user_session["preferences"]["radius"] = None  # Handle cases where no number is found

    # Create the response object with the basic text
    response_obj = {
        "text": response_text
    }

    # If we already have preferences stored in the session, use those instead
    if "current_search" in session_dict[user]:
        for key in ["cuisine", "budget", "location", "radius"]:
            if session_dict[user]["current_search"].get(key):
                user_session["preferences"][key] = session_dict[user]["current_search"][key]

    # Handle different scenarios and update the response text or add attachments as needed
    if "now searching" in response_text.lower():
        # Clear previous API results before performing a new search
        session_dict[user]["api_results"] = []
        session_dict[user]["top_choice"] = ""
        save_sessions(session_dict)  # Save before the API call
        
        api_results = search_restaurants(user_session)
        response_obj["text"] = api_results[0]

        # Store new results
        session_dict[user]["api_results"] = api_results[1]
        save_sessions(session_dict)  # Persist changes

        if len(session_dict[user]["api_results"]) > 2:
            response_obj["text"] += "\nWhat is your top choice restaurant? Please type 'Top choice: ' followed by the restaurant's number from the list."
            save_sessions(session_dict)
        else: 
            # Update user's top choice in session_dict and save to file
            session_dict[user]["top_choice"] = session_dict[user]["api_results"][1]
            save_sessions(session_dict)  # Persist changes
            response_obj["attachments"] = add_friends_button

    if "top choice" in message.lower():
        match = re.search(r"top choice[:\s]*(\d+)", re.sub(r"[^\x00-\x7F]+", "", message.lower()))
        if match:
            index = int(match.group(1).strip())  # Strip any unexpected spaces

            # Ensure the index is within the range of available results
            if 1 <= index < len(session_dict[user]["api_results"]):
                session_dict[user]["top_choice"] = session_dict[user]["api_results"][index]
                save_sessions(session_dict)  # Persist changes
                print("Got top choice from user:", session_dict[user]["top_choice"])
            else:
                print(f"⚠️ Invalid index: {index} (out of range 1 to {len(session_dict[user]['api_results'])})")
        else:
            print("⚠️ No valid top choice found in message.")

        response_obj["text"] = f"Great! Let's get started on booking you a table at {session_dict[user]['top_choice']}."
        response_obj["attachments"] = add_friends_button
    

    if message == "yes_clicked":
        response_obj["text"] = "Great! Let me know your **reservation date and time** and your friend's **Rocket.Chat ID**, and we can get that invitation ready! 😊✨"
    elif message == "no_clicked":
        # send the agent our restaurant choice
        response_obj["text"] = "Table for one it is! Let me know your **reservation date and time**. 😊✨"


    if "Reservation date:" in response_text:
        match_date = re.search(r'Reservation date:\s*(\w+\s\d{1,2}(?:st|nd|rd|th)?)', response_text)
        if match_date:
            reservation_date_str = match_date.group(1)
            # Convert "March 8th" to "2023-03-08" (add the current year)
            session_dict[user]["res_date"] = datetime.strptime(reservation_date_str + " 2025", "%B %d %Y").strftime("%Y-%m-%d")
            save_sessions(session_dict)
            print("Reservation Date:", session_dict[user]["res_date"])
    
    if "Reservation time:" in response_text:
        match_time = re.search(r'Reservation time:\s*(\d{1,2} (AM|PM))', response_text)
        if match_time:
            reservation_time_str = match_time.group(1)
            # Convert "12 PM" to "12:00" (24-hour format)
            session_dict[user]["res_time"] = datetime.strptime(reservation_time_str, "%I %p").strftime("%H:%M")
            save_sessions(session_dict)
            print("Reservation Time:", session_dict[user]["res_time"])


    tool = extract_tool(response_text)
    if tool:
        print("GOING TO EVALUATE:", tool)
        response = eval(tool)
        print(f"📩 Rocket.Chat API Response: {response}")
        response_obj["text"] = f"📩 Invitation sent on Rocket.Chat!"
    

    save_sessions(session_dict)
    print(str(response_obj))
    return response_obj




# """Uses Yelp API to find a restaurant based on user preferences."""
def search_restaurants(user_session):
    
    cuisine = user_session["preferences"]["cuisine"]
    budget = user_session["preferences"]["budget"]
    location = user_session["preferences"]["location"]
    radius = user_session["preferences"]["radius"]

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "accept": "application/json"
    }
    
    # Ensure radius is valid (Yelp API has a maximum of 40000 meters)
    try:
        radius_val = round(int(radius) * 1609.34) if radius else 20000
        if radius_val > 40000:
            radius_val = 40000
    except (ValueError, TypeError):
        radius_val = 20000
    
    params = {
        "term": cuisine,
        "location": location,
        "price": budget,  # Yelp API uses 1 (cheap) to 4 (expensive)
        "radius": radius_val,
        "limit": 5,  # top
        "sort_by": "best_match"
    }

    print(f"API request params: {params}")
    response = requests.get(YELP_API_URL, headers=headers, params=params)

    res = [f"Here are some budget-friendly suggestions we found for {cuisine} cuisine within a {radius}-mile radius of {location}!\n"]
    if response.status_code == 200:
        data = response.json()
        if "businesses" in data and data["businesses"]:
            for i in range(len(data["businesses"])):
                restaurant = data["businesses"][i]
                name = restaurant["name"]
                address = ", ".join(restaurant["location"]["display_address"])
                rating = restaurant["rating"]
                res.append(f"{i+1}. **{name}** ({rating}⭐) in {address}\n")
            
            return ["".join(res), res]
        else:
            return ["⚠️ Sorry, I couldn't find any matching restaurants. Try adjusting your preferences!", []]
    
    return [f"⚠️ Yelp API request failed. Error {response.status_code}: {response.text}", []]


    

# """Tool to send message to other user on Rocketchat"""
def RC_message(user_id, message):
    print("in RC_message function")
    url = "https://chat.genaiconnect.net/api/v1/chat.postMessage" #URL of RocketChat server, keep the same

# Headers with authentication tokens
    headers = {
        "Content-Type": "application/json",
        "X-Auth-Token": "NwEWNpYAyj0VjnGIWDqzLG_8JGUN4l2J3-4mQaZm_pF",
        "X-User-Id": "vuWQsF6j36wS6qxmf"
    }

    buttons = [
        {
            "type": "button",
            "text": "✅ Yes, I'll be there!",
            "msg": f"yes_response_{user_id}",
            "msg_in_chat_window": True,
            "msg_processing_type": "sendMessage",
            "button_id": "yes_button"
        },
        {
            "type": "button",
            "text": "❌ No, I can't make it.",
            "msg": f"no_response_{user_id}",
            "msg_in_chat_window": True,
            "msg_processing_type": "sendMessage",
            "button_id": "no_button"
        }
    ]

    # Payload (data to be sent)
    payload = {
        "channel": user_id, #Change this to your desired user, for any user it should start with @ then the username
        "text": message, #This where you add your message to the user
        "attachments": [
            {
                "title": "RSVP",
                "text": "Click a button to respond:",
                "actions": buttons  # Add buttons if provided
            }
        ]
    }

    # Sending the POST request
    response = requests.post(url, json=payload, headers=headers)

    # Print response status and content
    print(response.status_code)
    print(response.json())
    return response.json()




# """Handle other user's button response"""
def handle_friend_response(user, message, session_dict):    
    print("friend responded")
    user_id = message.split("_")[-1]
    if message.startswith("yes_response_"):
        event_date = session_dict.get(user, {}).get("res_date", "")
        event_time = session_dict.get(user, {}).get("res_time", "")
        top_choice = session_dict.get(user, {}).get("top_choice", "")
        print("event date: " + str(event_date))
        print("event time: " + str(event_time))
        print("top choice" + str(top_choice))
        
        if not event_date or not event_time or not top_choice:
            return {"text": "❌ Missing event details. Cannot generate calendar invite."}
        
        event_name, location = top_choice.split(" in ") if " in " in top_choice else (top_choice, "Unknown location")
        event_start = f"{event_date.replace('-', '')}T{event_time.replace(':', '')}00Z"
        event_end = f"{event_date.replace('-', '')}T{str(int(event_time[:2]) + 1).zfill(2)}{event_time[2:]}00Z"
        
        calendar_url = (
            "https://calendar.google.com/calendar/render?"
            "action=TEMPLATE&"
            f"text={urllib.parse.quote(event_name.strip())}&"
            f"dates={event_start}/{event_end}&"
            f"details={urllib.parse.quote('Dinner reservation with friends')}&"
            f"location={urllib.parse.quote(location.strip())}"
        )
        return {"text": f"🎉 {user_id} has accepted the invitation! \n📅 [Click here to add to Google Calendar]({calendar_url})"}
    else:
        return {"text": f"😢 {user_id} has declined the invitation."}

# def generate_calendar_invite(event_name, location, event_date, event_time):
#     """Creates a .ics file for the event and returns the filename."""

#     print("date: ", event_date, ", time: ", event_time)

#     event_start = f"{event_date}T{event_time}00"
#     event_end = f"{event_date}T{str(int(event_time) + 100)}00"  # Adds 1 hour

#     ics_content = f"""BEGIN:VCALENDAR
#         VERSION:2.0
#         BEGIN:VEVENT
#         SUMMARY:{event_name}
#         LOCATION:{location}
#         DTSTART:{event_start}
#         DTEND:{event_end}
#         DESCRIPTION:{None}
#         END:VEVENT
#         END:VCALENDAR
#         """

#     filename = f"{event_name.replace(' ', '_')}.ics"
#     filepath = os.path.join("invites", filename)

#     # Save the file
#     os.makedirs("invites", exist_ok=True)
#     with open(filepath, "w") as file:
#         file.write(ics_content)

#     return filename


# @app.route('/download/<filename>', methods=['GET'])
# def download_invite(filename):
#     """Serves the generated .ics calendar file."""
#     return send_file(os.path.join("invites", filename), as_attachment=True)





# """Extracts the tool from text using regex"""
def extract_tool(text):
    import re

    match = re.search(r'RC_message\(.*?"\)', text)
    if match:
        return match.group() 

    return



### --- FLASK ROUTE TO HANDLE USER REQUESTS --- ###
# """Handles user messages and manages session storage."""
@app.route('/query', methods=['POST'])
def main():
    print("starting main exec")
    
    data = request.get_json()
    message = data.get("text", "").strip()
    user = data.get("user_name", "Unknown")

    # Create a unique conversation ID based on time to better separate sessions
    import time

    # Load sessions at the beginning of each request
    session_dict = load_sessions()
    
    print("Current session dict:", session_dict)
    print("Current user:", user)

    # Check if we need to create a new conversation (e.g., if user starts over)
    if "restart" in message.lower() or "start over" in message.lower() or "new search" in message.lower():
        print(f"Starting new conversation for {user}")
        if user in session_dict:
            # Create new session
            session_dict[user]["api_results"] = []
            session_dict[user]["top_choice"] = ""
            session_dict[user]["current_search"] = {}
            save_sessions(session_dict)
            print(f"Created new session for {user}")

    # Initialize user session if it doesn't exist
    if user not in session_dict:
        print("new user", user)
        session_dict[user] = {
            "session_id": f"{user}-session",
            "api_results": [],
            "top_choice": "",
            "current_search": {},
            "res_date": "",
            "res_time": ""
        }
        save_sessions(session_dict)  # Save immediately after creating new session

    # **Check if the message is a button response from friend**
    if message.startswith("yes_response_") or message.startswith("no_response_"):
        print("friend responded")
        response = handle_friend_response(user, message, session_dict)

    # Get response from assistant
    else:
        response = restaurant_assistant_llm(message, user, session_dict)
    
    # Save session data at the end of the request
    save_sessions(session_dict)
    return jsonify(response)


### --- RUN THE FLASK APP --- ###
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)









