import json

from agent import prompts


class GroqClient:
    name = "groq"

    def __init__(self, api_key, model="openai/gpt-oss-20b"):
        from groq import Groq  # imported here so the tests do not need the package configured

        self.client = Groq(api_key=api_key)
        self.model = model

    def choose_tool(self, question, tool_specs):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompts.CHOOSE_TOOL_PROMPT},
                {"role": "user", "content": question},
            ],
            tools=tool_specs,
            tool_choice="auto",
            temperature=0,
        )
        message = response.choices[0].message

        if message.tool_calls:
            call = message.tool_calls[0]
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                return {"tool": None, "arguments": {}, "reply": "I could not read the tool arguments. Please rephrase."}
            return {"tool": call.function.name, "arguments": arguments, "reply": ""}

        return {"tool": None, "arguments": {}, "reply": message.content or ""}

    def explain(self, question, tool, summary):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompts.EXPLAIN_PROMPT},
                {"role": "user", "content": prompts.explain_message(question, tool, json.dumps(summary))},
            ],
            temperature=0,
        )
        return (response.choices[0].message.content or "").strip()
