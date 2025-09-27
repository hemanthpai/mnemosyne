#!/usr/bin/env python3
"""
Test script for the v2 OpenWebUI filter improvements
Tests the key fixes:
1. Only processes latest user messages
2. Never extracts from assistant responses
3. Proper message tracking and deduplication
4. Session isolation
"""

import asyncio
import sys
from typing import Dict, Any, Optional
from unittest.mock import MagicMock

# Import the v2 filter
sys.path.append('.')
from openwebui_mnemosyne_integration_v2 import Filter


class MockEventEmitter:
    """Mock event emitter for testing"""
    def __init__(self, session_name=""):
        self.events = []
        self.session_name = session_name

    async def __call__(self, event):
        self.events.append(event)
        if self.session_name:
            print(f"[{self.session_name}] EVENT: {event.get('data', {}).get('description', event)}")
        else:
            print(f"EVENT: {event.get('data', {}).get('description', event)}")


class TestFilterV2:
    """Test suite for v2 filter improvements"""

    def __init__(self):
        self.filter = Filter()
        # Disable persistence for testing
        self.filter.valves.persistence_enabled = False
        self.filter.valves.show_status_updates = True

    async def test_latest_message_extraction(self):
        """Test that only latest user message is used"""
        print("\n=== Test 1: Latest Message Extraction ===")

        event_emitter = MockEventEmitter("Test1")

        # Simulate a conversation with multiple messages
        body = {
            "messages": [
                {"role": "user", "content": "First user message"},
                {"role": "assistant", "content": "First assistant response"},
                {"role": "user", "content": "Second user message"},
                {"role": "assistant", "content": "Second assistant response"},
                {"role": "user", "content": "Latest user message - should be used"}
            ]
        }

        # Test latest message extraction
        latest = self.filter._get_latest_user_message(body)
        assert latest == "Latest user message - should be used"
        print("✅ Correctly extracted latest user message")

        # Test first message detection
        is_first = self.filter._is_first_user_message(body)
        assert is_first == False  # Not first since there are 3 user messages
        print("✅ Correctly identified not first message")

        # Test with single user message
        body_first = {
            "messages": [
                {"role": "user", "content": "Only user message"}
            ]
        }
        is_first = self.filter._is_first_user_message(body_first)
        assert is_first == True
        print("✅ Correctly identified first message")

    async def test_no_assistant_extraction(self):
        """Test that assistant messages are never extracted"""
        print("\n=== Test 2: No Assistant Message Extraction ===")

        event_emitter = MockEventEmitter("Test2")
        user = {"id": "test-user-1"}

        body = {
            "messages": [
                {"role": "user", "content": "Tell me about Python"},
                {"role": "assistant", "content": "Python is a programming language created by Guido van Rossum"},
                {"role": "user", "content": "What are its main features?"},
                {"role": "assistant", "content": "Python features include dynamic typing, garbage collection, and multiple paradigms"}
            ]
        }

        # Get session ID
        session_id = self.filter._get_session_id(body)
        user_id = self.filter._get_user_id(user)

        # Get unprocessed messages - should only be user messages
        unprocessed = self.filter._get_unprocessed_user_messages(body, user_id, session_id)

        print(f"Unprocessed messages: {unprocessed}")

        # Verify no assistant content is included
        for msg in unprocessed:
            assert "Guido van Rossum" not in msg  # Assistant info
            assert "dynamic typing" not in msg     # Assistant info
            assert "garbage collection" not in msg  # Assistant info

        print("✅ No assistant messages were included in extraction")

    async def test_duplicate_prevention(self):
        """Test that messages are not processed twice"""
        print("\n=== Test 3: Duplicate Prevention ===")

        user = {"id": "test-user-2"}

        body = {
            "messages": [
                {"role": "user", "content": "Message to process once"},
                {"role": "assistant", "content": "Response"}
            ]
        }

        session_id = self.filter._get_session_id(body)
        user_id = self.filter._get_user_id(user)

        # First processing
        unprocessed1 = self.filter._get_unprocessed_user_messages(body, user_id, session_id)
        print(f"First processing: {len(unprocessed1)} messages")
        assert len(unprocessed1) == 1

        # Second processing of same messages
        unprocessed2 = self.filter._get_unprocessed_user_messages(body, user_id, session_id)
        print(f"Second processing: {len(unprocessed2)} messages")
        assert len(unprocessed2) == 0  # Should be empty since already processed

        # Add new message
        body["messages"].append({"role": "user", "content": "New message"})
        body["messages"].append({"role": "assistant", "content": "New response"})

        # Third processing should only get the new message
        unprocessed3 = self.filter._get_unprocessed_user_messages(body, user_id, session_id)
        print(f"Third processing: {len(unprocessed3)} messages")
        assert len(unprocessed3) == 1
        assert unprocessed3[0] == "New message"

        print("✅ Duplicate prevention working correctly")

    async def test_session_isolation(self):
        """Test that different sessions are isolated"""
        print("\n=== Test 4: Session Isolation ===")

        user1 = {"id": "user-1"}
        user2 = {"id": "user-2"}

        # Session 1 for user 1
        body1 = {
            "messages": [
                {"role": "user", "content": "User 1 message in session 1"}
            ],
            "chat_id": "session-1"
        }

        # Session 2 for user 1 (different chat)
        body2 = {
            "messages": [
                {"role": "user", "content": "User 1 message in session 2"}
            ],
            "chat_id": "session-2"
        }

        # Session for user 2
        body3 = {
            "messages": [
                {"role": "user", "content": "User 2 message"}
            ],
            "chat_id": "session-3"
        }

        # Process messages for different sessions
        session1_id = self.filter._get_session_id(body1)
        session2_id = self.filter._get_session_id(body2)
        session3_id = self.filter._get_session_id(body3)

        # Verify sessions are different
        assert session1_id != session2_id
        assert session1_id != session3_id
        assert session2_id != session3_id
        print("✅ Sessions are properly isolated")

        # Process messages
        u1 = self.filter._get_unprocessed_user_messages(body1, "user-1", session1_id)
        u2 = self.filter._get_unprocessed_user_messages(body2, "user-1", session2_id)
        u3 = self.filter._get_unprocessed_user_messages(body3, "user-2", session3_id)

        assert len(u1) == 1
        assert len(u2) == 1
        assert len(u3) == 1

        # Reprocess same bodies - should get nothing (already processed)
        u1_again = self.filter._get_unprocessed_user_messages(body1, "user-1", session1_id)
        u2_again = self.filter._get_unprocessed_user_messages(body2, "user-1", session2_id)
        u3_again = self.filter._get_unprocessed_user_messages(body3, "user-2", session3_id)

        assert len(u1_again) == 0
        assert len(u2_again) == 0
        assert len(u3_again) == 0

        print("✅ Each session tracks its own processed messages")

    async def test_full_flow(self):
        """Test complete inlet/outlet flow"""
        print("\n=== Test 5: Full Flow Integration ===")

        # Simulate a conversation flow
        user = {"id": "test-user-flow"}

        # Initial message
        body = {
            "messages": [
                {"role": "user", "content": "What is machine learning?"}
            ]
        }

        event_emitter = MockEventEmitter("FullFlow")

        print("\n--- First Inlet (new conversation) ---")
        body = await self.filter.inlet(body, event_emitter, user)

        # Simulate assistant response
        body["messages"].append({
            "role": "assistant",
            "content": "Machine learning is a type of AI that allows systems to learn from data."
        })

        print("\n--- First Outlet ---")
        body = await self.filter.outlet(body, event_emitter, user)

        # Second user message
        body["messages"].append({
            "role": "user",
            "content": "Can you give me an example?"
        })

        print("\n--- Second Inlet ---")
        body = await self.filter.inlet(body, event_emitter, user)

        # Second assistant response
        body["messages"].append({
            "role": "assistant",
            "content": "Sure! Image recognition is a common example of machine learning."
        })

        print("\n--- Second Outlet ---")
        body = await self.filter.outlet(body, event_emitter, user)

        # Verify tracking state
        session_id = self.filter._get_session_id(body)
        user_id = self.filter._get_user_id(user)

        # All user messages should be processed
        unprocessed = self.filter._get_unprocessed_user_messages(body, user_id, session_id)
        assert len(unprocessed) == 0

        print("\n✅ Full flow completed successfully")
        print("✅ All user messages tracked as processed")
        print("✅ No duplicate processing occurred")


async def main():
    """Run all tests"""
    tester = TestFilterV2()

    try:
        await tester.test_latest_message_extraction()
        await tester.test_no_assistant_extraction()
        await tester.test_duplicate_prevention()
        await tester.test_session_isolation()
        await tester.test_full_flow()

        print("\n" + "="*50)
        print("🎉 ALL TESTS PASSED!")
        print("="*50)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)