from flask import Flask, request, jsonify, session, render_template_string
import sqlite3
import requests
import secrets
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# ============================================================
# SPARK.AI - COMPLETE APP
# ============================================================
# Includes:
# - Spark.ai branding
# - Login + Register
# - Live background watch
# - 21-second hard HTTP timeout
# - Chat history
# - User memory
# - Membership
# - OpenRouter AI
# ============================================================

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))

PORT = int(os.getenv("PORT", "5000"))
DB_FILE = "xai.db"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.getenv("SPARK_MODEL", "openrouter/free")
AI_TIMEOUT = 21


# ============================================================
# DATABASE
# ============================================================

def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    conn = db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            membership TEXT DEFAULT 'free',
            created_at TEXT NOT NULL
        )
    """)

    # Upgrade an older database if membership is missing.
    columns = [x["name"] for x in conn.execute(
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
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            memory TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


init_db()


# ============================================================
# AUTH HELPERS
# ============================================================

def user_id():
    return session.get("user_id")


def login_required():
    return bool(user_id())


def password_ok(stored, supplied):
    try:
        if stored.startswith(("scrypt:", "pbkdf2:")):
            return check_password_hash(stored, supplied)
    except Exception:
        pass

    # Compatibility with an old plaintext database.
    return secrets.compare_digest(stored, supplied)


def owner_chat(chat_id):
    conn = db()
    row = conn.execute("""
        SELECT *
        FROM chats
        WHERE id = ? AND user_id = ?
    """, (chat_id, user_id())).fetchone()
    conn.close()
    return row


def create_chat(uid, title="New Chat"):
    conn = db()
    cur = conn.execute("""
        INSERT INTO chats(user_id, title, created_at)
        VALUES (?, ?, ?)
    """, (uid, title, now()))
    chat_id = cur.lastrowid
    conn.commit()
    conn.close()
    return chat_id


# ============================================================
# HTML
# ============================================================

PAGE = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Spark.ai</title>

<style>
*{box-sizing:border-box}
:root{
 --bg:#05070d;
 --panel:#0b101c;
 --panel2:#101726;
 --line:#222c40;
 --text:#f5f7ff;
 --muted:#8995ae;
 --blue:#168eff;
 --purple:#7048ff;
 --pink:#c13dff;
}
html,body{
 margin:0;width:100%;height:100%;
 font-family:Arial,Helvetica,sans-serif;
 background:var(--bg);color:var(--text);
}
body{overflow:hidden}
button,input{font:inherit}
button{cursor:pointer}

/* ---------- LOGIN ---------- */
#loginScreen{
 width:100%;height:100vh;display:flex;
 background:
 radial-gradient(circle at 15% 15%,rgba(20,130,255,.18),transparent 35%),
 radial-gradient(circle at 65% 85%,rgba(145,50,255,.15),transparent 35%),
 #05070d;
}
.login-left{
 width:54%;position:relative;overflow:hidden;
 padding:0;border-right:1px solid rgba(130,150,255,.14);
 background-color:#05070d;
 background-image:url('/static/spark_login.png');
 background-repeat:no-repeat;
 background-position:left center;
 background-size:200% 100%;
}
.login-right{
 width:46%;display:flex;align-items:center;justify-content:center;
 padding:30px;
}
.login-left>.brand,
.login-left>.hero,
.login-left>.watch,
.login-left>.footer{display:none}
.brand{
 display:flex;align-items:center;gap:9px;
 font-size:31px;font-weight:800;
}
.brand .bolt{
 font-size:42px;line-height:1;
 text-shadow:0 0 20px #5478ff;
}
.brand-name{
 background:linear-gradient(100deg,#fff,#8060ff,#18a8ff);
 -webkit-background-clip:text;background-clip:text;color:transparent;
}
.tagline{margin-left:49px;color:#7e8aa6;font-size:12px;margin-top:2px}

.hero{position:relative;z-index:2;margin-top:85px;max-width:610px}
.hero h1{
 margin:0;font-size:clamp(43px,5vw,72px);
 line-height:.98;letter-spacing:-3px
}
.hero .gradient{
 background:linear-gradient(90deg,#24a8ff,#7654ff,#d043ff);
 -webkit-background-clip:text;background-clip:text;color:transparent;
}
.hero p{
 color:#a5afc6;font-size:19px;line-height:1.5;max-width:530px;
 margin-top:24px;
}
.features{display:flex;gap:10px;margin-top:38px}
.feature{
 width:150px;padding:13px;border-radius:14px;
 border:1px solid rgba(120,145,255,.16);
 background:rgba(10,15,27,.7);
}
.feature b{display:block;margin-top:6px;font-size:13px}
.feature small{color:#77839d;font-size:10px}

/* ---------- WATCH ---------- */
.watch{
 position:absolute;width:520px;height:520px;
 right:-40px;bottom:-95px;
 transform:rotate(-8deg);
 opacity:.82;
 filter:drop-shadow(0 0 45px rgba(76,80,255,.25));
}
.strap{
 position:absolute;width:205px;height:610px;left:158px;top:-45px;
 border-radius:100px;
 background:linear-gradient(90deg,#070a12,#28314a,#070a12);
}
.case{
 position:absolute;width:390px;height:390px;left:65px;top:65px;
 border-radius:50%;padding:14px;
 background:linear-gradient(135deg,#7080a7,#151b2a 43%,#805bff);
 box-shadow:inset 0 0 0 3px #070a11,0 0 0 7px rgba(55,66,96,.5);
}
.face{
 width:100%;height:100%;border-radius:50%;position:relative;
 overflow:hidden;background:
 radial-gradient(circle at 44% 32%,#1a2b68,#080c1c 58%,#02040a);
 border:3px solid #11182a;
}
.face:before{
 content:"";position:absolute;inset:17px;border-radius:50%;
 border:1px solid rgba(120,155,255,.32)
}
.tick{
 position:absolute;left:50%;top:50%;width:2px;height:12px;
 background:#94b7ff;transform-origin:50% 168px;opacity:.8
}
.t1{transform:translate(-50%,-50%) rotate(0deg)}
.t2{transform:translate(-50%,-50%) rotate(30deg)}
.t3{transform:translate(-50%,-50%) rotate(60deg)}
.t4{transform:translate(-50%,-50%) rotate(90deg)}
.t5{transform:translate(-50%,-50%) rotate(120deg)}
.t6{transform:translate(-50%,-50%) rotate(150deg)}
.t7{transform:translate(-50%,-50%) rotate(180deg)}
.t8{transform:translate(-50%,-50%) rotate(210deg)}
.t9{transform:translate(-50%,-50%) rotate(240deg)}
.t10{transform:translate(-50%,-50%) rotate(270deg)}
.t11{transform:translate(-50%,-50%) rotate(300deg)}
.t12{transform:translate(-50%,-50%) rotate(330deg)}
.watch-title{
 position:absolute;top:100px;width:100%;text-align:center;
 font-weight:800;letter-spacing:1px;font-size:16px
}
.watch-sub{
 position:absolute;top:124px;width:100%;text-align:center;
 font-size:7px;letter-spacing:3px;color:#7b8aad
}
.hand{
 position:absolute;left:50%;bottom:50%;
 transform-origin:50% 100%;border-radius:8px;z-index:3
}
.hour{width:6px;height:85px;background:#c5d1ff}
.minute{width:4px;height:119px;background:#40adff}
.second{width:2px;height:139px;background:#d653ff}
.dot{
 position:absolute;width:13px;height:13px;left:50%;top:50%;
 transform:translate(-50%,-50%);border-radius:50%;
 background:white;border:3px solid #765cff;z-index:5
}
.watch-date{
 position:absolute;top:196px;left:50%;transform:translateX(-50%);
 padding:3px 8px;border:1px solid #39476e;background:#090e1c;
 border-radius:5px;font-size:10px;color:#d1dbf5
}
.footer{
 position:absolute;bottom:20px;left:5vw;color:#66718a;font-size:11px
}

/* ---------- LOGIN CARD ---------- */
.card{
 width:min(610px,100%);padding:42px 48px;border-radius:24px;
 background:rgba(8,12,22,.94);border:1px solid #283249;
 box-shadow:0 25px 80px rgba(0,0,0,.55);
}
.card h2{margin:0;font-size:34px}
.welcome{margin:8px 0 28px;color:#8995ad}
.label{font-size:12px;color:#9ca7bf;margin:15px 0 7px}
.field{
 width:100%;height:54px;border-radius:13px;border:1px solid #29344a;
 background:#080c15;color:white;padding:0 15px;outline:none;
}
.field:focus{border-color:#5a6cff;box-shadow:0 0 0 3px rgba(70,90,255,.1)}
.password{position:relative}
.password .field{padding-right:50px}
.eye{
 position:absolute;right:6px;top:7px;width:40px;height:40px;
 border:0;background:transparent;color:#8793ac
}
.forgot{text-align:right;color:#5790ff;font-size:12px;margin:10px 0 18px}
.primary{
 width:100%;height:55px;border:0;border-radius:13px;color:white;
 font-weight:700;background:linear-gradient(100deg,#168eff,#7048ff,#bd3cff);
}
.secondary,.create{
 width:100%;height:51px;border-radius:12px;
 background:#111725;color:#dbe2f4;border:1px solid #2b3549
}
.create{margin-top:10px;background:transparent;color:#a990ff;border-color:#6550ff}
.create-link{
 border:0;background:transparent;color:#5790ff;padding:0;
 font-weight:700;cursor:pointer
}
.create-link:hover{text-decoration:underline}
.divider{
 display:flex;gap:12px;align-items:center;color:#68738c;font-size:11px;margin:23px 0
}
.divider:before,.divider:after{content:"";height:1px;background:#20293a;flex:1}
.login-status{text-align:center;color:#ff8294;font-size:12px;min-height:18px;margin-top:13px}

/* ---------- APP ---------- */
#appScreen{display:none;width:100%;height:100vh}
.sidebar{
 position:fixed;left:0;top:0;width:250px;height:100vh;
 background:rgba(6,9,16,.96);border-right:1px solid #192233;
 display:flex;flex-direction:column;z-index:10
}
.side-brand{font-size:23px;font-weight:800;padding:23px}
.new-chat{
 margin:0 15px 12px;width:calc(100% - 30px);height:45px;
 border:0;border-radius:11px;color:white;font-weight:700;
 background:linear-gradient(100deg,#168eff,#7048ff)
}
.chat-list{flex:1;overflow:auto;padding:6px 11px}
.chat-item{
 padding:11px;border-radius:9px;color:#929db5;cursor:pointer;
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis
}
.chat-item:hover,.chat-item.active{background:#141b2a;color:white}
.bottom{border-top:1px solid #192233;padding:11px}
.user-name{color:#8995ae;padding:7px;font-size:12px}
.side-btn{
 width:100%;border:0;background:transparent;color:#9aa5bd;
 padding:10px;border-radius:8px;text-align:left
}
.side-btn:hover{background:#141b2a;color:white}
.main{margin-left:250px;height:100vh;display:flex;flex-direction:column}
.topbar{
 height:60px;border-bottom:1px solid #192233;display:flex;
 align-items:center;padding:0 22px;background:rgba(5,8,14,.8)
}
.chat-area{flex:1;overflow:auto;padding:30px 10%}
.message{max-width:850px;margin:0 auto 22px;display:flex;gap:12px}
.avatar{
 min-width:35px;height:35px;border-radius:50%;
 display:flex;align-items:center;justify-content:center;
 background:linear-gradient(135deg,#168eff,#7048ff);font-weight:800
}
.user-avatar{background:#edf1ff;color:#111}
.content{white-space:pre-wrap;line-height:1.65;word-break:break-word}
.input-area{
 padding:13px 10%;border-top:1px solid #192233;
 background:rgba(5,8,14,.86)
}
.input-box{
 max-width:850px;margin:auto;display:flex;gap:8px;padding:7px;
 border:1px solid #2b3549;border-radius:15px;background:#0e1421
}
#messageInput{
 flex:1;background:transparent;border:0;outline:0;color:white;padding:11px
}
.send{
 border:0;border-radius:10px;padding:0 19px;color:white;font-weight:700;
 background:linear-gradient(100deg,#168eff,#7048ff)
}
.status{text-align:center;color:#6e7a92;font-size:10px;margin-top:7px}

/* ---------- MODALS ---------- */
.modal{
 display:none;position:fixed;inset:0;z-index:40;
 background:rgba(0,0,0,.72);align-items:center;justify-content:center
}
.modal-box{
 width:420px;max-width:92%;max-height:80vh;overflow:auto;
 background:#0d1220;border:1px solid #2a3449;border-radius:18px;padding:24px
}
.modal-box h2{margin-top:0}
.close{
 float:right;border:0;background:transparent;color:#a1acc3;font-size:21px
}
.modal-input{
 width:100%;padding:12px;margin:8px 0;border-radius:9px;
 background:#080c15;border:1px solid #2b3549;color:white
}

/* ---------- RESPONSIVE ---------- */
@media(max-width:900px){
 .login-left{display:none}
 .login-right{width:100%;padding:18px}
 .sidebar{width:205px}
 .main{margin-left:205px}
 .chat-area,.input-area{padding-left:14px;padding-right:14px}
}
</style>
</head>

<body>

<!-- ============================================================
LOGIN
============================================================ -->

<div id="loginScreen">

<section class="login-left">
</section>

<section class="login-right">
 <div class="card">
   <h2>Welcome Back!</h2>
   <div class="welcome">
     Log in to continue to <b style="color:#9075ff">Spark.ai</b>
   </div>

   <div class="label">Username, email or mobile number</div>
   <input id="username" class="field"
          placeholder="Enter your username, email or mobile"
          autocomplete="username">

   <div class="label">Password</div>
   <div class="password">
     <input id="password" class="field" type="password"
            placeholder="Enter your password"
            autocomplete="current-password">
     <button class="eye" type="button" onclick="togglePassword()">◉</button>
   </div>

   <div class="forgot" onclick="forgot()">Forgot password?</div>

   <button class="primary" onclick="login()">Log in &nbsp;→</button>

   <div class="divider">OR</div>

   <button class="secondary" type="button" onclick="instagramLogin()">
     <span style="font-size:20px">◎</span>&nbsp; Log in with Instagram
   </button>

   <button class="secondary" type="button" style="margin-top:10px"
           onclick="facebookLogin()">
     <span style="font-size:20px">f</span>&nbsp; Log in with Facebook
   </button>

   <div style="text-align:center;color:#8995ad;margin-top:28px;font-size:13px">
     Don't have an account?
     <button class="create-link" type="button" onclick="register()">
       Create new account
     </button>
   </div>

   <div id="loginStatus" class="login-status"></div>
 </div>
</section>
</div>


<!-- ============================================================
APP
============================================================ -->

<div id="appScreen">

<aside class="sidebar">
 <div class="side-brand">ϟ Spark.ai</div>

 <button class="new-chat" onclick="newChat()">+ New Chat</button>

 <div id="chatList" class="chat-list"></div>

 <div class="bottom">
   <div id="userName" class="user-name"></div>

   <button class="side-btn" onclick="openMemory()">🧠 Memory</button>
   <button class="side-btn" onclick="openMembership()">⭐ Membership</button>
   <button class="side-btn" onclick="openSettings()">⚙ Settings</button>
   <button class="side-btn" onclick="logout()">↪ Logout</button>
 </div>
</aside>

<main class="main">

 <div class="topbar">
   <b id="chatTitle">New Chat</b>
 </div>

 <div id="chatArea" class="chat-area"></div>

 <div class="input-area">
   <div class="input-box">
     <input id="messageInput"
            placeholder="Message Spark.ai..."
            onkeydown="keySend(event)">
     <button class="send" onclick="sendMessage()">Send</button>
   </div>
   <div id="status" class="status">
     Spark.ai ready • 21-second maximum request
   </div>
 </div>

</main>
</div>


<!-- SETTINGS -->
<div id="settingsModal" class="modal">
 <div class="modal-box">
  <button class="close" onclick="closeModal('settingsModal')">×</button>
  <h2>⚙ Settings</h2>
  <p><b>App:</b> Spark.ai</p>
  <p><b>Model:</b> {{ model }}</p>
  <p><b>AI timeout:</b> 21 seconds</p>
  <p><b>Provider:</b> OpenRouter</p>
 </div>
</div>


<!-- MEMORY -->
<div id="memoryModal" class="modal">
 <div class="modal-box">
  <button class="close" onclick="closeModal('memoryModal')">×</button>
  <h2>🧠 Memory</h2>

  <input id="memoryInput" class="modal-input"
         placeholder="What should Spark.ai remember?">

  <button class="primary" onclick="saveMemory()">Save Memory</button>

  <div id="memoryList" style="margin-top:18px"></div>
 </div>
</div>


<!-- MEMBERSHIP -->
<div id="membershipModal" class="modal">
 <div class="modal-box">
  <button class="close" onclick="closeModal('membershipModal')">×</button>
  <h2>⭐ Spark.ai Membership</h2>

  <h3>Free</h3>
  <p>Basic Spark.ai access.</p>

  <h3>Pro</h3>
  <p>Premium membership placeholder.</p>

  <button class="primary" onclick="choosePro()">Choose Pro</button>
  <div id="membershipStatus" class="status"></div>
 </div>
</div>


<script>
let currentChat = null;


/* ============================================================
WATCH
============================================================ */

function updateWatch(){
 const d=new Date();
 const s=d.getSeconds()+d.getMilliseconds()/1000;
 const m=d.getMinutes()+s/60;
 const h=(d.getHours()%12)+m/60;

 const values=[
   ["hourHand",h*30],
   ["minuteHand",m*6],
   ["secondHand",s*6]
 ];

 values.forEach(([id,deg])=>{
   const e=document.getElementById(id);
   if(e)e.style.transform="translateX(-50%) rotate("+deg+"deg)";
 });

 const date=document.getElementById("watchDate");
 if(date)date.textContent=String(d.getDate()).padStart(2,"0");
}

setInterval(updateWatch,50);
updateWatch();


/* ============================================================
LOGIN
============================================================ */

function togglePassword(){
 const p=document.getElementById("password");
 p.type=p.type==="password"?"text":"password";
}

async function login(){
 const username=document.getElementById("username").value.trim();
 const password=document.getElementById("password").value;
 const status=document.getElementById("loginStatus");

 if(!username||!password){
   status.textContent="Enter username and password.";
   return;
 }

 status.textContent="Logging in...";

 try{
  const r=await fetch("/login",{
   method:"POST",
   headers:{"Content-Type":"application/json"},
   body:JSON.stringify({username,password})
  });

  const data=await r.json();

  if(!r.ok){
   status.textContent=data.error||"Login failed.";
   return;
  }

  await showApp();

 }catch(e){
  status.textContent="Connection error.";
 }
}

async function register(){
 const username=document.getElementById("username").value.trim();
 const password=document.getElementById("password").value;
 const status=document.getElementById("loginStatus");

 if(!username||!password){
   status.textContent="Enter username and password.";
   return;
 }

 if(password.length<6){
   status.textContent="Password must be at least 6 characters.";
   return;
 }

 status.textContent="Creating account...";

 try{
  const r=await fetch("/register",{
   method:"POST",
   headers:{"Content-Type":"application/json"},
   body:JSON.stringify({username,password})
  });

  const data=await r.json();

  if(!r.ok){
   status.textContent=data.error||"Registration failed.";
   return;
  }

  await showApp();

 }catch(e){
  status.textContent="Connection error.";
 }
}

function instagramLogin(){
  document.getElementById("loginStatus").textContent=
    "Instagram login is not connected yet.";
 }

 function facebookLogin(){
  document.getElementById("loginStatus").textContent=
    "Facebook login is not connected yet.";
 }

 function forgot(){
 document.getElementById("loginStatus").textContent=
   "Password recovery is not configured yet.";
}

function socialLogin(){
 document.getElementById("loginStatus").textContent=
   "Connected-account login is not configured yet.";
}


/* ============================================================
APP
============================================================ */

async function showApp(){
 document.getElementById("loginScreen").style.display="none";
 document.getElementById("appScreen").style.display="flex";

 await loadUser();
 await loadChats();

 if(!currentChat){
   await newChat();
 }
}

async function loadUser(){
 const r=await fetch("/me");
 if(!r.ok)return;

 const data=await r.json();

 if(data.username){
  document.getElementById("userName").textContent=
    "User: "+data.username;
 }
}


/* ============================================================
CHATS
============================================================ */

async function loadChats(){
 const r=await fetch("/chats");
 if(!r.ok)return;

 const chats=await r.json();
 const list=document.getElementById("chatList");
 list.innerHTML="";

 chats.forEach(chat=>{
   const div=document.createElement("div");
   div.className="chat-item";

   if(chat.id===currentChat)div.classList.add("active");

   div.textContent=chat.title;
   div.onclick=()=>openChat(chat.id);

   list.appendChild(div);
 });
}

async function newChat(){
 const r=await fetch("/new_chat",{method:"POST"});
 const data=await r.json();

 if(!r.ok){
   alert(data.error||"Could not create chat.");
   return;
 }

 currentChat=data.chat_id;

 document.getElementById("chatArea").innerHTML="";
 document.getElementById("chatTitle").textContent="New Chat";

 addMessage("assistant","Hello! I'm Spark.ai ⚡ How can I help you?");

 await loadChats();
}

async function openChat(id){
 const r=await fetch("/chat/"+id);
 const data=await r.json();

 if(!r.ok){
   alert(data.error||"Could not open chat.");
   return;
 }

 currentChat=id;
 document.getElementById("chatTitle").textContent=data.title;

 const area=document.getElementById("chatArea");
 area.innerHTML="";

 data.messages.forEach(x=>addMessage(x.role,x.content));

 await loadChats();
}

function addMessage(role,text){
 const area=document.getElementById("chatArea");

 const row=document.createElement("div");
 row.className="message";

 const avatar=document.createElement("div");
 avatar.className="avatar";

 if(role==="user"){
   avatar.classList.add("user-avatar");
   avatar.textContent="U";
 }else{
   avatar.textContent="ϟ";
 }

 const content=document.createElement("div");
 content.className="content";
 content.textContent=text;

 row.appendChild(avatar);
 row.appendChild(content);
 area.appendChild(row);

 area.scrollTop=area.scrollHeight;
}

async function sendMessage(){
 const input=document.getElementById("messageInput");
 const text=input.value.trim();

 if(!text)return;

 if(!currentChat){
   await newChat();
 }

 addMessage("user",text);
 input.value="";

 document.getElementById("status").textContent=
   "Spark.ai is thinking... maximum 21 seconds";

 try{
  const r=await fetch("/ask",{
   method:"POST",
   headers:{"Content-Type":"application/json"},
   body:JSON.stringify({
     chat_id:currentChat,
     message:text
   })
  });

  const data=await r.json();

  if(!r.ok){
    addMessage("assistant","Error: "+(data.error||"AI request failed."));
  }else{
    addMessage("assistant",data.response);
  }

 }catch(e){
  addMessage("assistant","Connection error: "+e.message);
 }

 document.getElementById("status").textContent=
   "Spark.ai ready • 21-second maximum request";

 await loadChats();
}

function keySend(e){
 if(e.key==="Enter"){
   e.preventDefault();
   sendMessage();
 }
}


/* ============================================================
MEMORY
============================================================ */

async function openMemory(){
 document.getElementById("memoryModal").style.display="flex";
 await loadMemory();
}

async function loadMemory(){
 const r=await fetch("/memory");
 if(!r.ok)return;

 const memories=await r.json();
 const list=document.getElementById("memoryList");
 list.innerHTML="";

 memories.forEach(x=>{
   const div=document.createElement("div");
   div.style.padding="8px 0";
   div.textContent="• "+x.memory;
   list.appendChild(div);
 });
}

async function saveMemory(){
 const input=document.getElementById("memoryInput");
 const memory=input.value.trim();

 if(!memory)return;

 const r=await fetch("/memory",{
  method:"POST",
  headers:{"Content-Type":"application/json"},
  body:JSON.stringify({memory})
 });

 const data=await r.json();

 if(!r.ok){
   alert(data.error||"Could not save memory.");
   return;
 }

 input.value="";
 await loadMemory();
}


/* ============================================================
MEMBERSHIP
============================================================ */

function openMembership(){
 document.getElementById("membershipModal").style.display="flex";
}

async function choosePro(){
 const r=await fetch("/membership",{
  method:"POST",
  headers:{"Content-Type":"application/json"},
  body:JSON.stringify({plan:"pro"})
 });

 const data=await r.json();

 document.getElementById("membershipStatus").textContent=
   data.message||data.error||"Done";
}


/* ============================================================
SETTINGS / LOGOUT
============================================================ */

function openSettings(){
 document.getElementById("settingsModal").style.display="flex";
}

function closeModal(id){
 document.getElementById(id).style.display="none";
}

async function logout(){
 await fetch("/logout",{method:"POST"});
 location.reload();
}
</script>

</body>
</html>
"""


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def home():
    return render_template_string(
        PAGE,
        model=MODEL
    )


