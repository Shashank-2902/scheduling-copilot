"""The steps of answering a question. The LangGraph graph and the evals both use these,
so what is measured is exactly what runs in the API.

    choose a tool  ->  run it  ->  explain the result
"""
from agent import tools
from agent.tools import ToolInputError


def choose_step(llm, question):
    """Ask the model which tool to use. Returns {"tool", "arguments", "reply"}."""
    return llm.choose_tool(question, tools.tool_specs())


def run_step(tool, arguments, store=None):
    """Check the arguments and run the tool. Raises ToolInputError if the arguments are not usable."""
    clean = tools.check_arguments(tool, arguments)

    base_schedule = None
    if tool == "disrupt" and store is not None:
        base_schedule = store.latest_schedule(clean["instance"])

    try:
        result = tools.run_tool(tool, clean, base_schedule=base_schedule)
    except ValueError as error:
        raise ToolInputError(str(error))
    return clean, result, tools.summarize(result)


def explain_step(llm, question, tool, summary):
    return llm.explain(question, tool, summary)


def needs_approval(tool, result):
    """Only a new plan after a breakdown can be committed, and only if one was found."""
    return tool == "disrupt" and result.get("feasible", False)


def ask(llm, question, store=None):
    """Run the whole pipeline without the approval step. Used by the evals."""
    state = {"question": question, "tool": None, "arguments": {}, "result": None, "summary": None,
             "answer": "", "status": "answered"}

    chosen = choose_step(llm, question)
    if chosen["tool"] is None:
        state.update(answer=chosen["reply"] or "Which instance do you mean?", status="needs_clarification")
        return state
    state.update(tool=chosen["tool"], arguments=chosen["arguments"])

    try:
        clean, result, summary = run_step(chosen["tool"], chosen["arguments"], store)
    except ToolInputError as error:
        state.update(answer=str(error), status="needs_clarification")
        return state

    state.update(arguments=clean, result=result, summary=summary)
    state["answer"] = explain_step(llm, question, chosen["tool"], summary)
    return state

