import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Dictionary to store user sessions
user_sessions = {}

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
            "state": "awaiting_cuisine",
            "history": [],
            "preferences": {
                "cuisine": None,
                "budget": None,
                "location": None
            }
        }
        return jsonify({"text": "🍽️ **FEEEELING HUNGRY?** REMI IS HERE TO HELP YOU.\n\nJust tell me what you're looking for, and I'll help you **find and book a restaurant!**\n\nWhat type of food are you in the mood for?"})

    return jsonify({"text": "⚠️ Something went wrong. Please start over."})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
