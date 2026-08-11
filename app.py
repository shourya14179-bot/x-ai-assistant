from flask import Flask, request, jsonify, session, render_template_string
import sqlite3
import requests
import secrets
import os
from functools import wraps
from datetime import datetime

# ============================================================
# X.AI - FULL FLASK APP
# Flask + OpenRouter + SQLite + Login + Chats + Memory
# ============================================================

app = Flask(__name__)

app.secret_key = os.getenv(
    "SECRET_KEY",
    secrets.token_hex(32)
)

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "5000"))

# ============================================================
# OPENROUTER
# ============================================================

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Free model
MODEL = "meta-llama/llama-3.2-3b-instruct:free"

AI_TIMEOUT = 60

# ============================================================
# DATABASE
# ============================================================

DB_FILE = "xai.db"


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(chat_id) REFERENCES chats(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            memory TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


init_db()

# ============================================================
# HELPERS
# ============================================================


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def current_user():
    return session.get("user_id")


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user():
            return jsonify({
                "error": "Please login first."
            }), 401

        return func(*args, **kwargs)

    return wrapper


def make_chat(user_id, title="New Chat"):
    conn = get_db()

    cursor = conn.execute("""
        INSERT INTO chats
        (user_id, title, created_at)
        VALUES (?, ?, ?)
    """, (
        user_id,
        title,
        now()
    ))

    chat_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return chat_id


def check_chat_owner(chat_id, user_id):
    conn = get_db()

    chat = conn.execute("""
        SELECT *
        FROM chats
        WHERE id = ? AND user_id = ?
    """, (
        chat_id,
        user_id
    )).fetchone()

    conn.close()

    return chat


# ============================================================
# HTML
# ============================================================

HTML = """
<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>X.ai</title>

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: Arial, Helvetica, sans-serif;
    background: #000;
    color: #fff;
    height: 100vh;
    overflow: hidden;
}

button,
input {
    font-family: inherit;
}

button {
    border: 0;
    border-radius: 10px;
    padding: 11px 16px;
    cursor: pointer;
    background: #222;
    color: white;
}

button:hover {
    background: #333;
}

input {
    width: 100%;
    padding: 13px;
    margin: 7px 0;
    border-radius: 10px;
    border: 1px solid #333;
    background: #050505;
    color: white;
    outline: none;
}

input:focus {
    border-color: #777;
}

/* LOGIN */

#loginScreen {
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #000;
}

.login-box {
    width: 360px;
    background: #111;
    border: 1px solid #333;
    border-radius: 18px;
    padding: 35px;
}

.logo {
    text-align: center;
    font-size: 38px;
    font-weight: bold;
}

.subtitle {
    text-align: center;
    color: #999;
    margin: 8px 0 25px;
}

.login-button {
    width: 100%;
    margin-top: 12px;
    background: white;
    color: black;
    font-weight: bold;
}

.login-button:hover {
    background: #ddd;
}

.switch {
    text-align: center;
    margin-top: 18px;
    color: #aaa;
    cursor: pointer;
}

.status {
    text-align: center;
    color: #777;
    font-size: 12px;
    margin-top: 10px;
}

/* APP */

#appScreen {
    display: none;
    height: 100vh;
}

/* SIDEBAR */

.sidebar {
    width: 270px;
    height: 100vh;
    background: #080808;
    border-right: 1px solid #222;
    position: fixed;
    left: 0;
    top: 0;
    display: flex;
    flex-direction: column;
}

.sidebar-top {
    padding: 16px;
}

.brand {
    font-size: 23px;
    font-weight: bold;
    padding: 10px;
}

.new-chat {
    width: 100%;
    text-align: left;
    margin-top: 10px;
    background: #181818;
}

.chat-list {
    flex: 1;
    overflow-y: auto;
    padding: 10px;
}

.chat-item {
    padding: 11px;
    border-radius: 9px;
    margin-bottom: 4px;
    cursor: pointer;
    color: #ccc;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.chat-item:hover {
    background: #191919;
}

.chat-item.active {
    background: #222;
    color: white;
}

.sidebar-bottom {
    padding: 12px;
    border-top: 1px solid #222;
}

.user-name {
    padding: 10px;
    color: #aaa;
}

.sidebar-button {
    width: 100%;
    text-align: left;
    margin-top: 4px;
}

/* MAIN */

.main {
    margin-left: 270px;
    height: 100vh;
    display: flex;
    flex-direction: column;
}

.topbar {
    height: 60px;
    border-bottom: 1px solid #222;
    display: flex;
    align-items: center;
    padding: 0 20px;
}

.top-title {
    font-weight: bold;
}

.chat-area {
    flex: 1;
    overflow-y: auto;
    padding: 30px 15%;
}

.message {
    max-width: 850px;
    margin: 0 auto 25px;
    display: flex;
    gap: 15px;
}

.avatar {
    min-width: 35px;
    height: 35px;
    border-radius: 50%;
    background: #222;
    display: flex;
    justify-content: center;
    align-items: center;
    font-weight: bold;
}

.user-message .avatar {
    background: white;
    color: black;
}

.message-content {
    line-height: 1.6;
    white-space: pre-wrap;
    word-wrap: break-word;
}

.input-area {
    padding: 15px 15%;
    border-top: 1px solid #222;
}

.input-box {
    max-width: 850px;
    margin: auto;
    background: #151515;
    border: 1px solid #333;
    border-radius: 16px;
    display: flex;
    padding: 8px;
}

#messageInput {
    flex: 1;
    border: 0;
    background: transparent;
    margin: 0;
}

.send {
    background: white;
    color: black;
    font-weight: bold;
}

.send:hover {
    background: #ddd;
}

/* MODALS */

.modal {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,.75);
    justify-content: center;
    align-items: center;
    z-index: 10;
}

.modal-box {
    width: 420px;
    max-width: 90%;
    max-height: 80vh;
    overflow-y: auto;
    background: #111;
    border: 1px solid #333;
    border-radius: 15px;
    padding: 25px;
}

.close {
    float: right;
}

/* MOBILE */

@media(max-width: 700px) {

    .sidebar {
        width: 220px;
    }

    .main {
        margin-left: 220px;
    }

    .chat-area,
    .input-area {
        padding-left: 10px;
        padding-right: 10px;
    }

}

</style>

</head>

<body>

<!-- LOGIN -->

<div id="loginScreen">

    <div class="login-box">

        <div class="logo">X.ai</div>

        <div class="subtitle">
            Your personal AI assistant
        </div>

        <input
            id="username"
            placeholder="Username"
            autocomplete="username"
        >

        <input
            id="password"
            type="password"
            placeholder="Password"
            autocomplete="current-password"
        >

        <button
            class="login-button"
            onclick="login()">
            Login
        </button>

        <div
            class="switch"
            onclick="register()">
            Create a new account
        </div>

        <div
            id="loginStatus"
            class="status">
        </div>

    </div>

</div>


<!-- APP -->

<div id="appScreen">

    <div class="sidebar">

        <div class="sidebar-top">

            <div class="brand">
                X.ai
            </div>

            <button
                class="new-chat"
                onclick="newChat()">
                + New Chat
            </button>

        </div>

        <div
            id="chatList"
            class="chat-list">
        </div>

        <div class="sidebar-bottom">

            <div
                id="userName"
                class="user-name">
            </div>

            <button
                class="sidebar-button"
                onclick="openMemory()">
                Memory
            </button>

            <button
                class="sidebar-button"
                onclick="openSettings()">
                Settings
            </button>

            <button
                class="sidebar-button"
                onclick="logout()">
                Logout
            </button>

        </div>

    </div>


    <div class="main">

        <div class="topbar">

            <div
                id="chatTitle"
                class="top-title">
                New Chat
            </div>

        </div>

        <div
            id="chatArea"
            class="chat-area">
        </div>

        <div class="input-area">

            <div class="input-box">

                <input
                    id="messageInput"
                    placeholder="Message X.ai..."
                    onkeydown="handleKey(event)"
                >

                <button
                    class="send"
                    onclick="sendMessage()">
                    Send
                </button>

            </div>

            <div
                id="status"
                class="status">
                X.ai is ready
            </div>

        </div>

    </div>

</div>


<!-- SETTINGS -->

<div
    id="settingsModal"
    class="modal">

    <div class="modal-box">

        <button
            class="close"
            onclick="closeSettings()">
            X
        </button>

        <h2>Settings</h2>

        <p>
            <b>Model:</b>
            {{ model }}
        </p>

        <p>
            <b>AI timeout:</b>
            {{ timeout }} seconds
        </p>

        <p>
            <b>Provider:</b>
            OpenRouter
        </p>

        <p>
            <b>Theme:</b>
            Black
        </p>

    </div>

</div>


<!-- MEMORY -->

<div
    id="memoryModal"
    class="modal">

    <div class="modal-box">

        <button
            class="close"
            onclick="closeMemory()">
            X
        </button>

        <h2>Memory</h2>

        <input
            id="memoryInput"
            placeholder="Tell X.ai something to remember..."
        >

        <button onclick="saveMemory()">
            Save Memory
        </button>

        <div
            id="memoryList"
            style="margin-top:20px;">
        </div>

    </div>

</div>


<script>

let currentChat = null;


/* LOGIN */

async function login() {

    const username =
        document.getElementById("username").value.trim();

    const password =
        document.getElementById("password").value;

    if (!username || !password) {

        document.getElementById("loginStatus").innerText =
            "Enter username and password.";

        return;
    }

    try {

        const response = await fetch("/login", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                username: username,
                password: password
            })

        });

        const data = await response.json();

        if (!response.ok) {

            document.getElementById("loginStatus").innerText =
                data.error || "Login failed.";

            return;
        }

        showApp();

    } catch (error) {

        document.getElementById("loginStatus").innerText =
            "Connection error.";

    }

}


/* REGISTER */

async function register() {

    const username =
        document.getElementById("username").value.trim();

    const password =
        document.getElementById("password").value;

    if (!username || !password) {

        document.getElementById("loginStatus").innerText =
            "Enter username and password.";

        return;
    }

    try {

        const response = await fetch("/register", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                username: username,
                password: password
            })

        });

        const data = await response.json();

        document.getElementById("loginStatus").innerText =
            data.message || data.error;

        if (response.ok) {
            showApp();
        }

    } catch (error) {

        document.getElementById("loginStatus").innerText =
            "Connection error.";

    }

}


/* SHOW APP */

async function showApp() {

    document.getElementById("loginScreen")
        .style.display = "none";

    document.getElementById("appScreen")
        .style.display = "flex";

    await loadUser();
    await loadChats();

}


/* USER */

async function loadUser() {

    const response =
        await fetch("/me");

    const data =
        await response.json();

    if (data.username) {

        document.getElementById("userName").innerText =
            "User: " + data.username;

    }

}


/* CHATS */

async function loadChats() {

    const response =
        await fetch("/chats");

    if (!response.ok) {
        return;
    }

    const chats =
        await response.json();

    const list =
        document.getElementById("chatList");

    list.innerHTML = "";

    chats.forEach(chat => {

        const item =
            document.createElement("div");

        item.className = "chat-item";

        if (chat.id === currentChat) {
            item.classList.add("active");
        }

        item.innerText = chat.title;

        item.onclick = function() {
            openChat(chat.id);
        };

        list.appendChild(item);

    });

}


/* NEW CHAT */

async function newChat() {

    const response =
        await fetch("/new_chat", {
            method: "POST"
        });

    const data =
        await response.json();

    if (!response.ok) {

        alert(data.error || "Could not create chat.");

        return;
    }

    currentChat = data.chat_id;

    document.getElementById("chatArea").innerHTML = "";

    document.getElementById("chatTitle").innerText =
        "New Chat";

    await loadChats();

}


/* OPEN CHAT */

async function openChat(chatId) {

    const response =
        await fetch("/chat/" + chatId);

    const data =
        await response.json();

    if (!response.ok) {

        alert(data.error || "Could not open chat.");

        return;
    }

    currentChat = chatId;

    document.getElementById("chatTitle").innerText =
        data.title;

    const area =
        document.getElementById("chatArea");

    area.innerHTML = "";

    data.messages.forEach(message => {

        addMessage(
            message.role,
            message.content
        );

    });

    await loadChats();

}


/* MESSAGE DISPLAY */

function addMessage(role, content) {

    const area =
        document.getElementById("chatArea");

    const message =
        document.createElement("div");

    message.className = "message";

    const avatar =
        document.createElement("div");

    avatar.className = "avatar";

    avatar.innerText =
        role === "user" ? "U" : "X";

    const text =
        document.createElement("div");

    text.className = "message-content";

    text.innerText = content;

    message.appendChild(avatar);
    message.appendChild(text);

    area.appendChild(message);

    area.scrollTop =
        area.scrollHeight;
}


/* SEND MESSAGE */

async function sendMessage() {

    const input =
        document.getElementById("messageInput");

    const text =
        input.value.trim();

    if (!text) {
        return;
    }

    if (!currentChat) {
        await newChat();
    }

    addMessage("user", text);

    input.value = "";

    document.getElementById("status").innerText =
        "X.ai is thinking...";

    try {

        const response =
            await fetch("/ask", {

                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    chat_id: currentChat,
                    message: text
                })

            });

        const data =
            await response.json();

        if (data.error) {

            addMessage(
                "assistant",
                "Error: " + data.error
            );

        } else {

            addMessage(
                "assistant",
                data.response
            );

        }

    } catch (error) {

        addMessage(
            "assistant",
            "Connection error: " + error.message
        );

    }

    document.getElementById("status").innerText =
        "X.ai is ready";

    await loadChats();

}


/* ENTER */

function handleKey(event) {

    if (event.key === "Enter") {

        event.preventDefault();

        sendMessage();

    }

}


/* LOGOUT */

async function logout() {

    await fetch("/logout", {
        method: "POST"
    });

    location.reload();

}


/* SETTINGS */

function openSettings() {

    document.getElementById("settingsModal")
        .style.display = "flex";

}


function closeSettings() {

    document.getElementById("settingsModal")
        .style.display = "none";

}


/* MEMORY */

async function openMemory() {

    document.getElementById("memoryModal")
        .style.display = "flex";

    await loadMemory();

}


function closeMemory() {

    document.getElementById("memoryModal")
        .style.display = "none";

}


async function saveMemory() {

    const input =
        document.getElementById("memoryInput");

    const memory =
        input.value.trim();

    if (!memory) {
        return;
    }

    const response =
        await fetch("/memory", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                memory: memory
            })

        });

    const data =
        await response.json();

    if (!response.ok) {

        alert(data.error || "Could not save memory.");

        return;
    }

    input.value = "";

    await loadMemory();

}


async function loadMemory() {

    const response =
        await fetch("/memory");

    if (!response.ok) {
        return;
    }

    const memories =
        await response.json();

    const list =
        document.getElementById("memoryList");

    list.innerHTML = "";

    memories.forEach(memory => {

        const div =
            document.createElement("div");

        div.style.padding = "8px 0";

        div.innerText =
            "• " + memory.memory;

        list.appendChild(div);

    });

}

</script>

</body>
</html>
"""


# ============================================================
# HOME
# ============================================================

@app.route("/")
def index():
    return render_template_string(
        HTML,
        model=MODEL,
        timeout=AI_TIMEOUT
    )


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["POST"])
def register():

    data = request.get_json(silent=True) or {}

    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({
            "error": "Username and password are required."
        }), 400

    conn = get_db()

    try:

        cursor = conn.execute("""
            INSERT INTO users
            (username, password, created_at)
            VALUES (?, ?, ?)
        """, (
            username,
            password,
            now()
        ))

        user_id = cursor.lastrowid

        conn.commit()

        session["user_id"] = user_id
        session["username"] = username

        make_chat(
            user_id,
            "New Chat"
        )

        return jsonify({
            "message": "Account created successfully."
        })

    except sqlite3.IntegrityError:

        return jsonify({
            "error": "Username already exists."
        }), 400

    finally:

        conn.close()


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["POST"])
def login():

    data = request.get_json(silent=True) or {}

    username = data.get("username", "").strip()
    password = data.get("password", "")

    conn = get_db()

    user = conn.execute("""
        SELECT *
        FROM users
        WHERE username = ? AND password = ?
    """, (
        username,
        password
    )).fetchone()

    conn.close()

    if not user:

        return jsonify({
            "error": "Incorrect username or password."
        }), 401

    session["user_id"] = user["id"]
    session["username"] = user["username"]

    return jsonify({
        "message": "Login successful."
    })


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout", methods=["POST"])
def logout():

    session.clear()

    return jsonify({
        "message": "Logged out."
    })


# ============================================================
# CURRENT USER
# ============================================================

@app.route("/me")
def me():

    if not current_user():
        return jsonify({})

    return jsonify({
        "username": session.get("username")
    })


# ============================================================
# GET CHATS
# ============================================================

@app.route("/chats")
@login_required
def chats():

    conn = get_db()

    rows = conn.execute("""
        SELECT id, title, created_at
        FROM chats
        WHERE user_id = ?
        ORDER BY id DESC
    """, (
        current_user(),
    )).fetchall()

    conn.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


# ============================================================
# NEW CHAT
# ============================================================

@app.route("/new_chat", methods=["POST"])
@login_required
def create_new_chat():

    chat_id = make_chat(
        current_user(),
        "New Chat"
    )

    return jsonify({
        "chat_id": chat_id
    })


# ============================================================
# OPEN CHAT
# ============================================================

@app.route("/chat/<int:chat_id>")
@login_required
def get_chat(chat_id):

    chat = check_chat_owner(
        chat_id,
        current_user()
    )

    if not chat:

        return jsonify({
            "error": "Chat not found."
        }), 404

    conn = get_db()

    messages = conn.execute("""
        SELECT role, content, created_at
        FROM messages
        WHERE chat_id = ?
        ORDER BY id ASC
    """, (
        chat_id,
    )).fetchall()

    conn.close()

    return jsonify({

        "id": chat["id"],

        "title": chat["title"],

        "messages": [
            dict(message)
            for message in messages
        ]

    })


