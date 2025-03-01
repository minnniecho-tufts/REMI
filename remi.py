
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
            - THIRD:  Ask the user for their **location** in a natural way.
            - Put a lot of **emojis** and be **fun and quirky**.
            - Ask the user for the **occasion** to make it more engaging.
            - At the end, ONLY WHEN the user has provided all three parameters of cuisine, budget, AND location, 
            respond in a list format:
                "Cuisine noted: [cuisine]\nLocation noted: [location]\nBudget noted: [budget (1-4)]"
        """,

        query=message,
        temperature=0.7,
        lastk=50,
        session_id=sid,
        rag_usage=False
    )
    response_text = response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?").strip()

    # Initialize an object for user preferences
    user_session = {
            "state": "conversation",
            "preferences": {"cuisine": None, "budget": None, "location": None}
    }
    
    # Extract information from LLM response
    if "Cuisine noted:" in response_text:
        print('in cuisine')
        ascii_text = re.sub(r"[^\x00-\x7F]+", "", response_text)
        match = re.search(r"Cuisine noted[:\s]*(.*)", ascii_text)
        if match:
            user_session["preferences"]["cuisine"] = match.group(1)
            print("user_session[preferences][cuisine]:", user_session["preferences"]["cuisine"])

    if "Budget noted:" in response_text:
        print('in budget')
        ascii_text = re.sub(r"[^\x00-\x7F]+", "", response_text)
        match = re.search(r"Budget noted[:\s]*(.*)", ascii_text)
        if match:
            user_session["preferences"]["budget"] = match.group(1)
            print("user_session[preferences][budget]:", user_session["preferences"]["budget"])

    if "Location noted:" in response_text:
        print('in location')
        ascii_text = re.sub(r"[^\x00-\x7F]+", "", response_text)
        match = re.search(r"Location noted[:\s]*(.*)", ascii_text)
        if match:
            user_session["preferences"]["location"] = match.group(1)
            print("user_session[preferences][location]:", user_session["preferences"]["location"])
    
    if "now searching" in response_text.lower():
        # later, we'll pass these results to another LLM to keep asking the user if they like this choice
        api_result = search_restaurants(user_session)

    print("AFTER updated:")
    print("current details collected: ", user_session['preferences'])

    return response_text


def search_restaurants(user_session):
    print('In search restaurants function')
    # """Uses Yelp API to find a restaurant based on user preferences."""
    
    cuisine = user_session["preferences"]["cuisine"]
    budget = user_session["preferences"]["budget"]
    location = user_session["preferences"]["location"]

    print("cuisine: ", cuisine, "budget: ", budget, "location: ", location)

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "accept": "application/json"
    }
    
    params = {
        "term": cuisine,
        "location": location,
        "price": budget,  # Yelp API uses 1 (cheap) to 4 (expensive)
        "limit": 1,  # Fetch only one restaurant
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
            return f"🍽️ Found **{name}** ({rating}⭐) in {address} for {cuisine} cuisine within your budget!"
        else:
            return "⚠️ Sorry, I couldn't find any matching restaurants. Try adjusting your preferences!"
    
    return f"⚠️ Yelp API request failed. Error {response.status_code}: {response.text}"


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
        
    sid = session_dict[user][0]
    print("session id is", sid)

    return jsonify({"text": restaurant_assistant_llm(message, sid)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)



#########################################################################################################
# import os
# import requests
# from flask import Flask, request, jsonify
# from llmproxy import generate
# from dotenv import load_dotenv  

# app = Flask(__name__)

# # Load API Key from .env file
# load_dotenv()
# API_KEY = os.getenv("YELP_API_KEY")   
# YELP_API_URL = "https://api.yelp.com/v3/businesses/search"

# # Single user session
# session = {
#     "state": "conversation",
#     "preferences": {"cuisine": None, "budget": None, "location": None}
# }

# def restaurant_assistant_llm(message, sid):
#     print('hey')
#     """Handles the full conversation and recommends a restaurant."""
    
#     response = generate(
#         model="4o-mini",
#         system="""
#             You are a friendly restaurant assistant named REMI 🍽️. Your job is to help the user find a place to eat.
#             - put the welcome message (first message) FEEEELING HUNGRY?** REMI 🧑🏻‍🍳 IS HERE TO HELP YOU!\n\nTell us what you're looking for, and we'll help you **find and book a restaurant!**\n\nWhat type of food are you in the mood for?
#             - Ask the user for their **cuisine preference, budget, and location**.
#             - put a lot of emojis and be nice and quirky 
#              - DO NOT list what details you already have.
#             - Store the **budget as a number (1-4)** according to this scale:
#               "cheap": "1", "mid-range": "2", "expensive": "3", "fine dining": "4" 
#             - make it a fun casual conversation and ask for the occasion 
#             - Once all details are collected, recommend a restaurant!
#             - 
            
