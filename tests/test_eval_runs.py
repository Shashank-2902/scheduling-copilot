import json

import pytest

from agent.llm_interface import FallbackClient, LLMUnavailable
from agent.scripted_client import ScriptedClient
from evals import run, stats


# ---------- Fisher exact test ----------

def test_fisher_matches_the_textbook_tea_tasting_example():
    # 3 of 4 against 1 of 4, two-sided p = 34/70
    assert stats.fisher_exact_two_sided(3, 4, 1, 4) == pytest.approx(34 / 70)


def test_fisher_with_no_difference_gives_one():
    assert stats.fisher_exact_two_sided(5, 10, 5, 10) == pytest.approx(1.0)


def test_fisher_is_symmetric_in_the_groups():
    assert stats.fisher_exact_two_sided(28, 30, 23, 30) == pytest.approx(stats.fisher_exact_two_sided(23, 30, 28, 30))


def test_fisher_for_a_clear_difference_is_small():
    assert stats.fisher_exact_two_sided(25, 25, 19, 25) < 0.05


# ---------- retries and stopping ----------

class AlwaysRateLimited:
    name = "groq"

    def choose_tool(self, question, tool_specs):
        raise LLMUnavailable("rate limit")

    def explain(self, question, tool, summary):
        raise LLMUnavailable("rate limit")


def test_a_rate_limit_is_retried_three_times_then_the_run_stops():
    waits = []
    with pytest.raises(run.EvalStopped):
        run.ask_with_retry(AlwaysRateLimited(), "Solve ft06", sleep=waits.append)
    assert waits == [60, 60, 60]


def test_a_question_that_works_after_one_retry_is_answered():
    calls = []

    class FailsOnce(ScriptedClient):
        def choose_tool(self, question, tool_specs):
            calls.append(1)
            if len(calls) == 1:
                raise LLMUnavailable("rate limit")
            return super().choose_tool(question, tool_specs)

    waits = []
    state = run.ask_with_retry(FailsOnce(tool="solve", arguments={"instance": "ft06"}), "Solve ft06", sleep=waits.append)
    assert state["tool"] == "solve" and waits == [60]


def test_the_evaluation_never_switches_to_another_model():
    groq, ollama = ScriptedClient(), ScriptedClient()
    groq.name, ollama.name = "groq", "ollama"
    assert run.groq_only(FallbackClient([groq, ollama])) is groq
    with pytest.raises(SystemExit):
        run.groq_only(FallbackClient([ollama]))


# ---------- saved runs ----------

def test_a_saved_run_has_the_run_number_date_model_temperature_and_the_per_question_data(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "RUNS_DIR", tmp_path / "runs")
    results = {"Regex baseline": [{"id": 1, "passed": True}], "Language model": [{"id": 1, "passed": False}]}
    path = run.save_run(2, results, "some/model")
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "run2.json"
    assert saved["run"] == 2 and saved["model"] == "some/model" and saved["temperature"] == 0
    assert saved["date_utc"].endswith("+00:00") and saved["systems"] == results
    assert run.load_runs() == [saved]


def test_the_runs_section_lists_every_run_with_its_score_and_the_tests():
    questions = [{"id": i, "expected": {"tool": "solve" if i <= 4 else None}} for i in range(1, 7)]

    def rows(passed_ids):
        return [{"id": i, "passed": i in passed_ids} for i in range(1, 7)]

    runs = [{"run": 1, "date_utc": "2026-10-24T10:00:00+00:00", "model": "m", "temperature": 0,
             "systems": {"Regex baseline": rows({1, 2}), "Language model": rows({1, 2, 3, 4, 5})}}]
    text = "\n".join(run.runs_section(runs, questions))
    assert "Model: `m`" in text and "Number of runs: 1" in text
    assert "| 1 | 2026-10-24T10:00:00+00:00 | 2/6 | 5/6 | 2/4 | 4/4 |" in text
    assert "n = 30 questions per run is small" in text
    assert "answerable questions only: 4/4 against 2/4" in text
    assert run.runs_section([], questions) == []
