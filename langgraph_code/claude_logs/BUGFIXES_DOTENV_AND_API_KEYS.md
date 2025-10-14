# Bug Fixes: Dotenv Support and API Key Loading

**Date**: 2025-10-14
**Branch**: feature/multi-agent-eda
**Status**: ✅ Fixed

## Issues Addressed

### 1. API Key Loading Issue

**Problem**:
- `create_llm()` function in `core_nodes.py` was not explicitly passing the OpenAI API key
- Relied on environment variable being set externally via `export OPENAI_API_KEY=...`
- This caused `OpenAIError: The api_key client option must be set` when running tests

**Root Cause**:
```python
# In core_nodes.py:177 (before fix)
return ChatOpenAI(
    model=model_name,
    temperature=0.1,
    max_tokens=2048,
    timeout=60
)  # No api_key parameter - relies on env var
```

**Solution**:
1. Explicitly get API key from environment: `openai_api_key = os.getenv("OPENAI_API_KEY")`
2. Pass it to ChatOpenAI: `api_key=openai_api_key`
3. Add validation error if key not found
4. Load .env file early in core_nodes.py import

### 2. Dotenv Support

**Problem**:
- Users had to manually export API keys before each session
- No automatic loading from .env file

**Solution**:
- Added `python-dotenv` support throughout the codebase
- Created `multi_agent/utils/env_utils.py` with utility functions:
  - `load_env_config()`: Automatically find and load .env file
  - `get_api_config(model_name)`: Route to correct API (OpenAI/RunPod)
  - `check_api_keys()`: Validate API configuration
  - `print_api_status()`: Display API readiness

## Files Modified

### 1. `src/mact_langgraph/nodes/core_nodes.py`

**Changes**:
- Added dotenv import and automatic loading at module level (lines 18-24)
- Modified `create_llm()` to explicitly pass OpenAI API key (lines 139, 178-189)
- Added error handling for missing API keys

```python
# Added at top of file
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_file = Path(__file__).parent.parent.parent.parent / '.env'
if env_file.exists():
    load_dotenv(env_file)

# In create_llm function
openai_api_key = os.getenv("OPENAI_API_KEY")
...
if not openai_api_key:
    raise ValueError(
        "OPENAI_API_KEY not found in environment. "
        "Please set it in .env file or environment variables."
    )
return ChatOpenAI(
    model=model_name,
    api_key=openai_api_key,  # Explicitly pass
    temperature=0.1,
    max_tokens=2048,
    timeout=60
)
```

### 2. `src/multi_agent/utils/env_utils.py` (NEW)

**Features**:
- Automatic .env file discovery (searches current dir and parents)
- API routing based on model name (GPT → OpenAI, others → RunPod)
- Comprehensive API status checking
- Auto-loads environment on import

### 3. `src/multi_agent/utils/__init__.py`

**Changes**:
- Exported env utility functions: `load_env_config`, `get_api_config`, `check_api_keys`, `print_api_status`

### 4. `multi_agent_main.py` and `test_multi_agent.py`

**Changes**:
- Added `from multi_agent.utils.env_utils import load_env_config`
- Call `load_env_config()` at module level (automatically executed on import)

## Testing

### Test Commands

```bash
# No longer needed:
# export OPENAI_API_KEY="..."

# Just run directly:
python test_multi_agent.py
python multi_agent_main.py --dataset_path ../datasets_examples/mmqa_samples.json --plan_model gpt-3.5-turbo --code_model gpt-3.5-turbo --output_format mmqa_json --debug --debug_limit 1 --output_dir debug_test
```

### Test Results

**Before Fix**:
```
❌ Multi-Agent Graph Error: The api_key client option must be set either by passing api_key to the client or by setting the OPENAI_API_KEY environment variable
```

**After Fix**:
```
✅ Loaded environment from: /path/to/.env
✅ OPENAI_API_KEY found
✅ Ready for GPT models (gpt-3.5-turbo, gpt-4, etc.)
✅ Ready for RunPod models (Qwen, Llama, etc.)

[Tests run successfully]
```

### Validated Scenarios

1. ✅ Single table question answering
2. ✅ Multi-table question answering
3. ✅ EDA Agent FK detection
4. ✅ All agent orchestration
5. ✅ OpenAI API calls with dotenv-loaded keys
6. ✅ RunPod API routing (for non-GPT models)

## API Configuration

### .env File Format

```bash
# OpenAI Configuration
OPENAI_API_KEY="sk-..."
OPENAI_API_BASE="https://api.openai.com/v1"

# RunPod Configuration (for Qwen, Llama, etc.)
RUNPOD_API_KEY="..."
RUNPOD_BASE_URL="https://api.runpod.ai/v2/your_endpoint/openai/v1"
```

### API Routing Logic

```python
def get_api_config(model_name: str):
    is_gpt_model = model_name and ('gpt' in model_name.lower())

    if is_gpt_model:
        # Use OpenAI API
        return {
            'api_key': OPENAI_API_KEY,
            'base_url': OPENAI_API_BASE,
            'provider': 'openai'
        }
    else:
        # Use RunPod API for non-GPT models
        return {
            'api_key': RUNPOD_API_KEY,
            'base_url': RUNPOD_BASE_URL,
            'provider': 'runpod'
        }
```

## Impact

### User Experience
- ✅ No more manual API key exports
- ✅ Cleaner workflow
- ✅ Better error messages

### Code Quality
- ✅ Explicit API key passing (more secure)
- ✅ Centralized environment management
- ✅ Better separation of concerns

### Future Work
- Consider using environment-specific .env files (.env.dev, .env.prod)
- Add support for more API providers
- Implement API key validation on startup

## Notes

### Compatibility
- Works with both OpenAI and RunPod APIs
- Backward compatible (still accepts exported env vars)
- Cross-platform (tested on macOS)

### Security
- .env file is gitignored
- API keys never printed in logs
- Explicit error messages guide users to fix configuration

### Performance
- Minimal overhead (dotenv loads once at import)
- No impact on LLM call latency

## Related Documentation

- User requested features: "매번 api key를 terminal에서 export 하지말고, dotenv를 활용해서 사용하고 싶어"
- See [env_utils.py](../src/multi_agent/utils/env_utils.py) for implementation
- See [.env.example](../.env.example) for template