@app.route("/register", methods=["POST"])
def register():
    data=request.get_json(silent=True) or {}

    username=str(data.get("username","")).strip()
    password=str(data.get("password",""))

    if len(username)<3:
        return jsonify(error="Username must be at least 3 characters."),400

    if len(password)<6:
        return jsonify(error="Password must be at least 6 characters."),400

    conn=db()

    try:
        cur=conn.execute("""
            INSERT INTO users(username,password,membership,created_at)
            VALUES(?,?,?,?)
        """,(
            username,
            generate_password_hash(password),
            "free",
            now()
        ))

        uid=cur.lastrowid
        conn.commit()

    except sqlite3.IntegrityError:
        conn.close()
        return jsonify(error="Username already exists."),400

    conn.close()

    session["user_id"]=uid
    session["username"]=username

    create_chat(uid)

    return jsonify(message="Account created.")


@app.route("/login", methods=["POST"])
def login():
    data=request.get_json(silent=True) or {}

    username=str(data.get("username","")).strip()
    password=str(data.get("password",""))

    conn=db()

    user=conn.execute("""
        SELECT * FROM users WHERE username=?
    """,(username,)).fetchone()

    if not user:
        conn.close()
        return jsonify(error="Incorrect username or password."),401

    if not password_ok(user["password"],password):
        conn.close()
        return jsonify(error="Incorrect username or password."),401

    # Upgrade old plaintext password after successful login.
    if not user["password"].startswith(("scrypt:","pbkdf2:")):
        conn.execute("""
            UPDATE users SET password=? WHERE id=?
        """,(generate_password_hash(password),user["id"]))
        conn.commit()

    conn.close()

    session["user_id"]=user["id"]
    session["username"]=user["username"]

    return jsonify(message="Login successful.")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify(message="Logged out.")