#         """,
#         query=f"User input: '{message}'\nCurrent preferences: {session['preferences']}",
#         temperature=0.7,
#         lastk=10,
#         session_id=sid,
#         rag_usage=False
#     )
    
#     response_text = response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?").strip()
    
#     # if response_text.lower() == "search_restaurant":
#     #     return search_restaurants()
    
#     return response_text


# @app.route('/query', methods=['POST'])
# def main():
#     """Handles user messages and decides what to do."""
#     data = request.get_json()
#     message = data.get("text", "").strip()
#     user = data.get("user_name", "Unknown")

#     if user not in session_dict:
#         session_dict[user] = "{user}-session"
#     sid = session_dict[user]
    
#     return jsonify({"text": restaurant_assistant_llm(message, sid)})

# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=5001)

#########################################################################################################
# import os
# import requests
# from flask import Flask, request, jsonify
# from llmproxy import generate
# from dotenv import load_dotenv  

# app = Flask(__name__)

# # Load API Key from .env file
# load_dotenv()
# API_KEY = os.getenv("YELP_API_KEY")   
# YELP_API_URL = "https://api.yelp.com/v3/businesses/search"

# # Single user session
# session = {
#     "state": "conversation",
#     "history": [],
#     "preferences": {"cuisine": None, "budget": None, "location": None, "occasion": None}
# }

# def conversation_agent_llm(message):
#     print("conversation agent")
#     """Handles user conversation to gather details like cuisine, budget, and location."""
    
#     response = generate(
#         model="4o-mini",
#         system="""
#             You are a friendly restaurant assistant named REMI 🍽️.
#             Your job is to engage users in a natural conversation to gather their restaurant preferences.
            
#             - If the user hasn't provided cuisine, budget, or location, ask about them in a casual way.
#             - Infer details from context and suggest reasonable options.
#             - Always confirm what you have so far.
#             - for the budget store it as a number 1-4 according to this scale - "cheap": "1", "mid-range": "2", "expensive": "3", "fine dining": "4"
#             - If all required details (cuisine, budget, location) are collected, respond with "done" and reccomend the user ONE restaraunt and end the session
#         """,
#         query=f"User input: '{message}'\nCurrent known details: {session['preferences']}",
#         temperature=0.7,
#         lastk=10,
#         session_id="remi-conversation",
#         rag_usage=False
#     )
#     response_text = response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?").strip()

#     # if response_text.lower() == "done":
#     #     print("hello")
#     #     return control_agent_llm("done")  # Trigger control agent

#     return response_text  # Otherwise, return normal conversation response

# # def conversation_agent_llm(message):
# #     print("conversation agent")
    
# #     response = generate(
# #         model="4o-mini",
# #         system="""
# #             You are a friendly restaurant assistant named REMI 🍽️.
# #             Your job is to engage users in a natural conversation to gather their restaurant preferences.

