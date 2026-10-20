import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from agent import llm_factory, pipeline, tools
from agent.graph import build_graph
from agent.llm_interface import FallbackClient, LLMUnavailable
from agent.memory_store import MemoryStore
from agent.plan_store import PlanStore
from agent.scripted_client import ScriptedClient
from agent.tools import ToolInputError

BREAKDOWN = {"instance": "ft06", "machine": 2, "start": 10, "duration": 15}
QUESTION = "Machine 2 breaks down at time 10 for 15 units on ft06."


@pytest.fixture(params=["memory", "postgres"])
def store(request):
    """The same tests run against the in-memory store and the real Postgres store."""
    if request.param == "memory":
        return MemoryStore()
    database_url = request.getfixturevalue("clean_tables")
    return PlanStore(database_url)


def make_graph(store, llm):
    return build_graph(llm, store, MemorySaver())


def start(graph, thread_id="t1", question=QUESTION):
    config = {"configurable": {"thread_id": thread_id}}
    graph.invoke({"thread_id": thread_id, "question": question}, config)
    return config


def decide(graph, config, decision):
    return graph.invoke(Command(resume={"decision": decision, "reviewer": "tester"}), config)


def events(store):
    return [row["event"] for row in reversed(store.list_audit())]


# ---------- the approval rule ----------

def test_a_new_plan_waits_for_approval_and_nothing_is_written(store):
    graph = make_graph(store, ScriptedClient(tool="disrupt", arguments=BREAKDOWN))
    config = start(graph)

    snapshot = graph.get_state(config)
    assert snapshot.next == ("approval",)
    assert snapshot.values["status"] == "awaiting_approval"
    assert store.list_plans() == []
    assert events(store) == ["question", "approval_requested"]


def test_without_a_decision_the_plan_is_never_written(store):
    graph = make_graph(store, ScriptedClient(tool="disrupt", arguments=BREAKDOWN))
    start(graph, "a")
    start(graph, "b")
    assert store.list_plans() == []


def test_reject_writes_no_plan_but_is_logged(store):
    graph = make_graph(store, ScriptedClient(tool="disrupt", arguments=BREAKDOWN))
    config = start(graph)
    result = decide(graph, config, "reject")

    assert result["status"] == "rejected"
    assert store.list_plans() == []
    assert events(store)[-1] == "rejected"


def test_approve_writes_exactly_the_proposed_plan(store):
    graph = make_graph(store, ScriptedClient(tool="disrupt", arguments=BREAKDOWN))
    config = start(graph)
    proposed = graph.get_state(config).values["result"]
    result = decide(graph, config, "approve")

    assert result["status"] == "committed"
    plans = store.list_plans()
    assert len(plans) == 1
    assert plans[0]["makespan"] == proposed["new_makespan"]
    assert plans[0]["reviewer"] == "tester"
    assert store.get_plan(plans[0]["id"])["schedule"] == proposed["schedule"]
    assert events(store) == ["question", "approval_requested", "approved", "committed"]


def test_the_next_breakdown_starts_from_the_committed_plan(store):
    graph = make_graph(store, ScriptedClient(tool="disrupt", arguments=BREAKDOWN))
    config = start(graph, "first")
    first_makespan = graph.get_state(config).values["result"]["new_makespan"]
    decide(graph, config, "approve")

    second_config = start(graph, "second")
    assert graph.get_state(second_config).values["result"]["old_makespan"] == first_makespan


def test_solve_and_compare_never_ask_for_approval(store):
    for tool in ["solve", "compare"]:
        graph = make_graph(store, ScriptedClient(tool=tool, arguments={"instance": "ft06"}))
        config = start(graph, tool, "question")
        assert graph.get_state(config).next == ()
        assert graph.get_state(config).values["status"] == "answered"
    assert store.list_plans() == []


# ---------- the model never builds or edits a schedule ----------

def test_the_model_can_only_choose_between_three_tools():
    names = [spec["function"]["name"] for spec in tools.tool_specs()]
    assert names == ["solve", "disrupt", "compare"]


def test_extra_arguments_from_the_model_are_dropped():
    sneaky = dict(BREAKDOWN, schedule=[{"job": 0, "op": 0, "machine": 0, "start": 0, "end": 1}], makespan=1)
    assert tools.check_arguments("disrupt", sneaky) == BREAKDOWN


# ---------- bad input from the model ----------

@pytest.mark.parametrize("arguments", [
    {"instance": "xyz99"},
    {"instance": "ft06", "machine": 9, "start": 10, "duration": 15},
    {"instance": "ft06", "machine": 1, "start": -5, "duration": 15},
    {"instance": "ft06", "machine": 1, "start": 10, "duration": 0},
    {"instance": "ft06", "machine": "two", "start": 10, "duration": 5},
    {"instance": "ft06", "machine": 1.5, "start": 10, "duration": 5},
    {"instance": "ft06", "machine": 1, "start": 10},
])
def test_bad_arguments_are_refused(arguments):
    with pytest.raises(ToolInputError):
        tools.check_arguments("disrupt", arguments)


def test_the_graph_asks_the_user_when_the_model_gives_bad_arguments(store):
    llm = ScriptedClient(tool="disrupt", arguments={"instance": "ft06", "machine": 99, "start": 10, "duration": 5})
    graph = make_graph(store, llm)
    config = start(graph)
    values = graph.get_state(config).values
    assert values["status"] == "needs_clarification"
    assert "machines 0 to 5" in values["answer"]
    assert store.list_plans() == []


def test_the_graph_returns_the_models_question_when_no_tool_is_chosen(store):
    llm = ScriptedClient(tool=None, reply="Which instance do you mean?")
    graph = make_graph(store, llm)
    config = start(graph)
    values = graph.get_state(config).values
    assert values["status"] == "needs_clarification"
    assert values["answer"] == "Which instance do you mean?"
    assert [name for name, _ in llm.calls] == ["choose_tool"]  # no tool ran, nothing to explain


# ---------- the model interface ----------

class Broken:
    name = "broken"

    def choose_tool(self, question, tool_specs):
        raise ConnectionError("no network")

    explain = choose_tool


def test_fallback_uses_the_next_client_when_the_first_fails():
    client = FallbackClient([Broken(), ScriptedClient(tool="solve", arguments={"instance": "ft06"})])
    assert client.choose_tool("x", [])["tool"] == "solve"
    assert client.last_used == "scripted"


def test_fallback_raises_when_every_client_fails():
    with pytest.raises(LLMUnavailable):
        FallbackClient([Broken(), Broken()]).choose_tool("x", [])


def test_no_key_means_no_client():
    with pytest.raises(LLMUnavailable):
        llm_factory.make_llm_client()


def test_pipeline_ask_runs_without_the_graph():
    state = pipeline.ask(ScriptedClient(tool="solve", arguments={"instance": "la01"}), "Solve la01")
    assert state["summary"]["makespan"] == 666
