"""The tools the language model may ask for: solve, disrupt and compare.

The model only chooses a tool and its arguments. We check the arguments here,
because they come from a model and cannot be trusted, and then run plain Python.
"""
from scheduler import instance_loader, planner


class ToolInputError(Exception):
    """The arguments for a tool are missing or make no sense. The message is shown to the user."""


def tool_specs():
    """The tool descriptions sent to the model (OpenAI function-calling format)."""
    instance_property = {
        "type": "string",
        "enum": instance_loader.list_instances(),
        "description": "Name of the job-shop instance, for example ft06 or la01.",
    }
    return [
        {
            "type": "function",
            "function": {
                "name": "solve",
                "description": "Find the best schedule for an instance. Returns makespan, gap to the best-known value and solve time.",
                "parameters": {"type": "object", "properties": {"instance": instance_property}, "required": ["instance"]},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "disrupt",
                "description": "A machine breaks down. Freezes operations that already started, blocks the machine for the "
                               "given time and reschedules the rest. Returns the new makespan and how many operations moved.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "instance": instance_property,
                        "machine": {"type": "integer", "description": "Machine number, counted from 0 as in the data."},
                        "start": {"type": "integer", "description": "Time when the breakdown starts, in the time units of the instance."},
                        "duration": {"type": "integer", "description": "How long the machine is down, in the same time units."},
                    },
                    "required": ["instance", "machine", "start", "duration"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "compare",
                "description": "Compare the FIFO rule, the SPT rule and the CP-SAT solver on an instance. Returns a table.",
                "parameters": {"type": "object", "properties": {"instance": instance_property}, "required": ["instance"]},
            },
        },
    ]


def to_whole_number(value, name):
    if isinstance(value, bool):
        raise ToolInputError(f"{name} must be a number")
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            raise ToolInputError(f"{name} must be a number")
    if not isinstance(value, (int, float)) or value != int(value):
        raise ToolInputError(f"{name} must be a whole number")
    return int(value)


def check_arguments(tool, arguments):
    """Return clean arguments or raise ToolInputError."""
    if tool not in ("solve", "disrupt", "compare"):
        raise ToolInputError(f"unknown tool '{tool}'")

    name = str(arguments.get("instance", "")).strip().lower()
    if name not in instance_loader.list_instances():
        raise ToolInputError(f"I need an instance. Choose one of: {', '.join(instance_loader.list_instances())}")
    clean = {"instance": name}

    if tool == "disrupt":
        machines = instance_loader.load_instance(name)["num_machines"]
        machine = to_whole_number(arguments.get("machine"), "machine")
        start = to_whole_number(arguments.get("start"), "start")
        duration = to_whole_number(arguments.get("duration"), "duration")
        if not 0 <= machine < machines:
            raise ToolInputError(f"{name} has machines 0 to {machines - 1}")
        if start < 0:
            raise ToolInputError("start must be 0 or more")
        if duration <= 0:
            raise ToolInputError("duration must be more than 0")
        clean.update({"machine": machine, "start": start, "duration": duration})
    return clean


def run_tool(tool, arguments, base_schedule=None, earlier_windows=None):
    """Run a tool with checked arguments and return the full result."""
    if tool == "solve":
        return planner.solve(arguments["instance"])
    if tool == "compare":
        return planner.compare(arguments["instance"])
    return planner.disrupt(arguments["instance"], arguments["machine"], arguments["start"],
                           arguments["duration"], base_schedule=base_schedule, earlier_windows=earlier_windows)


def summarize(result):
    """The result without the schedule and the stored windows. This is what the model sees and may talk about."""
    return {key: value for key, value in result.items() if key not in ("schedule", "windows")}
