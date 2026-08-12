import tkinter as tk
from tkinter import scrolledtext
import requests
import threading
import time

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2"

# HARD 21-SECOND TIMEOUT
AI_TIMEOUT = 21


def ask_ai():
    message = input_box.get("1.0", tk.END).strip()

    if not message:
        return

    input_box.delete("1.0", tk.END)

    chat_box.config(state=tk.NORMAL)
    chat_box.insert(tk.END, f"You: {message}\n\n")
    chat_box.insert(tk.END, "Spark.ai: Thinking...\n\n")
    chat_box.config(state=tk.DISABLED)
    chat_box.see(tk.END)

    send_button.config(state=tk.DISABLED)

    threading.Thread(
        target=get_response,
        args=(message,),
        daemon=True
    ).start()


def get_response(message):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": message,
                "stream": False
            },
            timeout=AI_TIMEOUT
        )

        response.raise_for_status()

        data = response.json()
        answer = data.get(
            "response",
            "Sorry, I couldn't answer."
        )

    except requests.Timeout:
        answer = "Spark.ai timed out after 21 seconds. Please try again."

    except requests.ConnectionError:
        answer = (
            "Could not connect to Ollama.\n"
            "Make sure Ollama is running."
        )

    except Exception as e:
        answer = f"Error: {e}"

    window.after(0, show_response, answer)


def show_response(answer):
    chat_box.config(state=tk.NORMAL)

    content = chat_box.get("1.0", tk.END)
    position = content.rfind("Spark.ai: Thinking...")

    if position != -1:
        chat_box.delete(
            f"1.0+{position}c",
            tk.END
        )

    chat_box.insert(
        tk.END,
        f"Spark.ai: {answer}\n\n"
    )

    chat_box.config(state=tk.DISABLED)
    chat_box.see(tk.END)

    send_button.config(state=tk.NORMAL)


def enter_pressed(event):
    ask_ai()
    return "break"


# ============================================================
# WINDOW
# ============================================================

window = tk.Tk()

window.title("Spark.ai ⚡")
window.geometry("850x600")
window.minsize(600, 450)

# ============================================================
# HEADER
# ============================================================

header = tk.Label(
    window,
    text="⚡ Spark.ai",
    font=("Arial", 24, "bold")
)

header.pack(pady=15)


# ============================================================
# WATCH
# ============================================================

watch_frame = tk.Frame(window)
watch_frame.pack(pady=2)

watch_label = tk.Label(
    watch_frame,
    text="⌚ SPARK.AI",
    font=("Arial", 12, "bold")
)

watch_label.pack()

time_label = tk.Label(
    watch_frame,
    text="00:00:00",
    font=("Consolas", 16, "bold")
)

time_label.pack()


def update_watch():
    current_time = time.strftime("%H:%M:%S")
    time_label.config(text=current_time)

    window.after(1000, update_watch)


update_watch()


# ============================================================
# CHAT
# ============================================================

chat_box = scrolledtext.ScrolledText(
    window,
    wrap=tk.WORD,
    font=("Arial", 12),
    state=tk.DISABLED
)

chat_box.pack(
    padx=20,
    pady=10,
    fill=tk.BOTH,
    expand=True
)


# ============================================================
# INPUT
# ============================================================

input_box = tk.Text(
    window,
    height=4,
    font=("Arial", 12)
)

input_box.pack(
    side=tk.LEFT,
    padx=(20, 10),
    pady=15,
    fill=tk.X,
    expand=True
)


# ============================================================
# SEND
# ============================================================

send_button = tk.Button(
    window,
    text="Send ⚡",
    font=("Arial", 12, "bold"),
    command=ask_ai
)

send_button.pack(
    side=tk.RIGHT,
    padx=(0, 20),
    pady=15
)

input_box.bind(
    "<Return>",
    enter_pressed
)


# ============================================================
# WELCOME
# ============================================================

chat_box.config(state=tk.NORMAL)

chat_box.insert(
    tk.END,
    "Spark.ai: Hello! I'm ready to help you. ⚡🤖\n\n"
)

chat_box.config(state=tk.DISABLED)


# ============================================================
# START
# ============================================================

window.mainloop()