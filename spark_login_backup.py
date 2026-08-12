import tkinter as tk
from tkinter import messagebox

def login():
    username = username_entry.get().strip()
    password = password_entry.get()

    if not username or not password:
        messagebox.showwarning(
            "Spark.ai",
            "Please enter username and password."
        )
        return

    # Temporary login for testing
    if username == "admin" and password == "1234":
        messagebox.showinfo(
            "Spark.ai",
            "Login successful! ⚡"
        )
        login_window.destroy()

        # Start your Spark.ai app
        import subprocess
        subprocess.Popen(
            ["python", "SparkAI_actual_app.py"]
        )

    else:
        messagebox.showerror(
            "Spark.ai",
            "Incorrect username or password."
        )


# Window
login_window = tk.Tk()
login_window.title("Spark.ai Login")
login_window.geometry("500x600")
login_window.configure(bg="#050812")
login_window.resizable(False, False)


# Logo
tk.Label(
    login_window,
    text="⚡",
    font=("Arial", 50, "bold"),
    fg="#8b7cff",
    bg="#050812"
).pack(pady=(45, 5))


tk.Label(
    login_window,
    text="Spark.ai",
    font=("Arial", 30, "bold"),
    fg="white",
    bg="#050812"
).pack()


tk.Label(
    login_window,
    text="YOUR AI • YOUR SPARK",
    font=("Arial", 9, "bold"),
    fg="#7483aa",
    bg="#050812"
).pack(pady=(5, 35))


# Login card
card = tk.Frame(
    login_window,
    bg="#10182b",
    padx=35,
    pady=30
)

card.pack(
    padx=45,
    fill=tk.X
)


tk.Label(
    card,
    text="Welcome back",
    font=("Arial", 20, "bold"),
    fg="white",
    bg="#10182b"
).pack(pady=(0, 25))


# Username
tk.Label(
    card,
    text="Username",
    font=("Arial", 10, "bold"),
    fg="#aab5d1",
    bg="#10182b"
).pack(anchor="w")


username_entry = tk.Entry(
    card,
    font=("Arial", 13),
    bg="#080e1d",
    fg="white",
    insertbackground="white",
    relief=tk.FLAT
)

username_entry.pack(
    fill=tk.X,
    ipady=10,
    pady=(6, 18)
)


# Password
tk.Label(
    card,
    text="Password",
    font=("Arial", 10, "bold"),
    fg="#aab5d1",
    bg="#10182b"
).pack(anchor="w")


password_entry = tk.Entry(
    card,
    font=("Arial", 13),
    bg="#080e1d",
    fg="white",
    insertbackground="white",
    show="*",
    relief=tk.FLAT
)

password_entry.pack(
    fill=tk.X,
    ipady=10,
    pady=(6, 25)
)


# Login button
login_button = tk.Button(
    card,
    text="LOGIN ⚡",
    font=("Arial", 13, "bold"),
    bg="#5b55e8",
    fg="white",
    activebackground="#746dff",
    activeforeground="white",
    relief=tk.FLAT,
    cursor="hand2",
    command=login
)

login_button.pack(
    fill=tk.X,
    ipady=10
)


tk.Label(
    login_window,
    text="Spark.ai • Local AI Assistant",
    font=("Arial", 8),
    fg="#687696",
    bg="#050812"
).pack(pady=25)


username_entry.focus_set()

login_window.bind(
    "<Return>",
    lambda event: login()
)

login_window.mainloop()