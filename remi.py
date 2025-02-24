import os
import requests
from flask import Flask, request, jsonify
from llmproxy import generate  # Ensure this is set up for calling the LLM

app = Flask(__name__)

# Dictionary to store user sessions
user_sessions = {}

def decision_making_agent_llm(user_session):
    """
    Uses an LLM to determine if enough information has been collected.
    If any key information is missing, the LLM will infer and decide whether to proceed or ask for more details.
    """
    response = generate(
        model="4o-mini",  
        system="""
        You are an intelligent restaurant recommendation assistant named REMI 🍽️.
        Your task is to check if the user has provided enough details (cuisine, budget, location)
        to search for a restaurant. If any details are missing, identify them and guide the user
        naturally towards providing the missing details.

        Example:
        - If the user says "I want sushi," and no budget or location is provided, suggest asking about budget and location.
        - If all details are present, confirm and proceed to searching for restaurants.
        """,
        query=f"User session: {user_session}",
        temperature=0.5,
        lastk=0,
        session_id="remi-decision",
        rag_usage=False
    )

    return response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?")

def handle_conversation_with_llm(user_input, user_session):
    """
    Uses an LLM to process user input and determine the next conversational step.
    Updates the session dictionary with inferred preferences.
    """
    response = generate(
        model="4o-mini",   
        system=f"""
        You are a friendly restaurant assistant named REMI 🍽️. 
        Your job is to infer details about the user's restaurant preferences 
        and guide them naturally.
        
        If the user hasn't provided a cuisine, budget, or location, ask about them in a conversational way.
        If all details are provided, confirm and prepare to start searching for restaurants.
        
        Current known details:
        - Cuisine: {user_session['preferences']['cuisine']}
        - Budget: {user_session['preferences']['budget']}
        - Location: {user_session['preferences']['location']}

        If the user is vague, politely clarify what they mean.
        """,
        query=f"User input: '{user_input}'",
        temperature=0.7,
        lastk=0,
        session_id="remi-convo",
        rag_usage=False
    )

    return response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?")


@app.route('/query', methods=['POST'])
def main():
    """Handles user queries and initiates the restaurant recommendation process."""
    data = request.get_json()
    user = data.get("user_name", "Unknown")
    message = data.get("text", "").strip().lower()

    print(f"Message from {user}: {message}")

    # If the user session does not exist, initialize it only ONCE
    if user not in user_sessions:
        user_sessions[user] = {
            "state": "conversation",
            "history": [],
            "preferences": {
                "cuisine": None,
                "budget": None,
                "location": None
            }
        }
        return jsonify({"text": "🍽️ **FEEEELING HUNGRY?** REMI 🧑🏻‍🍳 IS HERE TO HELP YOU!\n\nJust tell me what you're looking for, and REMI will help you **find and book a restaurant!**\n\nWhat type of food are you in the mood for?"})

    session = user_sessions[user]

    # Decision-Making Agent checks if all info is gathered
    ready_to_search, missing_info = decision_making_agent_llm(session)
    print('hi')

    if ready_to_search:
        return jsonify({"text": "Awesome! I have everything I need. Let me find the best restaurant for you... 🍽️"})

    # If missing info, call LLM to keep the conversation going
    response_text = handle_conversation_with_llm(message, session)

    return jsonify({"text": response_text})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)