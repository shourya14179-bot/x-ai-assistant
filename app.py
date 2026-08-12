from flask import Flask, request, redirect, session, render_template, jsonify
import sqlite3
import hashlib
import requests

# ============================================================
# SPARK.AI
# Flask Backend
# ============================================================
app = Flask(__name__)


app.secret_key = "spark-ai-secret-key-change-this"

# ============================================================
# SETTINGS
# ============================================================

DB = "users.db"

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = "llama3.2"

# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ============================================================
# PASSWORD HASH
# ============================================================

def hash_password(password):
    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


# ============================================================
# LOGIN CHECK
# ============================================================

def logged_in():
    return "username" in session


# ============================================================
# OLLAMA FUNCTION
# ============================================================

def ask_ollama(prompt, system_prompt=None):

    if system_prompt is None:
        system_prompt = (
            "You are Spark.ai, a helpful, friendly and intelligent "
            "AI assistant. Give clear and useful answers."
        )

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=120
    )

    response.raise_for_status()

    result = response.json()

    answer = (
        result
        .get("message", {})
        .get("content", "")
        .strip()
    )

    if not answer:
        raise Exception("Ollama returned an empty response.")

    return answer


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    if not logged_in():
        return redirect("/login")

    return render_template(
        "index.html",
        username=session["username"]
    )


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        if not username or not password:
            return """
            <h2>❌ Please enter username and password.</h2>
            <a href="/login">Back to Login</a>
            """

        conn = get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        conn.close()

        if user and user["password"] == hash_password(password):

            session.clear()
            session["username"] = username

            return redirect("/")

        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Login Failed</title>
        </head>

        <body style="
            font-family: Arial;
            text-align: center;
            margin-top: 100px;
        ">

            <h2>❌ Incorrect username or password</h2>

            <br>

            <a href="/login">Try Again</a>

        </body>
        </html>
        """

    return render_template("login.html")


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        if not username or not password:
            return """
            <h2>❌ Username and password are required.</h2>
            <a href="/register">Go back</a>
            """

        if len(username) < 3:
            return """
            <h2>❌ Username must contain at least 3 characters.</h2>
            <a href="/register">Go back</a>
            """

        if len(password) < 4:
            return """
            <h2>❌ Password must contain at least 4 characters.</h2>
            <a href="/register">Go back</a>
            """

        conn = get_db()

        try:

            conn.execute(
                """
                INSERT INTO users
                (username, password)
                VALUES (?, ?)
                """,
                (
                    username,
                    hash_password(password)
                )
            )

            conn.commit()
            conn.close()

            return redirect("/login")

        except sqlite3.IntegrityError:

            conn.close()

            return """
            <h2>❌ Username already exists.</h2>
            <a href="/register">Try another username</a>
            """

    return render_template("register.html")


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# ============================================================
# CURRENT USER
# ============================================================

@app.route("/api/me")
def current_user():

    if not logged_in():

        return jsonify({
            "logged_in": False
        }), 401

    return jsonify({
        "logged_in": True,
        "username": session["username"]
    })


# ============================================================
# NORMAL CHAT
# ============================================================

@app.route("/chat", methods=["POST"])
@app.route("/api/chat", methods=["POST"])
def chat():

    if not logged_in():

        return jsonify({
            "error": "You are not logged in."
        }), 401

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "error": "No JSON data received."
        }), 400

    message = data.get("message", "")

    if not isinstance(message, str):

        return jsonify({
            "error": "Message must be text."
        }), 400

    message = message.strip()

    if not message:

        return jsonify({
            "error": "Message cannot be empty."
        }), 400

    try:

        answer = ask_ollama(message)

        return jsonify({
            "response": answer
        })

    except requests.exceptions.ConnectionError:

        return jsonify({
            "error": (
                "Cannot connect to Ollama. "
                "Make sure Ollama is running."
            )
        }), 503

    except requests.exceptions.Timeout:

        return jsonify({
            "error": "Ollama took too long to respond."
        }), 504

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# WRITING ASSISTANT
# ============================================================

WRITING_PROMPTS = {

    "grammar": (
        "Correct the grammar and punctuation in the user's text. "
        "Keep the original meaning. Return only the corrected text."
    ),

    "spelling": (
        "Correct spelling mistakes in the user's text. "
        "Keep the original meaning and wording as much as possible. "
        "Return only the corrected text."
    ),

    "improve": (
        "Improve the user's writing so it is clearer, smoother and "
        "more natural. Keep the original meaning. Return only the "
        "improved text."
    ),

    "rewrite": (
        "Rewrite the user's text in a clear and natural way while "
        "preserving its meaning. Return only the rewritten text."
    ),

    "summarize": (
        "Summarize the user's text using the most important information. "
        "Be concise and clear."
    ),

    "shorten": (
        "Make the user's text shorter while keeping its important meaning. "
        "Return only the shortened text."
    ),

    "expand": (
        "Expand the user's text with useful detail while preserving its "
        "original meaning. Return only the expanded text."
    ),

    "brainstorm": (
        "Generate useful ideas based on the user's text. "
        "Use a clear numbered list."
    ),

    "professional": (
        "Rewrite the user's text in a professional and polished tone. "
        "Keep the meaning."
    ),

    "friendly": (
        "Rewrite the user's text in a friendly, natural and warm tone. "
        "Keep the meaning."
    ),

    "simple": (
        "Rewrite the user's text using simple, easy-to-understand language. "
        "Keep the meaning."
    ),

    "translate": (
        "Translate the user's text into English. "
        "Return only the translation."
    )
}


@app.route("/api/writing", methods=["POST"])
def writing_assistant():

    if not logged_in():

        return jsonify({
            "error": "You are not logged in."
        }), 401

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "error": "No JSON data received."
        }), 400

    text = data.get("text", "")
    action = data.get("action", "")

    if not isinstance(text, str):

        return jsonify({
            "error": "Text must be text."
        }), 400

    text = text.strip()

    if not text:

        return jsonify({
            "error": "Please enter some text."
        }), 400

    if action not in WRITING_PROMPTS:

        return jsonify({
            "error": "Unknown writing action."
        }), 400

    system_prompt = (
        "You are Spark.ai Writing Assistant. "
        "You provide helpful writing assistance similar to a "
        "basic grammar and productivity assistant. "
        "Do not change the user's meaning unless explicitly asked."
    )

    prompt = (
        WRITING_PROMPTS[action]
        + "\n\nUser text:\n"
        + text
    )

    try:

        answer = ask_ollama(
            prompt,
            system_prompt
        )

        return jsonify({
            "response": answer,
            "action": action
        })

    except requests.exceptions.ConnectionError:

        return jsonify({
            "error": "Cannot connect to Ollama."
        }), 503

    except requests.exceptions.Timeout:

        return jsonify({
            "error": "Ollama took too long to respond."
        }), 504

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# STATUS
# ============================================================

@app.route("/api/status")
def status():

    ollama_status = False

    try:

        response = requests.get(
            "http://127.0.0.1:11434/api/tags",
            timeout=5
        )

        if response.ok:
            ollama_status = True

    except Exception:
        ollama_status = False

    return jsonify({
        "spark_ai": True,
        "logged_in": logged_in(),
        "ollama": ollama_status,
        "model": OLLAMA_MODEL
    })


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return """
    <h1>404</h1>
    <p>Page not found.</p>
    <a href="/">Go to Spark.ai</a>
    """, 404


@app.errorhandler(500)
def internal_error(error):

    return """
    <h1>500</h1>
    <p>Spark.ai server error.</p>
    <a href="/">Go to Spark.ai</a>
    """, 500


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    init_db()

    print("")
    print("==========================================")
    print("              ⚡ SPARK.AI")
    print("==========================================")
    print("")
    print("Website:")
    print("http://127.0.0.1:5000")
    print("")
    print("Ollama:")
    print(OLLAMA_URL)
    print("")
    print("Model:")
    print(OLLAMA_MODEL)
    print("")
    print("Writing Assistant:")
    print("Grammar / Spelling / Rewrite / Summarize")
    print("Improve / Shorten / Expand / Brainstorm")
    print("Professional / Friendly / Simple / Translate")
    print("")
    print("==========================================")
    print("Spark.ai is starting...")
    print("==========================================")
    print("")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )