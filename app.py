from flask import Flask, request, jsonify, render_template, redirect, session
import requests
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

DATABASE = "users.db"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "llama3.2"


def get_db():
    conn = sqlite3.connect(DATABASE)
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

    conn.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            user_message TEXT NOT NULL,
            ai_response TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return """
        <h2>Register</h2>
        <form method="POST">
            <input name="username" placeholder="Username" required>
            <br><br>
            <input type="password" name="password" placeholder="Password" required>
            <br><br>
            <button type="submit">Register</button>
        </form>
        <br>
        <a href="/login">Login</a>
        """

    username = request.form.get("username")
    password = request.form.get("password")

    if not username or not password:
        return "Username and password are required."

    hashed_password = generate_password_hash(password)

    try:
        conn = get_db()

        conn.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hashed_password)
        )

        conn.commit()
        conn.close()

        return redirect("/login")

    except sqlite3.IntegrityError:
        return "Username already exists."


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return """
        <h2>Login</h2>
        <form method="POST">
            <input name="username" placeholder="Username" required>
            <br><br>
            <input type="password" name="password" placeholder="Password" required>
            <br><br>
            <button type="submit">Login</button>
        </form>
        <br>
        <a href="/register">Create account</a>
        """

    username = request.form.get("username")
    password = request.form.get("password")

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    conn.close()

    if user and check_password_hash(user["password"], password):
        session["username"] = username
        return redirect("/")

    return "Invalid username or password."


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No JSON data received."}), 400

    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "Message is empty."}), 400

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": message,
                "stream": False
            },
            timeout=120
        )

        response.raise_for_status()

        result = response.json()
        ai_response = result.get("response", "")

    except requests.exceptions.ConnectionError:
        return jsonify({
            "error": "Ollama is not running."
        }), 500

    except requests.exceptions.Timeout:
        return jsonify({
            "error": "Ollama took too long to respond."
        }), 500

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

    username = session.get("username")

    if username:
        conn = get_db()

        conn.execute(
            """
            INSERT INTO chats
            (username, user_message, ai_response)
            VALUES (?, ?, ?)
            """,
            (username, message, ai_response)
        )

        conn.commit()
        conn.close()

    return jsonify({
        "response": ai_response
    })


@app.route("/history")
def history():
    username = session.get("username")

    if not username:
        return jsonify({"history": []})

    conn = get_db()

    chats = conn.execute(
        """
        SELECT id, user_message, ai_response, created_at
        FROM chats
        WHERE username = ?
        ORDER BY id DESC
        """,
        (username,)
    ).fetchall()

    conn.close()

    history_list = []

    for chat in chats:
        history_list.append({
            "id": chat["id"],
            "user_message": chat["user_message"],
            "ai_response": chat["ai_response"],
            "created_at": chat["created_at"]
        })

    return jsonify({
        "history": history_list
    })


@app.route("/history/clear", methods=["POST"])
def clear_history():
    username = session.get("username")

    if not username:
        return jsonify({
            "error": "Not logged in."
        }), 401

    conn = get_db()

    conn.execute(
        "DELETE FROM chats WHERE username = ?",
        (username,)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Chat history cleared."
    })


@app.route("/me")
def me():
    username = session.get("username")

    if not username:
        return jsonify({
            "logged_in": False
        })

    return jsonify({
        "logged_in": True,
        "username": username
    })


if __name__ == "__main__":
    init_db()

    print("----------------------------------------")
    print("X.ai Server Starting...")
    print("----------------------------------------")
    print("Model:", MODEL)
    print("Ollama:", OLLAMA_URL)
    print("Website: http://127.0.0.1:5000")
    print("----------------------------------------")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )