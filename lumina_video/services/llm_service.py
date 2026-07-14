# Copyright (C) 2025 Lumina AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
LLM Service with Hybrid Key Pool Rotation

Automatically rotates through API keys when one fails or runs out of credits.
Exhausted keys go into 24h cooldown, then rejoin the pool.
"""

import json
import re
import time
import asyncio
from pathlib import Path
from typing import Optional, Type, TypeVar, Union, List, Dict

import yaml
from openai import AsyncOpenAI
from pydantic import BaseModel
from loguru import logger


T = TypeVar("T", bound=BaseModel)

# State file to persist key cooldowns across restarts
_STATE_FILE = Path("/tmp/lumina_llm_key_pool_state.json")


class KeyState:
    """Tracks cooldown state for a single API key"""
    
    def __init__(self, index: int, config: dict, cooldown_seconds: int = 86400):
        self.index = index
        self.provider = config.get("provider", "unknown")
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "")
        self.model = config.get("model", "")
        self.cooldown_seconds = cooldown_seconds
        
        # Cooldown tracking
        self.exhausted_at: float = 0.0  # timestamp when key was marked exhausted
        self.fail_count: int = 0
        self.total_calls: int = 0
        self.total_errors: int = 0
    
    @property
    def is_cooling_down(self) -> bool:
        """Check if key is still in cooldown period"""
        if self.exhausted_at == 0:
            return False
        elapsed = time.time() - self.exhausted_at
        if elapsed >= self.cooldown_seconds:
            # Cooldown expired, key is available again
            self.exhausted_at = 0
            self.fail_count = 0
            logger.info(f"  Key [{self.index}] {self.provider}: cooldown expired, rejoining pool")
            return False
        return True
    
    @property
    def remaining_cooldown_min(self) -> float:
        """Remaining cooldown in minutes"""
        if self.exhausted_at == 0:
            return 0
        elapsed = time.time() - self.exhausted_at
        remaining = self.cooldown_seconds - elapsed
        return max(0, remaining / 60)
    
    def mark_exhausted(self):
        """Mark key as exhausted (rate limit, no credits, etc.)"""
        self.exhausted_at = time.time()
        self.fail_count += 1
        self.total_errors += 1
        logger.warning(
            f"  Key [{self.index}] {self.provider}: exhausted "
            f"(cooldown {self.cooldown_seconds // 3600}h)"
        )
    
    def mark_success(self):
        """Record a successful call"""
        self.total_calls += 1
        self.fail_count = 0  # Reset consecutive failures
    
    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "provider": self.provider,
            "exhausted_at": self.exhausted_at,
            "fail_count": self.fail_count,
            "total_calls": self.total_calls,
            "total_errors": self.total_errors,
        }
    
    def load_state(self, data: dict):
        self.exhausted_at = data.get("exhausted_at", 0.0)
        self.fail_count = data.get("fail_count", 0)
        self.total_calls = data.get("total_calls", 0)
        self.total_errors = data.get("total_errors", 0)


class KeyPool:
    """
    API Key Pool with automatic rotation and 24h cooldown cycle.
    
    Behavior:
    1. Tries keys in pool order (primary first)
    2. On failure (rate limit, 429, auth error, timeout), marks key exhausted
    3. Exhausted keys skip for 24 hours
    4. After 24h, key rejoins the pool automatically
    5. State persists across restarts via JSON file
    """
    
    def __init__(self):
        self.keys: List[KeyState] = []
        self.current_index: int = 0
        self.cooldown_seconds: int = 86400  # 24h default
        self._load_config()
        self._load_state()
    
    def _load_config(self):
        """Load key pool from config.yaml"""
        try:
            # Find config.yaml relative to this file
            config_path = Path(__file__).parent.parent.parent / "config.yaml"
            if not config_path.exists():
                # Try from working directory
                config_path = Path("config.yaml")
            
            with open(config_path) as f:
                raw = yaml.safe_load(f)
            
            pool_config = raw.get("llm_key_pool", {})
            self.cooldown_seconds = pool_config.get("cooldown_hours", 24) * 3600
            
            keys_config = pool_config.get("keys", [])
            for i, key_cfg in enumerate(keys_config):
                self.keys.append(KeyState(i, key_cfg, self.cooldown_seconds))
            
            logger.info(f"Loaded {len(self.keys)} API keys in rotation pool")
            
        except Exception as e:
            logger.error(f"Failed to load key pool config: {e}")
    
    def _load_state(self):
        """Load persisted cooldown state"""
        if not _STATE_FILE.exists():
            return
        try:
            data = json.loads(_STATE_FILE.read_text())
            for ks in self.keys:
                key = f"{ks.provider}_{ks.index}"
                if key in data:
                    ks.load_state(data[key])
            logger.debug("Loaded key pool state from disk")
        except Exception:
            pass
    
    def _save_state(self):
        """Persist cooldown state to disk"""
        try:
            state = {}
            for ks in self.keys:
                key = f"{ks.provider}_{ks.index}"
                state[key] = ks.to_dict()
            _STATE_FILE.write_text(json.dumps(state, indent=2))
        except Exception:
            pass
    
    def get_next_key(self) -> Optional[KeyState]:
        """Get next available key from pool"""
        if not self.keys:
            return None
        
        # Try all keys starting from current position
        for _ in range(len(self.keys)):
            ks = self.keys[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.keys)
            
            if not ks.is_cooling_down:
                return ks
        
        # All keys are cooling down - find the one with shortest remaining cooldown
        best = None
        for ks in self.keys:
            if ks.is_cooling_down:
                if best is None or ks.exhausted_at > best.exhausted_at:
                    best = ks
        
        if best:
            logger.warning(
                f"All {len(self.keys)} keys cooling down. "
                f"Next available: {best.provider} in {best.remaining_cooldown_min:.0f}min"
            )
        
        return best
    
    def report_success(self, key: KeyState):
        """Report successful call"""
        key.mark_success()
        self._save_state()
    
    def report_failure(self, key: KeyState, error: Exception):
        """Report failed call - may trigger rotation"""
        error_str = str(error).lower()
        
        # Determine if this is a "rotate-worthy" error
        should_rotate = any(signal in error_str for signal in [
            "429", "rate_limit", "rate limit", "too many requests",
            "quota", "credits", "insufficient", "billing",
            "invalid_api_key", "authentication", "auth",
            "timeout", "timed out", "connection",
            "500", "502", "503", "504",
        ])
        
        if should_rotate:
            key.mark_exhausted()
            self._save_state()
    
    def get_status(self) -> List[dict]:
        """Get status of all keys in pool"""
        result = []
        for ks in self.keys:
            status = "active"
            if ks.is_cooling_down:
                status = f"cooling ({ks.remaining_cooldown_min:.0f}min left)"
            
            result.append({
                "provider": ks.provider,
                "model": ks.model,
                "status": status,
                "calls": ks.total_calls,
                "errors": ks.total_errors,
                "key_preview": ks.api_key[:12] + "..." if len(ks.api_key) > 12 else ks.api_key,
            })
        return result


# Global key pool instance
_key_pool: Optional[KeyPool] = None


def get_key_pool() -> KeyPool:
    global _key_pool
    if _key_pool is None:
        _key_pool = KeyPool()
    return _key_pool


class LLMService:
    """
    LLM Service with hybrid key pool rotation.
    
    Automatically rotates through free API keys when one fails.
    24h cooldown cycle for exhausted keys.
    """
    
    def __init__(self, config: dict):
        self._client: Optional[AsyncOpenAI] = None
        self._pool = get_key_pool()
    
    def _get_config_value(self, key: str, default=None):
        from lumina_video.config import config_manager
        return getattr(config_manager.config.llm, key, default)
    
    def _create_client(self, api_key: str, base_url: str) -> AsyncOpenAI:
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        return AsyncOpenAI(**client_kwargs)
    
    async def __call__(
        self,
        prompt: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_type: Optional[Type[T]] = None,
        **kwargs
    ) -> Union[str, T]:
        """
        Generate text using LLM with automatic key rotation.
        
        If explicit api_key is provided, uses that directly.
        Otherwise, rotates through the key pool.
        """
        # If caller provides explicit key, use it directly (no rotation)
        if api_key:
            client = self._create_client(api_key, base_url or self._get_config_value("base_url"))
            final_model = model or self._get_config_value("model") or "gpt-3.5-turbo"
            return await self._call_llm(client, final_model, prompt, temperature, max_tokens, response_type, **kwargs)
        
        # Key pool rotation mode
        last_error = None
        tried_count = 0
        
        while tried_count < len(self._pool.keys):
            key_state = self._pool.get_next_key()
            if key_state is None:
                break
            
            tried_count += 1
            client = self._create_client(key_state.api_key, key_state.base_url)
            final_model = model or key_state.model
            
            logger.info(
                f"LLM call: {key_state.provider}/{final_model} "
                f"(key #{key_state.index}, attempt {tried_count})"
            )
            
            try:
                result = await self._call_llm(
                    client, final_model, prompt, temperature, max_tokens,
                    response_type, **kwargs
                )
                self._pool.report_success(key_state)
                return result
                
            except Exception as e:
                last_error = e
                self._pool.report_failure(key_state, e)
                logger.warning(f"LLM failed ({key_state.provider}): {e}")
                continue
        
        # All keys exhausted
        logger.error(f"All {tried_count} LLM keys exhausted or failed")
        if last_error:
            raise last_error
        raise RuntimeError("No LLM providers available")
    
    async def _call_llm(
        self,
        client: AsyncOpenAI,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        response_type: Optional[Type[T]] = None,
        **kwargs
    ) -> Union[str, T]:
        """Single LLM call attempt"""
        if response_type is not None:
            return await self._call_with_structured_output(
                client, model, prompt, response_type, temperature, max_tokens, **kwargs
            )
        else:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            raw_content = response.choices[0].message.content
            result = raw_content if isinstance(raw_content, str) else ""
            if not result or not result.strip():
                logger.warning(f"LLM returned empty content (model={model})")
            return result
    
    async def _call_with_structured_output(
        self, client, model, prompt, response_type, temperature, max_tokens, **kwargs
    ) -> T:
        json_schema_instruction = self._get_json_schema_instruction(response_type)
        enhanced_prompt = f"{prompt}\n\n{json_schema_instruction}"
        
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": enhanced_prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        raw_content = response.choices[0].message.content
        content = raw_content if isinstance(raw_content, str) else ""
        
        return self._parse_response_as_model(content, response_type)
    
    def _get_json_schema_instruction(self, response_type: Type[T]) -> str:
        try:
            schema = response_type.model_json_schema()
            schema_str = json.dumps(schema, indent=2, ensure_ascii=False)
            return f"""## IMPORTANT: JSON Output Format Required
