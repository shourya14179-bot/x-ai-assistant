from flask import Flask, request, jsonify, session, render_template_string, redirect
import sqlite3
import requests
import secrets
import re
from functools import wraps
from datetime import datetime

# ============================================================
# X.AI - SINGLE FILE APP
# ============================================================

app = Flask(__name__)

app.secret_key = secrets.token_hex(32)

HOST = "127.0.0.1"
PORT = 5000

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "llama3.2"

# AI request timeout = 20 seconds
AI_TIMEOUT = 20

DB_FILE = "xai.db"


# ============================================================
# DATABASE
# ============================================================

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
        INSERT INTO chats (user_id, title, created_at)
        VALUES (?, ?, ?)
    """, (user_id, title, now()))

    chat_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return chat_id


def check_chat_owner(chat_id, user_id):
    conn = get_db()

    chat = conn.execute("""
        SELECT * FROM chats
        WHERE id = ? AND user_id = ?
    """, (chat_id, user_id)).fetchone()

    conn.close()

    return chat



# ============================================================
# AUTOMATIC MEMORY
# ============================================================

def automatic_memory(user_id, message):
    """
    Save only simple, useful long-term preferences/facts.
    Explicitly avoids common sensitive credential/payment data.
    """
    text = message.strip()
    lower = text.lower()

    blocked = [
        "password", "passcode", "otp", "one time password",
        "credit card", "bank account", "upi id",
        "phone number", "home address", "my address"
    ]

    if any(word in lower for word in blocked):
        return None

    memory = None

    patterns = [
        (r"\bmy favorite (.+?) is (.+)", "User's favorite {0} is {1}."),
        (r"\bmy name is ([A-Za-z0-9 _.-]{1,50})", "User's name is {0}."),
        (r"\bI like (.+)", "User likes {0}."),
        (r"\bI love (.+)", "User loves {0}."),
        (r"\bI prefer (.+)", "User prefers {0}."),
        (r"\bI(?:'m| am) working on (.+)", "User is working on {0}."),
        (r"\bI(?:'m| am) building (.+)", "User is building {0}."),
        (r"\bremember that (.+)", "User asked X.ai to remember: {0}")
    ]

    for pattern, template in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            values = [v.strip() for v in match.groups()]
            if all(1 <= len(v) <= 150 for v in values):
                memory = template.format(*values)
                break

    if not memory:
        return None

    conn = get_db()
    existing = conn.execute("""
        SELECT id FROM memories
        WHERE user_id = ? AND LOWER(memory) = LOWER(?)
    """, (user_id, memory)).fetchone()

    if existing:
        conn.close()
        return None

    conn.execute("""
        INSERT INTO memories (user_id, memory, created_at)
        VALUES (?, ?, ?)
    """, (user_id, memory, now()))

    conn.commit()
    conn.close()

    return memory


# ============================================================
# MAIN PAGE
# ============================================================

HTML = r"""
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
    box-shadow: 0 0 40px rgba(255,255,255,.05);
}

.logo {
    text-align: center;
    font-size: 38px;
    font-weight: bold;
    margin-bottom: 8px;
}

