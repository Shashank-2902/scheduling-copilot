"""The LangGraph graph. It has one job beyond calling the pipeline: a human must approve
a new plan before it is saved.

    choose tool -> run tool -> explain -> (new plan?) -> ask for approval -> pause
                                                                              |
                                  human sends approve or reject through the API
                                                                              v
                                                     save the plan (approve) or only log it (reject)

The graph pauses with interrupt(). The state is saved by the checkpointer, so the
answer can arrive minutes later, even after the API restarted.
"""
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from agent import pipeline
from agent.tools import ToolInputError


class State(TypedDict, total=False):
    thread_id: str
    question: str
    tool: str
    arguments: dict
    result: dict
    summary: dict
    answer: str
    status: str          # answered, needs_clarification, awaiting_approval, committed, rejected
    decision: str
    reviewer: str
    plan_id: int


def build_graph(llm, store, checkpointer):
    """Create the graph. llm and store are passed in, so tests can use fakes."""

    def choose_node(state):
        store.add_audit("question", state["thread_id"], {"question": state["question"]})
        chosen = pipeline.choose_step(llm, state["question"])
        if chosen["tool"] is None:
            return {"answer": chosen["reply"] or "Which instance do you mean?", "status": "needs_clarification"}
        return {"tool": chosen["tool"], "arguments": chosen["arguments"]}

    def run_node(state):
        try:
            clean, result, summary = pipeline.run_step(state["tool"], state["arguments"], store)
        except ToolInputError as error:
            return {"answer": str(error), "status": "needs_clarification"}
        return {"arguments": clean, "result": result, "summary": summary}

    def explain_node(state):
        answer = pipeline.explain_step(llm, state["question"], state["tool"], state["summary"])
        status = "awaiting_approval" if pipeline.needs_approval(state["tool"], state["result"]) else "answered"
        return {"answer": answer, "status": status}

    def request_approval_node(state):
        # Kept apart from the interrupt, because a node starts again from the top when the graph resumes.
        store.add_audit("approval_requested", state["thread_id"], {"summary": state["summary"]})
        return {}

    def approval_node(state):
        reply = interrupt({
            "message": "A new plan is ready. Send approve or reject to commit or discard it.",
            "question": state["question"],
            "summary": state["summary"],
        })
        return {"decision": reply["decision"], "reviewer": reply.get("reviewer", "unknown")}

    def finalize_node(state):
        thread_id = state["thread_id"]
        if state["decision"] != "approve":
            store.add_audit("rejected", thread_id, {"reviewer": state["reviewer"]})
            return {"status": "rejected"}

        store.add_audit("approved", thread_id, {"reviewer": state["reviewer"]})
        plan_id = store.commit_plan(
            thread_id=thread_id,
            instance=state["result"]["instance"],
            makespan=state["result"]["new_makespan"],
            schedule=state["result"]["schedule"],
            question=state["question"],
            reviewer=state["reviewer"],
            disruptions=state["result"]["windows"],
        )
        store.add_audit("committed", thread_id, {"plan_id": plan_id, "makespan": state["result"]["new_makespan"]})
        return {"status": "committed", "plan_id": plan_id}

    def after_choose(state):
        return END if state.get("status") == "needs_clarification" else "run"

    def after_run(state):
        return END if state.get("status") == "needs_clarification" else "explain"

    def after_explain(state):
        return "request_approval" if state["status"] == "awaiting_approval" else END

    graph = StateGraph(State)
    graph.add_node("choose", choose_node)
    graph.add_node("run", run_node)
    graph.add_node("explain", explain_node)
    graph.add_node("request_approval", request_approval_node)
    graph.add_node("approval", approval_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "choose")
    graph.add_conditional_edges("choose", after_choose, ["run", END])
    graph.add_conditional_edges("run", after_run, ["explain", END])
    graph.add_conditional_edges("explain", after_explain, ["request_approval", END])
    graph.add_edge("request_approval", "approval")
    graph.add_edge("approval", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=checkpointer)