# #             - If the user hasn't provided cuisine, budget, or location, ask about them in a casual way.
# #             - Infer details from context and suggest reasonable options.
# #             - Always confirm what you have so far.
# #             - Store the budget as a number 1-4 according to this scale: 
# #               "cheap": "1", "mid-range": "2", "expensive": "3", "fine dining": "4"
# #             - If all required details (cuisine, budget, location) are collected, respond with exactly:
# #               "done | {cuisine} | {budget} | {location}" 
# #               - Ensure that the response format is strict to allow parsing.
# #         """,
# #         query=f"User input: '{message}'\nCurrent known details: {session['preferences']}",
# #         temperature=0.7,
# #         lastk=10,
# #         session_id="remi-conversation",
# #         rag_usage=False
# #     )

# #     response_text = response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?").strip()

# #     # 🛑 If REMI outputs "done", extract and store the preferences
# #     if response_text.lower().startswith("done |"):
# #         print(f"✅ Extracted completion message: {response_text}")

# #         try:
# #             _, cuisine, budget, location = response_text.split(" | ")

# #             # Store extracted values in session
# #             session["preferences"]["cuisine"] = cuisine
# #             session["preferences"]["budget"] = budget
# #             session["preferences"]["location"] = location

# #             print(f"🟢 Preferences Updated in Session: {session['preferences']}")

# #         except ValueError:
# #             print("🚨 ERROR: Failed to parse 'done' response format. Ignoring update.")

# #         return "done"  # Return "done" to trigger search in control agent

# #     return response_text  # Otherwise, continue conversation

# # def control_agent_llm(message):
# #     print("control agent")
# #     print(message)
# #     """Acts as REMI's control center, deciding whether to continue conversation or trigger restaurant search."""
    
# #     response = generate(
# #         model="4o-mini",
# #         system="""
# #             You are an AI agent managing a restaurant recommendation assistant.
# #             Your job is to decide the best next step based on the user's input.

# #             - If the conversation agent responds with "done", respond with "search_restaurant".
# #             - Otherwise, respond with "continue".
# #         """,
# #         query=f"User input: '{message}'\nCurrent session: {session['preferences']}",
# #         temperature=0.0,
# #         lastk=10,
# #         session_id="remi-control",
# #         rag_usage=False
# #     )

# #     result = response.get("response", "").strip().lower()

# #     print(f"🟡 Preferences Before Search: {session['preferences']}")

# #     if result == "search_restaurant":
# #         print('hello')

# #         return search_restaurants()

# #     return "continue"  # Either "continue" or "search_restaurant"

# def control_agent_llm(message):
#     print("control agent")
#     print(f"🟡 Received from Conversation Agent: {message}")

#     # If message contains preferences, extract them
#     if message.lower().startswith("done |"):
#         try:
#             # Parse response format "done | cuisine: Sushi | budget: 2 | location: Boston"
#             parts = message.split(" | ")
#             extracted_preferences = {part.split(": ")[0]: part.split(": ")[1] for part in parts[1:]}

#             # Store extracted values in session
#             session["preferences"]["cuisine"] = extracted_preferences.get("cuisine")
#             session["preferences"]["budget"] = extracted_preferences.get("budget")
#             session["preferences"]["location"] = extracted_preferences.get("location")

#             print(f"🟢 Preferences Successfully Passed to Search: {session['preferences']}")

#             return search_restaurants()  # Now, call search_restaurants with updated preferences

#         except Exception as e:
#             print(f"🚨 ERROR: Failed to parse 'done' response format. Error: {e}")
#             return "⚠️ There was an issue processing your request."

#     # Otherwise, use LLM to decide next step
#     response = generate(
#         model="4o-mini",
#         system="""
#             You are an AI agent managing a restaurant recommendation assistant.
#             Your job is to decide the best next step based on the user's input.
#              You are an AI agent designed to handle user requests.
#             In addition to your own intelligence, you are given access to a set of tools.

#             Think step-by-step, breaking down the task into a sequence small steps.

