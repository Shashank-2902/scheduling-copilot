"""The three things the copilot can do: solve, disrupt and compare.

This is plain Python. The language model never builds a schedule itself,
it only asks for these functions to be run.
"""
import time

from scheduler import cp_sat_solver, disruption, dispatch_rules, instance_loader
from scheduler.schedule import gap_percent, makespan, validate


def solve(instance_name, time_limit=20.0):
    """Best schedule the solver can find, with its gap to the best-known makespan."""
    instance = instance_loader.load_instance(instance_name)
    result = cp_sat_solver.solve_instance(instance, time_limit=time_limit)
    best = instance_loader.best_known(instance_name)
    return {
        "instance": instance["name"],
        "status": result["status"],
        "makespan": result["makespan"],
        "best_known": best,
        "gap_to_best_known_percent": gap_percent(result["makespan"], best),
        "solve_time_s": result["solve_time_s"],
        "schedule": result["schedule"],
    }


_base_plans = {}


def get_base_plan(instance_name, time_limit=20.0):
    """The plan that is 'running' before a disruption. Solved once and then remembered."""
    key = instance_name.strip().lower()
    if key not in _base_plans:
        instance = instance_loader.load_instance(key)
        # One worker and a fixed seed, so the same plan comes out every time.
        result = cp_sat_solver.solve_instance(instance, time_limit=time_limit, workers=1, seed=0)
        _base_plans[key] = result["schedule"]
    return _base_plans[key]


def disrupt(instance_name, machine, start, duration, base_schedule=None):
    """A machine goes down at `start` for `duration`. Reschedule what has not started yet."""
    instance = instance_loader.load_instance(instance_name)
    if not 0 <= machine < instance["num_machines"]:
        raise ValueError(f"machine must be between 0 and {instance['num_machines'] - 1}")
    if start < 0 or duration <= 0:
        raise ValueError("start must be 0 or more and duration must be more than 0")

    base = base_schedule or get_base_plan(instance_name)
    result = disruption.disrupt(instance, base, machine, start, duration)
    result["instance"] = instance["name"]
    result["machine"] = machine
    result["requested_start"] = start
    result["requested_duration"] = duration

    if result["feasible"]:
        problems = validate(instance, result["schedule"], blocked=result["window"])
        if problems:
            raise RuntimeError("the new plan is not valid: " + "; ".join(problems))
    return result


def compare(instance_name, time_limit=20.0):
    """Run FIFO, SPT and the solver and return a table."""
    instance = instance_loader.load_instance(instance_name)
    best = instance_loader.best_known(instance_name)
    rows = []

    for rule in ["FIFO", "SPT"]:
        began = time.time()
        schedule = dispatch_rules.dispatch(instance, rule)
        rows.append(table_row(rule, makespan(schedule), best, time.time() - began))

    result = cp_sat_solver.solve_instance(instance, time_limit=time_limit)
    rows.append(table_row("CP-SAT", result["makespan"], best, result["solve_time_s"]))

    return {"instance": instance["name"], "best_known": best, "rows": rows}


def table_row(method, value, best, seconds):
    return {
        "method": method,
        "makespan": value,
        "gap_to_best_known_percent": gap_percent(value, best),
        "time_s": round(seconds, 2),
    }
