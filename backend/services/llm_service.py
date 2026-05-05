"""LLM Service - Gemini (new SDK), Groq, and Ollama with async + vision support."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from backend.config import (
    LLM_PROVIDER,
    OLLAMA_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_FALLBACK_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
)

logger = logging.getLogger(__name__)

# --- Dependency checks ---

try:
    from google import genai as google_genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-genai not available")

try:
    import groq as groq_lib
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logger.warning("groq not available")

try:
    import ollama as ollama_lib
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logger.warning("ollama not available")


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, temperature: float = 0.1) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    async def async_generate(self, prompt: str, temperature: float = 0.1) -> str:
        """Default async wrapper using thread pool."""
        return await asyncio.to_thread(self.generate, prompt, temperature)

    def generate_vision(self, prompt: str, image) -> str:
        """Generate from image + text. Override in vision-capable providers."""
        raise NotImplementedError("Vision not supported by this provider")

    async def async_generate_vision(self, prompt: str, image) -> str:
        return await asyncio.to_thread(self.generate_vision, prompt, image)


class GeminiProvider(LLMProvider):
    """Google Gemini via new google-genai SDK. Free tier: gemini-2.0-flash."""

    def __init__(self, api_key: str = GEMINI_API_KEY, model: str = GEMINI_MODEL):
        self.api_key = api_key
        self.model_name = model
        self._client: Optional[Any] = None

    def _get_client(self):
        if self._client is None:
            if not GEMINI_AVAILABLE:
                raise RuntimeError("google-genai not installed")
            if not self.api_key or "your-gemini" in self.api_key:
                raise RuntimeError("Gemini API key not configured")
            self._client = google_genai.Client(api_key=self.api_key)
            logger.info(f"Gemini client initialized: {self.model_name}")
        return self._client

    def generate(self, prompt: str, temperature: float = 0.1) -> str:
        client = self._get_client()
        for model in [self.model_name, GEMINI_FALLBACK_MODEL]:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(temperature=temperature),
                )
                return response.text
            except Exception as e:
                err = str(e)
                if "429" in err or "RESOURCE_EXHAUSTED" in err:
                    logger.warning(f"Gemini quota exceeded for {model}, trying fallback")
                    continue
                raise
        raise RuntimeError("All Gemini models quota exhausted")

    def generate_vision(self, prompt: str, image) -> str:
        """Generate with image input (PIL Image or bytes)."""
        client = self._get_client()
        for model in [self.model_name, GEMINI_FALLBACK_MODEL]:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=[prompt, image],
                    config=genai_types.GenerateContentConfig(temperature=0.1),
                )
                return response.text
            except Exception as e:
                err = str(e)
                if "429" in err or "RESOURCE_EXHAUSTED" in err:
                    logger.warning(f"Gemini vision quota exceeded for {model}, trying fallback")
                    continue
                raise
        raise RuntimeError("All Gemini vision models quota exhausted")

    def is_available(self) -> bool:
        if not GEMINI_AVAILABLE:
            return False
        if not self.api_key or "your-gemini" in self.api_key:
            return False
        try:
            self._get_client()
            return True
        except Exception:
            return False


class GroqProvider(LLMProvider):
    """Groq cloud inference - free tier with LLaMA 3.3 70B."""

    def __init__(self, api_key: str = GROQ_API_KEY, model: str = GROQ_MODEL):
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str, temperature: float = 0.1) -> str:
        if not GROQ_AVAILABLE:
            raise RuntimeError("groq not installed")
        client = groq_lib.Groq(api_key=self.api_key)
        resp = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=2048,
        )
        return resp.choices[0].message.content

    async def async_generate(self, prompt: str, temperature: float = 0.1) -> str:
        """Native async via Groq AsyncClient."""
        if not GROQ_AVAILABLE:
            raise RuntimeError("groq not installed")
        client = groq_lib.AsyncGroq(api_key=self.api_key)
        resp = await client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=2048,
        )
        return resp.choices[0].message.content

    def is_available(self) -> bool:
        return GROQ_AVAILABLE and bool(self.api_key)


class OllamaProvider(LLMProvider):
    """Local Ollama provider."""

    def __init__(self, model: str = OLLAMA_MODEL):
        self.model = model

    def generate(self, prompt: str, temperature: float = 0.1) -> str:
        if not OLLAMA_AVAILABLE:
            raise RuntimeError("ollama not installed")
        resp = ollama_lib.generate(
            model=self.model,
            prompt=prompt,
            options={"temperature": temperature},
        )
        return resp["response"]

    def is_available(self) -> bool:
        if not OLLAMA_AVAILABLE:
            return False
        try:
            ollama_lib.list()
            return True
        except Exception:
            return False


class LLMService:
    """
    Multi-provider LLM service with async support and vision capability.

    Provider priority: configured provider → fallback chain
    Vision (OCR): Gemini only (Groq has no vision support)
    """

    def __init__(self, provider: Optional[str] = None):
        self.provider_name = provider or LLM_PROVIDER
        self._provider: Optional[LLMProvider] = None
        self._vision_provider: Optional[LLMProvider] = None
        self._initialize()

    def _initialize(self):
        order = [self.provider_name] + [p for p in ["gemini", "groq", "ollama"] if p != self.provider_name]

        for name in order:
            p = self._build_provider(name)
            if p and p.is_available():
                self._provider = p
                self.provider_name = name
                logger.info(f"LLM provider: {name}")
                break

        if self._provider is None:
            logger.warning("No LLM provider available - using rule-based fallbacks")

        # Vision always uses Gemini (only provider with free vision support)
        if GEMINI_AVAILABLE and GEMINI_API_KEY and "your-gemini" not in GEMINI_API_KEY:
            vision = GeminiProvider()
            if vision.is_available():
                self._vision_provider = vision
                logger.info("Vision provider: Gemini")

    def _build_provider(self, name: str) -> Optional[LLMProvider]:
        try:
            if name == "gemini":
                return GeminiProvider()
            elif name == "groq":
                return GroqProvider()
            elif name == "ollama":
                return OllamaProvider()
        except Exception as e:
            logger.debug(f"Could not build {name} provider: {e}")
        return None

    # --- Sync API ---

    def generate(self, prompt: str, temperature: float = 0.1) -> Optional[str]:
        if not self._provider:
            return None
        try:
            return self._provider.generate(prompt, temperature)
        except Exception as e:
            logger.error(f"LLM generate failed: {e}")
            return None

    # --- Async API ---

    async def async_generate(self, prompt: str, temperature: float = 0.1) -> Optional[str]:
        if not self._provider:
            return None
        try:
            return await self._provider.async_generate(prompt, temperature)
        except Exception as e:
            logger.error(f"Async LLM generate failed: {e}")
            return None

    async def async_generate_vision(self, prompt: str, image) -> Optional[str]:
        """Generate from image + prompt. Requires Gemini."""
        if not self._vision_provider:
            logger.warning("No vision provider available")
            return None
        try:
            return await self._vision_provider.async_generate_vision(prompt, image)
        except Exception as e:
            logger.error(f"Vision generate failed: {e}")
            return None

    def has_vision(self) -> bool:
        return self._vision_provider is not None

    def is_available(self) -> bool:
        return self._provider is not None

    def get_provider_name(self) -> str:
        return self.provider_name if self._provider else "none"

    def get_status(self) -> Dict[str, Any]:
        return {
            "active_provider": self.get_provider_name(),
            "vision_available": self.has_vision(),
            "gemini": {
                "installed": GEMINI_AVAILABLE,
                "configured": bool(GEMINI_API_KEY and "your-gemini" not in GEMINI_API_KEY),
                "model": GEMINI_MODEL,
            },
            "groq": {
                "installed": GROQ_AVAILABLE,
                "configured": bool(GROQ_API_KEY),
                "model": GROQ_MODEL,
            },
            "ollama": {
                "installed": OLLAMA_AVAILABLE,
                "model": OLLAMA_MODEL,
            },
        }


# Singleton
llm_service = LLMService()


def get_llm_service(provider: Optional[str] = None) -> LLMService:
    if provider and provider != llm_service.provider_name:
        return LLMService(provider)
    return llm_service
