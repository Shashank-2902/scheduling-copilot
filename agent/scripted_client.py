"""A fake language model for tests and demos without a key.

It does not understand anything: it returns what it was told to return.
"""
import json


class ScriptedClient:
    name = "scripted"

    def __init__(self, tool=None, arguments=None, reply="", explain_text=None):
        self.tool = tool
        self.arguments = arguments or {}
        self.reply = reply
        self.explain_text = explain_text
        self.calls = []

    def choose_tool(self, question, tool_specs):
        self.calls.append(("choose_tool", question))
        return {"tool": self.tool, "arguments": dict(self.arguments), "reply": self.reply}

    def explain(self, question, tool, summary):
        self.calls.append(("explain", question))
        if self.explain_text is not None:
            return self.explain_text
        # Default: repeat the real numbers, like a well-behaved model would.
        return "Result: " + json.dumps(summary, sort_keys=True)
