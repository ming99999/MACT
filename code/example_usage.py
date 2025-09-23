#!/usr/bin/env python3
""" Example usage of the unified LLM system.

This example demonstrates how to use both GPT and open-source models
with the same OpenAI API interface.
"""

import sys
import os

# Add the code directory to Python path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from llm import UnifiedLLM


def main():
    print("MACT Unified LLM Usage Example")
    print("=" * 40)
    
    # Example 1: Using GPT model (routed to OpenAI)
    print("\n1. GPT Model Example:")
    gpt_llm = UnifiedLLM("gpt-3.5-turbo")
    print(f"Created LLM for: gpt-3.5-turbo")
    print(f"Routes to: OpenAI API")
    
    # Example 2: Using open-source model (routed to RunPod)
    print("\n2. Open-source Model Example:")
    qwen_llm = UnifiedLLM("Qwen/Qwen3-8B")
    print(f"Created LLM for: Qwen/Qwen3-8B")
    print(f"Routes to: RunPod vLLM")
    
    # Example 3: Test prompting (if you want to test actual calls)
    print("\n3. Actual Usage (uncomment to test):")
    print("# Test GPT model")
    print("# response = gpt_llm('What is the capital of France?', num_return_sequences=1)")
    print("# print(f'GPT Response: {response[0]}')")
    print()
    print("# Test open-source model")
    print("# response = qwen_llm('What is 2 + 2?', num_return_sequences=1)")
    print("# print(f'Qwen Response: {response[0]}')")
    
    print("\n4. Usage in MACT:")
    print("# For table QA with GPT:")
    print("python tqa.py --plan_model_name gpt-3.5-turbo --code_model_name gpt-3.5-turbo --task tat")
    print()
    print("# For table QA with open-source:")
    print("python tqa.py --plan_model_name Qwen/Qwen3-8B --code_model_name Qwen/Qwen3-8B --task tat")
    print()
    print("# For mixed models:")
    print("python tqa.py --plan_model_name gpt-3.5-turbo --code_model_name Qwen/Qwen3-8B --task tat")


if __name__ == "__main__":
    main()