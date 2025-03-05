import os
import json
import requests
from flask import Flask, request, jsonify , Response
from llmproxy import generate
import re

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
                return {}  # If file is corrupted, return an empty dict
    return {}

def save_sessions(session_dict):
    """Save sessions to a JSON file."""
    with open(SESSION_FILE, "w") as file:
        json.dump(session_dict, file, indent=4)


# Load sessions when the app starts
session_dict = load_sessions()


### --- MAIN BOT FUNCTION --- ###
def restaurant_assistant_llm(message, user):
    """Handles the full conversation and recommends a restaurant."""
    sid = session_dict[user]["session_id"]
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
               - Store the **budget as a number (1-4)** according to this scale:  
              "cheap": "1", "mid-range": "2", "expensive": "3", "fine dining": "4"
            - THIRD:  Ask the user for their **location** in a natural way (acceptable inputs include city, state, and zip code).
            - FOURTH: Ask the user what their preferred search radius is. The search radius cannot be greater than 20 miles.
            - Put a lot of **emojis** and be **fun and quirky**.
            - Ask the user for the **occasion** to make it more engaging.
            - At the end, after the user has provided all four parameters of cuisine, budget, location, AND search radius, 
            respond with the following in a bulleted list format:
                "Cuisine noted: [cuisine]\nLocation noted: [location]\nBudget noted: [budget (1-4)]\nSearch radius noted: [radius (in meters)]"
            and then say, "Thank you! Now searching..."
        """,

        query=message,
        temperature=0.7,
        lastk=5,
        session_id=sid,
        rag_usage=False
    )
    response_text = response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?").strip()

    # Initialize an object for user preferences
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

    if "Budget noted:" in response_text:
        ascii_text = re.sub(r"[^\x00-\x7F]+", "", response_text)  # Remove non-ASCII characters
        match = re.search(r"Budget noted[:*\s]*(\d+)", ascii_text)  # Extract only the number
        if match:
            user_session["preferences"]["budget"] = match.group(1)  # Store as string (convert if needed)
        else:
            user_session["preferences"]["budget"] = None  # Handle cases where no number is found
    
    if "Location noted:" in response_text:
        ascii_text = re.sub(r"[^\x00-\x7F]+", "", response_text)  # Remove non-ASCII characters
        match = re.search(r"Location noted[:*\s]*(\S.*)", ascii_text)  # Capture actual text after "*Location noted:*"
        if match:
            user_session["preferences"]["location"] = match.group(1).strip()  # Remove extra spaces
    
    if "Search radius noted:" in response_text:
        ascii_text = re.sub(r"[^\x00-\x7F]+", "", response_text)  # Remove non-ASCII characters
        match = re.search(r"Search radius noted[:*\s]*(\d+)", ascii_text)  # Extract only the number
        if match:
            print("miles", int(match.group(1)))
            metric_radius = round(int(match.group(1)) * 1609.34)
            user_session["preferences"]["radius"] = str(metric_radius)  # Store as string (convert if needed)
        else:
            user_session["preferences"]["radius"] = None  # Handle cases where no number is found

    # Create the response object with the basic text
    response_obj = {
        "text": response_text
    }

    # Handle different scenarios and update the response text or add attachments as needed
    if "now searching" in response_text.lower():
        api_results = search_restaurants(user_session)
        response_obj["text"] = api_results[0]
        res = api_results[1]

        # Update user's top choice in session_dict and save to file
        if len(res) > 1:
            session_dict[user]["top_choice"] = res[1]  # Store the top restaurant
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
        while True:
            print("IN WHILE")
            agent_response = agent_contact(user)

            if isinstance(agent_response, Response):  
                agent_response = agent_response.get_json()

            response_obj["text"] = agent_response.get("agent_response", "⚠️ No response received from agent.")

            if response_obj["text"] == "$$EXIT$$":
                break  # Stop the loop safely

        # while response_obj["text"] != "$$EXIT$$":
        #     agent_response = agent_contact(user) 

        #     # If the response is a Flask Response object, extract its JSON content
        #     if isinstance(agent_response, Response):  
        #         agent_response = agent_response.get_json()  # Extract JSON data

        #     # Ensure we assign only the response text to the front-end
        #     response_obj["text"] = agent_response.get("agent_response", "⚠️ No response received from agent.")

        
    elif message == "no_clicked":
        # send the agent our restaurant choice
        response_obj["text"] = "Table for one it is!"
        booking()


    print("current details collected: ", user_session['preferences'])

    return response_obj



def search_restaurants(user_session):
    print('In search restaurants function')
    # """Uses Yelp API to find a restaurant based on user preferences."""
    
    cuisine = user_session["preferences"]["cuisine"]
    budget = user_session["preferences"]["budget"]
    location = user_session["preferences"]["location"]
    radius = user_session["preferences"]["radius"]

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "accept": "application/json"
    }
    
    params = {
        "term": cuisine,
        "location": location,
        "price": budget,  # Yelp API uses 1 (cheap) to 4 (expensive)
        "radius": radius,
        "limit": 1,  # top
        "sort_by": "best_match"
    }

    response = requests.get(YELP_API_URL, headers=headers, params=params)

    res = [f"Here is a budget-friendly suggestion we found for {cuisine} cuisine within a {round(float(radius) * 0.000621371)}-mile radius of {location}!\n"]
    if response.status_code == 200:
        data = response.json()
        if "businesses" in data and data["businesses"]:
            for i in range(len(data["businesses"])):
                restaurant = data["businesses"][i]
                name = restaurant["name"]
                address = ", ".join(restaurant["location"]["display_address"])
                rating = restaurant["rating"]
                print(f"🍽️ Found **{name}** ({rating}⭐) in {address}")
                res.append(f"{i+1}. **{name}** ({rating}⭐) in {address}\n")
            
            return ["".join(res), res]
        else:
            return "⚠️ Sorry, I couldn't find any matching restaurants. Try adjusting your preferences!"
    
    return f"⚠️ Yelp API request failed. Error {response.status_code}: {response.text}"


# COPIED FROM example_agent_tool
# TODO: update system instructions to instruct agent to only contact friends when the user has
# provided the rocket chat IDs of their friends
def agent_contact(user):
    print("iN AGENT CONTACT")
    # # Ensure user session exists
    if user not in session_dict:
        print("if user not")
        # return jsonify({"error": "⚠️ No active session found for this user."})

    sid = session_dict[user]["session_id"]
    top_choice = session_dict[user].get("top_choice", "N/A")  # Ensure it exists

    system = f"""
    You are an AI agent helping users invite friends to a restaurant reservation. 
    The user has chosen **{top_choice}** as their restaurant.

    GO THROUGH THESE STEPS:
    1. Ask the user for a **date and time** for their reservation.
    2. Ask the user for their **friend’s Rocket.Chat ID**.
    3. Generate an **invitation message** for the friend.
    4. Once both details are collected, format them like this:
    
        ✅ **Friend's Rocket.Chat ID:** [user_id]  
        ✅ **Invitation Message:** [message]  
        
        📩 *Thank you! Now contacting your friend...*

    5. **Once all details are collected, return:**  
       `"$$EXIT$$"`
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

    agent_response = response.get('response', "⚠️ Sorry, something went wrong while generating the invitation.")
    match_message, match_user_id = "", ""
    
    # Extract user ID and message using regex
    if "Friend's Rocket.Chat ID:" in agent_response:
        match_user_id = re.search(r"Friend's Rocket.Chat ID: (.+)", agent_response)
        print("match_user_id" + str(match_user_id))
    
    if "Invitation Message:" in agent_response:
        match_message = re.search(r"Invitation Message: (.+)", agent_response)
        print("match_message:" + str(match_message))
    


    if match_user_id and match_message:
        print("in IF STATEMENT")
        # print("match_message:" + str(match_message))
        # print("match_user_id" + str(match_user_id))
        user_id = match_user_id.group(1).strip()
        message_text = match_message.group(1).strip()

        # Send the message via Rocket.Chat and get a serializable response
        rocket_chat_response = RC_message(user_id, message_text)

        return jsonify({
            "agent_response": agent_response,
            "status": "Message Sent",
            "rocket_chat_response": rocket_chat_response  # This is now a dictionary
        })

    return jsonify({
        "agent_response": agent_response,
        "status": "error",
        "message": "⚠️ Missing required information. Please try again."
    })


   
    

