import os
import requests
from flask import Flask, request, jsonify
from llmproxy import generate

app = Flask(__name__)

# Dictionary to store session for a single user
user_session = {}

def conversation_agent_llm(message):
    """Handles user conversation to gather details like cuisine, budget, and location."""
    # Using the single user session data
    session = user_session

    response = generate(
        model="4o-mini",
        system="""
            You are a friendly restaurant assistant named REMI 🍽️.
            Your job is to engage the user in a natural conversation to gather their restaurant preferences.
            
            - If the user hasn't provided cuisine, budget, or location, ask about them in a casual way.
            - Infer details from context and suggest reasonable options.
            - If all details are collected, respond with "done".
        """,
        query=f"User input: '{message}'\nCurrent known details: {session['preferences']}",
        temperature=0.7,
        lastk=10,
        session_id="remi-conversation",
        rag_usage=False
    )

    return response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?").strip()


def control_agent_llm(message):
    """Acts as REMI's control center, deciding whether to continue conversation or trigger restaurant search."""
    session = user_session

    response = generate(
        model="4o-mini",
        system="""
            You are an AI agent managing a restaurant recommendation assistant.
            Your job is to decide the best next step based on the user's input.

            - If the user hasn't provided cuisine, budget, or location, respond with "continue".
            - If all required details are collected, respond with "search_restaurant".
            - If unsure, ask for clarification conversationally.
        """,
        query=f"User input: '{message}'\nCurrent session: {session['preferences']}",
        temperature=0.0,
        lastk=10,
        session_id="remi-control",
        rag_usage=False
    )

    result = response.get("response", "").strip().lower()

    if result == "search_restaurant":
        return "search_restaurant"
    elif result == "continue":
        return "continue"

    return "continue"  # Default: Keep asking


def search_restaurants():
    """Mocks a restaurant search based on user preferences."""
    session = user_session
    return f"🍽️ Found the best {session['preferences']['cuisine']} restaurant within your {session['preferences']['budget']} budget at {session['preferences']['location']}!"


@app.route('/query', methods=['POST'])
def main():
    """Handles user queries and initiates the restaurant recommendation process."""
    data = request.get_json()
    message = data.get("text", "").strip()

    print(f"Message: {message}")

    # If the user is new or restarting, reset session
    if not user_session or message.lower() in ["restart", "start over"]:
        user_session = {
            "state": "conversation",
            "history": [],
            "preferences": {"cuisine": None, "budget": None, "location": None}
        }
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
# from llmproxy import generate  # Ensure this is set up for calling the LLM

# app = Flask(__name__)

# # Dictionary to store user sessions
# user_sessions = {}

# def conversation_agent_llm(user, message):
#     """
#     Uses an LLM to interact with the user and collect necessary restaurant preferences.
#     Ensures the conversation is natural and avoids repeating questions.
#     """
#     session = user_sessions[user]

#     # Format conversation history for context
#     conversation_history = "\n".join(
#         [f"User: {entry['user']}\nREMI: {entry['remi']}" for entry in session["history"]]
#     )

#     response = generate(
#         model="4o-mini",
#         system="""
#             You are a friendly restaurant assistant named REMI 🍽️.
#             Your job is to gather information from the user about their restaurant preferences.

#             - If the user hasn't provided cuisine, budget, or location, ask about them naturally.
#             - Infer details when possible.
#             - Keep the conversation engaging and ask clarifying questions if needed.
#             - You have access to past user messages, so do not repeat questions unnecessarily.

#             Here is the conversation history so far:
#             {history}
#         """.format(history=conversation_history),
#         query=f"User input: '{message}'\nCurrent known details: {session['preferences']}",
#         temperature=0.7,
#         lastk=0,
#         session_id="remi-convo",
#         rag_usage=False
#     )

#     response_text = response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?").strip()

#     # Store user message and bot response in history
#     session["history"].append({"user": message, "remi": response_text})

#     return response_text

# def control_agent_llm(query):
    
#     system = """
#     You are an AI agent designed to handle user requests.
#     In addition to your own intelligence, you are given access to a set of tools.

#     Think step-by-step, breaking down the task into a sequence small steps.

#     If you can't resolve the query based on your intelligence, ask the user to execute a tool on your behalf and share the results with you.
#     If you want the user to execute a tool on your behalf, strictly only respond with the tool's name and parameters.
#     Example response for using tool: websearch('weather in boston today')

#     The name of the provided tools and their parameters are given below.
#     The output of tool execution will be shared with you so you can decide your next steps.

#     ### PROVIDED TOOLS INFORMATION ###
#     ##1. Tool to find a restaurant
#     Name:  
#     Parameters:  
#     example usage: 


#     ##2. Tool to 
#     Name: 
#     Parameters: 
#     example usage: websearch('caching in llms')


#     ##3.  
#     Name: 
#     Parameters: 


#     """

#     response = generate(model = '4o-mini',
#         system = system,
#         query = query,
#         temperature=0.7,
#         lastk=10,
#         session_id='DEMO_AGENT_EMAIL',
#         rag_usage = False)

#     try:
#         return response['response']
#     except Exception as e:
#         print(f"Error occured with parsing output: {response}")
#         raise e
#     return 


# @app.route('/query', methods=['POST'])
# def main():
#     """Handles user queries and initiates the restaurant recommendation process."""
#     data = request.get_json()
#     user = data.get("user_name", "Unknown")
#     message = data.get("text", "").strip()

#     print(f"Message from {user}: {message}")

#     # If it's a new user or a reset, start fresh
#     if user not in user_sessions or message.lower() in ["restart", "start over"]:
#         user_sessions[user] = {
#             "state": "conversation",
#             "history": [],
#             "preferences": {
#                 "cuisine": None,
#                 "budget": None,
#                 "location": None
#             }
#         }
#         return jsonify({"text": "🍽️ **FEEEELING HUNGRY?** REMI 🧑🏻‍🍳 IS HERE TO HELP YOU!\n\nJust tell us what you're looking for, and REMI will help you **find and book a restaurant!**\n\nWhat type of food are you in the mood for?"})

#     # Check if we have enough information to proceed
#     ready_to_search, missing_info = control_agent_llm(user, message)

#     if ready_to_search:
#         return jsonify({"text": "Awesome! I have everything I need. Let me find the best restaurant for you... 🍽️"})

#     # If missing info, continue gathering details using conversation agent
#     response_text = conversation_agent_llm(user, message)

#     return jsonify({"text": response_text})

# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=5001)
