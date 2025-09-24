""" Utility classes and functions related to MACT (NAACL 2025). 

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

import random
import math
import asyncio
import re
from typing import Union, List, Optional
from openai import OpenAI
from config import llm_config

random.seed(42)


class UnifiedLLM:
    """Unified LLM interface using OpenAI API format for both GPT and open-source models."""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.client = llm_config.get_client_for_model(model_name)
        self.async_client = llm_config.get_async_client_for_model(model_name)
        self.is_gpt = llm_config.is_gpt_model(model_name)
        
    def __call__(self, prompt: Union[str, List[dict]], num_return_sequences: int = 1, 
                 return_prob: bool = False, max_tokens: int = 2000, 
                 temperature: float = 0.6, top_p: float = 0.95) -> List[str]:
        """Generate text using the unified OpenAI API interface."""
        
        # Prepare messages in OpenAI chat format
        if isinstance(prompt, str):
            messages = [{"role": "user", "content": prompt}]
        elif isinstance(prompt, list):
            messages = prompt
        else:
            raise ValueError("Prompt must be either string or list of message dictionaries")
        
        try:
            # Use OpenAI chat completions API for both GPT and open-source models
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                n=num_return_sequences,
                stop=None
            )
            
            # Extract generated text from all choices
            results = [choice.message.content.strip() if choice.message.content else "" for choice in response.choices]
            
            # For consistency with original interface, return probability scores if requested
            # Note: This is a simplified implementation as true logprobs may not be available
            # from all endpoints
            # if return_prob:
            #     # Generate mock probability scores for compatibility
            #     scores = [1.0 / (i + 1) for i in range(len(results))]
            #     results.append(scores)
            
            return results
            
        except Exception as e:
            print(f"Error calling LLM {self.model_name}: {e}")
            return [""]

    async def _get_completion_async(self, 
                                    prompt: str, 
                                    max_tokens: int, 
                                    temperature: float, 
                                    num_return_sequences: int, 
                                    stop_sequences: Optional[List[str]]) -> List[str]:
        """Helper for async completion calls."""
        try:
            messages = [{"role": "user", "content": prompt}]
            call_params = {
                "model": self.model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "n": num_return_sequences
            }
            if stop_sequences:
                call_params["stop"] = stop_sequences
            
            response = await self.async_client.chat.completions.create(**call_params)
            
            results = []
            for choice in response.choices:
                content = choice.message.content.strip() if choice.message.content else ""
                results.append(content)
            return results
        except Exception as e:
            print(f"Error in async LLM call for prompt '{prompt[:50]}...': {e}")
            return [""] * num_return_sequences

    async def generate_batch(self, 
                             prompts: List[str], 
                             max_tokens: int = 1000,
                             temperature: float = 0.7,
                             num_return_sequences: int = 1,
                             stop_sequences: Optional[List[str]] = None) -> List[List[str]]:
        """
        Generate text completions for a batch of prompts asynchronously.
        """
        tasks = [
            self._get_completion_async(
                prompt, max_tokens, temperature, num_return_sequences, stop_sequences
            ) for prompt in prompts
        ]
        results = await asyncio.gather(*tasks)
        return results
    
    def encode(self, prompt: str) -> int:
        """Estimate token count for a prompt.
        
        Note: This is a simplified implementation. For accurate token counting,
        you might want to use tiktoken or similar libraries.
        """
        # Simple token estimation (approximately 4 characters per token)
        return len(prompt) // 4
    
    def get_completion(self, prompt: str, n: int = 1, model: Optional[str] = None) -> List[str]:
        """Legacy method for backward compatibility with existing agent code."""
        model_to_use = model or self.model_name
        return self.__call__(prompt, num_return_sequences=n)


def get_completion(prompt: str, client: Optional[OpenAI] = None, n: int = 1, 
                  model: str = "gpt-35-turbo", max_tokens: int = 400, 
                  temperature: float = 0.6) -> List[str]:
    """Legacy function for backward compatibility with existing agent code."""
    
    # Use the unified LLM approach
    if client is None:
        llm = UnifiedLLM(model)
        return llm(prompt, num_return_sequences=n, max_tokens=max_tokens, temperature=temperature)
    else:
        # Direct client usage for legacy support
        messages = [{"role": "user", "content": prompt}]
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0,
            n=n,
            stop=None
        )
        return [item.message.content.strip() if item.message.content else "" for item in response.choices]


# For backward compatibility, create an alias
OpenSourceLLM = UnifiedLLM


def extract_answer_from_response(response: str, method: str = "last_line") -> str:
    """
    Extract answer from LLM response using various methods.
    
    Args:
        response: LLM response text
        method: Extraction method ("last_line", "boxed", "answer_prefix", "smart")
        
    Returns:
        Extracted answer string
    """
    if not response or not response.strip():
        return ""
    
    response = response.strip()
    
    if method == "smart":
        # Try multiple extraction methods in order
        for extraction_method in ["answer_prefix", "boxed", "last_line"]:
            result = extract_answer_from_response(response, extraction_method)
            if result and result != response:  # Found a shorter, extracted answer
                return result
        return response  # Fallback to full response
    
    elif method == "last_line":
        # Get the last non-empty line
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        return lines[-1] if lines else ""
    
    elif method == "boxed":
        # Look for \\boxed{answer} pattern
        boxed_pattern = r'\\boxed\{([^}]+)\}'
        matches = re.findall(boxed_pattern, response)
        return matches[-1] if matches else ""
    
    elif method == "answer_prefix":
        # Look for common answer patterns
        patterns = [
            r'(?:Answer|Final Answer|The answer is):\s*(.+)',
            r'(?:Answer|Final Answer|The answer is)\s+(.+)',
            r'.*?\$([0-9.,]+\s*million)',  # Dollar amounts first
            r'.*?(?:was|is|were|are)\s+([^.]+?)\.',
            r'.*?utilizing\s+(.+?)\.',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                extracted = match.group(1).strip()
                # Clean up common prefixes/suffixes
                extracted = re.sub(r'^(the|a|an)\s+', '', extracted, flags=re.IGNORECASE)
                return extracted
        
        return ""
    
    else:
        return response
