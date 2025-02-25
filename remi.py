import os
import requests
from flask import Flask, request, jsonify
from llmproxy import generate  # Ensure this is set up for calling the LLM

app = Flask(__name__)

# Dictionary to store user sessions
user_sessions = {}

def conversation_agent_llm(user, message):
    """
    Uses an LLM to interact with the user and collect necessary restaurant preferences.
    Ensures the conversation is natural and avoids repeating questions.
    """
    session = user_sessions[user]

    # Format conversation history for context
    conversation_history = "\n".join(
        [f"User: {entry['user']}\nREMI: {entry['remi']}" for entry in session["history"]]
    )

    response = generate(
        model="4o-mini",
        system="""
            You are a friendly restaurant assistant named REMI 🍽️.
            Your job is to gather information from the user about their restaurant preferences.

            - If the user hasn't provided cuisine, budget, or location, ask about them naturally.
            - Infer details when possible.
            - Keep the conversation engaging and ask clarifying questions if needed.
            - You have access to past user messages, so do not repeat questions unnecessarily.

            Here is the conversation history so far:
            {history}
        """.format(history=conversation_history),
        query=f"User input: '{message}'\nCurrent known details: {session['preferences']}",
        temperature=0.7,
        lastk=0,
        session_id="remi-convo",
        rag_usage=False
    )

    response_text = response.get("response", "⚠️ Sorry, I couldn't process that. Could you rephrase?").strip()

    # Store user message and bot response in history
    session["history"].append({"user": message, "remi": response_text})

    return response_text

def control_agent_llm(user, message):
    """
    Uses an LLM to decide the next step in the conversation.
    Determines if more details are needed or if REMI is ready to search for restaurants.
    """
    session = user_sessions[user]

    response = generate(
        model="4o-mini",
        system="""
            You are a conversational restaurant assistant named REMI 🍽️.
            Your job is to manage the conversation and determine the next step.

            - If the user hasn't provided cuisine, budget, or location, guide them conversationally.
            - If all details are collected, confirm and proceed to restaurant search.
            - Keep the conversation friendly, and infer preferences naturally when possible.
            - If the user’s message is vague, politely ask for clarification.

            Respond with:
            - "ready" if all details are present.
            - "missing: [list of missing details]" if details are missing.
        """,
        query=f"User input: '{message}'\nCurrent known details: {session['preferences']}",
        temperature=0.0,
        lastk=0,
        session_id="remi-control",
        rag_usage=False
    )

    result = response.get("response", "").strip().lower()

    if result == "ready":
        return True, None  # All details collected, move to restaurant search
    elif result.startswith("missing:"):
        missing_details = result.replace("missing:", "").strip().split(", ")
        return False, missing_details  # Still missing some information

    return False, ["unknown"]  # Default fallback case

@app.route('/query', methods=['POST'])
def main():
    """Handles user queries and initiates the restaurant recommendation process."""
    data = request.get_json()
    user = data.get("user_name", "Unknown")
    message = data.get("text", "").strip()

    print(f"Message from {user}: {message}")

    # If it's a new user or a reset, start fresh
    if user not in user_sessions or message.lower() in ["restart", "start over"]:
        user_sessions[user] = {
            "state": "conversation",
            "history": [],
            "preferences": {
                "cuisine": None,
                "budget": None,
                "location": None
            }
        }
        return jsonify({"text": "🍽️ **FEEEELING HUNGRY?** REMI 🧑🏻‍🍳 IS HERE TO HELP YOU!\n\nJust tell us what you're looking for, and REMI will help you **find and book a restaurant!**\n\nWhat type of food are you in the mood for?"})

    # Check if we have enough information to proceed
    ready_to_search, missing_info = control_agent_llm(user, message)

    if ready_to_search:
        return jsonify({"text": "Awesome! I have everything I need. Let me find the best restaurant for you... 🍽️"})

    # If missing info, continue gathering details using conversation agent
    response_text = conversation_agent_llm(user, message)

    return jsonify({"text": response_text})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