#             If you can't resolve the query based on your intelligence, ask the user to execute a tool on your behalf and share the results with you.
#             If you want the user to execute a tool on your behalf, strictly only respond with the tool's name and parameters.

#             - If the conversation agent responds with "done", respond with a restaurant reccomendation within the area and end the session.
#             - Otherwise, respond with "continue".
#         """,
#         query=f"User input: '{message}'\nCurrent session: {session['preferences']}",
#         temperature=0.0,
#         lastk=10,
#         session_id="remi-control",
#         rag_usage=False
#     )

#     #result = response.get("response", "").strip().lower()

#     print(f"🟡 Preferences Before Search: {session['preferences']}")

#     # if result == "search_restaurant":
#     #     print('✅ Triggering restaurant search...')
#     #     return search_restaurants()

#     return "continue"


# def search_restaurants():
#     """Searches for a restaurant based on user preferences using Yelp API."""
#     return print('✅ Entering search_restaurants()')

#     # # Extract values safely
#     # cuisine = session["preferences"].get("cuisine", "").strip()
#     # budget = session["preferences"].get("budget", "").strip()
#     # location = session["preferences"].get("location", "").strip()

#     # # 🛑 Debugging: Print session data
#     # print(f"🟢 Preferences Passed to Yelp API: Cuisine={cuisine}, Budget={budget}, Location={location}")

#     # # 🔴 If preferences are missing, print error message
#     # if not cuisine or not budget or not location:
#     #     print("🚨 ERROR: Missing required fields in session before calling Yelp API.")
#     #     return "⚠️ Missing details! Please make sure you've provided cuisine, budget, and location."

#     # headers = {
#     #     "Authorization": f"Bearer {API_KEY}",
#     #     "accept": "application/json"
#     # }

#     # params = {
#     #     "term": cuisine,
#     #     "location": location,
#     #     "price": budget,  # Yelp API uses 1 (cheap) to 4 (expensive)
#     #     "limit": 1,  
#     #     "sort_by": "best_match"
#     # }

#     # print(f"🔵 Sending API Request to Yelp with Params: {params}")

#     # response = requests.get(YELP_API_URL, headers=headers, params=params)
#     # print(f"🟠 Yelp API Response Status: {response.status_code}")

#     # if response.status_code == 200:
#     #     data = response.json()
#     #     print(f"🟣 Raw API Response: {data}")

#     #     if "businesses" in data and data["businesses"]:
#     #         restaurant = data["businesses"][0]
#     #         name = restaurant["name"]
#     #         address = ", ".join(restaurant["location"]["display_address"])
#     #         rating = restaurant["rating"]

#     #         print(f"✅ Found Restaurant: {name}, {rating}⭐, {address}")
#     #         return f"🍽️ Found **{name}** ({rating}⭐) in {address} for {cuisine} cuisine within your budget!"
#     #     else:
#     #         print("⚠️ No restaurants found in Yelp API response.")
#     #         return "⚠️ Sorry, I couldn't find a matching restaurant. Try adjusting your preferences!"
#     # else:
#     #     print(f"🚨 Yelp API Error: {response.status_code} - {response.text}")
#     #     return f"⚠️ Yelp API request failed. Error {response.status_code}: {response.text}"


# @app.route('/query', methods=['POST'])
# def main():
#     """Handles user queries and initiates the restaurant recommendation process."""
#     data = request.get_json()
#     message = data.get("text", "").strip()

#     print(f"Message received: {message}")

#     # If user restarts, reset session
#     if message.lower() in ["restart", "start over"]:
#         session.update({
#             "state": "conversation",
#             "history": [],
#             "preferences": {"cuisine": None, "budget": None, "location": None, "occasion": None}
#         })
#         return jsonify({"text": "🍽️ **FEEEELING HUNGRY?** REMI 🧑🏻‍🍳 IS HERE TO HELP YOU!\n\nTell us what you're looking for, and we'll help you **find and book a restaurant!**\n\nWhat type of food are you in the mood for?"})

