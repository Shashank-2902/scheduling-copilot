"""The CP-SAT model of the job-shop problem.

Every operation is an interval with a fixed length. Two things are required:
  1. the steps of a job run in order (precedence);
  2. on each machine, intervals do not overlap (no-overlap).
The objective is to make the last end time (the makespan) as small as possible.
"""
from ortools.sat.python import cp_model

from scheduler.schedule import merge_windows

STATUS_NAMES = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.MODEL_INVALID: "MODEL_INVALID",
    cp_model.UNKNOWN: "UNKNOWN",
}


def solve_instance(instance, time_limit=20.0, workers=8, seed=0,
                   frozen=None, blocked=None, earliest_start=0, hint=None):
    """Solve the instance.

    frozen         dict {(job, op): start} of operations that must keep their start time
    blocked        one dict {"machine": m, "start": s, "end": e} or a list of them: the machine cannot
                   work in those windows. Overlapping or touching windows of a machine are merged.
    earliest_start operations that are not frozen may not start before this time
    hint           a schedule used as a starting guess for the solver
    """
    frozen = frozen or {}
    windows = merge_windows(blocked)
    model = cp_model.CpModel()

    all_durations = [d for job in instance["jobs"] for (_, d) in job]
    horizon = sum(all_durations) + earliest_start + max((w["end"] for w in windows), default=0)

    starts = {}
    ends = {}
    intervals_on_machine = {m: [] for m in range(instance["num_machines"])}

    for job_index, operations in enumerate(instance["jobs"]):
        for op_index, (machine, duration) in enumerate(operations):
            key = (job_index, op_index)
            if key in frozen:
                low = high = frozen[key]
            else:
                low, high = earliest_start, horizon
            start = model.new_int_var(low, high, f"start_{job_index}_{op_index}")
            end = model.new_int_var(low + duration, high + duration, f"end_{job_index}_{op_index}")
            interval = model.new_interval_var(start, duration, end, f"interval_{job_index}_{op_index}")
            starts[key], ends[key] = start, end
            intervals_on_machine[machine].append(interval)

    for number, window in enumerate(windows):
        interval = model.new_fixed_size_interval_var(window["start"], window["end"] - window["start"], f"breakdown_{number}")
        intervals_on_machine[window["machine"]].append(interval)

    for machine, intervals in intervals_on_machine.items():
        model.add_no_overlap(intervals)

    for job_index, operations in enumerate(instance["jobs"]):
        for op_index in range(1, len(operations)):
            model.add(starts[(job_index, op_index)] >= ends[(job_index, op_index - 1)])

    makespan = model.new_int_var(0, horizon, "makespan")
    model.add_max_equality(makespan, list(ends.values()))
    model.minimize(makespan)

    if hint:
        for op in hint:
            model.add_hint(starts[(op["job"], op["op"])], op["start"])

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = workers
    solver.parameters.random_seed = seed

    status = solver.solve(model)
    result = {
        "status": STATUS_NAMES.get(status, "UNKNOWN"),
        "solve_time_s": round(solver.wall_time, 2),
        "makespan": None,
        "lower_bound": None,
        "schedule": [],
    }
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result["makespan"] = int(solver.objective_value)
        result["lower_bound"] = int(solver.best_objective_bound)
        for (job_index, op_index), start in starts.items():
            machine, duration = instance["jobs"][job_index][op_index]
            begin = solver.value(start)
            result["schedule"].append({
                "job": job_index, "op": op_index, "machine": machine,
                "start": begin, "end": begin + duration,
            })
    return result
