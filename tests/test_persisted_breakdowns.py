"""A breakdown that was approved earlier must stay in force for later disruptions."""
import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from agent import pipeline
from agent.graph import build_graph
from agent.memory_store import MemoryStore
from agent.plan_store import PlanStore
from agent.scripted_client import ScriptedClient
from api.main import create_app, make_checkpointer
from scheduler import cp_sat_solver, disruption, instance_loader, planner
from scheduler.schedule import merge_windows, validate

FIRST = {"instance": "ft06", "machine": 2, "start": 10, "duration": 15}
SECOND = {"instance": "ft06", "machine": 3, "start": 5, "duration": 10}


@pytest.fixture(params=["memory", "postgres"])
def store(request):
    if request.param == "memory":
        return MemoryStore()
    return PlanStore(request.getfixturevalue("clean_tables"))


def run_and_approve(store, arguments, thread_id):
    graph = build_graph(ScriptedClient(tool="disrupt", arguments=arguments), store, MemorySaver())
    config = {"configurable": {"thread_id": thread_id}}
    graph.invoke({"thread_id": thread_id, "question": "q"}, config)
    proposed = graph.get_state(config).values["result"]
    graph.invoke(Command(resume={"decision": "approve", "reviewer": "tester"}), config)
    return proposed


def ops_inside(schedule, window):
    return [op for op in schedule
            if op["machine"] == window["machine"] and op["start"] < window["end"] and op["end"] > window["start"]]


# ---------- (a) an approved breakdown stays in force ----------

def test_a_later_disruption_keeps_the_earlier_machine_idle(store):
    run_and_approve(store, FIRST, "first")
    first_window = store.latest_plan("ft06")["disruptions"][0]
    assert first_window["machine"] == 2

    second = run_and_approve(store, SECOND, "second")
    instance = instance_loader.load_instance("ft06")
    assert ops_inside(second["schedule"], first_window) == []
    assert validate(instance, second["schedule"], blocked=second["windows"]) == []
    assert second["windows"][0] == first_window and len(second["windows"]) == 2


def test_the_stored_windows_grow_with_every_approved_breakdown(store):
    run_and_approve(store, FIRST, "first")
    assert len(store.latest_plan("ft06")["disruptions"]) == 1
    run_and_approve(store, SECOND, "second")
    stored = store.latest_plan("ft06")["disruptions"]
    assert [w["machine"] for w in stored] == [2, 3]


def test_without_the_earlier_windows_the_old_plan_would_have_used_the_broken_machine():
    """The control: this is the bug that the stored windows fix."""
    first = planner.disrupt("ft06", FIRST["machine"], FIRST["start"], FIRST["duration"])
    window = first["window"]
    forgetful = planner.disrupt("ft06", SECOND["machine"], SECOND["start"], SECOND["duration"],
                                base_schedule=first["schedule"])
    assert ops_inside(forgetful["schedule"], window) != []
    careful = planner.disrupt("ft06", SECOND["machine"], SECOND["start"], SECOND["duration"],
                              base_schedule=first["schedule"], earlier_windows=first["windows"])
    assert ops_inside(careful["schedule"], window) == []


def test_the_pipeline_reads_the_windows_from_the_store():
    store = MemoryStore()
    run_and_approve(store, FIRST, "first")
    _, result, _ = pipeline.run_step("disrupt", SECOND, store)
    assert len(result["windows"]) == 2


# ---------- (b) the direct /disrupt endpoint does the same ----------

def test_the_direct_disrupt_endpoint_respects_the_earlier_window(clean_tables):
    database = clean_tables
    app = create_app(store=PlanStore(database), llm=ScriptedClient(tool="disrupt", arguments=FIRST),
                     checkpointer=make_checkpointer(database))
    with TestClient(app) as client:
        thread_id = client.post("/ask", json={"question": "Machine 2 is down on ft06"}).json()["thread_id"]
        assert client.post(f"/approvals/{thread_id}", json={"decision": "approve"}).json()["status"] == "committed"
        first_window = PlanStore(database).latest_plan("ft06")["disruptions"][0]

        moved = client.post("/disrupt", json=SECOND).json()
        assert moved["feasible"]
        assert ops_inside(moved["schedule"], first_window) == []
        assert len(moved["windows"]) == 2
        assert len(client.get("/plans").json()) == 1


# ---------- (c) no earlier plan: nothing changes ----------

