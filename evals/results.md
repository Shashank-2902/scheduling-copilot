# Evaluation results

30 questions. The 30 questions were written by Claude Code. Ground truth is computed by calling the solver directly, never by a language model.

## Summary

| System | Tool correct | Arguments correct | Numbers faithful | All three |
| --- | --- | --- | --- | --- |
| Regex baseline | 77%  (23/30) | 77%  (23/30) | 100%  (30/30) | 77%  (23/30) |
| Language model | 93%  (28/30) | 93%  (28/30) | 100%  (30/30) | 93%  (28/30) |

## By category (questions passed)

| Category | Regex baseline | Language model |
| --- | --- | --- |
| solve | 5/8 | 8/8 |
| compare | 7/8 | 8/8 |
| disrupt | 7/9 | 9/9 |
| clarify | 4/5 | 3/5 |

## Tool output equals a direct solver call

For the questions where the right tool and arguments were chosen:

- Regex baseline: 19 of 19
- Language model: 25 of 25

## Failures

- Regex baseline, question 3 (solve): Can you work out how fast we could finish all the jobs on the 10 by 10 Fisher-Thompson instance ft10?
  chose tool None, expected 'solve'
- Regex baseline, question 5 (solve): I want the plan for ft 20 with the lowest possible finish time.
  chose tool None, expected 'solve'
- Regex baseline, question 8 (solve): Any chance you can do better than 700 on la05?
  chose tool None, expected 'solve'
- Regex baseline, question 13 (compare): On la04, would first-in-first-out or shortest-processing-time give the shorter schedule?
  chose tool 'solve', expected 'compare'
- Regex baseline, question 21 (disrupt): On la05, machine four is out of service starting at 150 for 60 units. What is the new makespan?
  chose tool None, expected 'disrupt'
- Regex baseline, question 25 (disrupt): la01: at time 120 we lose machine 3 for 45 units. What does that do to the plan?
  chose tool None, expected 'disrupt'
- Regex baseline, question 28 (clarify): Machine 2 is down at time 10 and again at time 40 for 5 units on ft06.
  chose tool 'disrupt', expected None

- Language model, question 28 (clarify): Machine 2 is down at time 10 and again at time 40 for 5 units on ft06.
  chose tool 'disrupt', expected None
- Language model, question 30 (clarify): Machine 2 breaks down on ft06 at time 10 for 2 hours. What happens?
  chose tool 'disrupt', expected None

## Runs and significance

Model: `openai/gpt-oss-20b`, temperature 0. Number of runs: 3. Each run asked all 30 questions once.

| Run | Date (UTC) | Regex baseline | Language model | Baseline, answerable only | Language model, answerable only |
| --- | --- | --- | --- | --- | --- |
| 1 | 2026-10-24T10:26:39+00:00 | 23/30 | 28/30 | 19/25 | 25/25 |
| 2 | 2026-10-24T10:31:01+00:00 | 23/30 | 28/30 | 19/25 | 25/25 |
| 3 | 2026-10-24T10:34:34+00:00 | 23/30 | 28/30 | 19/25 | 25/25 |

n = 30 questions per run is small, so a difference of a few questions can be chance.

Two-sided Fisher exact tests, language model against regex baseline (computed with `math.comb`):

- Run 1, all 30 questions: 28/30 against 23/30, p = 0.1455
- Run 1, answerable questions only: 25/25 against 19/25, p = 0.0223
- Run 2, all 30 questions: 28/30 against 23/30, p = 0.1455
- Run 2, answerable questions only: 25/25 against 19/25, p = 0.0223
- Run 3, all 30 questions: 28/30 against 23/30, p = 0.1455
- Run 3, answerable questions only: 25/25 against 19/25, p = 0.0223