@app.route("/me")
def me():
    if not user_id():
        return jsonify({})

    return jsonify(username=session.get("username"))


@app.route("/chats")
def chats():
    if not login_required():
        return jsonify(error="Login required."),401

    conn=db()

    rows=conn.execute("""
        SELECT id,title,created_at
        FROM chats
        WHERE user_id=?
        ORDER BY id DESC
    """,(user_id(),)).fetchall()

    conn.close()

    return jsonify([dict(x) for x in rows])


@app.route("/new_chat", methods=["POST"])
def new_chat():
    if not login_required():
        return jsonify(error="Login required."),401

    return jsonify(chat_id=create_chat(user_id()))


@app.route("/chat/<int:chat_id>")
def chat(chat_id):
    if not login_required():
        return jsonify(error="Login required."),401

    row=owner_chat(chat_id)

    if not row:
        return jsonify(error="Chat not found."),404

    conn=db()

    messages=conn.execute("""
        SELECT role,content,created_at
        FROM messages
        WHERE chat_id=?
        ORDER BY id ASC
    """,(chat_id,)).fetchall()

    conn.close()

    return jsonify({
        "id":row["id"],
        "title":row["title"],
        "messages":[dict(x) for x in messages]
    })


@app.route("/ask", methods=["POST"])
def ask():
    if not login_required():
        return jsonify(error="Login required."),401

    data=request.get_json(silent=True) or {}

    chat_id=data.get("chat_id")
    text=str(data.get("message","")).strip()

    if not chat_id or not text:
        return jsonify(error="Message is empty."),400

    chat_row=owner_chat(chat_id)

    if not chat_row:
        return jsonify(error="Chat not found."),404

    if not OPENROUTER_API_KEY:
        return jsonify(
            error="OPENROUTER_API_KEY is not configured."
        ),500

    conn=db()

    conn.execute("""
        INSERT INTO messages(chat_id,role,content,created_at)
        VALUES(?,?,?,?)
    """,(chat_id,"user",text,now()))

    history=conn.execute("""
        SELECT role,content
        FROM messages
        WHERE chat_id=?
        ORDER BY id ASC
    """,(chat_id,)).fetchall()

    memories=conn.execute("""
        SELECT memory
        FROM memories
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 20
    """,(user_id(),)).fetchall()

    conn.commit()
    conn.close()

    messages=[{
        "role":"system",
        "content":
            "You are Spark.ai, a helpful AI assistant. "
            "Be clear, friendly and useful."
    }]

    if memories:
        memory_text="\n".join(
            "- "+x["memory"] for x in memories
        )

        messages.append({
            "role":"system",
            "content":
                "Relevant user memories:\n"+memory_text
        })

    for x in history:
        if x["role"] in ("user","assistant"):
            messages.append({
                "role":x["role"],
                "content":x["content"]
            })

    headers={
        "Authorization":"Bearer "+OPENROUTER_API_KEY,
        "Content-Type":"application/json",
        "X-Title":"Spark.ai",
        "HTTP-Referer":request.host_url
    }

    payload={
        "model":MODEL,
        "messages":messages,
        "temperature":0.7
    }

    try:
        # HARD network timeout: 21 seconds.
        response=requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=AI_TIMEOUT
        )

    except requests.Timeout:
        return jsonify(
            error="Spark.ai timed out after 21 seconds. Try again."
        ),504

    except requests.RequestException as e:
        return jsonify(
            error="AI connection error: "+str(e)
        ),502

    if response.status_code!=200:
        try:
            details=response.json()
        except Exception:
            details=response.text

        return jsonify(
            error="OpenRouter error: "+str(details)
        ),502

    try:
        result=response.json()
        answer=result["choices"][0]["message"]["content"]

    except Exception:
        return jsonify(
            error="Invalid AI response."
        ),502

    if not answer:
        answer="I could not generate a response."

    conn=db()

    conn.execute("""
        INSERT INTO messages(chat_id,role,content,created_at)
        VALUES(?,?,?,?)
    """,(chat_id,"assistant",answer,now()))

    if chat_row["title"]=="New Chat":
        title=text[:40]
        if len(text)>40:
            title+="..."

        conn.execute("""
            UPDATE chats SET title=? WHERE id=?
        """,(title,chat_id))

    conn.commit()
    conn.close()

    return jsonify(response=answer)


