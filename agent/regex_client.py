"""A rule-based question parser made of keywords and regular expressions.

It is the baseline of the evals, and it also lets the API run as a demo without any
language model (LLM_BACKEND=regex). It has the same two methods as a model client,
so it runs through exactly the same pipeline. It never invents anything: when
something is missing it asks.
"""
import re

INSTANCE = re.compile(r"\b((?:ft|la)\d{2})\b")
MACHINE = re.compile(r"machine\s+(\d+)")
RANGE = re.compile(r"(?:between|from)\s+(?:time\s+)?(\d+)\s+(?:and|to|until)\s+(?:time\s+)?(\d+)")
START = re.compile(r"(?:\bat|from|starting at|starting)\s+(?:time\s+)?(\d+)")
DURATION = re.compile(r"(?:\bfor|after|lasting|lasts)\s+(\d+)")
OTHER_UNITS = re.compile(r"\b(?:second|minute|hour|day|week)s?\b")

BREAKDOWN_WORDS = ["break", "broke", "broken", "down", "fail", "stops", "out of service", "unavailable", "outage"]
COMPARE_WORDS = ["compare", "comparison", "fifo", "spt", "rule", "heuristic", "dispatch", "benchmark", "versus", " vs "]
SOLVE_WORDS = ["solve", "schedule", "makespan", "optim", "best", "shortest", "minimum", "good"]


def ask_for(text):
    return {"tool": None, "arguments": {}, "reply": text}


def parse_breakdown(question, instance):
    if OTHER_UNITS.search(question):
        return ask_for("I can only use the time units of the instance. Please give the times in those units.")

    machine = MACHINE.search(question)
    window = RANGE.search(question)
    if window:
        start, duration = int(window.group(1)), int(window.group(2)) - int(window.group(1))
    else:
        start_match, duration_match = START.search(question), DURATION.search(question)
        start = int(start_match.group(1)) if start_match else None
        duration = int(duration_match.group(1)) if duration_match else None

    missing = [name for name, value in [("machine", machine), ("start time", start), ("duration", duration)] if value is None]
    if missing:
        return ask_for("Please tell me the " + " and the ".join(missing) + " of the breakdown.")
    return {"tool": "disrupt", "reply": "",
            "arguments": {"instance": instance, "machine": int(machine.group(1)), "start": start, "duration": duration}}


def parse(question):
    text = question.lower()
    found = INSTANCE.search(text)
    if not found:
        return ask_for("Which instance do you mean? For example ft06 or la01.")
    instance = found.group(1)

    if any(word in text for word in BREAKDOWN_WORDS):
        return parse_breakdown(text, instance)
    if any(word in text for word in COMPARE_WORDS):
        return {"tool": "compare", "arguments": {"instance": instance}, "reply": ""}
    if any(word in text for word in SOLVE_WORDS):
        return {"tool": "solve", "arguments": {"instance": instance}, "reply": ""}
    return ask_for("I can solve an instance, compare rules with the solver, or handle a machine breakdown.")


def template_answer(tool, summary):
    """A plain sentence built only from the tool output."""
    if tool == "solve":
        return (f"The best makespan for {summary['instance']} is {summary['makespan']} "
                f"(best known {summary['best_known']}, gap {summary['gap_to_best_known_percent']} percent).")
    if tool == "compare":
        parts = [f"{row['method']} {row['makespan']}" for row in summary["rows"]]
        return f"Makespan on {summary['instance']}: " + ", ".join(parts) + f". Best known is {summary['best_known']}."
    if not summary.get("feasible"):
        return "No feasible plan was found for this breakdown."
    return (f"The makespan changes from {summary['old_makespan']} to {summary['new_makespan']}. "
            f"{summary['operations_moved']} operations moved and {summary['operations_frozen']} were frozen.")


class RegexClient:
    name = "regex-baseline"

    def choose_tool(self, question, tool_specs):
        return parse(question)

    def explain(self, question, tool, summary):
        return template_answer(tool, summary)