#     # Control agent decides next step
#     decision = control_agent_llm(message)

#     if decision == "search_restaurant":
#         return jsonify({"text": search_restaurants()})

#     # Continue gathering user details
#     response_text = conversation_agent_llm(message)
#     return jsonify({"text": response_text})


# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=5001)



# # import os
# # import requests
# # from flask import Flask, request, jsonify
# # from llmproxy import generate
# # from dotenv import load_dotenv  

# # app = Flask(__name__)

# # # Load API Key from .env file
# # load_dotenv()
# # API_KEY = os.getenv("YELP_API_KEY")   

# # YELP_API_URL = "https://api.yelp.com/v3/businesses/search"

# # # Single user session
# # session = {
# #     "state": "conversation",
# #     "history": [],
# #     "preferences": {"cuisine": None, "budget": None, "location": None, "occasion": None}
# # }

# # def conversation_agent_llm(message):
# #     print("conversation agent")
# #     """Handles user conversation to gather details like cuisine, budget, and location."""
    
# #     response = generate(
# #         model="4o-mini",
# #         system="""
# #             You are a friendly restaurant assistant named REMI 🍽️.
# #             Your job is to engage users in a natural conversation to gather their restaurant preferences.
            
# #             - If the user hasn't provided cuisine, budget, or location, ask about them in a casual way.
# #             - Infer details from context and suggest reasonable options.
# #             - Always confirm what you have so far.
# #             - If all required details (cuisine, budget, location) are collected, respond with "done" AND NOTHING ELSE
# #             - DO NOT RECCOMEND RESTARAUNTS AT ALL  
# #         """,
# #         query=f"User input: '{message}'\nCurrent known details: {session['preferences']}",
# #         temperature=0.7,
# #         lastk=10,
# #         session_id="remi-conversation",
# #         rag_usage=False
# #     )

# #     return response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?").strip()


# # def control_agent_llm(message):
# #     print("control agent")
# #     """Acts as REMI's control center, deciding whether to continue conversation or trigger restaurant search."""
    
# #     response = generate(
# #         model="4o-mini",
# #         system="""
# #             You are an AI agent managing a restaurant recommendation assistant.
# #             Your job is to decide the best next step based on the user's input.

# #             - If the user hasn't provided cuisine, budget, AND location, respond with "continue".
# #             - If all required details are collected, respond with "search_restaurant".
# #         """,
# #         query=f"User input: '{message}'\nCurrent session: {session['preferences']}",
# #         temperature=0.0,
# #         lastk=10,
# #         session_id="remi-control",
# #         rag_usage=False
# #     )

# #     result = response.get("response", "").strip().lower()

# #     # Ensure all details are filled before transitioning to search
# #     if session["preferences"]["cuisine"] and session["preferences"]["budget"] and session["preferences"]["location"]:
# #         return "search_restaurant"

# #     return result  # Either "continue" or "search_restaurant"


# # def search_restaurants():
# #     """Mocks a restaurant search based on user preferences."""

# #     return f"🍽️ Found the best {session['preferences']['cuisine']} restaurant within your {session['preferences']['budget']} budget at {session['preferences']['location']}!"


# # @app.route('/query', methods=['POST'])
# # def main():
# #     """Handles user queries and initiates the restaurant recommendation process."""
# #     data = request.get_json()
# #     message = data.get("text", "").strip()

# #     print(f"Message received: {message}")

# #     # If user restarts, reset session
# #     if message.lower() in ["restart", "start over"]:
# #         session.update({
# #             "state": "conversation",
# #             "history": [],
# #             "preferences": {"cuisine": None, "budget": None, "location": None, "occasion": None}
# #         })
# #         return jsonify({"text": "🍽️ **FEEEELING HUNGRY?** REMI 🧑🏻‍🍳 IS HERE TO HELP YOU!\n\nTell us what you're looking for, and we'll help you **find and book a restaurant!**\n\nWhat type of food are you in the mood for?"})

