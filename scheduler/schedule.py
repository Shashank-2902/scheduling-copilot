"""A schedule is a list of operations. Each operation is a dict:
    {"job": 0, "op": 2, "machine": 3, "start": 12, "end": 19}
"""


def makespan(schedule):
    return max(op["end"] for op in schedule) if schedule else 0


def as_window_list(blocked):
    """None, one window or a list of windows, always returned as a list."""
    if not blocked:
        return []
    if isinstance(blocked, dict):
        return [blocked]
    return list(blocked)


def merge_windows(blocked):
    """Join windows of the same machine that overlap or touch.

    Two fixed intervals that overlap on one machine would make the solver model infeasible,
    so the solver only gets the merged windows.
    """
    merged = []
    for window in sorted(as_window_list(blocked), key=lambda w: (w["machine"], w["start"], w["end"])):
        last = merged[-1] if merged else None
        if last and last["machine"] == window["machine"] and window["start"] <= last["end"]:
            last["end"] = max(last["end"], window["end"])
        else:
            merged.append({"machine": window["machine"], "start": window["start"], "end": window["end"]})
    return merged


def gap_percent(value, best):
    """How far above the best-known makespan a value is, in percent."""
    return round(100.0 * (value - best) / best, 2)


def validate(instance, schedule, blocked=None):
    """Return a list of problems. An empty list means the schedule is valid.

    blocked is optional: one dict {"machine": m, "start": s, "end": e} or a list of them.
    No operation may run on that machine inside such a window.
    """
    problems = []
    by_key = {(op["job"], op["op"]): op for op in schedule}

    for job_index, operations in enumerate(instance["jobs"]):
        for op_index, (machine, duration) in enumerate(operations):
            op = by_key.get((job_index, op_index))
            if op is None:
                problems.append(f"job {job_index} op {op_index} is missing")
                continue
            if op["machine"] != machine or op["end"] - op["start"] != duration:
                problems.append(f"job {job_index} op {op_index} has wrong machine or duration")
            if op["start"] < 0:
                problems.append(f"job {job_index} op {op_index} starts before time 0")
            if op_index > 0 and op["start"] < by_key[(job_index, op_index - 1)]["end"]:
                problems.append(f"job {job_index} op {op_index} starts before the previous step ends")

    if len(schedule) != len(by_key):
        problems.append("some operations appear twice")

    for machine in range(instance["num_machines"]):
        on_machine = sorted((op for op in schedule if op["machine"] == machine), key=lambda op: op["start"])
        for first, second in zip(on_machine, on_machine[1:]):
            if second["start"] < first["end"]:
                problems.append(f"machine {machine}: two operations overlap at time {second['start']}")

    for window in as_window_list(blocked):
        for op in schedule:
            if op["machine"] == window["machine"] and op["start"] < window["end"] and op["end"] > window["start"]:
                problems.append(f"job {op['job']} op {op['op']} runs while machine {window['machine']} is down")

    return problems