.subtitle {
    text-align: center;
    color: #999;
    margin-bottom: 25px;
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

button {
    border: 0;
    border-radius: 10px;
    padding: 11px 16px;
    cursor: pointer;
    color: white;
    background: #222;
}

button:hover {
    background: #333;
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
    margin: 0 auto 25px auto;
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

.message-content {
    line-height: 1.6;
    white-space: pre-wrap;
    word-wrap: break-word;
}

.user-message .avatar {
    background: white;
    color: black;
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
    resize: none;
}

.send {
    background: white;
    color: black;
    font-weight: bold;
}

.send:hover {
    background: #ddd;
}

.status {
    text-align: center;
    color: #777;
    font-size: 12px;
    margin-top: 8px;
}

/* SETTINGS */

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
    background: #111;
    border: 1px solid #333;
    border-radius: 15px;
    padding: 25px;
}

.modal-box h2 {
    margin-top: 0;
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


<!-- ======================================================
     LOGIN
====================================================== -->

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


<!-- ======================================================
     APP
====================================================== -->

<div id="appScreen">

    <div class="sidebar">

        <div class="sidebar-top">

            <div class="brand">
                X.ai
            </div>

            <button
                class="new-chat"
                onclick="newChat()">
                ＋ New Chat
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
                🧠 Memory
            </button>

            <button
                class="sidebar-button"
                onclick="openSettings()">
                ⚙ Settings
            </button>

            <button
                class="sidebar-button"
                onclick="logout()">
                ⇥ Logout
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


<!-- ======================================================
     SETTINGS MODAL
====================================================== -->

<div
    id="settingsModal"
    class="modal">

    <div class="modal-box">

        <button
            class="close"
            onclick="closeSettings()">
            ✕
        </button>

        <h2>Settings</h2>

        <p>
            <b>Model:</b> llama3.2
        </p>

        <p>
            <b>AI timeout:</b> 20 seconds
        </p>

        <p>
            <b>Theme:</b> Black
        </p>

        <p>
            X.ai local assistant
        </p>

    </div>

</div>


<!-- ======================================================
     MEMORY MODAL
====================================================== -->

<div
    id="memoryModal"
    class="modal">

    <div class="modal-box">

        <button
            class="close"
            onclick="closeMemory()">
            ✕
        </button>

        <h2>Memory</h2>

        <input
            id="memoryInput"
            placeholder="Tell X.ai something to remember..."
        >

        <button
            onclick="saveMemory()">
            Save Memory
        </button>

        <div
            id="memoryList"
            style="margin-top:20px;">
        </div>

    </div>

</div>


<script>

/* ============================================================
   STATE
============================================================ */

let currentChat = null;


/* ============================================================
   LOGIN
============================================================ */

async function login() {

    const username =
        document.getElementById("username").value;

    const password =
        document.getElementById("password").value;

    const response = await fetch("/login", {

        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({
            username,
            password
        })

    });

    const data = await response.json();

    if (!response.ok) {

        document.getElementById("loginStatus").innerText =
            data.error;

        return;
    }

    showApp();

}


/* ============================================================
   REGISTER
============================================================ */

async function register() {

    const username =
        document.getElementById("username").value;

    const password =
        document.getElementById("password").value;

    if (!username || !password) {

        document.getElementById("loginStatus").innerText =
            "Enter username and password.";

        return;
    }

    const response = await fetch("/register", {

        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({
            username,
            password
        })

    });

    const data = await response.json();

    document.getElementById("loginStatus").innerText =
        data.message || data.error;

}


/* ============================================================
   SHOW APP
============================================================ */

async function showApp() {

    document.getElementById("loginScreen").style.display =
        "none";

    document.getElementById("appScreen").style.display =
        "flex";

    await loadUser();
    await loadChats();

}


/* ============================================================
   USER
============================================================ */

async function loadUser() {

    const response =
        await fetch("/me");

    const data =
        await response.json();

    if (data.username) {

        document.getElementById("userName").innerText =
            "👤 " + data.username;

    }

}


/* ============================================================
   CHAT LIST
============================================================ */

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

        item.className =
            "chat-item";

        if (chat.id === currentChat) {
            item.classList.add("active");
        }

        item.innerText =
            chat.title;

        item.onclick = () => {
            openChat(chat.id);
        };

        list.appendChild(item);

    });

}


/* ============================================================
   NEW CHAT
============================================================ */

async function newChat() {

    const response =
        await fetch("/new_chat", {
            method: "POST"
        });

    const data =
        await response.json();

    currentChat =
        data.chat_id;

    document.getElementById("chatArea").innerHTML =
        "";

    document.getElementById("chatTitle").innerText =
        "New Chat";

    await loadChats();

}


/* ============================================================
   OPEN CHAT
============================================================ */

