import pytest

from scheduler import cp_sat_solver, dispatch_rules, instance_loader
from scheduler.schedule import makespan, validate

ALL_INSTANCES = instance_loader.list_instances()


def test_file_contains_82_instances_and_we_know_13():
    assert len(instance_loader.load_all()) == 82
    assert len(ALL_INSTANCES) == 13


def test_ft06_was_read_correctly():
    ft06 = instance_loader.load_instance("ft06")
    assert (ft06["num_jobs"], ft06["num_machines"]) == (6, 6)
    assert ft06["jobs"][0] == [(2, 1), (0, 3), (1, 6), (3, 7), (5, 3), (4, 6)]


def test_every_job_uses_every_machine_once():
    for name in ALL_INSTANCES:
        instance = instance_loader.load_instance(name)
        for job in instance["jobs"]:
            assert sorted(machine for machine, _ in job) == list(range(instance["num_machines"]))


def test_known_values():
    assert instance_loader.best_known("ft06") == 55
    assert instance_loader.best_known("ft10") == 930


def test_unknown_instance_is_rejected():
    with pytest.raises(ValueError):
        instance_loader.load_instance("abz5")


def test_validate_catches_problems():
    ft06 = instance_loader.load_instance("ft06")
    good = dispatch_rules.dispatch(ft06, "FIFO")
    assert validate(ft06, good) == []

    overlapping = [dict(op) for op in good]
    first_on_machine = [op for op in overlapping if op["machine"] == 0][:2]
    first_on_machine[1]["start"] = first_on_machine[0]["start"]
    first_on_machine[1]["end"] = first_on_machine[0]["end"]
    assert validate(ft06, overlapping) != []

    window = {"machine": good[0]["machine"], "start": good[0]["start"], "end": good[0]["end"]}
    assert validate(ft06, good, blocked=window) != []


def test_ft06_reaches_the_known_optimum():
    ft06 = instance_loader.load_instance("ft06")
    result = cp_sat_solver.solve_instance(ft06, time_limit=20)
    assert result["status"] == "OPTIMAL"
    assert result["makespan"] == 55
    assert validate(ft06, result["schedule"]) == []


def test_ft10_reaches_the_known_optimum():
    ft10 = instance_loader.load_instance("ft10")
    result = cp_sat_solver.solve_instance(ft10, time_limit=90)
    assert result["makespan"] == 930
    assert result["status"] == "OPTIMAL"
    assert validate(ft10, result["schedule"]) == []


@pytest.mark.parametrize("name", ["la01", "la06", "ft20"])
def test_other_instances_reach_the_known_optimum(name):
    instance = instance_loader.load_instance(name)
    result = cp_sat_solver.solve_instance(instance, time_limit=60)
    assert result["makespan"] == instance_loader.best_known(name)


@pytest.mark.parametrize("rule", ["FIFO", "SPT"])
def test_dispatch_rules_give_valid_schedules_that_cannot_beat_the_optimum(rule):
    for name in ALL_INSTANCES:
        instance = instance_loader.load_instance(name)
        schedule = dispatch_rules.dispatch(instance, rule)
        assert validate(instance, schedule) == []
        assert makespan(schedule) >= instance_loader.best_known(name)


def test_the_solver_is_better_than_both_rules():
    ft06 = instance_loader.load_instance("ft06")
    fifo = makespan(dispatch_rules.dispatch(ft06, "FIFO"))
    spt = makespan(dispatch_rules.dispatch(ft06, "SPT"))
    assert 55 < fifo and 55 < spt
