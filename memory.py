import sqlite3

DATABASE = "users.db"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_memory():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, memory TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()
    conn.close()

def save_memory(username, memory):
    if not username or not memory or not memory.strip():
        return False
    init_memory()
    conn = get_db()
    conn.execute("INSERT INTO memories (username, memory) VALUES (?, ?)", (username, memory.strip()))
    conn.commit()
    conn.close()
    return True

def get_memories(username):
    init_memory()
    conn = get_db()
    rows = conn.execute("SELECT id, memory, created_at FROM memories WHERE username = ? ORDER BY id DESC", (username,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_memory(username, memory_id):
    init_memory()
    conn = get_db()
    conn.execute("DELETE FROM memories WHERE id = ? AND username = ?", (memory_id, username))
    conn.commit()
    conn.close()

def clear_memories(username):
    init_memory()
    conn = get_db()
    conn.execute("DELETE FROM memories WHERE username = ?", (username,))
    conn.commit()
    conn.close()

def memory_text(username):
    memories = get_memories(username)
    if not memories:
        return "No saved memories."
    return "\\n".join("- " + item["memory"] for item in memories)

if __name__ == "__main__":
    init_memory()
    print("X.ai Memory System")
    print("Memory database is ready.")
