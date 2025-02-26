import os
import requests
from flask import Flask, request, jsonify
from llmproxy import generate
from dotenv import load_dotenv  

app = Flask(__name__)

# Load API Key from .env file
load_dotenv()
API_KEY = os.getenv("YELP_API_KEY")   
YELP_API_URL = "https://api.yelp.com/v3/businesses/search"

# Single user session
session = {
    "state": "conversation",
    "history": [],
    "preferences": {"cuisine": None, "budget": None, "location": None, "occasion": None}
}

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
#             - If all required details (cuisine, budget, location) are collected, respond with "done" AND NOTHING ELSE
#             - DO NOT RECOMMEND RESTAURANTS AT ALL  
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
def conversation_agent_llm(message):
    print("conversation agent")
    
    response = generate(
        model="4o-mini",
        system="""
            You are a friendly restaurant assistant named REMI 🍽️.
            Your job is to engage users in a natural conversation to gather their restaurant preferences.

            - If the user hasn't provided cuisine, budget, or location, ask about them in a casual way.
            - Infer details from context and suggest reasonable options.
            - Always confirm what you have so far.
            - Store the budget as a number 1-4 according to this scale: 
              "cheap": "1", "mid-range": "2", "expensive": "3", "fine dining": "4"
            - If all required details (cuisine, budget, location) are collected, respond with exactly:
              "done | {cuisine} | {budget} | {location}" 
              - Ensure that the response format is strict to allow parsing.
        """,
        query=f"User input: '{message}'\nCurrent known details: {session['preferences']}",
        temperature=0.7,
        lastk=10,
        session_id="remi-conversation",
        rag_usage=False
    )

    response_text = response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?").strip()

    # Check if REMI outputs "done" and update the session
    if response_text.lower().startswith("done |"):
        print(f"✅ Extracted completion message: {response_text}")

        # Extract the preferences from the response
        try:
            _, cuisine, budget, location = response_text.split(" | ")

            # Update session with extracted values
            session["preferences"]["cuisine"] = cuisine
            session["preferences"]["budget"] = budget
            session["preferences"]["location"] = location

            print(f"🟢 Preferences Updated in Session: {session['preferences']}")

        except ValueError:
            print("🚨 ERROR: Failed to parse 'done' response format. Ignoring update.")

        return "done"  # Return "done" so control agent can decide what to do next

    return response_text  # Otherwise, continue the conversation


def control_agent_llm(message):
    print("control agent")
    """Acts as REMI's control center, deciding whether to continue conversation or trigger restaurant search."""
    
    response = generate(
        model="4o-mini",
        system="""
            You are an AI agent managing a restaurant recommendation assistant.
            Your job is to decide the best next step based on the user's input.

            - If the conversation agent responds with "done", respond with "search_restaurant".
            - Otherwise, respond with "continue".
        """,
        query=f"User input: '{message}'\nCurrent session: {session['preferences']}",
        temperature=0.0,
        lastk=10,
        session_id="remi-control",
        rag_usage=False
    )

    result = response.get("response", "").strip().lower()

    print(f"🟡 Preferences Before Search: {session['preferences']}")

    if result == "search_restaurant":
        print('hello')
        return search_restaurants()

    return "continue"  # Either "continue" or "search_restaurant"


def search_restaurants():
    """Searches for a restaurant based on user preferences using Yelp API."""
    print('hello1')
    
    cuisine = session["preferences"]["cuisine"]
    budget = session["preferences"]["budget"]
    location = session["preferences"]["location"]
    print(f"🟡 Preferences Before API Call: Cuisine={cuisine}, Budget={budget}, Location={location}")
    print('hello2')

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "accept": "application/json"
    }

    print('hello3')
    params = {
        "term": cuisine,
        "location": location,
        "price": budget, 
        "limit": 1,  
        "sort_by": "best_match"
    }
    print(f"🔵 Sending API Request to Yelp with Params: {params}")

    response = requests.get(YELP_API_URL, headers=headers, params=params)
    print(f"🟠 Yelp API Response Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"🟣 Raw API Response: {data}")

        if "businesses" in data and len(data["businesses"]) > 0:
            restaurant = data["businesses"][0]
            name = restaurant["name"]
            address = ", ".join(restaurant["location"]["display_address"])
            rating = restaurant["rating"]

            print(f"✅ Found Restaurant: {name}, {rating}⭐, {address}")
            return f"🍽️ Found **{name}** ({rating}⭐) in {address} for {cuisine} cuisine within your {budget} budget!"
        else:
            print("⚠️ No restaurants found in Yelp API response.")
            return "⚠️ Sorry, I couldn't find a matching restaurant. Try adjusting your preferences!"
    else:
        print(f"🚨 Yelp API Error: {response.status_code} - {response.text}")
        return f"⚠️ Yelp API request failed. Error {response.status_code}: {response.text}"

@app.route('/query', methods=['POST'])
def main():
    """Handles user queries and initiates the restaurant recommendation process."""
    data = request.get_json()
    message = data.get("text", "").strip()

    print(f"Message received: {message}")

    # If user restarts, reset session
    if message.lower() in ["restart", "start over"]:
        session.update({
            "state": "conversation",
            "history": [],
            "preferences": {"cuisine": None, "budget": None, "location": None, "occasion": None}
        })
        return jsonify({"text": "🍽️ **FEEEELING HUNGRY?** REMI 🧑🏻‍🍳 IS HERE TO HELP YOU!\n\nTell us what you're looking for, and we'll help you **find and book a restaurant!**\n\nWhat type of food are you in the mood for?"})

    # Control agent decides next step
    decision = control_agent_llm(message)

    if decision == "search_restaurant":
        return jsonify({"text": search_restaurants()})

    # Continue gathering user details
    response_text = conversation_agent_llm(message)
    return jsonify({"text": response_text})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)



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
#             - If all required details (cuisine, budget, location) are collected, respond with "done" AND NOTHING ELSE
#             - DO NOT RECCOMEND RESTARAUNTS AT ALL  
#         """,
#         query=f"User input: '{message}'\nCurrent known details: {session['preferences']}",
#         temperature=0.7,
#         lastk=10,
#         session_id="remi-conversation",
#         rag_usage=False
#     )

