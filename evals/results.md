# Evaluation results

30 questions. Ground truth is computed by calling the solver directly, never by a language model.

## Summary

| System | Tool correct | Arguments correct | Numbers faithful | All three |
| --- | --- | --- | --- | --- |
| Regex baseline | 77%  (23/30) | 77%  (23/30) | 100%  (30/30) | 77%  (23/30) |

## By category (questions passed)

| Category | Regex baseline |
| --- | --- |
| solve | 5/8 |
| compare | 7/8 |
| disrupt | 7/9 |
| clarify | 4/5 |

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

## Language model

Not run yet. It needs a free Groq key in `.env`. Then run `python -m evals.run --system both --write`.
