"""Evaluate the question answering on 30 questions.

    python -m evals.run --system baseline      regex parser, needs no key
    python -m evals.run --system llm           language model, needs GROQ_API_KEY or OLLAMA_URL in .env
    python -m evals.run --system both --write  also writes evals/results.md

Ground truth comes from calling the solver directly, never from a language model.
For every question we measure:
  tool correct     the right tool was chosen (or no tool, when the question is incomplete)
  args correct     the tool arguments are exactly right
  numbers faithful every number in the answer comes from the tool output or from the question
"""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from agent import pipeline, tools
from agent.llm_interface import LLMUnavailable
from evals import checks, stats
from agent.regex_client import RegexClient

HERE = Path(__file__).resolve().parent
QUESTIONS_FILE = HERE / "questions.json"
RESULTS_FILE = HERE / "results.md"
RAW_FILE = HERE / "results_raw.json"
RUNS_DIR = HERE / "runs"
IGNORED_KEYS = {"solve_time_s", "time_s"}


def load_questions():
    return json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))


def load_env_file():
    """Put the values of .env into the environment (without overriding existing ones)."""
    path = HERE.parent / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                if value.strip():
                    os.environ.setdefault(key.strip(), value.strip())


def ground_truth(question):
    """The tool output for the expected tool and arguments, computed by the solver directly."""
    expected = question["expected"]
    if expected["tool"] is None:
        return None
    result = tools.run_tool(expected["tool"], expected["arguments"])
    return tools.summarize(result)


def without_timings(data):
    if isinstance(data, dict):
        return {k: without_timings(v) for k, v in data.items() if k not in IGNORED_KEYS}
    if isinstance(data, list):
        return [without_timings(v) for v in data]
    return data


class EvalStopped(Exception):
    """A question could not be answered after the retries. The run is stopped, nothing is filled in."""


def ask_with_retry(client, text, retries=3, wait_seconds=60, sleep=time.sleep):
    """Ask once and, if the model is unavailable (for example a rate limit), wait and retry up to 3 times."""
    for attempt in range(retries + 1):
        try:
            return pipeline.ask(client, text)
        except LLMUnavailable as error:
            if attempt == retries:
                raise EvalStopped(str(error)[:200])
            sleep(wait_seconds)


def evaluate(client, question):
    expected = question["expected"]
    truth = ground_truth(question)
    row = {"id": question["id"], "category": question["category"], "question": question["question"],
           "expected_tool": expected["tool"], "expected_arguments": expected["arguments"]}

    began = time.time()
    try:
        state = ask_with_retry(client, question["question"])
    except EvalStopped:
        raise
    except Exception as error:  # noqa: BLE001  (any other error counts as a failed question)
        row.update(error=str(error)[:200], tool=None, tool_ok=False, args_ok=False, numbers_ok=False, passed=False)
        return row
    row["seconds"] = round(time.time() - began, 2)

    row["tool"] = state["tool"]
    row["arguments"] = state["arguments"]
    row["answer"] = state["answer"]
    row["tool_ok"] = state["tool"] == expected["tool"]
    row["args_ok"] = row["tool_ok"] and (expected["tool"] is None or checks.same_arguments(expected["arguments"], state["arguments"]))

    wrong_numbers = checks.unmatched_numbers(state["answer"], state["summary"] or {}, question["question"])
    row["numbers_ok"] = not wrong_numbers
    row["wrong_numbers"] = wrong_numbers

    row["matches_ground_truth"] = None
    if row["args_ok"] and truth is not None and state["summary"] is not None:
        row["matches_ground_truth"] = without_timings(state["summary"]) == without_timings(truth)

    row["passed"] = row["tool_ok"] and row["args_ok"] and row["numbers_ok"]
    return row


def run_system(client, questions):
    rows = []
    for question in questions:
        rows.append(evaluate(client, question))
        print(f"  q{question['id']:>2} {'ok  ' if rows[-1]['passed'] else 'FAIL'} {question['question'][:70]}", flush=True)
    return rows


def percent(rows, key):
    return f"{100 * sum(1 for r in rows if r.get(key)) / len(rows):.0f}%  ({sum(1 for r in rows if r.get(key))}/{len(rows)})"


def table_for(results):
    lines = ["| System | Tool correct | Arguments correct | Numbers faithful | All three |", "| --- | --- | --- | --- | --- |"]
    for name, rows in results.items():
        lines.append(f"| {name} | {percent(rows, 'tool_ok')} | {percent(rows, 'args_ok')} | {percent(rows, 'numbers_ok')} | {percent(rows, 'passed')} |")
    return "\n".join(lines)


def truth_lines(results):
    """When tool and arguments were right, did the tool output equal a direct call of the solver?"""
    lines = []
    for name, rows in results.items():
        checked = [r for r in rows if r.get("matches_ground_truth") is not None]
        same = sum(1 for r in checked if r["matches_ground_truth"])
        lines.append(f"- {name}: {same} of {len(checked)}")
    return "\n".join(lines)


