"""
Environment utilities for loading API keys and configuration.

Handles automatic loading of .env files and routing to appropriate API endpoints.
"""

import os
from pathlib import Path
from dotenv import load_dotenv


def load_env_config():
    """
    Load environment variables from .env file.

    Searches for .env file in current directory and parent directories.
    """
    # Try to find .env file
    current_dir = Path.cwd()
    env_file = current_dir / '.env'

    # If not found in current dir, try parent directories
    if not env_file.exists():
        # Try langgraph_code directory
        possible_paths = [
            current_dir.parent / '.env',
            current_dir.parent.parent / '.env',
            Path(__file__).parent.parent.parent / '.env',  # From utils dir
        ]

        for path in possible_paths:
            if path.exists():
                env_file = path
                break

    if env_file.exists():
        load_dotenv(env_file)
        print(f"✅ Loaded environment from: {env_file}")
        return True
    else:
        print("⚠️  No .env file found, using system environment variables")
        return False


def get_api_config(model_name: str = None):
    """
    Get API configuration based on model name.

    Routes to appropriate API endpoint:
    - GPT models (gpt-3.5-turbo, gpt-4, etc.) → OpenAI API
    - Other models (Qwen, Llama, etc.) → RunPod API

    Args:
        model_name: Name of the model (e.g., "gpt-3.5-turbo", "Qwen/Qwen3-8B")

    Returns:
        dict with 'api_key' and 'base_url'
    """
    # Ensure env is loaded
    load_env_config()

    # Determine if this is a GPT model
    is_gpt_model = model_name and ('gpt' in model_name.lower())

    if is_gpt_model:
        # Use OpenAI API
        api_key = os.getenv('OPENAI_API_KEY')
        base_url = os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1')

        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY not found in environment. "
                "Please set it in .env file or environment variables."
            )

        return {
            'api_key': api_key,
            'base_url': base_url,
            'provider': 'openai'
        }

    else:
        # Use RunPod API for non-GPT models
        api_key = os.getenv('RUNPOD_API_KEY') or os.getenv('OPENAI_API_KEY')
        base_url = os.getenv('RUNPOD_BASE_URL')

        if not base_url:
            # Fallback to OpenAI if RunPod not configured
            print(f"⚠️  RunPod not configured for model '{model_name}', falling back to OpenAI")
            api_key = os.getenv('OPENAI_API_KEY')
            base_url = os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1')

            if not api_key:
                raise ValueError(
                    "Neither RUNPOD_API_KEY nor OPENAI_API_KEY found in environment. "
                    "Please set one in .env file or environment variables."
                )

            return {
                'api_key': api_key,
                'base_url': base_url,
                'provider': 'openai_fallback'
            }

        if not api_key:
            raise ValueError(
                "RUNPOD_API_KEY not found in environment. "
                "Please set it in .env file or environment variables."
            )

        return {
            'api_key': api_key,
            'base_url': base_url,
            'provider': 'runpod'
        }


def check_api_keys():
    """
    Check if required API keys are available.

    Returns:
        dict with status of each API key
    """
    load_env_config()

    status = {
        'openai': bool(os.getenv('OPENAI_API_KEY')),
        'runpod': bool(os.getenv('RUNPOD_API_KEY')),
        'runpod_base_url': bool(os.getenv('RUNPOD_BASE_URL'))
    }

    return status


def print_api_status():
    """Print status of API configuration."""
    status = check_api_keys()

    print("\n" + "="*60)
    print("API Configuration Status")
    print("="*60)
    print(f"OpenAI API Key:     {'✅ Set' if status['openai'] else '❌ Not Set'}")
    print(f"RunPod API Key:     {'✅ Set' if status['runpod'] else '❌ Not Set'}")
    print(f"RunPod Base URL:    {'✅ Set' if status['runpod_base_url'] else '❌ Not Set'}")
    print("="*60)

    if status['openai']:
        print("✅ Ready for GPT models (gpt-3.5-turbo, gpt-4, etc.)")

    if status['runpod'] and status['runpod_base_url']:
        print("✅ Ready for RunPod models (Qwen, Llama, etc.)")
    elif not status['openai']:
        print("⚠️  No API keys configured!")
        print("   Please set OPENAI_API_KEY or RUNPOD_API_KEY in .env file")

    print()


# Auto-load environment on import
load_env_config()