# #     # Control agent decides next step
# #     decision = control_agent_llm(message)

# #     if decision == "search_restaurant":
# #         return jsonify({"text": search_restaurants()})

# #     # Continue gathering user details
# #     response_text = conversation_agent_llm(message)
# #     return jsonify({"text": response_text})


# # if __name__ == "__main__":
# #     app.run(host="0.0.0.0", port=5001)


# ####################################################################


# # import os
# # import requests
# # from flask import Flask, request, jsonify
# # from llmproxy import generate

# # app = Flask(__name__)

# # # Single user session
# # session = {
# #     "state": "conversation",
# #     "history": [],
# #     "preferences": {"cuisine": None, "budget": None, "location": None}
# # }

# # def conversation_agent_llm(message):
# #     """Handles user conversation to gather details like cuisine, budget, and location."""
    
# #     response = generate(
# #         model="4o-mini",
# #         system="""
# #             You are a friendly restaurant assistant named REMI 🍽️.
# #             Your job is to engage users in a natural conversation to gather their restaurant preferences.
# #             Make it feel very conversational and casual
# #             Please ask the user what occasion they are dining for 
# #             Use emojis to make it more fun!
# #             Be nice and welcoming! 
            
# #             - If the user hasn't provided cuisine, budget, or location, ask about them in a casual way.
# #             - Infer details from context and suggest reasonable options.
# #             - If all details are collected, respond with "done".
# #         """,
# #         query=f"User input: '{message}'\nCurrent known details: {session['preferences']}",
# #         temperature=0.7,
# #         lastk=10,
# #         session_id="remi-conversation",
# #         rag_usage=False
# #     )

# #     return response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?").strip()


# # def control_agent_llm(message):
# #     """Acts as REMI's control center, deciding whether to continue conversation or trigger restaurant search."""
    
# #     response = generate(
# #         model="4o-mini",
# #         system="""
# #             You are an AI agent managing a restaurant recommendation assistant.
# #             Your job is to decide the best next step based on the user's input.

# #             - If the user hasn't provided cuisine, budget, AND location, respond with "continue".
# #             - If all required details are collected, respond with "search_restaurant".
# #         """,
# #         query=f"User input: '{message}'\nCurrent session: {session['preferences']}",
# #         temperature=0.0,
# #         lastk=10,
# #         session_id="remi-control",
# #         rag_usage=False
# #     )

# #     result = response.get("response", "").strip().lower()
# #     return result


# # def search_restaurants():
# #     """Mocks a restaurant search based on user preferences."""
# #     return f"🍽️ Found the best {session['preferences']['cuisine']} restaurant within your {session['preferences']['budget']} budget at {session['preferences']['location']}!"


# # @app.route('/query', methods=['POST'])
# # def main():
# #     """Handles user queries and initiates the restaurant recommendation process."""
# #     data = request.get_json()
# #     message = data.get("text", "").strip()

# #     print(f"Message received: {message}")

# #     # If user restarts, reset session
# #     if message.lower() in ["restart", "start over"]:
# #         session.update({
# #             "state": "conversation",
# #             "history": [],
# #             "preferences": {"cuisine": None, "budget": None, "location": None}
# #         })
# #         return jsonify({"text": "🍽️ **FEEEELING HUNGRY?** REMI 🧑🏻‍🍳 IS HERE TO HELP YOU!\n\nTell us what you're looking for, and we'll help you **find and book a restaurant!**\n\nWhat type of food are you in the mood for?"})

# #     # Control agent decides next step
# #     decision = control_agent_llm(message)

# #     if decision == "search_restaurant":
# #         return jsonify({"text": search_restaurants()})

# #     # Continue gathering user details
# #     response_text = conversation_agent_llm(message)
# #     return jsonify({"text": response_text})


# # if __name__ == "__main__":
# #     app.run(host="0.0.0.0", port=5001)
