#!/usr/bin/env python3
"""Ingest Open WebUI conversations from webui.db into Mnemosyne backend.

Usage:
  uv run ingest-webui.py --db ../webui.db --backend-url http://localhost:3100
  uv run ingest-webui.py --db ../webui.db --backend-url http://localhost:3100 --dry-run
"""
import argparse
import json
import sqlite3
import sys
import time

import httpx


def extract_messages(chat_json: dict) -> list[dict]:
    """Walk the message tree from root to leaf, following first child."""
    history = chat_json.get("history", {})
    messages_map = history.get("messages", {})

    if not messages_map:
        return []

    # Find root: parentId is None or "None"
    root_id = None
    for mid, msg in messages_map.items():
        parent = msg.get("parentId")
        if parent is None or str(parent) == "None":
            root_id = mid
            break

    if root_id is None:
        return []

    # Walk the chain
    chain = []
    current = root_id
    while current and current in messages_map:
        msg = messages_map[current]
        content = msg.get("content", "")
        if isinstance(content, str) and content.strip():
            chain.append({"role": msg["role"], "content": content})

        children = msg.get("childrenIds", [])
        current = children[0] if children else None

    return chain


def extract_tags(meta_json: dict) -> list[str]:
    """Extract tags from the meta column."""
    tags = meta_json.get("tags", [])
    if isinstance(tags, list):
        return [t for t in tags if isinstance(t, str)]
    return []


def load_conversations(db_path: str) -> list[dict]:
    """Load all conversations from webui.db."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, chat, meta, created_at FROM chat ORDER BY created_at")

    conversations = []
    for row in cursor.fetchall():
        row_id, title, chat_str, meta_str, created_at = row

        try:
            chat = json.loads(chat_str) if chat_str else {}
            meta = json.loads(meta_str) if meta_str else {}
        except json.JSONDecodeError:
            print(f"  Skipping {row_id}: invalid JSON")
            continue

        messages = extract_messages(chat)
        if not messages:
            continue

        tags = extract_tags(meta)

        conversations.append({
            "source_id": row_id,
            "title": title or "Untitled",
            "source": "open-webui",
            "tags": tags,
            "messages": messages,
        })

    conn.close()
    return conversations


def main():
    parser = argparse.ArgumentParser(description="Ingest Open WebUI conversations into Mnemosyne")
    parser.add_argument("--db", required=True, help="Path to webui.db")
    parser.add_argument("--backend-url", required=True, help="Mnemosyne backend URL (e.g. http://localhost:3100)")
    parser.add_argument("--dry-run", action="store_true", help="Parse and validate only, don't POST")
    args = parser.parse_args()

    print(f"Loading conversations from {args.db}...")
    conversations = load_conversations(args.db)
    print(f"Found {len(conversations)} conversations with messages")

    total_messages = sum(len(c["messages"]) for c in conversations)
    user_messages = sum(
        1 for c in conversations for m in c["messages"] if m["role"] == "user"
    )
    embeddable = sum(
        1 for c in conversations for m in c["messages"]
        if m["role"] == "user" and len(m["content"]) >= 50
    )
    print(f"Total messages: {total_messages}")
    print(f"User messages: {user_messages}")
    print(f"Embeddable (user, >= 50 chars): {embeddable}")

    if args.dry_run:
        print("\n--- Dry run summary ---")
        for i, conv in enumerate(conversations[:5]):
            print(f"  [{i+1}] {conv['title']} ({len(conv['messages'])} msgs, tags: {conv['tags']})")
        if len(conversations) > 5:
            print(f"  ... and {len(conversations) - 5} more")
        print("\nDry run complete. No data was sent.")
        return

    print(f"\nIngesting into {args.backend_url}...")
    client = httpx.Client(base_url=args.backend_url, timeout=120.0)

    # Health check
    try:
        resp = client.get("/health")
        if resp.status_code != 200:
            print(f"Backend unhealthy: {resp.status_code}")
            sys.exit(1)
    except httpx.ConnectError:
        print(f"Cannot connect to {args.backend_url}")
        sys.exit(1)

    succeeded = 0
    failed = 0
    start = time.time()

    for i, conv in enumerate(conversations):
        payload = {
            "title": conv["title"],
            "source": conv["source"],
            "sourceId": conv["source_id"],
            "tags": conv["tags"],
            "messages": conv["messages"],
        }

        try:
            resp = client.post("/api/conversations", json=payload)
            if resp.status_code == 200:
                succeeded += 1
            else:
                failed += 1
                print(f"  [{i+1}] FAIL {resp.status_code}: {conv['title'][:60]}")
        except Exception as e:
            failed += 1
            print(f"  [{i+1}] ERROR: {e}")

        # Progress every 50
        if (i + 1) % 50 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            print(f"  Progress: {i+1}/{len(conversations)} ({rate:.1f}/s)")

    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f}s")
    print(f"Succeeded: {succeeded}, Failed: {failed}")

    client.close()


if __name__ == "__main__":
    main()
