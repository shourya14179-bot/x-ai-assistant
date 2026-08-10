import tkinter as tk
from tkinter import scrolledtext
import requests
import threading

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2"


def ask_ai():
    message = input_box.get("1.0", tk.END).strip()

    if not message:
        return

    input_box.delete("1.0", tk.END)

    chat_box.config(state=tk.NORMAL)
    chat_box.insert(tk.END, f"You: {message}\n\n")
    chat_box.insert(tk.END, "X.ai: Thinking...\n\n")
    chat_box.config(state=tk.DISABLED)
    chat_box.see(tk.END)

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
            timeout=120
        )

        data = response.json()
        answer = data.get("response", "Sorry, I couldn't answer.")

    except Exception as e:
        answer = f"Error: {e}"

    window.after(0, show_response, answer)


def show_response(answer):
    chat_box.config(state=tk.NORMAL)

    # Remove "Thinking..."
    content = chat_box.get("1.0", tk.END)
    position = content.rfind("X.ai: Thinking...")

    if position != -1:
        chat_box.delete(f"1.0+{position}c", tk.END)

    chat_box.insert(tk.END, f"X.ai: {answer}\n\n")
    chat_box.config(state=tk.DISABLED)
    chat_box.see(tk.END)


def enter_pressed(event):
    ask_ai()
    return "break"


# Window
window = tk.Tk()
window.title("X.ai")
window.geometry("850x600")
window.minsize(600, 450)

# Header
header = tk.Label(
    window,
    text="X.ai 🤖",
    font=("Arial", 24, "bold")
)
header.pack(pady=15)

# Chat
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

# Input area
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

send_button = tk.Button(
    window,
    text="Send",
    font=("Arial", 12, "bold"),
    command=ask_ai
)
send_button.pack(
    side=tk.RIGHT,
    padx=(0, 20),
    pady=15
)

input_box.bind("<Return>", enter_pressed)

chat_box.config(state=tk.NORMAL)
chat_box.insert(
    tk.END,
    "X.ai: Hello! I'm ready to help you. 🤖\n\n"
)
chat_box.config(state=tk.DISABLED)

window.mainloop()