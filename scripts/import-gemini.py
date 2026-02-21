#!/usr/bin/env python3
"""Import a Gemini conversation export into Open WebUI's chat database.

Usage:
  uv run scripts/import-gemini.py --json Default-Mode-Network-Brains-Inner-World.json --db webui.db --user-id e2d01235-b828-4797-8acd-350289fdcff3
"""
import argparse
import json
import sqlite3
import time
import uuid


def gemini_to_owui_chat(gemini_data: dict) -> dict:
    """Convert Gemini export JSON into Open WebUI chat format."""
    messages_map = {}
    message_ids = []
    prev_id = None

    for msg in gemini_data["messages"]:
        msg_id = str(uuid.uuid4())
        message_ids.append(msg_id)

        # Map Gemini roles to OWUI roles
        role = "user" if msg["role"] == "Prompt" else "assistant"
        content = msg["say"]
        # Strip "Gemini said\n\n\n" prefix from responses
        if role == "assistant" and content.startswith("Gemini said"):
            content = content.split("\n", 3)[-1].lstrip("\n")

        entry = {
            "id": msg_id,
            "parentId": prev_id,
            "childrenIds": [],
            "role": role,
            "content": content,
            "timestamp": int(time.time()),
        }

        if role == "user":
            entry["models"] = ["gemini"]
        else:
            entry["model"] = "gemini"
            entry["modelName"] = "Google Gemini"
            entry["modelIdx"] = 0
            entry["done"] = True

        messages_map[msg_id] = entry

        # Link parent to child
        if prev_id and prev_id in messages_map:
            messages_map[prev_id]["childrenIds"].append(msg_id)

        prev_id = msg_id

    # Build the top-level messages list (OWUI format)
    top_messages = []
    for msg_id in message_ids:
        m = messages_map[msg_id]
        top_messages.append({
            "id": m["id"],
            "parentId": m["parentId"],
            "childrenIds": m["childrenIds"],
            "role": m["role"],
            "content": m["content"],
            "timestamp": m["timestamp"],
        })

    chat = {
        "id": str(uuid.uuid4()),
        "title": gemini_data["metadata"]["title"],
        "models": ["gemini"],
        "params": {},
        "history": {
            "messages": messages_map,
            "currentId": message_ids[-1] if message_ids else None,
        },
        "messages": top_messages,
        "tags": [],
        "timestamp": int(time.time()),
        "files": [],
    }
    return chat


def main():
    parser = argparse.ArgumentParser(description="Import Gemini conversation into Open WebUI DB")
    parser.add_argument("--json", required=True, help="Path to Gemini export JSON")
    parser.add_argument("--db", required=True, help="Path to webui.db")
    parser.add_argument("--user-id", required=True, help="OWUI user_id to assign the conversation to")
    parser.add_argument("--dry-run", action="store_true", help="Parse and validate only, don't INSERT")
    args = parser.parse_args()

    with open(args.json) as f:
        gemini_data = json.load(f)

    title = gemini_data["metadata"]["title"]
    num_messages = len(gemini_data["messages"])
    print(f"Title: {title}")
    print(f"Messages: {num_messages}")
    print(f"User ID: {args.user_id}")

    chat = gemini_to_owui_chat(gemini_data)
    chat_id = chat["id"]

    if args.dry_run:
        print(f"\nDry run — would insert chat {chat_id} with {num_messages} messages")
        print(f"First message: {gemini_data['messages'][0]['say'][:80]}...")
        return

    conn = sqlite3.connect(args.db)
    cursor = conn.cursor()

    # Check if already inserted (by title + user)
    cursor.execute(
        "SELECT id FROM chat WHERE user_id = ? AND title = ?",
        (args.user_id, title),
    )
    existing = cursor.fetchone()
    if existing:
        print(f"\nConversation already exists with id={existing[0]}. Skipping.")
        conn.close()
        return

    now = int(time.time())
    cursor.execute(
        """INSERT INTO chat (id, user_id, title, share_id, archived, created_at, updated_at, chat, pinned, meta, folder_id)
           VALUES (?, ?, ?, NULL, 0, ?, ?, ?, 0, '{"tags": ["gemini", "imported"]}', NULL)""",
        (chat_id, args.user_id, title, now, now, json.dumps(chat)),
    )
    conn.commit()
    conn.close()

    print(f"\nInserted chat {chat_id} into {args.db}")
    print(f"Title: {title}")
    print(f"Messages: {num_messages}")


if __name__ == "__main__":
    main()
