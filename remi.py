import os
import json
import requests
from flask import Flask, request, jsonify
from llmproxy import generate
import re

app = Flask(__name__)

# Yelp API Config
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
                return {}  # If file is corrupted, return an empty dict
    return {}

def save_sessions(session_dict):
    """Save sessions to a JSON file."""
    with open(SESSION_FILE, "w") as file:
        json.dump(session_dict, file, indent=4)

# Load sessions when the app starts
session_dict = load_sessions()


### --- MAIN BOT FUNCTION --- ###
def restaurant_assistant_llm(message, sid, user):
    """Handles the full conversation and recommends a restaurant."""
    
    response = generate(
        model="4o-mini",
        system="""
            You are a friendly restaurant assistant named REMI 🍽️. Your job is to help the user find a place to eat.
            
            - The first message should be:  
              **FEEEELING HUNGRY?** REMI 🧑🏻‍🍳 IS HERE TO HELP YOU!  
              Tell us what you're looking for, and we'll help you **find and book a restaurant!**  
              What type of food are you in the mood for?  
            
            - FIRST: Ask the user for their **cuisine preference** in a natural way.
            - SECOND: Ask the user for their **budget** in a natural way.
            - THIRD: Ask the user for their **location**.
            - FOURTH: Ask the user what their preferred search radius is (max 20 miles).
            - Make it **fun** and use **emojis**!
            - Confirm collected info with:
              ```
              Cuisine: [cuisine]
              Location: [location]
              Budget: [budget (1-4)]
              Search Radius: [radius in meters]
              ```
              Then say, "Thank you! Now searching..."
        """,
        query=message,
        temperature=0.7,
        lastk=5,
        session_id=sid,
        rag_usage=False
    )

    response_text = response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?").strip()

    response_obj = {"text": response_text}

    if "now searching" in response_text.lower():
        api_results = search_restaurants(user)
        response_obj["text"] = api_results[0]

        # Update user's top choice in session_dict and save to file
        session_dict[user]["top_choice"] = api_results[1][1]  # Store the selected restaurant
        save_sessions(session_dict)  # Persist changes

        print("Got top choice from API:", session_dict[user]["top_choice"])

        response_obj["attachments"] = [
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
    
    if message == "yes_clicked":
        # Invite friends using the stored top_choice
        agent_response = agent_contact(sid, session_dict[user]["top_choice"])
        response_obj["text"] = agent_response
    elif message == "no_clicked":
        # Proceed with booking the stored top_choice
        response_obj["text"] = "Table for one it is!"
        booking()

    return response_obj


### --- YELP API SEARCH FUNCTION --- ###
def search_restaurants(user):
    """Uses Yelp API to find a restaurant based on stored user preferences."""
    print('In search restaurants function')

    user_session = session_dict[user]  # Retrieve user's stored preferences
    cuisine = user_session.get("cuisine", "")
    budget = user_session.get("budget", "")
    location = user_session.get("location", "")
    radius = user_session.get("radius", "")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "accept": "application/json"
    }
    
    params = {
        "term": cuisine,
        "location": location,
        "price": budget,  
        "radius": radius,
        "limit": 1,  # Get only the top result
        "sort_by": "best_match"
    }

    response = requests.get(YELP_API_URL, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        if "businesses" in data and data["businesses"]:
            restaurant = data["businesses"][0]
            name = restaurant["name"]
            address = ", ".join(restaurant["location"]["display_address"])
            rating = restaurant["rating"]

            result_text = f"🍽️ **{name}** ({rating}⭐) at {address}."
            print(f"Found restaurant: {result_text}")
            return [result_text, ["", result_text]]  # Second element for top choice update
    
    return ["⚠️ Sorry, I couldn't find any matching restaurants. Try adjusting your preferences!", ["", ""]]


### --- AGENT CONTACT FUNCTION --- ###
def agent_contact(sid, top_choice):
    print(f"Selected restaurant: {top_choice}")

    system = f"""
    You are an AI assistant helping users invite friends to a restaurant reservation. The user has chosen **{top_choice}**.

    GO THROUGH THESE STEPS:
    1️⃣ **Ask the user for their friend's Rocket.Chat ID** (store it in `user_id`).
    2️⃣ **Ask the user to write a short invitation message** for their friend (store it in `message`).
    3️⃣ **Once both details are collected, display them in the following format:**
    
        ✅ **Friend's Rocket.Chat ID:** [user_id]  
        ✅ **Invitation Message:** [message]  
        
        📩 *Thank you! Now contacting your friend...*

    4️⃣ **Then, send the message using the Rocket.Chat messaging tool.**
    """

    response = generate(
        model='4o-mini',
        system=system,
        query=f"The user has chosen {top_choice}. Start the process.",
        temperature=0.7,
        lastk=10,
        session_id=sid,
        rag_usage=False
    )
    
    return response.get("response", "⚠️ An error occurred while processing your request.")


### --- ROCKET.CHAT MESSAGE FUNCTION --- ###
def RC_message(user_id, message):
    url = "https://chat.genaiconnect.net/api/v1/chat.postMessage"

    headers = {
        "Content-Type": "application/json",
        "X-Auth-Token": "NwEWNpYAyj0VjnGIWDqzLG_8JGUN4l2J3-4mQaZm_pF",
        "X-User-Id": "vuWQsF6j36wS6qxmf"
    }

    payload = {
        "channel": user_id,
        "text": message
    }

    response = requests.post(url, json=payload, headers=headers)
    print(response.status_code, response.json())


### --- FLASK ROUTE TO HANDLE USER REQUESTS --- ###
@app.route('/query', methods=['POST'])
def main():
    global session_dict

    data = request.get_json()
    message = data.get("text", "").strip()
    user = data.get("user_name", "Unknown")

    if user not in session_dict:
        session_dict[user] = {"session_id": f"{user}-session", "top_choice": ""}
        save_sessions(session_dict)

    sid = session_dict[user]["session_id"]

    response = restaurant_assistant_llm(message, sid, user)
    return jsonify(response)


### --- RUN THE FLASK APP --- ###
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)