def RC_message(user_id, message):
    print('in RC MESSAGE')
    url = "https://chat.genaiconnect.net/api/v1/chat.postMessage" #URL of RocketChat server, keep the same

# Headers with authentication tokens
    headers = {
        "Content-Type": "application/json",
        "X-Auth-Token": "NwEWNpYAyj0VjnGIWDqzLG_8JGUN4l2J3-4mQaZm_pF",
        "X-User-Id": "vuWQsF6j36wS6qxmf"
    }

    # Payload (data to be sent)
    payload = {
        "channel": user_id, #Change this to your desired user, for any user it should start with @ then the username
        "text": message #This where you add your message to the user
    }

    # Sending the POST request
    response = requests.post(url, json=payload, headers=headers)

    # Print response status and content
    print(response.status_code)
    print(response.json())


def booking():
    return jsonify({"text": "BOOKING NOW..."})


### --- FLASK ROUTE TO HANDLE USER REQUESTS --- ###
@app.route('/query', methods=['POST'])
def main():
    """Handles user messages and manages session storage."""
    global session_dict

    data = request.get_json()
    message = data.get("text", "").strip()
    user = data.get("user_name", "Unknown")

    print("Current session dict:", session_dict)
    print("Current user:", user)

    # Load user session if it exists, otherwise create a new one
    if user not in session_dict:
        print("new user", user)
        session_dict[user] = {"session_id": f"{user}-session", "top_choice": ""}
        save_sessions(session_dict)

    sid = session_dict[user]["session_id"]
    print("Session ID:", sid)

    # Get response from assistant
    response = restaurant_assistant_llm(message, user)
    return jsonify(response)


### --- RUN THE FLASK APP --- ###
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
