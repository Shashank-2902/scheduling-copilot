import pytest

from scheduler import cp_sat_solver, disruption, instance_loader, planner
from scheduler.schedule import makespan, validate

CASES = [
    ("ft06", 2, 10, 15),
    ("ft06", 0, 20, 30),
    ("la01", 1, 100, 50),
    ("la05", 3, 200, 80),
    ("ft10", 3, 300, 100),
]


def base_plan(name):
    return planner.get_base_plan(name, time_limit=10)


@pytest.mark.parametrize("name,machine,start,duration", CASES)
def test_frozen_operations_do_not_move(name, machine, start, duration):
    instance = instance_loader.load_instance(name)
    base = base_plan(name)
    result = disruption.disrupt(instance, base, machine, start, duration, time_limit=20)
    assert result["feasible"]

    new_start = {(op["job"], op["op"]): op["start"] for op in result["schedule"]}
    for op in base:
        if op["start"] < start:
            assert new_start[(op["job"], op["op"])] == op["start"], "a frozen operation moved"


@pytest.mark.parametrize("name,machine,start,duration", CASES)
def test_new_plan_is_valid_and_respects_the_breakdown(name, machine, start, duration):
    instance = instance_loader.load_instance(name)
    result = disruption.disrupt(instance, base_plan(name), machine, start, duration, time_limit=20)
    assert validate(instance, result["schedule"], blocked=result["window"]) == []
    assert result["window"]["end"] - result["window"]["start"] == duration
    assert makespan(result["schedule"]) == result["new_makespan"]


@pytest.mark.parametrize("name,machine,start,duration", CASES)
def test_nothing_that_was_not_started_begins_before_the_disruption(name, machine, start, duration):
    instance = instance_loader.load_instance(name)
    base = base_plan(name)
    result = disruption.disrupt(instance, base, machine, start, duration, time_limit=20)
    started_before = {(op["job"], op["op"]) for op in base if op["start"] < start}
    for op in result["schedule"]:
        if (op["job"], op["op"]) not in started_before:
            assert op["start"] >= start


def test_a_running_operation_on_the_broken_machine_is_allowed_to_finish():
    instance = instance_loader.load_instance("ft06")
    base = base_plan("ft06")
    running = next(op for op in base if op["start"] < 10 < op["end"])  # something is running at time 10
    result = disruption.disrupt(instance, base, running["machine"], 10, 5)
    assert result["window"]["start"] >= running["end"]
    assert validate(instance, result["schedule"], blocked=result["window"]) == []


def test_a_breakdown_after_everything_is_finished_changes_nothing():
    instance = instance_loader.load_instance("ft06")
    base = base_plan("ft06")
    result = disruption.disrupt(instance, base, 0, makespan(base) + 10, 20)
    assert result["operations_moved"] == 0
    assert result["new_makespan"] == makespan(base)
    assert result["operations_frozen"] == len(base)


def test_a_breakdown_at_time_zero_freezes_nothing():
    instance = instance_loader.load_instance("ft06")
    result = disruption.disrupt(instance, base_plan("ft06"), 0, 0, 10)
    assert result["operations_frozen"] == 0
    assert result["feasible"]


def test_planner_checks_its_inputs():
    with pytest.raises(ValueError):
        planner.disrupt("ft06", 9, 10, 5)      # machine does not exist
    with pytest.raises(ValueError):
        planner.disrupt("ft06", 1, -1, 5)      # negative start
    with pytest.raises(ValueError):
        planner.disrupt("ft06", 1, 10, 0)      # no duration


def test_the_solver_can_keep_operations_fixed():
    ft06 = instance_loader.load_instance("ft06")
    first = cp_sat_solver.solve_instance(ft06, time_limit=10)
    keep = {(op["job"], op["op"]): op["start"] for op in first["schedule"] if op["start"] < 20}
    again = cp_sat_solver.solve_instance(ft06, time_limit=10, frozen=keep)
    for op in again["schedule"]:
        if (op["job"], op["op"]) in keep:
            assert op["start"] == keep[(op["job"], op["op"])]
