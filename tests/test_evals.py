import json

from agent import pipeline
from agent.scripted_client import ScriptedClient
from evals import checks
from agent.regex_client import RegexClient, parse
from evals.run import QUESTIONS_FILE, load_questions

SUMMARY = {"instance": "ft06", "makespan": 60, "best_known": 55, "gap_to_best_known_percent": 9.09, "solve_time_s": 0.08}


# ---------- every number in the answer must come from the tool output ----------

def test_answer_with_only_tool_numbers_passes():
    answer = "The makespan on ft06 is 60, best known is 55, a gap of 9.09 percent. It took 0.08 seconds."
    assert checks.unmatched_numbers(answer, SUMMARY, "Solve ft06") == []


def test_an_invented_number_is_caught():
    answer = "The makespan is 61 and the gap is 9.09 percent."
    assert checks.unmatched_numbers(answer, SUMMARY, "Solve ft06") == ["61"]


def test_rounding_is_allowed_but_a_different_number_is_not():
    assert checks.unmatched_numbers("The gap is about 9 percent.", SUMMARY, "q") == []
    assert checks.unmatched_numbers("The gap is 9.1 percent.", SUMMARY, "q") == []
    assert checks.unmatched_numbers("The gap is 10 percent.", SUMMARY, "q") == ["10"]


def test_numbers_from_the_question_are_allowed():
    assert checks.unmatched_numbers("Machine 2 is down for 15 units.", {}, "Machine 2 down for 15 units") == []


def test_instance_names_are_not_counted_as_numbers():
    assert checks.numbers_in_text("Compare la01 with ft10") == []


def test_answer_numbers_equal_tool_output_in_the_pipeline():
    llm = ScriptedClient(tool="compare", arguments={"instance": "la01"})
    state = pipeline.ask(llm, "Compare la01")
    assert checks.unmatched_numbers(state["answer"], state["summary"], "Compare la01") == []


def test_a_model_that_invents_numbers_is_detected_in_the_pipeline():
    llm = ScriptedClient(tool="solve", arguments={"instance": "la01"}, explain_text="la01 can be done in 700 time units.")
    state = pipeline.ask(llm, "Solve la01")
    assert checks.unmatched_numbers(state["answer"], state["summary"], "Solve la01") == ["700"]


# ---------- the question set ----------

def test_there_are_30_questions_with_ground_truth_arguments():
    questions = load_questions()
    assert len(questions) == 30
    assert len({q["id"] for q in questions}) == 30
    categories = {q["category"] for q in questions}
    assert categories == {"solve", "compare", "disrupt", "clarify"}
    for q in questions:
        if q["expected"]["tool"] == "disrupt":
            assert set(q["expected"]["arguments"]) == {"instance", "machine", "start", "duration"}


def test_the_file_is_valid_json():
    json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))


# ---------- the baseline parser ----------

def test_baseline_parses_a_breakdown():
    parsed = parse("Machine 2 breaks down at time 10 for 15 time units on ft06.")
    assert parsed["tool"] == "disrupt"
    assert parsed["arguments"] == {"instance": "ft06", "machine": 2, "start": 10, "duration": 15}


def test_baseline_reads_a_time_range():
    assert parse("Machine 1 on la03 is broken between time 50 and time 90.")["arguments"]["duration"] == 40


def test_baseline_asks_when_something_is_missing():
    assert parse("What is the makespan?")["tool"] is None
    assert parse("Machine 2 broke down on ft06.")["tool"] is None
    assert parse("Machine 2 breaks down on ft06 at time 10 for 2 hours.")["tool"] is None


def test_baseline_has_known_weak_spots():
    # Spelled-out numbers and unusual wording are exactly what a keyword parser cannot read.
    assert parse("On la05, machine four is out of service starting at 150 for 60 units.")["tool"] is None
    assert parse("I want the plan for ft 20 with the lowest possible finish time.")["tool"] is None


def test_baseline_runs_through_the_same_pipeline():
    state = pipeline.ask(RegexClient(), "Compare FIFO, SPT and the solver on ft06.")
    assert state["tool"] == "compare"
    assert checks.unmatched_numbers(state["answer"], state["summary"], "") == []