# ============================================================
# ASK AI
# ============================================================

@app.route("/ask", methods=["POST"])
@login_required
def ask():

    data = request.get_json(silent=True) or {}

    chat_id = data.get("chat_id")
    message = data.get("message", "").strip()

    if not chat_id or not message:

        return jsonify({
            "error": "Invalid message."
        }), 400

    chat = check_chat_owner(
        chat_id,
        current_user()
    )

    if not chat:

        return jsonify({
            "error": "Chat not found."
        }), 404

    # --------------------------------------------------------
    # CHECK API KEY
    # --------------------------------------------------------

    if not OPENROUTER_API_KEY:

        return jsonify({
            "error": (
                "OPENROUTER_API_KEY is not configured. "
                "Add it to the environment variables."
            )
        }), 500

    conn = get_db()

    # --------------------------------------------------------
    # SAVE USER MESSAGE
    # --------------------------------------------------------

    conn.execute("""
        INSERT INTO messages
        (chat_id, role, content, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        chat_id,
        "user",
        message,
        now()
    ))

    # --------------------------------------------------------
    # GET CONVERSATION
    # --------------------------------------------------------

    rows = conn.execute("""
        SELECT role, content
        FROM messages
        WHERE chat_id = ?
        ORDER BY id ASC
    """, (
        chat_id,
    )).fetchall()

    # --------------------------------------------------------
    # GET MEMORY
    # --------------------------------------------------------

    memories = conn.execute("""
        SELECT memory
        FROM memories
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 20
    """, (
        current_user(),
    )).fetchall()

    conn.commit()
    conn.close()

    # --------------------------------------------------------
    # BUILD OPENROUTER MESSAGES
    # --------------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": (
                "You are X.ai, a helpful personal AI assistant. "
                "Be clear, friendly, useful and concise."
            )
        }
    ]

    if memories:

        memory_text = "\n".join(
            "- " + memory["memory"]
            for memory in memories
        )

        messages.append({
            "role": "system",
            "content": (
                "The following are memories saved by the user. "
                "Use them when relevant:\n\n"
                + memory_text
            )
        })

    for row in rows:

        role = row["role"]

        if role not in ["user", "assistant"]:
            continue

        messages.append({
            "role": role,
            "content": row["content"]
        })

    # --------------------------------------------------------
    # CALL OPENROUTER
    # --------------------------------------------------------

    headers = {
        "Authorization": "Bearer " + OPENROUTER_API_KEY,
        "Content-Type": "application/json",
        "HTTP-Referer": request.host_url,
        "X-Title": "X.ai"
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.7
    }

    try:

        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=AI_TIMEOUT
        )

    except requests.RequestException as error:

        return jsonify({
            "error": "Could not connect to OpenRouter: " + str(error)
        }), 502

    # --------------------------------------------------------
    # OPENROUTER ERROR
    # --------------------------------------------------------

    if response.status_code != 200:

        try:
            error_data = response.json()
        except Exception:
            error_data = response.text

        return jsonify({
            "error": "OpenRouter error: " + str(error_data)
        }), 502

    # --------------------------------------------------------
    # GET ANSWER
    # --------------------------------------------------------

    try:

        result = response.json()

        answer = result["choices"][0]["message"]["content"]

    except (KeyError, IndexError, TypeError, ValueError):

        return jsonify({
            "error": "Invalid response received from OpenRouter."
        }), 502

    if not answer:
        answer = "I couldn't generate a response."

    # --------------------------------------------------------
    # SAVE ASSISTANT MESSAGE
    # --------------------------------------------------------

    conn = get_db()

    conn.execute("""
        INSERT INTO messages
        (chat_id, role, content, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        chat_id,
        "assistant",
        answer,
        now()
    ))

    # --------------------------------------------------------
    # AUTOMATIC CHAT TITLE
    # --------------------------------------------------------

    if chat["title"] == "New Chat":

        title = message[:40]

        if len(message) > 40:
            title += "..."

        conn.execute("""
            UPDATE chats
            SET title = ?
            WHERE id = ?
        """, (
            title,
            chat_id
        ))

    conn.commit()
    conn.close()

    return jsonify({
        "response": answer
    })


