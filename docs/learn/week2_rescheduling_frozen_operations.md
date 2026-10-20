# Week 2: rescheduling, frozen operations and the gap to best-known

## 1. Concept

### Scheduling from scratch versus rescheduling

When you build a plan before work starts, every operation is still open. You are free to place
each one anywhere. That is **scheduling from scratch**.

Real life interrupts the plan. A machine breaks down at time 100. Now part of the plan is already
history: some operations are finished and some are running. You cannot move those. You can only
change what has not started yet. That is **rescheduling**, and it is a different problem:

- the past is fixed;
- the broken machine has a time window in which it cannot work;
- the goal is still a small makespan, but also a plan people can follow, so changing less is better.

### Why frozen operations matter

An operation that has already started is **frozen**: it keeps its start time. If the solver were
allowed to move it, the new plan would say "this started at time 40" when it really started at 25.
That plan could never be executed. It would look good and be useless.

So the rule of this project is exact and tested:

> An operation with start time before the breakdown time is frozen and must have the same start
> time in the new plan.

The remaining operations may only start at or after the breakdown time, because nothing can be
placed in the past.

### One more rule: an operation that is still running on the broken machine

Suppose the machine breaks down at time 10, but it is in the middle of an operation that ends at
time 13. We let that operation finish. The breakdown window then starts at 13 and lasts for the given
duration. The API reports the real window, so nobody is surprised. (Another choice is to interrupt the
operation, but that needs rules about restarting work, which this project does not model.)

### What the disruption tool returns

- the old makespan and the new makespan;
- how many operations were frozen;
- how many operations **moved** (not frozen, and with a different start than before);
- the real breakdown window;
- a full valid schedule.

### Gap to best-known, again, for a changed problem

After a breakdown there is no published optimum, because the problem is new. So the **gap to best-known**
applies to the original plan only. For the new plan we report the change against the old plan: how much
later the work finishes, and how many operations had to move.

### Approval before a plan is committed

A new plan is only a **proposal** until a person agrees. The system keeps two tables in Postgres:

- `committed_plans`: plans a human approved, with who approved them;
- `audit_log`: every step (question, approval requested, approved or rejected, committed).

The only code that writes to `committed_plans` is the final step of the approval flow (week 3).

## 2. Code walkthrough

**`scheduler/disruption.py`**

- `find_frozen` selects the operations of the old plan that started before the breakdown time.
- `breakdown_window` returns the real window, which starts later if a frozen operation is still running
  on the broken machine.
- `disrupt` calls the solver with the frozen start times fixed, the machine window blocked and
  "not before breakdown time" for everything else. The old plan is given to the solver as a hint, so it
  starts from a good guess.
- `count_moved` compares old and new start times of the non-frozen operations.

**`scheduler/planner.py`** wraps this with input checks and runs `validate` on the result. If the new plan is
ever invalid, it raises an error instead of returning it.

**The old plan.** `get_base_plan` solves the instance once and remembers the result. In the API, the newest
committed plan of an instance is used as the starting point, so a second breakdown builds on the first.

**`db/init.sql`** creates the two tables. **`agent/plan_store.py`** reads and writes them.

**`api/main.py`** (FastAPI) has `/solve`, `/disrupt` and `/compare` for direct use, and Gantt charts as PNG.
These direct endpoints never save anything.

**Tests** (`tests/test_disruption.py`) cover five instance and breakdown combinations:

- frozen operations keep their start times;
- the new plan is valid (order, no overlaps, nothing in the breakdown window);
- nothing that had not started begins before the breakdown time;
- a running operation on the broken machine may finish;
- a breakdown after all work is done changes nothing; a breakdown at time 0 freezes nothing.

I also tested the tests: when I temporarily switched the freeze rule off, seven of them failed.

## 3. Interview questions

1. **How is rescheduling different from scheduling from scratch?**
   Part of the plan is already history. You must keep what started and only plan the rest, around the
   broken machine.

2. **Why must started operations be frozen?**
   They have happened. A plan that moves them cannot be executed.

3. **How do you know your freeze rule works?**
   A test compares the start times of all started operations before and after rescheduling, on several
   instances and breakdown times. It fails if even one moved.

4. **What if the machine breaks while it is running an operation?**
   The operation finishes and the breakdown window starts after it. The real window is returned.

5. **What does "operations moved" mean?**
   The number of not-frozen operations that now start at a different time than in the old plan.

6. **Why give the old plan to the solver as a hint?**
   It starts the search from a plan that is already close to good, so a solution appears quickly.

7. **Why is there no gap to best-known after a breakdown?**
   The disrupted problem is new, so there is no published optimum. We compare with the old plan.

8. **Why does the new makespan not always get worse by the length of the breakdown?**
   Other machines may have idle time that absorbs part of the delay, and the solver can reorder the
   unstarted operations.

9. **Why not just let the language model move the operations?**
   A language model cannot guarantee feasibility. A solver plus a validator can.

10. **What guarantees that a plan is only saved after a human agrees?**
    The only code that writes plans is the last step of the approval flow. A test checks that no
    decision means no row, and that reject means no row.

## 4. Glossary

- **Rescheduling**: changing a running plan after a disruption.
- **Disruption**: an event that breaks the plan, here a machine breakdown.
- **Frozen operation**: an operation that already started and must not move.
- **Breakdown window**: the time interval in which a machine cannot work.
- **Hint**: a starting guess given to the solver.
- **Operations moved**: how many unfrozen operations changed their start time.
- **Proposal**: a new plan that nobody has approved yet.
- **Committed plan**: a plan that a human approved and the system stored.
- **Audit log**: a record of what happened and who decided.
- **Validate**: check that a schedule obeys all rules.