You MUST respond with ONLY a valid JSON object (no markdown, no extra text).
The JSON must strictly follow this schema:

```json
{schema_str}
```

Output ONLY the JSON object, nothing else."""
        except Exception as e:
            logger.warning(f"Failed to generate JSON schema: {e}")
            return """## IMPORTANT: JSON Output Format Required
You MUST respond with ONLY a valid JSON object (no markdown, no extra text)."""
    
    def _parse_response_as_model(self, content: str, response_type: Type[T]) -> T:
        try:
            data = json.loads(content)
            return response_type.model_validate(data)
        except json.JSONDecodeError:
            pass
        
        json_pattern = r'```(?:json)?\s*([\s\S]+?)\s*```'
        match = re.search(json_pattern, content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                return response_type.model_validate(data)
            except json.JSONDecodeError:
                pass
        
        brace_start = content.find('{')
        brace_end = content.rfind('}')
        if brace_start != -1 and brace_end > brace_start:
            try:
                json_str = content[brace_start:brace_end + 1]
                data = json.loads(json_str)
                return response_type.model_validate(data)
            except json.JSONDecodeError:
                pass
        
        raise ValueError(f"Failed to parse LLM response as {response_type.__name__}: {content[:200]}...")
    
    @property
    def active(self) -> str:
        return self._get_config_value("model", "gpt-3.5-turbo")
    
    @property
    def pool_status(self) -> List[dict]:
        """Get key pool status"""
        return self._pool.get_status()
    
    def __repr__(self) -> str:
        return f"<LLMService pool={len(self._pool.keys)} keys active>"
