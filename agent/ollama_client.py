import json

import requests

from agent import prompts


class OllamaClient:
    """Local fallback. Needs Ollama running and a model that supports tool calling."""

    name = "ollama"

    def __init__(self, base_url="http://localhost:11434", model="llama3.1:8b"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _chat(self, messages, tools=None):
        body = {"model": self.model, "messages": messages, "stream": False, "options": {"temperature": 0}}
        if tools:
            body["tools"] = tools
        response = requests.post(f"{self.base_url}/api/chat", json=body, timeout=120)
        response.raise_for_status()
        return response.json()["message"]

    def choose_tool(self, question, tool_specs):
        message = self._chat(
            [{"role": "system", "content": prompts.CHOOSE_TOOL_PROMPT}, {"role": "user", "content": question}],
            tools=tool_specs,
        )
        calls = message.get("tool_calls") or []
        if calls:
            function = calls[0]["function"]
            arguments = function.get("arguments") or {}
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            return {"tool": function["name"], "arguments": arguments, "reply": ""}
        return {"tool": None, "arguments": {}, "reply": message.get("content", "")}

    def explain(self, question, tool, summary):
        message = self._chat([
            {"role": "system", "content": prompts.EXPLAIN_PROMPT},
            {"role": "user", "content": prompts.explain_message(question, tool, json.dumps(summary))},
        ])
        return message.get("content", "").strip()
