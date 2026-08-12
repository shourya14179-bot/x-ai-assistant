import tkinter as tk
from tkinter import scrolledtext
import requests
import threading
import time
import math

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2"
AI_TIMEOUT = 21

# ---------------- AI ----------------

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
        answer = data.get("response", "Sorry, I couldn't answer.")

    except requests.Timeout:
        answer = "Spark.ai timed out after 21 seconds. Please try again."

    except requests.ConnectionError:
        answer = "Could not connect to Ollama. Make sure Ollama is running."

    except Exception as e:
        answer = f"Error: {e}"

    window.after(0, show_response, answer)


def show_response(answer):
    chat_box.config(state=tk.NORMAL)

    content = chat_box.get("1.0", tk.END)
    position = content.rfind("Spark.ai: Thinking...")

    if position != -1:
        chat_box.delete(f"1.0+{position}c", tk.END)

    chat_box.insert(tk.END, f"Spark.ai: {answer}\n\n")
    chat_box.config(state=tk.DISABLED)
    chat_box.see(tk.END)

    send_button.config(state=tk.NORMAL)
    input_box.focus_set()


def enter_pressed(event):
    ask_ai()
    return "break"


# ---------------- Window ----------------

window = tk.Tk()
window.title("Spark.ai ⚡")
window.geometry("900x850")
window.minsize(700, 700)
window.configure(bg="#050812")


# ---------------- Header ----------------

tk.Label(
    window,
    text="⚡ Spark.ai",
    font=("Arial", 26, "bold"),
    fg="white",
    bg="#050812"
).pack(pady=(12, 0))

tk.Label(
    window,
    text="YOUR AI • YOUR SPARK",
    font=("Arial", 8, "bold"),
    fg="#7483aa",
    bg="#050812"
).pack(pady=(0, 4))


# ---------------- Round Watch ----------------

WATCH = 210

watch = tk.Canvas(
    window,
    width=WATCH,
    height=WATCH,
    bg="#050812",
    highlightthickness=0
)
watch.pack(pady=2)


def point(cx, cy, radius, degrees):
    angle = math.radians(degrees - 90)
    return (
        cx + radius * math.cos(angle),
        cy + radius * math.sin(angle)
    )


def draw_watch():
    watch.delete("all")

    cx = WATCH / 2
    cy = WATCH / 2

    watch.create_oval(
        5, 5, WATCH - 5, WATCH - 5,
        outline="#5868ff",
        width=4
    )

    watch.create_oval(
        13, 13, WATCH - 13, WATCH - 13,
        fill="#111827",
        outline="#6879ad",
        width=3
    )

    watch.create_oval(
        27, 27, WATCH - 27, WATCH - 27,
        fill="#050a18",
        outline="#29385f",
        width=2
    )

    # Minute markers
    for i in range(60):
        outer = 84
        inner = 78 if i % 5 else 73
        x1, y1 = point(cx, cy, outer, i * 6)
        x2, y2 = point(cx, cy, inner, i * 6)

        watch.create_line(
            x1, y1, x2, y2,
            fill="#b8c5e8" if i % 5 == 0 else "#46577e",
            width=2 if i % 5 == 0 else 1
        )

    watch.create_text(
        cx, 57,
        text="SPARK.AI",
        fill="white",
        font=("Arial", 11, "bold")
    )

    now = time.localtime()
    hour = now.tm_hour % 12
    minute = now.tm_min
    second = now.tm_sec

    hour_angle = (hour + minute / 60) * 30
    minute_angle = (minute + second / 60) * 6
    second_angle = second * 6

    hx, hy = point(cx, cy, 39, hour_angle)
    mx, my = point(cx, cy, 61, minute_angle)
    sx, sy = point(cx, cy, 70, second_angle)

    watch.create_line(
        cx, cy, hx, hy,
        fill="white", width=6, capstyle=tk.ROUND
    )
    watch.create_line(
        cx, cy, mx, my,
        fill="#4aa9ff", width=4, capstyle=tk.ROUND
    )
    watch.create_line(
        cx, cy, sx, sy,
        fill="#b765ff", width=2, capstyle=tk.ROUND
    )

    watch.create_oval(
        cx - 6, cy - 6, cx + 6, cy + 6,
        fill="white", outline="#6758ff", width=3
    )

    watch.create_text(
        cx, 130,
        text=time.strftime("%d %b"),
        fill="#bfc9e5",
        font=("Arial", 9, "bold")
    )

    watch.create_text(
        cx, 160,
        text="⚡",
        fill="#957cff",
        font=("Arial", 18, "bold")
    )

    window.after(200, draw_watch)


draw_watch()


# ---------------- Chat history ----------------

tk.Label(
    window,
    text="CHAT",
    font=("Arial", 9, "bold"),
    fg="#7483aa",
    bg="#050812"
).pack(anchor="w", padx=24, pady=(4, 2))

chat_box = scrolledtext.ScrolledText(
    window,
    wrap=tk.WORD,
    height=10,
    font=("Arial", 12),
    bg="#0b1120",
    fg="#edf2ff",
    insertbackground="white",
    selectbackground="#344e8a",
    relief=tk.FLAT,
    state=tk.DISABLED
)
chat_box.pack(
    fill=tk.BOTH,
    expand=True,
    padx=22,
    pady=(0, 8)
)

chat_box.config(state=tk.NORMAL)
chat_box.insert(
    tk.END,
    "Spark.ai: Hello! I'm ready to help you. ⚡🤖\n\n"
)
chat_box.config(state=tk.DISABLED)


# ---------------- Message box ----------------

tk.Label(
    window,
    text="MESSAGE",
    font=("Arial", 9, "bold"),
    fg="#7483aa",
    bg="#050812"
).pack(anchor="w", padx=24, pady=(0, 2))

message_frame = tk.Frame(window, bg="#050812")
message_frame.pack(
    fill=tk.X,
    padx=22,
    pady=(0, 8)
)

input_box = tk.Text(
    message_frame,
    height=4,
    font=("Arial", 12),
    bg="#10182b",
    fg="white",
    insertbackground="white",
    relief=tk.FLAT,
    padx=12,
    pady=10
)
input_box.pack(
    side=tk.LEFT,
    fill=tk.X,
    expand=True
)

send_button = tk.Button(
    message_frame,
    text="SEND ⚡",
    font=("Arial", 12, "bold"),
    bg="#5b55e8",
    fg="white",
    activebackground="#746dff",
    activeforeground="white",
    relief=tk.FLAT,
    padx=22,
    pady=14,
    command=ask_ai
)
send_button.pack(
    side=tk.RIGHT,
    padx=(10, 0)
)


# ---------------- Status ----------------

tk.Label(
    window,
    text="Ollama • llama3.2 • 21-second hard timeout",
    font=("Arial", 8),
    fg="#687696",
    bg="#050812"
).pack(pady=(0, 10))


input_box.bind("<Return>", enter_pressed)
input_box.focus_set()

window.mainloop()
