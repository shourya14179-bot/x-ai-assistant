from pathlib import Path
import re

src_path = Path("/mnt/data/xai_source/Pasted text(1).txt")
src = src_path.read_text(encoding="utf-8")
src = re.sub(r'(?m)^\s*```\s*$', '', src)

memory_code = '''
# ---------------- MEMORY SYSTEM ----------------

def init_memory():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            memory TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def save_memory(username, memory):
    if not username or not memory or not memory.strip():
        return False

    init_memory()
    conn = get_db()
    conn.execute(
        "INSERT INTO memories (username, memory) VALUES (?, ?)",
        (username, memory.strip())
    )
    conn.commit()
    conn.close()
    return True


def get_memories(username):
    init_memory()
    conn = get_db()
    rows = conn.execute(
        """
        SELECT id, memory, created_at
        FROM memories
        WHERE username = ?
        ORDER BY id DESC
        """,
        (username,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def memory_text(username):
    memories = get_memories(username)

    if not memories:
        return "No saved memories."

    return "\\n".join(
        "- " + item["memory"]
        for item in memories
    )


def delete_memory(username, memory_id):
    init_memory()
    conn = get_db()
    conn.execute(
        "DELETE FROM memories WHERE id = ? AND username = ?",
        (memory_id, username)
    )
    conn.commit()
    conn.close()


def clear_memories(username):
    init_memory()
    conn = get_db()
    conn.execute(
        "DELETE FROM memories WHERE username = ?",
        (username,)
    )
    conn.commit()
    conn.close()

# ------------------------------------------------
'''

marker = "\n\nLOGIN_PAGE = "
if marker not in src:
    raise RuntimeError("Could not find LOGIN_PAGE.")
src = src.replace(marker, "\n\n" + memory_code + marker, 1)

chat_start = src.find('@app.route("/chat", methods=["POST"])')
main_start = src.find('\n\nif __name__ == "__main__":')
if chat_start == -1 or main_start == -1 or main_start <= chat_start:
    raise RuntimeError("Could not locate the chat route/main block.")

chat_route = '''@app.route("/chat", methods=["POST"])
def chat():
    if "username" not in session:
        return jsonify({"error": "Please login first"}), 401

    data = request.get_json()

    if not data:
        return jsonify({"error": "No message received"}), 400

    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "Message is empty"}), 400

    username = session["username"]

    conversation_id = session.get("conversation_id")

    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        session["conversation_id"] = conversation_id

    # Automatically save memories when the user says:
    # "remember that I like Minecraft"
    lower_message = message.lower()

    if lower_message.startswith("remember that "):
        new_memory = message[len("remember that "):].strip()

        if new_memory:
            save_memory(username, new_memory)

    # Load this user's memories and give them to Ollama.
    memories = memory_text(username)

    prompt = f"""You are X.ai.

Saved memories about this user:
{memories}

Use these memories only when relevant.
Do not invent memories.
If the user asks what you remember, use the saved memories above.

User:
{message}
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=30
        )

        response.raise_for_status()

        result = response.json()
        ai_response = result.get("response", "").strip()

        if not ai_response:
            return jsonify({
                "error": "Ollama returned an empty response."
            }), 500

    except requests.exceptions.ConnectionError:
        return jsonify({
            "error": "Cannot connect to Ollama. Make sure Ollama is running."
        }), 500

    except requests.exceptions.Timeout:
        return jsonify({
            "error": "Ollama took too long to respond."
        }), 500

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

    conn = get_db()

    conn.execute(
        """
        INSERT INTO chats
        (username, user_message, ai_response, conversation_id)
        VALUES (?, ?, ?, ?)
        """,
        (
            username,
            message,
            ai_response,
            conversation_id
        )
    )

    conn.commit()
    conn.close()

    return jsonify({
        "response": ai_response
    })


@app.route("/memories", methods=["GET"])
def memories():
    if "username" not in session:
        return jsonify({"error": "Please login first"}), 401

    return jsonify({
        "memories": get_memories(session["username"])
    })


@app.route("/memories/delete", methods=["POST"])
def memories_delete():
    if "username" not in session:
        return jsonify({"error": "Please login first"}), 401

    data = request.get_json() or {}
    memory_id = data.get("id")

    if memory_id is None:
        return jsonify({"error": "Memory id is required"}), 400

    delete_memory(session["username"], memory_id)

    return jsonify({"success": True})


@app.route("/memories/clear", methods=["POST"])
def memories_clear():
    if "username" not in session:
        return jsonify({"error": "Please login first"}), 401

    clear_memories(session["username"])

    return jsonify({"success": True})


@app.route("/history", methods=["GET"])
def history():
    if "username" not in session:
        return jsonify({"error": "Please login first"}), 401

    conn = get_db()

    rows = conn.execute(
        """
        SELECT id, user_message, ai_response, conversation_id, created_at
        FROM chats
        WHERE username = ?
        ORDER BY id DESC
        """,
        (session["username"],)
    ).fetchall()

    conn.close()

    return jsonify({
        "history": [dict(row) for row in rows]
    })
'''

src = src[:chat_start] + chat_route + src[main_start:]

old = '''    init_db()

    print("----------------------------------------")'''
new = '''    init_db()
    init_memory()

    print("----------------------------------------")'''
if old not in src:
    raise RuntimeError("Could not find server startup block.")
src = src.replace(old, new, 1)

out = Path("/mnt/data/XAI_app_with_memory.py")
out.write_text(src, encoding="utf-8")
compile(src, str(out), "exec")

print(f"Created: {out}")
print("Syntax check: OK")