async function openChat(chatId) {

    currentChat =
        chatId;

    const response =
        await fetch("/chat/" + chatId);

    const data =
        await response.json();

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


/* ============================================================
   DISPLAY MESSAGE
============================================================ */

function addMessage(role, content) {

    const area =
        document.getElementById("chatArea");

    const message =
        document.createElement("div");

    message.className =
        "message";

    const avatar =
        document.createElement("div");

    avatar.className =
        "avatar";

    avatar.innerText =
        role === "user" ? "U" : "X";

    const text =
        document.createElement("div");

    text.className =
        "message-content";

    text.innerText =
        content;

    message.appendChild(avatar);

    message.appendChild(text);

    area.appendChild(message);

    area.scrollTop =
        area.scrollHeight;
}


/* ============================================================
   SEND MESSAGE
============================================================ */

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

    addMessage(
        "user",
        text
    );

    input.value = "";

    document.getElementById("status").innerText =
        "X.ai is thinking...";

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
            "⚠ " + data.error
        );

        if (data.memory_saved) {
            document.getElementById("status").innerText =
                "🧠 Memory saved";

            setTimeout(() => {
                document.getElementById("status").innerText =
                    "X.ai is ready";
            }, 2500);
        } else {
            document.getElementById("status").innerText =
                "X.ai is ready";
        }

    } else {

        addMessage(
            "assistant",
            data.response
        );

        if (data.memory_saved) {
            document.getElementById("status").innerText =
                "🧠 Memory saved";

            setTimeout(() => {
                document.getElementById("status").innerText =
                    "X.ai is ready";
            }, 2500);
        } else {
            document.getElementById("status").innerText =
                "X.ai is ready";
        }
    }

    await loadChats();

}


/* ============================================================
   ENTER KEY
============================================================ */

function handleKey(event) {

    if (event.key === "Enter") {

        event.preventDefault();

        sendMessage();

    }

}


/* ============================================================
   LOGOUT
============================================================ */

async function logout() {

    await fetch("/logout", {
        method: "POST"
    });

    location.reload();

}


/* ============================================================
   SETTINGS
============================================================ */

function openSettings() {

    document.getElementById("settingsModal")
        .style.display = "flex";

}

function closeSettings() {

    document.getElementById("settingsModal")
        .style.display = "none";

}


/* ============================================================
   MEMORY
============================================================ */

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

    await fetch("/memory", {

        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({
            memory
        })

    });

    input.value = "";

    await loadMemory();

}


async function deleteMemory(memoryId) {

    await fetch("/memory/" + memoryId, {
        method: "DELETE"
    });

    await loadMemory();
}


async function loadMemory() {

    const response =
        await fetch("/memory");

    const memories =
        await response.json();

    const list =
        document.getElementById("memoryList");

    list.innerHTML = "";

    memories.forEach(memory => {

        const div =
            document.createElement("div");

        div.style.padding =
            "8px 0";

        div.style.display = "flex";
        div.style.justifyContent = "space-between";
        div.style.gap = "10px";

        const text = document.createElement("span");
        text.innerText = "• " + memory.memory;

        const remove = document.createElement("button");
        remove.innerText = "Delete";
        remove.onclick = () => deleteMemory(memory.id);

        div.appendChild(text);
        div.appendChild(remove);

        list.appendChild(div);

    });

}

</script>

</body>

