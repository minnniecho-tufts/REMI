import os
import requests
from flask import Flask, request, jsonify
from llmproxy import generate
# from dotenv import load_dotenv  
import re

app = Flask(__name__)

# Load API Key from .env file
# load_dotenv()
API_KEY = os.getenv("YELP_API_KEY")   
YELP_API_URL = "https://api.yelp.com/v3/businesses/search"
session_dict = {}


def restaurant_assistant_llm(message, sid):
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
        lastk=20,
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
            metric_radius = int(int(match.group(1)) * 1609.34)
            user_session["preferences"]["radius"] = str(metric_radius)  # Store as string (convert if needed)
        else:
            user_session["preferences"]["radius"] = None  # Handle cases where no number is found

    # Create the response object with the basic text
    response_obj = {
        "text": response_text
    }

    # Handle different scenarios and update the response text or add attachments as needed
    if "now searching" in response_text.lower():
        response_obj["text"] = search_restaurants(user_session)
        print("in now searching: ", response_obj["text"])


        # Note: I was trying to attach a button to the response so the user could pick which 
        # restaurant they wanted or have the AI pick the restaurant for them, like a "Surprise me"
        # feature, but this wasn't working. I think it would be cool if we could get the restaurant
        # from here using this logic and pass the restaurant info to the AI agent, so maybe see
        # if you can get this to work?

        response_obj["attachments"] = [
            {
                "title": "User Options",
                "text": "Do you have a top choice, or would you like us to pick?",
                "actions": [
                    {
                        "type": "button",
                        "text": "✅ I have my top choice",
                        "msg": "yes_clicked",
                        "msg_in_chat_window": True,
                        "msg_processing_type": "sendMessage",
                        "button_id": "yes_button"
                    },
                    {
                        "type": "button",
                        "text": "🤔 Surprise me!",
                        "msg": "no_clicked",
                        "msg_in_chat_window": True,
                        "msg_processing_type": "sendMessage"
                    }
                ]
            }
        ]
    # elif message == "yes_clicked":
    #     response_obj["text"] = "Great! To select a restaurant, type 'Top choice: ' followed by its number from the list. For example, if you want the first choice in the list, type 'Top choice: 1'."
    # elif message == "no_clicked":
    #     our_pick = search_restaurants(user_session, -1)
    #     response_obj["text"] = f"Great! Let's go with {our_pick}."
    #     agent_contact(our_pick, sid)  # send the agent our restaurant choice
    # elif "top choice" in message.lower():
    #     ascii_text = re.sub(r"[^\x00-\x7F]+", "", message.lower())  # Remove non-ASCII characters
    #     match = re.search(r"top choice[:*\s]*(\d+)", ascii_text)  # Extract only the number
    #     if match:
    #         index = int(match.group(1))
    #         their_pick = search_restaurants(user_session, index)
    #         response_obj["text"] = f"Great choice! You've selected {their_pick}."
    #         agent_contact(their_pick, sid)  # send the agent their restaurant choice


    print("AFTER updated:")
    print("current details collected: ", user_session['preferences'])

    return response_obj


def search_restaurants(user_session, index=0):
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
        "limit": 5,  # Fetch top five restaurants
        "sort_by": "best_match"
    }

    response = requests.get(YELP_API_URL, headers=headers, params=params)

    res = [f"Here are some budget-friendly suggestions we found for {cuisine} cuisine within a {int(float(radius) * 0.000621371)}-mile radius of {location}!\n"]
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

            if index > 0 and index < len(res):  # return a specific restaurant in the result list
                return res[index]
            elif index == -1:                   # return a random restaurant in the list
                import random
                return res[random.randint(1, len(res))]
            
            return "".join(res)
        else:
            return "⚠️ Sorry, I couldn't find any matching restaurants. Try adjusting your preferences!"
    
    return f"⚠️ Yelp API request failed. Error {response.status_code}: {response.text}"


# COPIED FROM example_agent_tool
# TODO: update system instructions to instruct agent to only contact friends when the user has
# provided the rocket chat IDs of their friends
def agent_contact(message, sid):
    print("in the agent!")

    system = """
    You are an AI agent designed contact the main users friend when they give their rocket chat ID of their friend. 
    In addition to your own intelligence, you are given access to a set of tools.
    Think step-by-step, breaking down the task into a sequence small steps.

    The name of the provided tools and their parameters are given below.
    The output of tool execution will be shared with you so you can decide your next steps.

    GO THROUGH THESE STEPS IN ORDER:
    - FIRST: ask the user to enter their friends rocket chat ID store that in variable user_id
    - SECOND : Generate an invitation message to send to the friend for the meal store in variable  message
    - THIRD: Use the RC_message tool to send a message.

    ### PROVIDED TOOLS INFORMATION ###
    ##1. Tool to send an email
    Name: RC_message
    Parameters: user_id , message 
    example usage: RC_message(user_id, message)
    
    
    """

    response = generate(model = '4o-mini',
        system = system,
        query = message,
        temperature=0.7,
        lastk=10,
        session_id=sid,
        rag_usage = False)
    
    try:
        return response['response']
    except Exception as e:
        print(f"Error occured with parsing output: {response}")
        raise e
    return 
    

def RC_message(user_id, message):
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

@app.route('/query', methods=['POST'])
def main():
    """Handles user messages and decides what to do."""
    data = request.get_json()
    message = data.get("text", "").strip()
    user = data.get("user_name", "Unknown")
    
    print("current session dict", session_dict)
    print("current user", user)

    if user not in session_dict:
        print("new user, ", user)
        # Single user session
        session_dict[user] = (f"{user}-session")
    sid = session_dict[user]
    print("session id is", sid)

    # return jsonify({"text": restaurant_assistant_llm(message, sid)})
    
    # Get response from assistant
    response = restaurant_assistant_llm(message, sid)
    return jsonify(response)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)