def test_with_no_earlier_plan_the_result_is_the_same_as_before():
    instance = instance_loader.load_instance("ft06")
    base = planner.get_base_plan("ft06", time_limit=10)
    plain = disruption.disrupt(instance, base, 2, 10, 15)
    with_none = disruption.disrupt(instance, base, 2, 10, 15, earlier_windows=None)
    with_empty = disruption.disrupt(instance, base, 2, 10, 15, earlier_windows=[])
    assert plain["schedule"] == with_none["schedule"] == with_empty["schedule"]
    assert plain["windows"] == [plain["window"]]


def test_one_window_as_a_dict_or_as_a_list_gives_the_same_schedule():
    instance = instance_loader.load_instance("ft06")
    window = {"machine": 2, "start": 13, "end": 28}
    as_dict = cp_sat_solver.solve_instance(instance, time_limit=10, workers=1, blocked=window)
    as_list = cp_sat_solver.solve_instance(instance, time_limit=10, workers=1, blocked=[window])
    assert as_dict["schedule"] == as_list["schedule"]
    assert as_dict["makespan"] == as_list["makespan"]


def test_the_store_has_no_windows_for_an_instance_without_a_plan():
    assert MemoryStore().latest_plan("ft06") is None


# ---------- (d) overlapping windows are merged ----------

def test_overlapping_and_touching_windows_of_one_machine_are_merged():
    windows = [
        {"machine": 2, "start": 10, "end": 20},
        {"machine": 2, "start": 15, "end": 30},
        {"machine": 2, "start": 30, "end": 35},
        {"machine": 2, "start": 40, "end": 45},
        {"machine": 1, "start": 12, "end": 18},
    ]
    assert merge_windows(windows) == [
        {"machine": 1, "start": 12, "end": 18},
        {"machine": 2, "start": 10, "end": 35},
        {"machine": 2, "start": 40, "end": 45},
    ]


def test_merging_does_not_change_the_windows_it_was_given():
    windows = [{"machine": 2, "start": 10, "end": 20}, {"machine": 2, "start": 15, "end": 30}]
    merge_windows(windows)
    assert windows == [{"machine": 2, "start": 10, "end": 20}, {"machine": 2, "start": 15, "end": 30}]


def test_two_overlapping_windows_on_one_machine_still_give_a_feasible_plan():
    instance = instance_loader.load_instance("ft06")
    windows = [{"machine": 2, "start": 13, "end": 28}, {"machine": 2, "start": 20, "end": 40}]
    result = cp_sat_solver.solve_instance(instance, time_limit=10, workers=1, blocked=windows)
    assert result["status"] in ("OPTIMAL", "FEASIBLE")
    assert validate(instance, result["schedule"], blocked=windows) == []


def test_a_second_breakdown_that_overlaps_the_first_is_feasible():
    first = planner.disrupt("ft06", 2, 10, 15)
    overlapping = planner.disrupt("ft06", 2, 20, 15, base_schedule=first["schedule"], earlier_windows=first["windows"])
    assert overlapping["feasible"]
    instance = instance_loader.load_instance("ft06")
    assert validate(instance, overlapping["schedule"], blocked=overlapping["windows"]) == []


# ---------- (e) frozen operations are unchanged ----------

def test_frozen_operations_still_keep_their_start_time_with_earlier_windows():
    first = planner.disrupt("ft06", FIRST["machine"], FIRST["start"], FIRST["duration"])
    second = planner.disrupt("ft06", SECOND["machine"], SECOND["start"], SECOND["duration"],
                             base_schedule=first["schedule"], earlier_windows=first["windows"])
    new_start = {(op["job"], op["op"]): op["start"] for op in second["schedule"]}
    frozen = [op for op in first["schedule"] if op["start"] < SECOND["start"]]
    assert len(frozen) == second["operations_frozen"] > 0
    for op in frozen:
        assert new_start[(op["job"], op["op"])] == op["start"]


def test_the_same_question_still_gives_the_same_plan_with_earlier_windows():
    first = planner.disrupt("ft06", FIRST["machine"], FIRST["start"], FIRST["duration"])
    runs = [planner.disrupt("ft06", SECOND["machine"], SECOND["start"], SECOND["duration"],
                            base_schedule=first["schedule"], earlier_windows=first["windows"]) for _ in range(2)]
    assert runs[0]["schedule"] == runs[1]["schedule"]