</html>
"""


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def index():
    return render_template_string(HTML)


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["POST"])
def register():

    data = request.get_json()

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
        """, (username, password, now()))

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

    data = request.get_json()

    username = data.get("username", "").strip()
    password = data.get("password", "")

    conn = get_db()

    user = conn.execute("""
        SELECT * FROM users
        WHERE username = ? AND password = ?
    """, (username, password)).fetchone()

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
    """, (current_user(),)).fetchall()

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
    """, (chat_id,)).fetchall()

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

    data = request.get_json()

    chat_id = data.get("chat_id")
    message = data.get("message", "").strip()

    if not chat_id or not message:

        return jsonify({
            "error": "Invalid message."
        }), 400

    # Automatically remember useful long-term information.
    memory_saved = automatic_memory(
        current_user(),
        message
    )

    chat = check_chat_owner(
        chat_id,
        current_user()
    )

    if not chat:

        return jsonify({
            "error": "Chat not found."
        }), 404

    conn = get_db()

    # Save user message

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

    # Get previous messages

    rows = conn.execute("""
        SELECT role, content
        FROM messages
        WHERE chat_id = ?
        ORDER BY id ASC
    """, (chat_id,)).fetchall()

    # Get memory

    memories = conn.execute("""
        SELECT memory
        FROM memories
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 20
    """, (current_user(),)).fetchall()

    conn.commit()
    conn.close()


    # --------------------------------------------------------
    # BUILD PROMPT
    # --------------------------------------------------------

    prompt = """
You are X.ai, a helpful personal AI assistant.

Be clear, friendly and useful.

User memories:
"""

    for memory in memories:
        prompt += "\n- " + memory["memory"]

    prompt += "\n\nConversation:\n"

    for row in rows:
        role = row["role"].upper()

        prompt += (
            f"\n{role}: {row['content']}"
        )

    prompt += "\n\nASSISTANT:"


    # --------------------------------------------------------
    # CALL OLLAMA
    # --------------------------------------------------------

    try:

        response = requests.post(

            OLLAMA_URL,

            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False
            },

            # IMPORTANT: 20-second timeout
            timeout=AI_TIMEOUT

        )

        response.raise_for_status()

        result = response.json()

        answer = result.get(
            "response",
            ""
        ).strip()

        if not answer:

            answer = "I didn't receive a response from the model."


    except requests.exceptions.Timeout:

        return jsonify({

            "error":
            "X.ai took longer than 20 seconds to respond. "
            "Please try again.",
            "memory_saved": bool(memory_saved),
            "memory": memory_saved

        }), 504


    except requests.exceptions.ConnectionError:

        return jsonify({

            "error":
            "Cannot connect to Ollama. "
            "Make sure Ollama is running.",
            "memory_saved": bool(memory_saved),
            "memory": memory_saved

        }), 503


    except Exception as e:

        return jsonify({

            "error":
            "AI error: " + str(e),
            "memory_saved": bool(memory_saved),
            "memory": memory_saved

        }), 500


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


    # Automatically create a title
    # from the first user message

    current_title = chat["title"]

    if current_title == "New Chat":

        title = message[:40]

        if len(message) > 40:
            title += "..."

        conn.execute("""
            UPDATE chats
            SET title = ?
            WHERE id = ?
        """, (title, chat_id))


    conn.commit()
    conn.close()


    return jsonify({
        "response": answer,
        "memory_saved": bool(memory_saved),
        "memory": memory_saved
    })


# ============================================================
# MEMORY
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
    """, (current_user(),)).fetchall()

    conn.close()

    return jsonify([
        dict(memory)
        for memory in memories
    ])


@app.route("/memory", methods=["POST"])
@login_required
def save_memory():

    data = request.get_json()

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



@app.route("/memory/<int:memory_id>", methods=["DELETE"])
@login_required
def delete_memory(memory_id):

    conn = get_db()

    result = conn.execute("""
        DELETE FROM memories
        WHERE id = ? AND user_id = ?
    """, (memory_id, current_user()))

    conn.commit()
    conn.close()

    if result.rowcount == 0:
        return jsonify({
            "error": "Memory not found."
        }), 404

    return jsonify({
        "message": "Memory deleted."
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
    print("Local URL:")
    print("http://127.0.0.1:5000")
    print()
    print("Model:")
    print(MODEL)
    print()
    print("AI timeout:")
    print(str(AI_TIMEOUT) + " seconds")
    print()
    print("Theme:")
    print("Black")
    print()
    print("========================================")
    print()

    app.run(
        host=HOST,
        port=PORT,
        debug=False
    )