# ============================================================
# MEMORY - GET
# ============================================================

@app.route("/memory", methods=["GET"])
@login_required
def get_memory():

    conn = get_db()

    memories = conn.execute("""
        SELECT id, memory, created_at
        FROM memories
        WHERE user_id = ?
        ORDER BY id DESC
    """, (
        current_user(),
    )).fetchall()

    conn.close()

    return jsonify([
        dict(memory)
        for memory in memories
    ])


# ============================================================
# MEMORY - SAVE
# ============================================================

@app.route("/memory", methods=["POST"])
@login_required
def save_memory():

    data = request.get_json(silent=True) or {}

    memory = data.get(
        "memory",
        ""
    ).strip()

    if not memory:

        return jsonify({
            "error": "Memory cannot be empty."
        }), 400

    conn = get_db()

    conn.execute("""
        INSERT INTO memories
        (user_id, memory, created_at)
        VALUES (?, ?, ?)
    """, (
        current_user(),
        memory,
        now()
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Memory saved."
    })


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    print()
    print("========================================")
    print("          X.AI STARTING")
    print("========================================")
    print()
    print("Host:")
    print(HOST)
    print()
    print("Port:")
    print(PORT)
    print()
    print("Local URL:")
    print("http://127.0.0.1:" + str(PORT))
    print()
    print("Model:")
    print(MODEL)
    print()
    print("AI timeout:")
    print(str(AI_TIMEOUT) + " seconds")
    print()
    print("Provider:")
    print("OpenRouter")
    print()
    print("========================================")
    print()

    app.run(
        host=HOST,
        port=PORT,
        debug=False
    )