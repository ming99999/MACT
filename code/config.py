""" Configuration module for unified LLM client management.

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
from typing import Dict, Optional
from dotenv import load_dotenv
from openai import OpenAI, AsyncOpenAI


class LLMConfig:
    """Configuration class for unified LLM client management."""
    
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # OpenAI API Configuration
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_base_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        self.openai_org_id = os.getenv("OPENAI_ORG_ID")
        
        # RunPod vLLM Configuration
        self.runpod_api_key = os.getenv("RUNPOD_API_KEY")
        self.runpod_base_url = os.getenv("RUNPOD_BASE_URL")
        
        # Model routing configuration
        self.gpt_models = {"gpt-3.5-turbo", "gpt-35-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o"}
        self.open_source_models = {"qwen", "llama", "mistral", "phi", "codellama"}
        
    def get_client_for_model(self, model_name: str) -> OpenAI:
        """Get appropriate OpenAI client based on model name."""
        model_name_lower = model_name.lower()
        
        # Route GPT models to OpenAI
        if any(gpt_model in model_name_lower for gpt_model in self.gpt_models):
            return self._get_openai_client()
        
        # Route open-source models to RunPod vLLM
        elif any(os_model in model_name_lower for os_model in self.open_source_models):
            return self._get_runpod_client()
        
        # Default to OpenAI for unknown models
        else:
            return self._get_openai_client()

    def get_async_client_for_model(self, model_name: str) -> AsyncOpenAI:
        """Get appropriate AsyncOpenAI client based on model name."""
        model_name_lower = model_name.lower()
        
        # Route GPT models to OpenAI
        if any(gpt_model in model_name_lower for gpt_model in self.gpt_models):
            return self._get_async_openai_client()
        
        # Route open-source models to RunPod vLLM
        elif any(os_model in model_name_lower for os_model in self.open_source_models):
            return self._get_async_runpod_client()
        
        # Default to OpenAI for unknown models
        else:
            return self._get_async_openai_client()
    
    def _get_openai_client(self) -> OpenAI:
        """Get OpenAI client for GPT models."""
        try:
            return OpenAI(
                api_key=self.openai_api_key,
                base_url=self.openai_base_url,
                organization=self.openai_org_id if self.openai_org_id else None
            )
        except Exception as e:
            # Fallback for different OpenAI client versions
            return OpenAI(
                api_key=self.openai_api_key,
                base_url=self.openai_base_url
            )
    
    def _get_runpod_client(self) -> OpenAI:
        """Get OpenAI client configured for RunPod vLLM endpoint."""
        if not self.runpod_api_key or not self.runpod_base_url:
            raise ValueError(
                "RunPod configuration missing. Please set RUNPOD_API_KEY and RUNPOD_BASE_URL "
                "environment variables."
            )
        
        return OpenAI(
            api_key=self.runpod_api_key,
            base_url=self.runpod_base_url,
        )

    def _get_async_openai_client(self) -> AsyncOpenAI:
        """Create AsyncOpenAI client for GPT models."""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        client_kwargs = {
            "api_key": self.openai_api_key,
            "base_url": self.openai_base_url
        }
        
        if self.openai_org_id:
            client_kwargs["organization"] = self.openai_org_id
        
        return AsyncOpenAI(**client_kwargs)

    def _get_async_runpod_client(self) -> AsyncOpenAI:
        """Create OpenAI-compatible async client for RunPod vLLM."""
        if not self.runpod_api_key or not self.runpod_base_url:
            raise ValueError("RUNPOD_API_KEY and RUNPOD_BASE_URL must be set for open-source models")
        
        return AsyncOpenAI(
            api_key=self.runpod_api_key,
            base_url=self.runpod_base_url
        )
    
    def is_gpt_model(self, model_name: str) -> bool:
        """Check if model is a GPT model."""
        return any(gpt_model in model_name.lower() for gpt_model in self.gpt_models)
    
    def is_open_source_model(self, model_name: str) -> bool:
        """Check if model is an open-source model."""
        return any(os_model in model_name.lower() for os_model in self.open_source_models)


# Global configuration instance
llm_config = LLMConfig()
