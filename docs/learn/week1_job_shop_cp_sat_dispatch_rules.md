# Week 1: the job-shop problem, CP-SAT and dispatch rules

## 1. Concept

### What is a job-shop problem?

A factory has several **machines** and several **jobs**. Each job is a fixed list of
steps (called operations), and each step needs one specific machine for a fixed time.
Rules:

- the steps of a job must run in order, one after the other;
- a machine can only do one operation at a time;
- once started, an operation runs to its end.

You decide **when each operation starts**. That is the schedule.

Example from the instance `ft06`: job 0 needs machine 2 for 1 time unit, then machine 0
for 3, then machine 1 for 6, and so on through six machines. There are six such jobs
competing for six machines.

### Makespan

The **makespan** is the time when the last operation finishes. A smaller makespan means
the factory is done sooner. It is the most common goal in job-shop research, and it is
what this project minimises. If the first operation starts at time 0, the makespan is
the end time of the last one.

### Why is it hard?

A 10 by 10 problem has an astronomically large number of possible schedules. You cannot try
them all. The instance `ft10` (10 jobs, 10 machines) looked unsolvable for 25 years after it was
published in 1963. Modern solvers prove the optimum in seconds.

### How CP-SAT models it

**CP-SAT** is a solver from Google's OR-Tools. You describe the problem with variables and
constraints, and the solver searches for the best answer. For the job shop we use:

- an **interval variable** for every operation. It has a start, a fixed length and an end;
- a **precedence constraint** between neighbouring steps of a job: the next start must be at or
  after the previous end;
- a **no-overlap constraint** for every machine: the intervals on one machine may not overlap;
- one **objective**: minimise the makespan, which is the maximum of all end times.

The solver also keeps a **lower bound**, a number the makespan can never go below. When the best
schedule found equals the lower bound, the schedule is **proven optimal**.

### Why dispatch rules are a baseline

A **dispatch rule** builds a schedule step by step with a simple rule for "who goes first":

- **FIFO**: the operation that has waited longest goes first.
- **SPT** (shortest processing time): the shortest operation goes first.

They are fast, need no solver and are easy to explain, which is why many real shops use them.
But they are greedy: they never look ahead. We use them as a **baseline**. If the solver cannot
clearly beat a simple rule, the solver is not worth the trouble. On `ft10`, FIFO ends at 1184
(27 percent above the best-known 930) and SPT at 1429 (54 percent above).

### Best-known value and gap

For benchmark instances the optimum is published. The **gap** says how far a result is above it:

> gap = (makespan - best known) / best known x 100

A gap of 0 means optimal. A result is only meaningful with its gap, because 1184 alone says nothing.

## 2. Code walkthrough

All in `scheduler/`, plain Python.

- `instance_loader.py` reads the OR-Library file into dictionaries and the best-known values from
  `data/best_known.json`.
- `schedule.py` has `makespan`, `gap_percent` and `validate`. `validate` is a safety net: it checks
  that every operation exists once, steps run in order, no machine does two things at once and
  nothing runs while a machine is down. Tests use it on every result.
- `cp_sat_solver.py` builds the CP-SAT model described above. It can also fix some start times
  (frozen operations) and block a machine for a window. We use that in week 2.
- `dispatch_rules.py` builds FIFO and SPT schedules (Giffler-Thompson: find the operation that
  could finish first, then let the rule pick among the operations that compete for that machine).
- `gantt.py` draws the schedule as a chart: one row per machine, one colour per job.
- `planner.py` has the functions `solve`, `compare` and `disrupt`, which the rest of the project calls.

**Checked results:** all 13 instances were solved to proven optimality and match the published values
(for example ft06 = 55 and ft10 = 930). See `data/README.md`.

## 3. Interview questions

1. **What is a job-shop problem?**
   Jobs with ordered steps, each step on a specific machine for a fixed time. Decide the start
   times so that steps keep their order and no machine does two things at once.

2. **What is the makespan?**
   The time at which the last operation finishes. The goal is to make it as small as possible.

3. **How do you model it in CP-SAT?**
   One interval variable per operation, precedence constraints within a job, a no-overlap constraint
   per machine, and an objective that minimises the largest end time.

4. **What does "proven optimal" mean?**
   The best schedule found has the same makespan as the solver's lower bound, so nothing better exists.

5. **Why use dispatch rules if a solver exists?**
   They are instant and simple. They also give a baseline that shows how much value the solver adds.

6. **What is the weakness of FIFO and SPT?**
   They are greedy and never look ahead, so they can make early choices that cost a lot later.

7. **What is the gap to best-known?**
   How far a result is above the best-known makespan, in percent. Zero means optimal.

8. **Why did you verify the best-known values yourself?**
   I copied them from one source and then re-proved every one with the solver. A wrong reference value
   would make every gap in the project wrong.

9. **Why is ft10 famous?**
   It was published in 1963 and its optimum (930) was only proven about 25 years later. Today a solver
   proves it in seconds.

10. **Does a faster solver mean a better schedule?**
    Not by itself. For large problems you set a time limit and accept the best schedule found, and then
    the gap tells you how good it is.

## 4. Glossary

- **Job**: an ordered list of operations.
- **Operation**: one step of a job on one machine for a fixed time.
- **Machine**: a resource that does one operation at a time.
- **Schedule**: a start time for every operation.
- **Makespan**: the finish time of the last operation.
- **Precedence**: the rule that a job's steps run in order.
- **No-overlap**: the rule that one machine does one thing at a time.
- **Interval variable**: a solver variable with a start, a length and an end.
- **Lower bound**: a value the objective can never go below.
- **Optimal**: no better schedule exists.
- **Dispatch rule**: a simple rule that decides which operation goes next.
- **FIFO / SPT**: first in, first out / shortest processing time.
- **Gap**: the percentage above the best-known value.
- **Benchmark instance**: a published problem that everyone uses to compare methods.