def table_by_category(results):
    categories = ["solve", "compare", "disrupt", "clarify"]
    lines = ["| Category | " + " | ".join(results) + " |", "| --- | " + " | ".join("---" for _ in results) + " |"]
    for category in categories:
        cells = []
        for rows in results.values():
            subset = [r for r in rows if r["category"] == category]
            cells.append(f"{sum(1 for r in subset if r['passed'])}/{len(subset)}")
        lines.append(f"| {category} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def failures_for(name, rows):
    lines = []
    for r in rows:
        if r["passed"]:
            continue
        if r.get("error"):
            reason = f"call failed: {r['error']}"
        elif not r["tool_ok"]:
            reason = f"chose tool {r['tool']!r}, expected {r['expected_tool']!r}"
        elif not r["args_ok"]:
            reason = f"arguments {r['arguments']}, expected {r['expected_arguments']}"
        else:
            reason = f"numbers not in tool output: {r['wrong_numbers']}"
        lines.append(f"- {name}, question {r['id']} ({r['category']}): {r['question']}\n  {reason}")
    return "\n".join(lines) if lines else f"- {name}: no failures"


def write_markdown(results):
    parts = ["# Evaluation results", "",
             "30 questions. The 30 questions were written by Claude Code. "
             "Ground truth is computed by calling the solver directly, never by a language model.", "",
             "## Summary", "", table_for(results), "", "## By category (questions passed)", "", table_by_category(results), "",
             "## Tool output equals a direct solver call", "",
             "For the questions where the right tool and arguments were chosen:", "", truth_lines(results), "",
             "## Failures", ""]
    for name, rows in results.items():
        parts += [failures_for(name, rows), ""]
    parts += runs_section(load_runs(), load_questions())
    if "Language model" not in results:
        parts += ["## Language model", "",
                  "Not run yet. It needs a free Groq key in `.env`. Then run `python -m evals.run --system both --write`.", ""]
    RESULTS_FILE.write_text("\n".join(parts), encoding="utf-8")


def groq_only(client):
    """The evaluation must not switch models: use the Groq client alone, never the fallback."""
    for candidate in getattr(client, "clients", [client]):
        if getattr(candidate, "name", "") == "groq":
            return candidate
    raise SystemExit("Cannot run the LLM evaluation: no Groq client is configured.")


def is_answerable(question):
    return question["expected"]["tool"] is not None


def run_record(number, results, model):
    """One saved run: who, when, which model, plus the same per-question data as results_raw.json."""
    return {"run": number, "date_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": model, "temperature": 0, "systems": results}


def save_run(number, results, model):
    RUNS_DIR.mkdir(exist_ok=True)
    path = RUNS_DIR / f"run{number}.json"
    path.write_text(json.dumps(run_record(number, results, model), indent=1), encoding="utf-8")
    return path


def load_runs():
    """The committed runs, in order of their number."""
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(RUNS_DIR.glob("run*.json"))]


def score(rows, answerable_ids=None):
    """(passed, total), optionally only for the answerable questions."""
    chosen = [r for r in rows if answerable_ids is None or r["id"] in answerable_ids]
    return sum(1 for r in chosen if r["passed"]), len(chosen)


def runs_section(runs, questions):
    """Text for evals/results.md: model, dates, the score of each run and the significance of the difference."""
    if not runs:
        return []
    answerable_ids = {q["id"] for q in questions if is_answerable(q)}
    lines = ["## Runs and significance", "",
             f"Model: `{runs[0]['model']}`, temperature {runs[0]['temperature']}. Number of runs: {len(runs)}. "
             "Each run asked all 30 questions once.", "",
             "| Run | Date (UTC) | Regex baseline | Language model | Baseline, answerable only | Language model, answerable only |",
             "| --- | --- | --- | --- | --- | --- |"]
    for run in runs:
        base, llm = run["systems"]["Regex baseline"], run["systems"]["Language model"]
        cells = [score(base), score(llm), score(base, answerable_ids), score(llm, answerable_ids)]
        lines.append(f"| {run['run']} | {run['date_utc']} | " + " | ".join(f"{a}/{b}" for a, b in cells) + " |")
    lines += ["", "n = 30 questions per run is small, so a difference of a few questions can be chance.", "",
              "Two-sided Fisher exact tests, language model against regex baseline (computed with `math.comb`):", ""]
    for run in runs:
        base, llm = run["systems"]["Regex baseline"], run["systems"]["Language model"]
        for label, ids in [("all 30 questions", None), ("answerable questions only", answerable_ids)]:
            (lp, lt), (bp, bt) = score(llm, ids), score(base, ids)
            p = stats.fisher_exact_two_sided(lp, lt, bp, bt)
            lines.append(f"- Run {run['run']}, {label}: {lp}/{lt} against {bp}/{bt}, p = {p:.4f}")
    lines.append("")
    return lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", choices=["baseline", "llm", "both"], default="baseline")
    parser.add_argument("--write", action="store_true", help="write evals/results.md")
    parser.add_argument("--run", type=int, help="save this run as evals/runs/run<N>.json (with date and model)")
    args = parser.parse_args()

    load_env_file()
    questions = load_questions()
    results = {}

    if args.system in ("baseline", "both"):
        print("Baseline (regex parser):")
        results["Regex baseline"] = run_system(RegexClient(), questions)

    if args.system in ("llm", "both"):
        from agent import llm_factory
        try:
            client = groq_only(llm_factory.make_llm_client())
        except LLMUnavailable as error:
            raise SystemExit(f"Cannot run the LLM evaluation: {error}")
        print("Language model:")
        try:
            results["Language model"] = run_system(client, questions)
        except EvalStopped as error:
            raise SystemExit(f"Stopped: a question failed after 3 retries ({error}). Nothing was saved.")

    print()
    print(table_for(results))
    RAW_FILE.write_text(json.dumps(results, indent=1), encoding="utf-8")
    if args.run is not None and "Language model" in results:
        print(f"Saved {save_run(args.run, results, client.model)}")
    if args.write:
        write_markdown(results)
        print(f"\nWrote {RESULTS_FILE}")


if __name__ == "__main__":
    main()