@app.route("/memory")
def get_memory():
    if not login_required():
        return jsonify(error="Login required."),401

    conn=db()

    rows=conn.execute("""
        SELECT id,memory,created_at
        FROM memories
        WHERE user_id=?
        ORDER BY id DESC
    """,(user_id(),)).fetchall()

    conn.close()

    return jsonify([dict(x) for x in rows])


@app.route("/memory", methods=["POST"])
def save_memory():
    if not login_required():
        return jsonify(error="Login required."),401

    data=request.get_json(silent=True) or {}
    memory=str(data.get("memory","")).strip()

    if not memory:
        return jsonify(error="Memory is empty."),400

    conn=db()

    conn.execute("""
        INSERT INTO memories(user_id,memory,created_at)
        VALUES(?,?,?)
    """,(user_id(),memory,now()))

    conn.commit()
    conn.close()

    return jsonify(message="Memory saved.")


@app.route("/membership", methods=["POST"])
def membership():
    if not login_required():
        return jsonify(error="Login required."),401

    data=request.get_json(silent=True) or {}
    plan=data.get("plan","free")

    if plan not in ("free","pro"):
        return jsonify(error="Invalid membership."),400

    conn=db()

    conn.execute("""
        UPDATE users SET membership=? WHERE id=?
    """,(plan,user_id()))

    conn.commit()
    conn.close()

    return jsonify(
        message="Membership set to "+plan.upper()+"."
    )


# ============================================================
# START
# ============================================================

if __name__=="__main__":
    print("")
    print("==========================================")
    print("             SPARK.AI")
    print("==========================================")
    print("URL: http://127.0.0.1:"+str(PORT))
    print("Model: "+MODEL)
    print("AI HTTP timeout: 21 seconds")
    print("==========================================")
    print("")

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False
    )
