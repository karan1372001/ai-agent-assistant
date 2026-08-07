import sqlite3
# Lets us open and read/write to our database file

import requests
# Lets us send requests to Ollama to create fingerprints

import json
# Lets us convert the fingerprint (a list of numbers) into text to store in the database

# Connect to your existing memory database (the same one your app already uses)
conn = sqlite3.connect("memory.db")
cursor = conn.cursor()


def get_embedding(text):
    # This turns any message into a "meaning fingerprint" - a list of numbers
    # representing what the message means, so we can search by meaning later
    response = requests.post(
        "http://localhost:11434/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": text}
    )
    return response.json()["embedding"]


# Find every old message that's missing a fingerprint
# (these are messages sent BEFORE we added the smart memory feature)
cursor.execute("SELECT id, content FROM history WHERE embedding IS NULL OR embedding = ''")
rows = cursor.fetchall()

print(f"Found {len(rows)} old messages without fingerprints. Processing...")
# Just tells you how many messages need fixing

# Go through each old message one at a time
for row_id, content in rows:
    try:
        embedding = get_embedding(content)
        # Create the fingerprint for this specific old message

        embedding_json = json.dumps(embedding)
        # Convert it into text so it can be saved in the database

        cursor.execute("UPDATE history SET embedding = ? WHERE id = ?", (embedding_json, row_id))
        conn.commit()
        # Save the new fingerprint into that message's row in the database

        print(f"Fixed message {row_id}")
        # Just prints progress so you can see it working

    except Exception as e:
        print(f"Failed on message {row_id}: {e}")
        # If something goes wrong on one message, print the error but keep going

print("Done! All old messages now have fingerprints.")
# Final confirmation once everything is finished