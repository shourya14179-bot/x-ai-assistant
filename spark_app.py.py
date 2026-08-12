from flask import Flask, request, jsonify, session, render_template_string
import sqlite3
import requests
import secrets
import os
from functools import wraps
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# ============================================================
# SPARK.AI - FLASK AI ASSISTANT
# Login + Register + Chats + Memory + Membership
# OpenRouter + SQLite
# AI timeout: hard 21 seconds per request
# ============================================================

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "5000"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MODEL = "openrouter/free"
AI_TIMEOUT = 21

# Keep the old database filename so existing X.ai data can remain available.
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
            membership TEXT DEFAULT 'free',
            created_at TEXT NOT NULL
        )
    """)

    # Upgrade an older database that does not have membership yet.
    columns = [row["name"] for row in conn.execute(
        "PRAGMA table_info(users)"
    ).fetchall()]

    if "membership" not in columns:
        conn.execute(
            "ALTER TABLE users ADD COLUMN membership TEXT DEFAULT 'free'"
        )

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
            return jsonify({"error": "Please login first."}), 401
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


def verify_password(stored_password, supplied_password):
    # Supports old plaintext passwords from the previous version,
    # then upgrades them to a secure hash after a successful login.
    try:
        if stored_password.startswith(("pbkdf2:", "scrypt:")):
            return check_password_hash(stored_password, supplied_password)
    except Exception:
        pass
    return secrets.compare_digest(stored_password, supplied_password)


# ============================================================
# FRONTEND
# ============================================================

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Spark.ai</title>

<style>
* {
    box-sizing: border-box;
}

:root {
    --bg: #05070d;
    --panel: rgba(12, 16, 29, 0.86);
    --panel2: rgba(18, 23, 40, 0.82);
    --border: rgba(120, 145, 255, 0.22);
    --blue: #1688ff;
    --purple: #7c3cff;
    --pink: #c735ff;
    --text: #f7f8ff;
    --muted: #9ca7c2;
}

html, body {
    margin: 0;
    width: 100%;
    height: 100%;
    font-family: Inter, Arial, Helvetica, sans-serif;
    background: var(--bg);
    color: var(--text);
}

body {
    overflow: hidden;
}

button, input {
    font-family: inherit;
}

button {
    cursor: pointer;
}

/* ============================================================
   LOGIN
   ============================================================ */

#loginScreen {
    width: 100%;
    height: 100vh;
    display: flex;
    background:
        radial-gradient(circle at 10% 10%, rgba(20, 111, 255, .20), transparent 32%),
        radial-gradient(circle at 55% 80%, rgba(132, 39, 255, .16), transparent 35%),
        #05070d;
}

.login-left {
    width: 53%;
    position: relative;
    overflow: hidden;
    border-right: 1px solid rgba(120, 145, 255, .16);
    padding: 42px 5vw;
}

.login-right {
    width: 47%;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 35px;
    position: relative;
}

.brand {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 31px;
    font-weight: 800;
    letter-spacing: -1px;
}

.brand-bolt {
    width: 39px;
    height: 45px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 43px;
    line-height: 1;
    text-shadow: 0 0 18px #4d7dff;
}

.brand span {
    background: linear-gradient(100deg, #ffffff 35%, #7d5cff 68%, #18a8ff);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}

.tagline-small {
    color: #8994b0;
    font-size: 13px;
    margin-top: 2px;
    margin-left: 51px;
}

.hero {
    position: relative;
    z-index: 2;
    margin-top: 90px;
    max-width: 600px;
}

.hero h1 {
    font-size: clamp(42px, 5vw, 72px);
    line-height: .98;
    margin: 0;
    letter-spacing: -3px;
}

.hero h1 .spark {
    background: linear-gradient(90deg, #23a5ff, #7755ff, #cf43ff);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}

.hero p {
    color: #aab4cc;
    font-size: 20px;
    line-height: 1.5;
    max-width: 520px;
    margin-top: 24px;
}

.feature-row {
    display: flex;
    gap: 12px;
    margin-top: 42px;
    position: relative;
    z-index: 5;
}

.feature {
    min-width: 145px;
    padding: 14px 15px;
    border: 1px solid rgba(118, 145, 255, .17);
    background: rgba(12, 17, 30, .72);
    border-radius: 15px;
    backdrop-filter: blur(12px);
}

.feature-icon {
    font-size: 21px;
}

.feature b {
    display: block;
    margin-top: 7px;
    font-size: 13px;
}

.feature small {
    color: #7f8ba8;
    font-size: 11px;
}

.login-footer {
    position: absolute;
    left: 5vw;
    bottom: 22px;
    color: #69748d;
    font-size: 12px;
    z-index: 5;
}

/* Original Spark.ai watch */
.watch-wrap {
    position: absolute;
    width: 560px;
    height: 560px;
    right: -65px;
    bottom: -90px;
    opacity: .82;
    transform: rotate(-8deg);
    filter: drop-shadow(0 0 50px rgba(70, 89, 255, .22));
}

.watch-strap {
    position: absolute;
    width: 230px;
    height: 650px;
    left: 165px;
    top: -45px;
    border-radius: 100px;
    background: linear-gradient(90deg, #080b13, #27304a, #080b13);
    opacity: .8;
}

.watch-case {
    position: absolute;
    width: 410px;
    height: 410px;
    left: 75px;
    top: 75px;
    border-radius: 50%;
    padding: 15px;
    background: linear-gradient(135deg, #6878a5, #151b2a 42%, #7d5cff);
    box-shadow:
        inset 0 0 0 3px #080b12,
        0 0 0 8px rgba(45, 57, 86, .55),
        0 0 55px rgba(78, 79, 255, .24);
}

.watch-face {
    width: 100%;
    height: 100%;
    border-radius: 50%;
    position: relative;
    overflow: hidden;
    background:
        radial-gradient(circle at 45% 35%, #18265b, #070b18 60%, #02040a);
    border: 3px solid #131a2d;
}

.watch-face:before {
    content: "";
    position: absolute;
    inset: 17px;
    border: 1px solid rgba(117, 151, 255, .34);
    border-radius: 50%;
}

.tick {
    position: absolute;
    left: 50%;
    top: 50%;
    width: 2px;
    height: 13px;
    background: #94b7ff;
    transform-origin: 50% 177px;
    opacity: .8;
}

.t1 { transform: translate(-50%, -50%) rotate(0deg); }
.t2 { transform: translate(-50%, -50%) rotate(30deg); }
.t3 { transform: translate(-50%, -50%) rotate(60deg); }
.t4 { transform: translate(-50%, -50%) rotate(90deg); }
.t5 { transform: translate(-50%, -50%) rotate(120deg); }
.t6 { transform: translate(-50%, -50%) rotate(150deg); }
.t7 { transform: translate(-50%, -50%) rotate(180deg); }
.t8 { transform: translate(-50%, -50%) rotate(210deg); }
.t9 { transform: translate(-50%, -50%) rotate(240deg); }
.t10 { transform: translate(-50%, -50%) rotate(270deg); }
.t11 { transform: translate(-50%, -50%) rotate(300deg); }
.t12 { transform: translate(-50%, -50%) rotate(330deg); }

.watch-logo {
    position: absolute;
    top: 103px;
    width: 100%;
    text-align: center;
    font-weight: 800;
    font-size: 17px;
    letter-spacing: 1px;
    color: #dce5ff;
}

.watch-sub {
    position: absolute;
    top: 127px;
    width: 100%;
    text-align: center;
    font-size: 7px;
    color: #7585ac;
    letter-spacing: 3px;
}

.hand {
    position: absolute;
    left: 50%;
    bottom: 50%;
    transform-origin: 50% 100%;
    border-radius: 8px;
    z-index: 4;
}

.hour-hand {
    width: 6px;
    height: 92px;
    background: linear-gradient(#bfcaff, #6559ff);
    transform: translateX(-50%) rotate(35deg);
}

.minute-hand {
    width: 4px;
    height: 125px;
    background: linear-gradient(#ffffff, #3caeff);
    transform: translateX(-50%) rotate(132deg);
}

.second-hand {
    width: 2px;
    height: 145px;
    background: #d54dff;
    transform: translateX(-50%) rotate(210deg);
}

.center-dot {
    position: absolute;
    width: 13px;
    height: 13px;
    border-radius: 50%;
    background: #fff;
    border: 3px solid #765cff;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    z-index: 7;
}

.watch-date {
    position: absolute;
    top: 201px;
    left: 50%;
    transform: translateX(-50%);
    border: 1px solid #39476e;
    background: #090e1c;
    padding: 4px 9px;
    border-radius: 5px;
    color: #cbd6f3;
    font-size: 10px;
}

/* Login card */
.login-card {
    width: min(500px, 100%);
    padding: 42px;
    border: 1px solid rgba(126, 150, 255, .24);
    border-radius: 25px;
    background: rgba(9, 13, 24, .86);
    box-shadow: 0 25px 80px rgba(0,0,0,.48);
    backdrop-filter: blur(22px);
}

.login-card h2 {
    margin: 0;
    font-size: 34px;
    letter-spacing: -1px;
}

.login-card .welcome {
    color: #8d99b5;
    margin: 9px 0 32px;
}

.input-label {
    color: #9da8c0;
    font-size: 13px;
    margin: 18px 0 8px;
}

.field {
    width: 100%;
    height: 55px;
    border: 1px solid #29334a;
    border-radius: 14px;
    background: #090d17;
    color: white;
    padding: 0 16px;
    outline: none;
    font-size: 15px;
}

.field:focus {
    border-color: #4e6cff;
    box-shadow: 0 0 0 3px rgba(71, 95, 255, .10);
}

.password-wrap {
    position: relative;
}

.password-wrap .field {
    padding-right: 52px;
}

.eye {
    position: absolute;
    right: 10px;
    top: 9px;
    height: 37px;
    width: 37px;
    border: 0;
    background: transparent;
    color: #8f9bb7;
    font-size: 17px;
}

.forgot {
    text-align: right;
    margin: 11px 0 20px;
    color: #4f8dff;
    font-size: 13px;
    cursor: pointer;
}

.primary {
    width: 100%;
    height: 56px;
    border: 0;
    border-radius: 14px;
    color: white;
    font-size: 16px;
    font-weight: 700;
    background: linear-gradient(100deg, #148eff, #7048ff, #bd3cff);
    box-shadow: 0 10px 30px rgba(76, 71, 255, .24);
}

.primary:hover {
    filter: brightness(1.08);
}

.divider {
    display: flex;
    align-items: center;
    gap: 13px;
    margin: 25px 0;
    color: #68738b;
    font-size: 12px;
}

.divider:before, .divider:after {
    content: "";
    flex: 1;
    height: 1px;
    background: #20283b;
}

.secondary {
    width: 100%;
    height: 52px;
    border: 1px solid #2a3347;
    border-radius: 13px;
    background: #111625;
    color: #dbe2f5;
    font-size: 14px;
}

.create {
    width: 100%;
    height: 52px;
    margin-top: 12px;
    border: 1px solid #6650ff;
    border-radius: 13px;
    background: transparent;
    color: #a98bff;
    font-weight: 700;
}

.login-status {
    min-height: 20px;
    text-align: center;
    margin-top: 15px;
    color: #ff8092;
    font-size: 13px;
}

/* ============================================================
   APP
   ============================================================ */

#appScreen {
    display: none;
    width: 100%;
    height: 100vh;
}

.app-watch-bg {
    position: fixed;
    right: 40px;
    top: 105px;
    width: 310px;
    height: 310px;
    opacity: .08;
    pointer-events: none;
    z-index: 0;
}

.app-watch-bg .watch-case {
    transform: scale(.72);
    transform-origin: top left;
}

.sidebar {
    width: 255px;
    height: 100vh;
    background: rgba(6, 9, 16, .94);
    border-right: 1px solid #1a2232;
    position: fixed;
    left: 0;
    top: 0;
    display: flex;
    flex-direction: column;
    z-index: 5;
}

.side-brand {
    padding: 24px;
    font-size: 22px;
    font-weight: 800;
}

.new-chat {
    margin: 0 16px 15px;
    width: calc(100% - 32px);
    height: 46px;
    border: 0;
    border-radius: 12px;
    color: white;
    font-weight: 700;
    background: linear-gradient(100deg, #168eff, #7148ff);
}

.chat-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px 12px;
}

.chat-item {
    padding: 12px;
    margin-bottom: 4px;
    border-radius: 10px;
    color: #9ca8c1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    cursor: pointer;
}

.chat-item:hover, .chat-item.active {
    background: #141b2b;
    color: white;
}

.sidebar-bottom {
    border-top: 1px solid #1a2232;
    padding: 12px;
}

.user-name {
    color: #8d99b5;
    padding: 8px;
    font-size: 13px;
}

.side-btn {
    width: 100%;
    padding: 11px;
    margin-top: 4px;
    border: 0;
    border-radius: 9px;
    background: transparent;
    color: #9da8c1;
    text-align: left;
}

.side-btn:hover {
    background: #141b2b;
    color: white;
}

.main {
    margin-left: 255px;
    height: 100vh;
    display: flex;
    flex-direction: column;
    position: relative;
    z-index: 1;
}

.topbar {
    height: 62px;
    border-bottom: 1px solid #1a2232;
    display: flex;
    align-items: center;
    padding: 0 22px;
    background: rgba(5, 8, 14, .78);
    backdrop-filter: blur(15px);
}

.top-title {
    font-weight: 700;
}

.chat-area {
    flex: 1;
    overflow-y: auto;
    padding: 30px 12%;
}

.message {
    max-width: 850px;
    margin: 0 auto 24px;
    display: flex;
    gap: 13px;
}

.avatar {
    min-width: 35px;
    height: 35px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    background: linear-gradient(135deg, #138fff, #7847ff);
}

.user-message .avatar {
    background: #eef2ff;
    color: #10131c;
}

.message-content {
    line-height: 1.65;
    white-space: pre-wrap;
    word-wrap: break-word;
}

.input-area {
    padding: 14px 12%;
    border-top: 1px solid #1a2232;
    background: rgba(5, 8, 14, .82);
}

.input-box {
    max-width: 850px;
    margin: auto;
    display: flex;
    gap: 8px;
    padding: 7px;
    border: 1px solid #2b354b;
    border-radius: 16px;
    background: #0e1421;
}

#messageInput {
    flex: 1;
    border: 0;
    outline: 0;
    background: transparent;
    color: white;
    padding: 11px;
    font-size: 15px;
}

.send {
    border: 0;
    border-radius: 11px;
    padding: 0 20px;
    color: white;
    font-weight: 700;
    background: linear-gradient(100deg, #168eff, #7048ff);
}

.status {
    text-align: center;
    color: #6f7b94;
    font-size: 11px;
    margin-top: 8px;
}

/* ============================================================
   MODALS
   ============================================================ */

.modal {
    display: none;
    position: fixed;
    inset: 0;
    z-index: 30;
    background: rgba(0,0,0,.72);
    align-items: center;
    justify-content: center;
}

.modal-box {
    width: 420px;
    max-width: 92%;
    max-height: 80vh;
    overflow-y: auto;
    padding: 25px;
    border-radius: 18px;
    border: 1px solid #29334a;
    background: #0d1220;
}

.modal-box h2 {
    margin-top: 0;
}

.close {
    float: right;
    border: 0;
    background: transparent;
    color: #9aa6be;
    font-size: 20px;
}

.modal-box input {
    width: 100%;
    padding: 13px;
    margin: 8px 0;
    border-radius: 10px;
    border: 1px solid #2c354a;
    background: #080c15;
    color: white;
}

/* ============================================================
   RESPONSIVE
   ============================================================ */

@media (max-width: 900px) {
    .login-left {
        display: none;
    }

    .login-right {
        width: 100%;
        padding: 18px;
    }

    .login-card {
        padding: 28px;
    }

    .sidebar {
        width: 210px;
    }

    .main {
        margin-left: 210px;
    }

    .chat-area, .input-area {
        padding-left: 15px;
        padding-right: 15px;
    }
}
</style>
</head>

<body>

<!-- ============================================================
     LOGIN SCREEN
     ============================================================ -->

<div id="loginScreen">

    <section class="login-left">

        <div class="brand">
            <div class="brand-bolt">ϟ</div>
            <span>Spark.ai</span>
        </div>

        <div class="tagline-small">Your AI. Your Spark.</div>

        <div class="hero">
            <h1>
                Think Smart.<br>
                <span class="spark">Spark More.</span>
            </h1>

            <p>
                Your intelligent AI assistant for study, coding,
                creativity, football, gaming and everyday questions.
            </p>

            <div class="feature-row">
                <div class="feature">
                    <div class="feature-icon">⚡</div>
                    <b>Smart Answers</b>
                    <small>Fast and useful</small>
                </div>

                <div class="feature">
                    <div class="feature-icon">🧠</div>
                    <b>Memory</b>
                    <small>Remember what matters</small>
                </div>

                <div class="feature">
                    <div class="feature-icon">🛡️</div>
                    <b>Private</b>
                    <small>Your own account</small>
                </div>
            </div>
        </div>

        <!-- Spark.ai original watch -->
        <div class="watch-wrap">
            <div class="watch-strap"></div>
            <div class="watch-case">
                <div class="watch-face">
                    <div class="tick t1"></div>
                    <div class="tick t2"></div>
                    <div class="tick t3"></div>
                    <div class="tick t4"></div>
                    <div class="tick t5"></div>
                    <div class="tick t6"></div>
                    <div class="tick t7"></div>
                    <div class="tick t8"></div>
                    <div class="tick t9"></div>
                    <div class="tick t10"></div>
                    <div class="tick t11"></div>
                    <div class="tick t12"></div>

                    <div class="watch-logo">SPARK.AI</div>
                    <div class="watch-sub">YOUR AI • YOUR SPARK</div>
                    <div class="watch-date" id="watchDate">12</div>

                    <div class="hand hour-hand" id="hourHand"></div>
                    <div class="hand minute-hand" id="minuteHand"></div>
                    <div class="hand second-hand" id="secondHand"></div>
                    <div class="center-dot"></div>
                </div>
            </div>
        </div>

        <div class="login-footer">
            © 2026 Spark.ai • Your AI. Your Spark.
        </div>

    </section>


    <section class="login-right">

        <div class="login-card">

            <h2>Welcome Back!</h2>

            <div class="welcome">
                Log in to continue to <b style="color:#8a6cff;">Spark.ai</b>
            </div>

            <div class="input-label">Username or email</div>

            <input
                id="username"
                class="field"
                type="text"
                placeholder="Enter your username or email"
                autocomplete="username"
            >

            <div class="input-label">Password</div>

            <div class="password-wrap">
                <input
                    id="password"
                    class="field"
                    type="password"
                    placeholder="Enter your password"
                    autocomplete="current-password"
                >

                <button class="eye" onclick="togglePassword()" type="button">
                    ◉
                </button>
            </div>

            <div class="forgot" onclick="forgotPassword()">
                Forgot password?
            </div>

            <button class="primary" onclick="login()" type="button">
                Log in &nbsp; →
            </button>

            <div class="divider">OR</div>

            <button class="secondary" onclick="socialNotice()" type="button">
                Continue with a connected account
            </button>

            <button class="create" onclick="register()" type="button">
                Create new account
            </button>

            <div id="loginStatus" class="login-status"></div>

        </div>

    </section>
</div>


<!-- ============================================================
     APP SCREEN
     ============================================================ -->

<div id="appScreen">

    <div class="app-watch-bg">
        <div class="watch-case">
            <div class="watch-face">
                <div class="watch-logo">SPARK.AI</div>
                <div class="watch-sub">LIVE CLOCK</div>
                <div class="hand hour-hand" id="appHourHand"></div>
                <div class="hand minute-hand" id="appMinuteHand"></div>
                <div class="hand second-hand" id="appSecondHand"></div>
                <div class="center-dot"></div>
            </div>
        </div>
    </div>

    <aside class="sidebar">

        <div class="side-brand">ϟ Spark.ai</div>

        <button class="new-chat" onclick="newChat()">
            + New Chat
        </button>

        <div id="chatList" class="chat-list"></div>

        <div class="sidebar-bottom">

            <div id="userName" class="user-name"></div>

            <button class="side-btn" onclick="openMemory()">
                🧠 Memory
            </button>

            <button class="side-btn" onclick="openMembership()">
                ⭐ Membership
            </button>

            <button class="side-btn" onclick="openSettings()">
                ⚙ Settings
            </button>

            <button class="side-btn" onclick="logout()">
                ↪ Logout
            </button>

        </div>

    </aside>


    <main class="main">

        <div class="topbar">
            <div id="chatTitle" class="top-title">New Chat</div>
        </div>

        <div id="chatArea" class="chat-area"></div>

        <div class="input-area">

            <div class="input-box">

                <input
                    id="messageInput"
                    placeholder="Message Spark.ai..."
                    onkeydown="handleKey(event)"
                >

                <button class="send" onclick="sendMessage()">
                    Send
                </button>

            </div>

            <div id="status" class="status">
                Spark.ai is ready • 21s maximum AI request
            </div>

        </div>

    </main>
</div>


<!-- SETTINGS -->
<div id="settingsModal" class="modal">
    <div class="modal-box">
        <button class="close" onclick="closeSettings()">×</button>
        <h2>Settings</h2>
        <p><b>AI:</b> Spark.ai</p>
        <p><b>Model:</b> {{ model }}</p>
        <p><b>Maximum request time:</b> {{ timeout }} seconds</p>
        <p><b>Provider:</b> OpenRouter</p>
        <p><b>Theme:</b> Dark</p>
    </div>
</div>


<!-- MEMORY -->
<div id="memoryModal" class="modal">
    <div class="modal-box">
        <button class="close" onclick="closeMemory()">×</button>
        <h2>🧠 Memory</h2>

        <input
            id="memoryInput"
            placeholder="Tell Spark.ai something to remember..."
        >

        <button class="primary" style="margin-top:8px;"
                onclick="saveMemory()">
            Save Memory
        </button>

        <div id="memoryList" style="margin-top:20px;"></div>
    </div>
</div>


<!-- MEMBERSHIP -->
<div id="membershipModal" class="modal">
    <div class="modal-box">
        <button class="close" onclick="closeMembership()">×</button>

        <h2>⭐ Spark.ai Membership</h2>

        <h3>Free</h3>
        <p>Basic AI access</p>

        <h3>Pro</h3>
        <p>Higher limits and premium features</p>
        <p><b>₹299 / month</b></p>

        <button class="primary" onclick="selectPlan('pro')">
            Choose Pro
        </button>

        <div id="membershipStatus" class="status"></div>
    </div>
</div>


<script>
let currentChat = null;


/* ============================================================
   LIVE WATCH
   ============================================================ */

function updateWatch() {
    const now = new Date();

    const seconds = now.getSeconds() + now.getMilliseconds() / 1000;
    const minutes = now.getMinutes() + seconds / 60;
    const hours = (now.getHours() % 12) + minutes / 60;

    const hourDeg = hours * 30;
    const minuteDeg = minutes * 6;
    const secondDeg = seconds * 6;

    const hands = [
        ["hourHand", hourDeg],
        ["minuteHand", minuteDeg],
        ["secondHand", secondDeg],
        ["appHourHand", hourDeg],
        ["appMinuteHand", minuteDeg],
        ["appSecondHand", secondDeg]
    ];

    hands.forEach(([id, deg]) => {
        const element = document.getElementById(id);
        if (element) {
            element.style.transform =
                "translateX(-50%) rotate(" + deg + "deg)";
        }
    });

    const date = document.getElementById("watchDate");

    if (date) {
        date.innerText = String(now.getDate()).padStart(2, "0");
    }
}

setInterval(updateWatch, 50);
updateWatch();


/* ============================================================
   LOGIN
   ============================================================ */

function togglePassword() {
    const input = document.getElementById("password");

    input.type =
        input.type === "password"
            ? "text"
            : "password";
}


async function login() {
    const username =
        document.getElementById("username").value.trim();

    const password =
        document.getElementById("password").value;

    const status =
        document.getElementById("loginStatus");

    if (!username || !password) {
        status.innerText = "Enter username and password.";
        return;
    }

    status.innerText = "Logging in...";

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
            status.innerText = data.error || "Login failed.";
            return;
        }

        showApp();

    } catch (error) {
        status.innerText = "Connection error.";
    }
}


async function register() {
    const username =
        document.getElementById("username").value.trim();

    const password =
        document.getElementById("password").value;

    const status =
        document.getElementById("loginStatus");

    if (!username || !password) {
        status.innerText = "Enter username and password.";
        return;
    }

    status.innerText = "Creating account...";

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

        if (!response.ok) {
            status.innerText = data.error || "Registration failed.";
            return;
        }

        showApp();

    } catch (error) {
        status.innerText = "Connection error.";
    }
}


function forgotPassword() {
    document.getElementById("loginStatus").innerText =
        "Password recovery is not configured yet.";
}


function socialNotice() {
    document.getElementById("loginStatus").innerText =
        "Social login is not configured yet.";
}


/* ============================================================
   APP
   ============================================================ */

async function showApp() {
    document.getElementById("loginScreen").style.display = "none";
    document.getElementById("appScreen").style.display = "flex";

    await loadUser();
    await loadChats();

    if (!currentChat) {
        await newChat();
    }
}


async function loadUser() {
    const response = await fetch("/me");
    const data = await response.json();

    if (data.username) {
        document.getElementById("userName").innerText =
            "User: " + data.username;
    }
}


/* ============================================================
   CHATS
   ============================================================ */

async function loadChats() {
    const response = await fetch("/chats");

    if (!response.ok) return;

    const chats = await response.json();
    const list = document.getElementById("chatList");

    list.innerHTML = "";

    chats.forEach(chat => {
        const item = document.createElement("div");

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


async function newChat() {
    const response = await fetch("/new_chat", {
        method: "POST"
    });

    const data = await response.json();

    if (!response.ok) {
        alert(data.error || "Could not create chat.");
        return;
    }

    currentChat = data.chat_id;

    document.getElementById("chatArea").innerHTML = "";
    document.getElementById("chatTitle").innerText = "New Chat";

    addMessage(
        "assistant",
        "Hello! I'm Spark.ai ⚡ How can I help you?"
    );

    await loadChats();
}


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
        addMessage(message.role, message.content);
    });

    await loadChats();
}


function addMessage(role, content) {
    const area = document.getElementById("chatArea");

    const message = document.createElement("div");
    message.className = "message";

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.innerText = role === "user" ? "U" : "ϟ";

    const text = document.createElement("div");
    text.className = "message-content";
    text.innerText = content;

    message.appendChild(avatar);
    message.appendChild(text);

    area.appendChild(message);
    area.scrollTop = area.scrollHeight;
}


async function sendMessage() {
    const input =
        document.getElementById("messageInput");

    const text = input.value.trim();

    if (!text) return;

    if (!currentChat) {
        await newChat();
    }

    addMessage("user", text);
    input.value = "";

    document.getElementById("status").innerText =
        "Spark.ai is thinking... (maximum 21 seconds)";

    try {
        const response = await fetch("/ask", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                chat_id: currentChat,
                message: text
            })
        });

        const data = await response.json();

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
        "Spark.ai is ready • 21s maximum AI request";

    await loadChats();
}


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
    document.getElementById("settingsModal").style.display = "flex";
}

function closeSettings() {
    document.getElementById("settingsModal").style.display = "none";
}


/* ============================================================
   MEMORY
   ============================================================ */

async function openMemory() {
    document.getElementById("memoryModal").style.display = "flex";
    await loadMemory();
}

function closeMemory() {
    document.getElementById("memoryModal").style.display = "none";
}


async function saveMemory() {
    const input =
        document.getElementById("memoryInput");

    const memory =
        input.value.trim();

    if (!memory) return;

    const response = await fetch("/memory", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            memory: memory
        })
    });

    const data = await response.json();

    if (!response.ok) {
        alert(data.error || "Could not save memory.");
        return;
    }

    input.value = "";
    await loadMemory();
}


async function loadMemory() {
    const response = await fetch("/memory");

    if (!response.ok) return;

    const memories = await response.json();

    const list =
        document.getElementById("memoryList");

    list.innerHTML = "";

    memories.forEach(memory => {
        const div = document.createElement("div");

        div.style.padding = "8px 0";
        div.innerText = "• " + memory.memory;

        list.appendChild(div);
    });
}


/* ============================================================
   MEMBERSHIP
   ============================================================ */

function openMembership() {
    document.getElementById("membershipModal").style.display = "flex";
}

function closeMembership() {
    document.getElementById("membershipModal").style.display = "none";
}


async function selectPlan(plan) {
    const response = await fetch("/membership", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            plan: plan
        })
    });

    const data = await response.json();

    document.getElementById("membershipStatus").innerText =
        data.message || data.error || "Done";
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
    return render_template_string(
        HTML,
        model=MODEL,
        timeout=AI_TIMEOUT
    )


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    username = data.get("username", "").strip()
    password = data.get("password", "")

    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters."}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    conn = get_db()

    try:
        cursor = conn.execute("""
            INSERT INTO users
            (username, password, membership, created_at)
            VALUES (?, ?, 'free', ?)
        """, (
            username,
            generate_password_hash(password),
            now()
        ))

        user_id = cursor.lastrowid

        conn.commit()

        session["user_id"] = user_id
        session["username"] = username

        make_chat(user_id, "New Chat")

        return jsonify({
            "message": "Account created successfully."
        })

    except sqlite3.IntegrityError:
        return jsonify({
            "error": "Username already exists."
        }), 400

    finally:
        conn.close()


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    username = data.get("username", "").strip()
    password = data.get("password", "")

    conn = get_db()

    user = conn.execute("""
        SELECT * FROM users
        WHERE username = ?
    """, (username,)).fetchone()

    if not user:
        conn.close()
        return jsonify({
            "error": "Incorrect username or password."
        }), 401

    if not verify_password(user["password"], password):
        conn.close()
        return jsonify({
            "error": "Incorrect username or password."
        }), 401

    # Upgrade old plaintext password to a secure hash.
    if not user["password"].startswith(("pbkdf2:", "scrypt:")):
        conn.execute("""
            UPDATE users
            SET password = ?
            WHERE id = ?
        """, (
            generate_password_hash(password),
            user["id"]
        ))
        conn.commit()

    conn.close()

    session["user_id"] = user["id"]
    session["username"] = user["username"]

    return jsonify({
        "message": "Login successful."
    })


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out."})


@app.route("/me")
def me():
    if not current_user():
        return jsonify({})

    return jsonify({
        "username": session.get("username")
    })


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

    return jsonify([dict(row) for row in rows])


@app.route("/new_chat", methods=["POST"])
@login_required
def create_new_chat():
    chat_id = make_chat(current_user(), "New Chat")
    return jsonify({"chat_id": chat_id})


@app.route("/chat/<int:chat_id>")
@login_required
def get_chat(chat_id):
    chat = check_chat_owner(chat_id, current_user())

    if not chat:
        return jsonify({"error": "Chat not found."}), 404

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
        "messages": [dict(message) for message in messages]
    })


@app.route("/ask", methods=["POST"])
@login_required
def ask():
    data = request.get_json(silent=True) or {}

    chat_id = data.get("chat_id")
    message = data.get("message", "").strip()

    if not chat_id or not message:
        return jsonify({"error": "Invalid message."}), 400

    chat = check_chat_owner(chat_id, current_user())

    if not chat:
        return jsonify({"error": "Chat not found."}), 404

    if not OPENROUTER_API_KEY:
        return jsonify({
            "error": "OPENROUTER_API_KEY is not configured."
        }), 500

    conn = get_db()

    conn.execute("""
        INSERT INTO messages
        (chat_id, role, content, created_at)
        VALUES (?, 'user', ?, ?)
    """, (chat_id, message, now()))

    rows = conn.execute("""
        SELECT role, content
        FROM messages
        WHERE chat_id = ?
        ORDER BY id ASC
    """, (chat_id,)).fetchall()

    memories = conn.execute("""
        SELECT memory
        FROM memories
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 20
    """, (current_user(),)).fetchall()

    conn.commit()
    conn.close()

    messages = [{
        "role": "system",
        "content": (
            "You are Spark.ai, a helpful personal AI assistant. "
            "Be clear, friendly, useful and concise."
        )
    }]

    if memories:
        memory_text = "\n".join(
            "- " + memory["memory"] for memory in memories
        )

        messages.append({
            "role": "system",
            "content": (
                "The following are memories saved by the user. "
                "Use them only when relevant:\n\n" + memory_text
            )
        })

    for row in rows:
        if row["role"] not in ["user", "assistant"]:
            continue

        messages.append({
            "role": row["role"],
            "content": row["content"]
        })

    headers = {
        "Authorization": "Bearer " + OPENROUTER_API_KEY,
        "Content-Type": "application/json",
        "HTTP-Referer": request.host_url,
        "X-Title": "Spark.ai"
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.7
    }

    try:
        # Hard HTTP timeout is 21 seconds.
        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=AI_TIMEOUT
        )

    except requests.Timeout:
        return jsonify({
            "error": "Spark.ai timed out after 21 seconds. Please try again."
        }), 504

    except requests.RequestException as error:
        return jsonify({
            "error": "Could not connect to OpenRouter: " + str(error)
        }), 502

    if response.status_code != 200:
        try:
            error_data = response.json()
        except Exception:
            error_data = response.text

        return jsonify({
            "error": "OpenRouter error: " + str(error_data)
        }), 502

    try:
        result = response.json()
        answer = result["choices"][0]["message"]["content"]

    except (KeyError, IndexError, TypeError, ValueError):
        return jsonify({
            "error": "Invalid response received from OpenRouter."
        }), 502

    if not answer:
        answer = "I couldn't generate a response."

    conn = get_db()

    conn.execute("""
        INSERT INTO messages
        (chat_id, role, content, created_at)
        VALUES (?, 'assistant', ?, ?)
    """, (chat_id, answer, now()))

    if chat["title"] == "New Chat":
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

    return jsonify({"response": answer})


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

    return jsonify([dict(memory) for memory in memories])


@app.route("/memory", methods=["POST"])
@login_required
def save_memory():
    data = request.get_json(silent=True) or {}

    memory = data.get("memory", "").strip()

    if not memory:
        return jsonify({"error": "Memory cannot be empty."}), 400

    conn = get_db()

    conn.execute("""
        INSERT INTO memories
        (user_id, memory, created_at)
        VALUES (?, ?, ?)
    """, (current_user(), memory, now()))

    conn.commit()
    conn.close()

    return jsonify({"message": "Memory saved."})


@app.route("/membership", methods=["POST"])
@login_required
def membership():
    data = request.get_json(silent=True) or {}
    plan = data.get("plan", "free")

    if plan not in ["free", "pro"]:
        return jsonify({"error": "Invalid membership plan."}), 400

    conn = get_db()

    conn.execute("""
        UPDATE users
        SET membership = ?
        WHERE id = ?
    """, (plan, current_user()))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Membership changed to " + plan.upper() + "."
    })


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    print()
    print("========================================")
    print("          SPARK.AI STARTING")
    print("========================================")
    print("Local URL: http://127.0.0.1:" + str(PORT))
    print("Model: " + MODEL)
    print("AI timeout: " + str(AI_TIMEOUT) + " seconds")
    print("Provider: OpenRouter")
    print("========================================")
    print()

    app.run(
        host=HOST,
        port=PORT,
        debug=False
    )
