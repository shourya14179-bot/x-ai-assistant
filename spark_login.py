from flask import Flask, request, redirect, session, render_template_string
import sqlite3
import hashlib

app = Flask(__name__)
app.secret_key = "spark-ai-secret-key-change-this"

DB = "users.db"


def get_db():
    conn = sqlite3.connect(DB, timeout=15)
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Spark.ai Login</title>

    <style>
        body {
            font-family: Arial;
            background: #111;
            color: white;
            text-align: center;
            padding-top: 100px;
        }

        .box {
            width: 320px;
            margin: auto;
            padding: 30px;
            background: #222;
            border-radius: 15px;
        }

        input {
            width: 90%;
            padding: 12px;
            margin: 8px;
            border-radius: 8px;
            border: none;
            box-sizing: border-box;
        }

        button {
            padding: 12px 25px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            background: #00aaff;
            color: white;
        }

        a {
            color: #00aaff;
        }
    </style>
</head>

<body>

<div class="box">

<h1>⚡ Spark.ai</h1>
<h2>Login</h2>

<form method="POST">

<input type="text"
       name="username"
       placeholder="Username"
       required>

<input type="password"
       name="password"
       placeholder="Password"
       required>

<br>

<button type="submit">LOGIN ⚡</button>

</form>

<p>{{ message }}</p>

<p>
Don't have an account?
<a href="/register">Create Account</a>
</p>

</div>

</body>
</html>
"""


REGISTER_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Create Spark.ai Account</title>

    <style>
        body {
            font-family: Arial;
            background: #111;
            color: white;
            text-align: center;
            padding-top: 100px;
        }

        .box {
            width: 320px;
            margin: auto;
            padding: 30px;
            background: #222;
            border-radius: 15px;
        }

        input {
            width: 90%;
            padding: 12px;
            margin: 8px;
            border-radius: 8px;
            border: none;
            box-sizing: border-box;
        }

        button {
            padding: 12px 25px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            background: #00aaff;
            color: white;
        }

        a {
            color: #00aaff;
        }
    </style>
</head>

<body>

<div class="box">

<h1>⚡ Spark.ai</h1>
<h2>Create Account</h2>

<form method="POST">

<input type="text"
       name="username"
       placeholder="Choose username"
       required>

<input type="password"
       name="password"
       placeholder="Choose password"
       required>

<br>

<button type="submit">CREATE ACCOUNT</button>

</form>

<p>{{ message }}</p>

<p>
Already have an account?
<a href="/">Login</a>
</p>

</div>

</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def login():

    message = ""

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = None

        try:
            conn = get_db()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT password FROM users WHERE username = ?",
                (username,)
            )

            user = cursor.fetchone()

        except sqlite3.Error as e:
            print("Database error:", e)
            message = "❌ Database error. Please try again."
            user = None

        finally:
            if conn:
                conn.close()

        if user and user[0] == hash_password(password):

            session["username"] = username

            return f"""
            <!DOCTYPE html>
            <html>
            <body style="font-family:Arial;text-align:center;padding-top:100px;background:#111;color:white;">

            <h1>⚡ Login Successful!</h1>
            <h2>Welcome, {username}!</h2>
            <p>Spark.ai is ready.</p>

            <a href="/logout" style="color:#00aaff;">Logout</a>

            </body>
            </html>
            """

        elif not message:
            message = "❌ Incorrect username or password."

    return render_template_string(
        LOGIN_PAGE,
        message=message
    )


@app.route("/register", methods=["GET", "POST"])
def register():

    message = ""

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if len(username) < 3 or len(password) < 4:

            message = "Username must be 3+ characters and password 4+ characters."

        else:

            conn = None

            try:

                conn = get_db()
                cursor = conn.cursor()

                cursor.execute(
                    "INSERT INTO users (username, password) VALUES (?, ?)",
                    (username, hash_password(password))
                )

                conn.commit()

                return redirect("/")

            except sqlite3.IntegrityError:

                message = "❌ Username already exists."

            except sqlite3.Error as e:

                print("Database error:", e)
                message = "❌ Database error. Please try again."

            finally:

                if conn:
                    conn.close()

    return render_template_string(
        REGISTER_PAGE,
        message=message
    )


@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


if __name__ == "__main__":

    init_db()

    print("⚡ Spark.ai Login Server Starting...")
    print("Open: http://127.0.0.1:5000")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )