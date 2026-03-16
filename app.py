import os
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from cbt_engine import load_exercises, cbt_reply
from db import init_db, save_message, save_mood, get_chat_history, get_dynamics

APP_ROOT = Path(__file__).resolve().parent
DATA_PATH = APP_ROOT / "data" / "exercises.json"

app = Flask(__name__, static_folder="web", static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

EXERCISES = load_exercises(DATA_PATH)
init_db()


@app.get("/")
def index():
    return send_from_directory("web", "index.html")


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/exercises")
def api_exercises():
    return jsonify(EXERCISES)


@app.post("/api/chat")
def api_chat():
    data = request.get_json(force=True) or {}
    message = data.get("message", "")
    state = data.get("state", {})
    user_id = data.get("user_id", "default")

    save_message(user_id, "user", message)
    if isinstance(state, dict):
        save_mood(
            user_id,
            int(state.get("anxiety", 0) or 0),
            int(state.get("stress", 0) or 0),
            int(state.get("mood", 5) or 5)
        )

    history = get_chat_history(user_id, limit=6)
    reply = cbt_reply(message, state, EXERCISES, history)
    save_message(user_id, "sabi", reply.text)

    return jsonify({
        "reply": reply.text,
        "intent": reply.intent,
        "next": reply.next_action,
        "suggested_exercise_id": reply.suggested_exercise_id,
    })


@app.get("/api/history")
def api_history():
    user_id = request.args.get("user_id", "default")
    return jsonify(get_chat_history(user_id))


@app.get("/api/dynamics")
def api_dynamics():
    user_id = request.args.get("user_id", "default")
    return jsonify(get_dynamics(user_id))


@app.get("/<path:path>")
def static_files(path):
    return send_from_directory("web", path)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
