"""The small interface the rest of the code uses to talk to a language model.

A client must have two methods:

    choose_tool(question, tool_specs) -> {"tool": "solve" | "disrupt" | "compare" | None,
                                          "arguments": {...},
                                          "reply": "text, used when no tool was chosen"}
    explain(question, tool, summary) -> "text that explains the tool result"

Real clients are in groq_client.py and ollama_client.py. Tests use a scripted fake.
"""


class LLMUnavailable(Exception):
    """No model could be reached (no key, no network, rate limit, ...)."""


class FallbackClient:
    """Try the clients in order. The first one that works answers."""

    def __init__(self, clients):
        self.clients = clients
        self.last_used = None

    def _try(self, method, *args):
        errors = []
        for client in self.clients:
            try:
                answer = getattr(client, method)(*args)
                self.last_used = client.name
                return answer
            except Exception as error:  # noqa: BLE001  (any failure means: try the next one)
                errors.append(f"{client.name}: {error}")
        raise LLMUnavailable("; ".join(errors))

    def choose_tool(self, question, tool_specs):
        return self._try("choose_tool", question, tool_specs)

    def explain(self, question, tool, summary):
        return self._try("explain", question, tool, summary)


class UnavailableClient:
    """Stands in when no model is configured, so the API can still start and serve the direct tools."""

    name = "none"

    def __init__(self, error):
        self.error = error

    def choose_tool(self, question, tool_specs):
        raise self.error

    def explain(self, question, tool, summary):
        raise self.error
