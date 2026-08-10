```python
import requests

print("🤖 X.ai is ready!")
print("Type 'exit' to stop.\n")

while True:
    user = input("You: ")

    if user.lower() == "exit":
        print("X.ai: Goodbye!")
        break

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2",
                "prompt": user,
                "stream": False
            },
            timeout=30
        )

        response.raise_for_status()
        data = response.json()
        print("X.ai:", data["response"])

    except requests.exceptions.Timeout:
        print("X.ai: Sorry, I took longer than 30 seconds to answer.")

    except requests.exceptions.ConnectionError:
        print("X.ai: Cannot connect to Ollama. Make sure Ollama is running.")

    except Exception as e:
        print("X.ai: Error:", e)
```

