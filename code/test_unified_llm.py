#!/usr/bin/env python3
""" Test script for unified LLM integration.

Copyright (c) 2025 Robert Bosch GmbH 

This program is free software: you can redistribute it and/or modify 
it under the terms of the GNU Affero General Public License as published 
by the Free Software Foundation, either version 3 of the License, or 
(at your option) any later version. 

This program is distributed in the hope that it will be useful, 
but WITHOUT ANY WARRANTY; without even the implied warranty of 
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the 
GNU Affero General Public License for more details. 

You should have received a copy of the GNU Affero General Public License 
along with this program.  If not, see <https://www.gnu.org/licenses/>. 
"""

import os
from config import llm_config
from llm import UnifiedLLM


def test_configuration():
    """Test basic configuration loading."""
    print("=== Configuration Test ===")
    
    # Check if required environment variables are set
    openai_key = os.getenv("OPENAI_API_KEY")
    runpod_key = os.getenv("RUNPOD_API_KEY")
    runpod_url = os.getenv("RUNPOD_BASE_URL")
    
    print(f"OpenAI API Key: {'✓ Set' if openai_key else '✗ Missing'}")
    print(f"RunPod API Key: {'✓ Set' if runpod_key else '✗ Missing'}")
    print(f"RunPod Base URL: {'✓ Set' if runpod_url else '✗ Missing'}")
    
    return bool(openai_key and runpod_key and runpod_url)


def test_model_routing():
    """Test model routing logic."""
    print("\n=== Model Routing Test ===")
    
    test_models = [
        ("gpt-35-turbo", "GPT"),
        ("gpt-4", "GPT"), 
        ("Qwen/Qwen3-8B", "Open-source"),
        ("meta-llama/Llama-3-8B", "Open-source"),
        ("mistralai/Mistral-7B", "Open-source"),
        ("unknown-model", "Default (GPT)")
    ]
    
    for model_name, expected_type in test_models:
        is_gpt = llm_config.is_gpt_model(model_name)
        is_os = llm_config.is_open_source_model(model_name)
        
        if is_gpt:
            detected_type = "GPT"
        elif is_os:
            detected_type = "Open-source"
        else:
            detected_type = "Default (GPT)"
            
        status = "✓" if detected_type == expected_type else "✗"
        print(f"{status} {model_name} → {detected_type}")


def test_client_creation():
    """Test client creation for different models."""
    print("\n=== Client Creation Test ===")
    
    test_models = ["gpt-35-turbo", "Qwen/Qwen3-8B"]
    
    for model_name in test_models:
        try:
            client = llm_config.get_client_for_model(model_name)
            print(f"✓ {model_name} → Client created (base_url: {client.base_url})")
        except Exception as e:
            print(f"✗ {model_name} → Error: {e}")


def test_unified_llm():
    """Test UnifiedLLM class initialization."""
    print("\n=== UnifiedLLM Test ===")
    
    test_models = ["gpt-35-turbo", "Qwen/Qwen3-8B"]
    
    for model_name in test_models:
        try:
            llm = UnifiedLLM(model_name)
            print(f"✓ {model_name} → UnifiedLLM created")
            
            # Test token encoding
            token_count = llm.encode("This is a test prompt")
            print(f"  Token estimation: {token_count}")
            
        except Exception as e:
            print(f"✗ {model_name} → Error: {e}")


def test_actual_completion():
    """Test actual LLM completion (requires valid API keys)."""
    print("\n=== Actual Completion Test ===")
    
    if not test_configuration():
        print("⚠️ Skipping completion test - missing required configuration")
        return
    
    test_prompt = "What is 2 + 2?"
    test_models = ["Qwen/Qwen3-8B"]  # Test with RunPod model
    
    for model_name in test_models:
        try:
            print(f"\nTesting {model_name}...")
            llm = UnifiedLLM(model_name)
            
            response = llm(test_prompt, num_return_sequences=1, max_tokens=50)
            
            if response and response[0]:
                print(f"✓ {model_name} → Response: {response[0][:100]}...")
            else:
                print(f"✗ {model_name} → Empty response")
                
        except Exception as e:
            print(f"✗ {model_name} → Error: {e}")


def main():
    """Run all tests."""
    print("MACT Unified LLM Integration Test")
    print("=" * 40)
    
    test_configuration()
    test_model_routing()
    test_client_creation()
    test_unified_llm()
    
    # Only run actual completion test if explicitly requested
    import sys
    if "--with-completion" in sys.argv:
        test_actual_completion()
    else:
        print(f"\n💡 To test actual completions, run: python {__file__} --with-completion")
    
    print("\n✅ Test completed!")


if __name__ == "__main__":
    main()