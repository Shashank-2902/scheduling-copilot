import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INSTANCE_FILE = DATA_DIR / "jobshop1.txt"
BEST_KNOWN_FILE = DATA_DIR / "best_known.json"


def parse_instances(text):
    """Read the OR-Library job-shop format and return {name: instance}.

    Each instance in the file looks like this:
        instance ft06
        +++++++++++++++++++
        a line of description
        6 6                     <- number of jobs, number of machines
        2 1 0 3 1 6 ...         <- one line per job: machine, time, machine, time, ...
    Machines are numbered from 0.
    """
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line and not line.startswith("+++")]

    instances = {}
    position = 0
    while position < len(lines):
        if lines[position].startswith("instance "):
            name = lines[position].split()[1]
            description = lines[position + 1]
            num_jobs, num_machines = (int(x) for x in lines[position + 2].split())
            jobs = []
            for job_line in lines[position + 3: position + 3 + num_jobs]:
                numbers = [int(x) for x in job_line.split()]
                operations = [(numbers[i], numbers[i + 1]) for i in range(0, len(numbers), 2)]
                jobs.append(operations)
            instances[name] = {
                "name": name,
                "description": description,
                "num_jobs": num_jobs,
                "num_machines": num_machines,
                "jobs": jobs,
            }
            position += 3 + num_jobs
        else:
            position += 1
    return instances


_cache = {}


def load_all():
    if not _cache:
        _cache.update(parse_instances(INSTANCE_FILE.read_text(encoding="utf-8")))
    return _cache


def load_best_known():
    return json.loads(BEST_KNOWN_FILE.read_text(encoding="utf-8"))["instances"]


def list_instances():
    """The instances this project uses: the ones that have a best-known value."""
    return list(load_best_known())


def load_instance(name):
    name = name.strip().lower()
    if name not in load_best_known():
        raise ValueError(f"unknown instance '{name}'. Known: {', '.join(list_instances())}")
    return load_all()[name]


def best_known(name):
    return load_best_known()[name.strip().lower()]["makespan"]
