import os

from agent.groq_client import GroqClient
from agent.llm_interface import FallbackClient, LLMUnavailable
from agent.ollama_client import OllamaClient
from agent.regex_client import RegexClient


def make_llm_client():
    """Build the model client from environment variables.

    GROQ_API_KEY (and GROQ_MODEL) turn Groq on. OLLAMA_URL (and OLLAMA_MODEL) turn Ollama on.
    Groq is tried first, Ollama is the fallback.
    LLM_BACKEND=regex skips models completely and uses the rule-based parser (demo mode).
    """
    if os.getenv("LLM_BACKEND") == "regex":
        return RegexClient()  # demo mode: no model, only simple phrasing is understood

    clients = []
    if os.getenv("GROQ_API_KEY"):
        clients.append(GroqClient(os.environ["GROQ_API_KEY"], os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")))
    if os.getenv("OLLAMA_URL"):
        clients.append(OllamaClient(os.environ["OLLAMA_URL"], os.getenv("OLLAMA_MODEL", "llama3.1:8b")))
    if not clients:
        raise LLMUnavailable("No language model is configured. Set GROQ_API_KEY (or OLLAMA_URL) in .env.")
    return FallbackClient(clients)
