"""What happens to a running plan when a machine breaks down?

Rules:
  1. Operations that have already started (start < disruption time) are frozen.
     They keep their start time, because they cannot be undone.
  2. The broken machine cannot work for the given duration.
  3. Everything else is rescheduled by the solver, and cannot start before the disruption time.

If a frozen operation is still running on the broken machine at the disruption time,
we let it finish. The breakdown then starts when that operation ends.
"""
from scheduler import cp_sat_solver
from scheduler.schedule import makespan


def find_frozen(base_schedule, disruption_time):
    return [op for op in base_schedule if op["start"] < disruption_time]


def breakdown_window(frozen, machine, disruption_time, duration):
    """The window in which the machine is really down."""
    start = disruption_time
    for op in frozen:
        if op["machine"] == machine and op["end"] > start:
            start = op["end"]
    return {"machine": machine, "start": start, "end": start + duration}


def count_moved(base_schedule, new_schedule, frozen):
    """How many not-frozen operations got a different start time."""
    old_start = {(op["job"], op["op"]): op["start"] for op in base_schedule}
    frozen_keys = {(op["job"], op["op"]) for op in frozen}
    moved = 0
    for op in new_schedule:
        key = (op["job"], op["op"])
        if key not in frozen_keys and op["start"] != old_start[key]:
            moved += 1
    return moved


def disrupt(instance, base_schedule, machine, start, duration, time_limit=20.0, workers=1):
    """Reschedule after the machine is down from `start` for `duration` time units.

    One worker and a fixed seed, so the same question always gives the same plan. With several
    workers, different schedules with the same makespan can come out, and the number of moved
    operations would change from run to run.
    """
    frozen = find_frozen(base_schedule, start)
    window = breakdown_window(frozen, machine, start, duration)
    frozen_starts = {(op["job"], op["op"]): op["start"] for op in frozen}

    result = cp_sat_solver.solve_instance(
        instance,
        time_limit=time_limit,
        workers=workers,
        frozen=frozen_starts,
        blocked=window,
        earliest_start=start,
        hint=base_schedule,
    )

    old_makespan = makespan(base_schedule)
    if result["makespan"] is None:
        return {"feasible": False, "old_makespan": old_makespan, "window": window, "status": result["status"]}

    return {
        "feasible": True,
        "status": result["status"],
        "old_makespan": old_makespan,
        "new_makespan": result["makespan"],
        "delay": result["makespan"] - old_makespan,
        "operations_frozen": len(frozen),
        "operations_moved": count_moved(base_schedule, result["schedule"], frozen),
        "window": window,
        "solve_time_s": result["solve_time_s"],
        "schedule": result["schedule"],
    }