#     return response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?").strip()


# def control_agent_llm(message):
#     print("control agent")
#     """Acts as REMI's control center, deciding whether to continue conversation or trigger restaurant search."""
    
#     response = generate(
#         model="4o-mini",
#         system="""
#             You are an AI agent managing a restaurant recommendation assistant.
#             Your job is to decide the best next step based on the user's input.

#             - If the user hasn't provided cuisine, budget, AND location, respond with "continue".
#             - If all required details are collected, respond with "search_restaurant".
#         """,
#         query=f"User input: '{message}'\nCurrent session: {session['preferences']}",
#         temperature=0.0,
#         lastk=10,
#         session_id="remi-control",
#         rag_usage=False
#     )

#     result = response.get("response", "").strip().lower()

#     # Ensure all details are filled before transitioning to search
#     if session["preferences"]["cuisine"] and session["preferences"]["budget"] and session["preferences"]["location"]:
#         return "search_restaurant"

#     return result  # Either "continue" or "search_restaurant"


# def search_restaurants():
#     """Mocks a restaurant search based on user preferences."""

#     return f"🍽️ Found the best {session['preferences']['cuisine']} restaurant within your {session['preferences']['budget']} budget at {session['preferences']['location']}!"


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


####################################################################


# import os
# import requests
# from flask import Flask, request, jsonify
# from llmproxy import generate

# app = Flask(__name__)

# # Single user session
# session = {
#     "state": "conversation",
#     "history": [],
#     "preferences": {"cuisine": None, "budget": None, "location": None}
# }

# def conversation_agent_llm(message):
#     """Handles user conversation to gather details like cuisine, budget, and location."""
    
#     response = generate(
#         model="4o-mini",
#         system="""
#             You are a friendly restaurant assistant named REMI 🍽️.
#             Your job is to engage users in a natural conversation to gather their restaurant preferences.
#             Make it feel very conversational and casual
#             Please ask the user what occasion they are dining for 
#             Use emojis to make it more fun!
#             Be nice and welcoming! 
            
#             - If the user hasn't provided cuisine, budget, or location, ask about them in a casual way.
#             - Infer details from context and suggest reasonable options.
#             - If all details are collected, respond with "done".
#         """,
#         query=f"User input: '{message}'\nCurrent known details: {session['preferences']}",
#         temperature=0.7,
#         lastk=10,
#         session_id="remi-conversation",
#         rag_usage=False
#     )

#     return response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?").strip()


# def control_agent_llm(message):
#     """Acts as REMI's control center, deciding whether to continue conversation or trigger restaurant search."""
    
#     response = generate(
#         model="4o-mini",
#         system="""
#             You are an AI agent managing a restaurant recommendation assistant.
#             Your job is to decide the best next step based on the user's input.

#             - If the user hasn't provided cuisine, budget, AND location, respond with "continue".
#             - If all required details are collected, respond with "search_restaurant".
#         """,
#         query=f"User input: '{message}'\nCurrent session: {session['preferences']}",
#         temperature=0.0,
#         lastk=10,
#         session_id="remi-control",
#         rag_usage=False
#     )

#     result = response.get("response", "").strip().lower()
#     return result


# def search_restaurants():
#     """Mocks a restaurant search based on user preferences."""
#     return f"🍽️ Found the best {session['preferences']['cuisine']} restaurant within your {session['preferences']['budget']} budget at {session['preferences']['location']}!"


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
#             "preferences": {"cuisine": None, "budget": None, "location": None}
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
