#!/usr/bin/env python3
"""
Test script to verify the token context calculation fix.
"""

import sys
import os
sys.path.append('backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'memory_service.settings')

import django
django.setup()

from memories.token_utils import TokenCounter

def test_token_calculation():
    """Test the fixed token calculation logic"""
    
    print("🧪 Testing Token Context Calculation Fix")
    print("=" * 50)
    
    # Simulate the memory extraction scenario
    system_prompt = "You are a helpful assistant that extracts memories from conversations."
    user_prompt = "Extract memories from: I love hiking in the mountains every weekend."
    model_name = "Qwen3-30B-A3B"
    max_tokens = 2048  # Default setting
    
    # Calculate token estimates
    system_tokens = TokenCounter.estimate_tokens(system_prompt, model_name)
    user_tokens = TokenCounter.estimate_tokens(user_prompt, model_name)
    safety_margin = max_tokens + 512
    
    print(f"📊 Token Analysis:")
    print(f"   System prompt: {system_tokens} tokens")
    print(f"   User prompt: {user_tokens} tokens")
    print(f"   Safety margin: {safety_margin} tokens")
    print(f"   Total needed: {system_tokens + user_tokens + safety_margin} tokens")
    
    # Test old behavior (what it would have been)
    old_required_context = TokenCounter.calculate_required_context(
        system_prompt, user_prompt, model_name, safety_margin
    )
    
    print(f"\n📈 Context Size Calculation:")
    print(f"   Required context: {old_required_context} tokens")
    
    # Verify the fix
    if old_required_context <= 8192:
        print(f"   ✅ FIXED: Context size is reasonable ({old_required_context:,} tokens)")
        reduction = 32768 - old_required_context
        print(f"   💾 Reduction: {reduction:,} tokens saved ({reduction/32768*100:.1f}% smaller)")
    else:
        print(f"   ⚠️  Still high: {old_required_context:,} tokens")
    
    # Test various input sizes
    print(f"\n🔍 Testing Different Input Sizes:")
    test_cases = [
        ("Short", "Hello", 100),
        ("Medium", "Hello " * 50, 1000), 
        ("Long", "Hello " * 200, 4000),
        ("Very Long", "Hello " * 500, 10000)
    ]
    
    for name, text, expected_safety in test_cases:
        context = TokenCounter.calculate_required_context(
            "System prompt", text, model_name, expected_safety
        )
        print(f"   {name}: {context:,} tokens")

if __name__ == "__main__":
    test_token_calculation()