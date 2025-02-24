import os
import requests
from flask import Flask, request, jsonify
from llmproxy import generate  # Ensure this is set up for calling the LLM

app = Flask(__name__)

# Dictionary to store user sessions
user_sessions = {}


def agent_decision(user_session):
    """
    Uses an LLM to determine if enough information has been collected.
    If any key information is missing, the LLM will infer and decide whether to proceed or ask for more details.
    """
    system = """
    You are an AI agent named REMI 🍽️ that determines if enough details (cuisine, budget, location)
    have been provided to search for a restaurant.
    
    Respond with:
    - "ready" if all details are present.
    - "missing: [list of missing details]" if details are missing.
    """

    response = generate(
        model="4o-mini",
        system=system,
        query=f"User session: {user_session}",
        temperature=0.0,
        lastk=0,
        session_id="remi-decision",
        rag_usage=False
    )

    result = response.get("response", "").strip().lower()

    if result == "ready":
        return "ready"
    elif result.startswith("missing:"):
        return result  # Returns "missing: cuisine, budget" etc.

    return "missing: unknown"


def extract_preferences(user_input, user_session):
    """
    Extracts preferences (cuisine, budget, location) from user input and updates the session.
    """
    # Example: Extract cuisine
    if "cuisine" not in user_session["preferences"] or not user_session["preferences"]["cuisine"]:
        if "pizza" in user_input:
            user_session["preferences"]["cuisine"] = "Italian"
        elif "sushi" in user_input:
            user_session["preferences"]["cuisine"] = "Japanese"
        # Add more cuisine mappings as needed

    # Example: Extract budget
    if "budget" not in user_session["preferences"] or not user_session["preferences"]["budget"]:
        if "cheap" in user_input or "low" in user_input:
            user_session["preferences"]["budget"] = "low"
        elif "expensive" in user_input or "high" in user_input:
            user_session["preferences"]["budget"] = "high"
        # Add more budget mappings as needed

    # Example: Extract location
    if "location" not in user_session["preferences"] or not user_session["preferences"]["location"]:
        if "downtown" in user_input:
            user_session["preferences"]["location"] = "downtown"
        elif "suburb" in user_input:
            user_session["preferences"]["location"] = "suburb"
        # Add more location mappings as needed


def agent_conversation(user_input, user_session):
    """
    Uses an LLM to infer user details (cuisine, budget, location) and update the session.
    """
    system = """
    You are a friendly restaurant assistant named REMI 🍽️.
    Your job is to infer details about the user's restaurant preferences and guide them naturally.
    
    If the user hasn't provided a cuisine, budget, or location, ask about them in a conversational way.
    If all details are provided, confirm and prepare to start searching for restaurants.

    Respond with:
    - The next conversational step based on missing details.
    - A structured JSON response with extracted values for cuisine, budget, and location.
    """

    # Update session with preferences extracted from user input
    extract_preferences(user_input, user_session)

    response = generate(
        model="4o-mini",
        system=system,
        query=f"User input: '{user_input}'\nCurrent known details: {user_session['preferences']}",
        temperature=0.7,
        lastk=0,
        session_id="remi-convo",
        rag_usage=False
    )

    response_text = response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?").strip()

    # Extract inferred preferences from response (assume JSON format in response)
    try:
        # Parse JSON if present in the response
        if "{" in response_text and "}" in response_text:
            import json
            parsed_response = json.loads(response_text.split("{")[1].split("}")[0])
            if "cuisine" in parsed_response:
                user_session["preferences"]["cuisine"] = parsed_response["cuisine"]
            if "budget" in parsed_response:
                user_session["preferences"]["budget"] = parsed_response["budget"]
            if "location" in parsed_response:
                user_session["preferences"]["location"] = parsed_response["location"]
    except Exception as e:
        print(f"Error parsing JSON from LLM response: {e}")

    # Add user input and bot response to conversation history
    user_session["history"].append({"user": user_input, "bot": response_text})

    return response_text


@app.route('/query', methods=['POST'])
def main():
    """Handles user queries and initiates the restaurant recommendation process."""
    data = request.get_json()
    user = data.get("user_name", "Unknown")
    message = data.get("text", "").strip().lower()

    print(f"Message from {user}: {message}")

    # If the user session does not exist, initialize it
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

        # Send the welcome message first
        welcome_message = "🍽️ **FEEEELING HUNGRY?** REMI 🧑🏻‍🍳 IS HERE TO HELP YOU!\n\nJust tell me what you're looking for, and REMI will help you **find and book a restaurant!**"
        
        # Immediately start conversation after welcome message
        response_text = agent_conversation("start", user_sessions[user])

        return jsonify({"text": f"{welcome_message}\n\n{response_text}"})

    session = user_sessions[user]

    # Alternate between conversation and decision-making
    max_iterations = 5  # Prevent infinite loops
    i = 0

    while i < max_iterations:
        decision_result = agent_decision(session)

        if decision_result == "ready":
            return jsonify({"text": "Awesome! I have everything I need. Let me find the best restaurant for you... 🍽️"})

        # Otherwise, continue the conversation
        response_text = agent_conversation(message, session)
        
        i += 1  # Ensure loop does not run forever
        return jsonify({"text": response_text})  # Respond to user and wait for next input

    return jsonify({"text": "⚠️ Sorry, something went wrong. Try again!"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)