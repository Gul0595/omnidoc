"""
core/llm_chain.py — Multi-LLM Fallback Chain

Priority order (tries each in sequence until one succeeds):
  1. Ollama     — local GPU (RTX 4050), dev only, unlimited
  2. Groq       — cloud free tier, 14,400 req/day  ← CREDENTIAL REQUIRED
  3. Gemini     — cloud free tier, 1,500 req/day   ← CREDENTIAL REQUIRED
  4. Cloudflare — cloud free tier, 10,000 req/day  ← CREDENTIAL REQUIRED
  5. HuggingFace— cloud, always-on fallback        ← CREDENTIAL REQUIRED

Set keys in .env — the chain auto-builds from whatever is configured.
"""
import os, time, logging
from typing import Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    OLLAMA      = "ollama"
    GROQ        = "groq"
    GEMINI      = "gemini"
    CLOUDFLARE  = "cloudflare"
    HUGGINGFACE = "huggingface"


@dataclass
class LLMResponse:
    content:    str
    provider:   LLMProvider
    latency_ms: float


class LLMChain:
    def __init__(self):
        self.chain: list[LLMProvider] = []
        self._build()

    def _build(self):
        if os.getenv("OLLAMA_URL"):
            self.chain.append(LLMProvider.OLLAMA)
        if os.getenv("GROQ_API_KEY"):
            self.chain.append(LLMProvider.GROQ)
        if os.getenv("GEMINI_API_KEY"):
            self.chain.append(LLMProvider.GEMINI)
        if os.getenv("CLOUDFLARE_ACCOUNT_ID") and os.getenv("CLOUDFLARE_API_TOKEN"):
            self.chain.append(LLMProvider.CLOUDFLARE)
        if os.getenv("HUGGINGFACE_API_KEY"):
            self.chain.append(LLMProvider.HUGGINGFACE)
        if not self.chain:
            raise RuntimeError(
                "No LLM provider configured.\n"
                "Set at least one of: GROQ_API_KEY, GEMINI_API_KEY, "
                "CLOUDFLARE_API_TOKEN, HUGGINGFACE_API_KEY in your .env file.\n"
                "Get free keys:\n"
                "  Groq:        https://console.groq.com\n"
                "  Gemini:      https://aistudio.google.com\n"
                "  Cloudflare:  https://dash.cloudflare.com -> Workers AI"
            )
        logger.info(f"LLM chain: {[p.value for p in self.chain]}")

    async def invoke(self, prompt: str, system_prompt: str = "",
                     temperature: float = 0.1, max_tokens: int = 2048) -> LLMResponse:
        last_error = None
        for provider in self.chain:
            try:
                start   = time.time()
                content = await self._call(provider, prompt, system_prompt,
                                           temperature, max_tokens)
                latency = (time.time() - start) * 1000
                logger.info(f"LLM OK: {provider.value} ({latency:.0f}ms)")
                return LLMResponse(content=content, provider=provider, latency_ms=latency)
            except Exception as e:
                last_error = e
                logger.warning(f"LLM FAIL: {provider.value} — {e}. Trying next...")
        raise RuntimeError(f"All LLM providers failed. Last: {last_error}")

    async def _call(self, provider: LLMProvider, prompt: str,
                    system_prompt: str, temperature: float, max_tokens: int) -> str:
        if provider == LLMProvider.OLLAMA:
            return await self._ollama(prompt, system_prompt, temperature, max_tokens)
        elif provider == LLMProvider.GROQ:
            return await self._groq(prompt, system_prompt, temperature, max_tokens)
        elif provider == LLMProvider.GEMINI:
            return await self._gemini(prompt, system_prompt, temperature, max_tokens)
        elif provider == LLMProvider.CLOUDFLARE:
            return await self._cloudflare(prompt, system_prompt, temperature, max_tokens)
        elif provider == LLMProvider.HUGGINGFACE:
            return await self._huggingface(prompt, system_prompt, temperature, max_tokens)
        raise ValueError(f"Unknown provider: {provider}")

    async def _ollama(self, prompt, system_prompt, temperature, max_tokens) -> str:
        import httpx
        url   = os.getenv("OLLAMA_URL", "http://localhost:11434")
        model = os.getenv("OLLAMA_MODEL", "llama3.1")
        msgs  = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.append({"role": "user", "content": prompt})
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(f"{url}/api/chat",
                json={"model": model, "messages": msgs, "stream": False,
                      "options": {"temperature": temperature, "num_predict": max_tokens}})
            r.raise_for_status()
            return r.json()["message"]["content"]

    async def _groq(self, prompt, system_prompt, temperature, max_tokens) -> str:
        import httpx
        model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        msgs  = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.append({"role": "user", "content": prompt})
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"},
                json={"model": model, "messages": msgs,
                      "temperature": temperature, "max_tokens": max_tokens})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    async def _gemini(self, prompt, system_prompt, temperature, max_tokens) -> str:
        import httpx
        model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        full  = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": os.getenv("GEMINI_API_KEY")},
                json={"contents": [{"parts": [{"text": full}]}],
                      "generationConfig": {"temperature": temperature,
                                           "maxOutputTokens": max_tokens}})
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    async def _cloudflare(self, prompt, system_prompt, temperature, max_tokens) -> str:
        import httpx
        account = os.getenv("CLOUDFLARE_ACCOUNT_ID")
        token   = os.getenv("CLOUDFLARE_API_TOKEN")
        model   = os.getenv("CLOUDFLARE_MODEL", "@cf/meta/llama-3.1-8b-instruct")
        msgs    = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.append({"role": "user", "content": prompt})
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}",
                headers={"Authorization": f"Bearer {token}"},
                json={"messages": msgs, "max_tokens": max_tokens})
            r.raise_for_status()
            return r.json()["result"]["response"]

    async def _huggingface(self, prompt, system_prompt, temperature, max_tokens) -> str:
        import httpx
        model = os.getenv("HUGGINGFACE_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")
        full  = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(
                f"https://api-inference.huggingface.co/models/{model}",
                headers={"Authorization": f"Bearer {os.getenv('HUGGINGFACE_API_KEY')}"},
                json={"inputs": full,
                      "parameters": {"max_new_tokens": max_tokens,
                                     "temperature": temperature,
                                     "return_full_text": False}})
            r.raise_for_status()
            result = r.json()
            if isinstance(result, list):
                return result[0].get("generated_text", "")
            return result.get("generated_text", str(result))

    def status(self) -> dict:
        return {
            "chain":     [p.value for p in self.chain],
            "primary":   self.chain[0].value if self.chain else None,
            "fallbacks": [p.value for p in self.chain[1:]],
            "total":     len(self.chain),
        }


_instance: Optional[LLMChain] = None


def get_llm_chain() -> LLMChain:
    global _instance
    if _instance is None:
        _instance = LLMChain()
    return _instance
