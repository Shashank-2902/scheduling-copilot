"""A schedule is a list of operations. Each operation is a dict:
    {"job": 0, "op": 2, "machine": 3, "start": 12, "end": 19}
"""


def makespan(schedule):
    return max(op["end"] for op in schedule) if schedule else 0


def gap_percent(value, best):
    """How far above the best-known makespan a value is, in percent."""
    return round(100.0 * (value - best) / best, 2)


def validate(instance, schedule, blocked=None):
    """Return a list of problems. An empty list means the schedule is valid.

    blocked is an optional dict {"machine": m, "start": s, "end": e}: no operation
    may run on that machine inside that window.
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

    if blocked:
        for op in schedule:
            if op["machine"] == blocked["machine"] and op["start"] < blocked["end"] and op["end"] > blocked["start"]:
                problems.append(f"job {op['job']} op {op['op']} runs while machine {blocked['machine']} is down")

    return problems
