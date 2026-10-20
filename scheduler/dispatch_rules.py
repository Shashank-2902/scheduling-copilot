"""Simple dispatch rules. They are quick and need no solver, which makes them
a good baseline to compare the optimal solver against.

The schedule is built step by step (Giffler-Thompson): find the operation that
could finish first, then let the rule choose among the operations that compete
for the same machine at that moment.
"""


def fifo_key(candidate):
    """First in, first out: the job that has waited longest (ready earliest) goes first."""
    return (candidate["ready"], candidate["job"])


def spt_key(candidate):
    """Shortest processing time: the shortest operation goes first."""
    return (candidate["duration"], candidate["job"])


RULES = {"FIFO": fifo_key, "SPT": spt_key}


def find_candidates(instance, next_op, job_ready, machine_free):
    """The next operation of every unfinished job, with its earliest start and end."""
    candidates = []
    for job_index, operations in enumerate(instance["jobs"]):
        if next_op[job_index] >= len(operations):
            continue
        machine, duration = operations[next_op[job_index]]
        start = max(job_ready[job_index], machine_free[machine])
        candidates.append({
            "job": job_index,
            "op": next_op[job_index],
            "machine": machine,
            "duration": duration,
            "ready": job_ready[job_index],
            "start": start,
            "end": start + duration,
        })
    return candidates


def dispatch(instance, rule):
    """Build a schedule with the rule "FIFO" or "SPT"."""
    key = RULES[rule]
    next_op = [0] * instance["num_jobs"]
    job_ready = [0] * instance["num_jobs"]
    machine_free = {m: 0 for m in range(instance["num_machines"])}
    schedule = []
    total_operations = sum(len(job) for job in instance["jobs"])

    while len(schedule) < total_operations:
        candidates = find_candidates(instance, next_op, job_ready, machine_free)
        first_to_finish = min(candidates, key=lambda c: (c["end"], c["job"]))
        machine = first_to_finish["machine"]

        competing = [c for c in candidates if c["machine"] == machine and c["start"] < first_to_finish["end"]]
        chosen = min(competing, key=key)

        schedule.append({
            "job": chosen["job"], "op": chosen["op"], "machine": machine,
            "start": chosen["start"], "end": chosen["end"],
        })
        next_op[chosen["job"]] += 1
        job_ready[chosen["job"]] = chosen["end"]
        machine_free[machine] = chosen["end"]

    return schedule
