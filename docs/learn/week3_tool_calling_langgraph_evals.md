# Week 3: tool calling, LangGraph interrupts and how to evaluate an agent

## 1. Concept

### Tool calling

A language model writes text. It cannot run a solver. **Tool calling** lets the model ask for a
function by name:

1. you describe your tools (name, purpose, arguments) to the model;
2. the model answers either with text or with "call tool X with these arguments";
3. your code runs the tool and gives the result back;
4. the model explains the result.

In this project the tools are `solve`, `disrupt` and `compare`. They are plain Python in `scheduler/`.

### Why the model must not do arithmetic or build schedules

Language models sound sure even when they are wrong. A schedule has hard rules (order, no overlaps), and
a number like "new makespan 61" is either correct or not. So:

- the model never creates or edits a schedule;
- the model never calculates: it must not subtract, add, round or estimate;
- every number it says must come from the tool output.

The model has two jobs only: pick the tool with the right arguments, and explain the returned numbers
in plain words. Our code checks everything the model hands over (the arguments) and checks the result
(a validator). Model output is treated as untrusted input.

### Why one question may need no tool

If the question is missing something ("What is the makespan?" with no instance), the right answer is to
ask. A wrong guess here would be a confident wrong answer. The prompt tells the model to ask, and the
evaluation has questions that test exactly this.

### The graph and the interrupt

**LangGraph** runs a flow as a graph of steps (nodes) that share a state. We use it for one purpose:
a human must approve a new plan before it is saved.

```
choose tool -> run tool -> explain -> (is it a new plan?) -> request approval -> approval -> finalize
```

- `interrupt()` in the approval step **pauses** the graph and returns the proposal to the caller.
- The state is stored by a **checkpointer** (Postgres), so the pause can last minutes and survives a restart.
- The human calls the API with approve or reject. The graph **resumes** and the last step either saves the
  plan or only logs the rejection.
- One detail: when a graph resumes, the node that paused starts again from its first line. So the approval
  node contains only the interrupt; the audit entry is written in the step before it.

Nothing else is "agentic": no extra agents, no loops. One graph, one pause.

### How to evaluate an agent

You cannot judge an agent by reading a few good answers. You need a fixed question set with the right
answers decided **before** you run it, and a number.

1. **Questions**: 30, in four groups: solve (8), compare (8), disrupt (9) and incomplete or unclear (5).
   They are written in natural variations, including spelled-out numbers, odd word order and a
   double breakdown.
2. **Ground truth** comes from calling the solver directly with the expected arguments. A language model
   is never used to create the answer key.
3. **Three measurements** per question:
   - **tool correct**: the right tool was chosen (or no tool, if the question is incomplete);
   - **arguments correct**: exactly the expected arguments;
   - **numbers faithful**: every number in the answer appears in the tool output or in the question
     (rounding to the number of decimals shown is allowed).
4. **A baseline** to compare with: a rule-based parser made of keywords and regular expressions.
   An agent is only interesting if it beats something simple, and a fair comparison shows where it does not.
5. **Honest failures**: list the questions that failed and why, including wrong units and ambiguous
   questions.

A note on our own process. The first version of the question set was too tidy: the regex baseline scored
30 out of 30, which meant the test could not tell the systems apart. I rewrote eight questions into more
natural phrasing and did not touch the baseline. It now scores 23 out of 30. A test that everything passes
is a test that proves nothing.

## 2. Code walkthrough

**`agent/tools.py`** lists the three tools for the model and checks every argument: the instance must exist,
the machine must be in range, start and duration must be whole numbers, and extra keys are dropped. The
model cannot smuggle a schedule in.

**`agent/llm_interface.py`** defines the two methods every model client has (`choose_tool` and `explain`)
and `FallbackClient`, which tries Groq first and Ollama second. **`groq_client.py`** and **`ollama_client.py`**
implement them with temperature 0. **`scripted_client.py`** is a fake model for tests. **`regex_client.py`**
is the rule-based parser (baseline and key-less demo mode).

**`agent/pipeline.py`** has the three steps (choose, run, explain). The graph and the evals both use them,
so what is measured is exactly what the API runs.

**`agent/graph.py`** builds the LangGraph graph with the interrupt and the final commit or reject step.

**`api/main.py`** adds `/ask` (starts a graph run), `/approvals/{thread_id}` (resumes it), `/threads/{id}`,
`/plans`, `/audit` and the Gantt PNGs.

**`evals/`**: `questions.json` (the 30 questions), `checks.py` (the faithfulness check), `run.py` (the runner
and the results table).

**Tests** include: an unapproved plan is never written; reject writes nothing; approve writes exactly the
proposed plan; the paused conversation survives an API restart; the model cannot change a schedule; bad
arguments are refused; answer numbers equal tool output; an invented number is caught. I also broke the
approval rule on purpose to confirm that the tests fail when it is broken.

## 3. Interview questions

1. **What is tool calling?**
   The model returns the name of a function and its arguments instead of text. Our code runs the function
   and the model explains the result.

2. **Why should the language model not do arithmetic?**
   It is fluent but not reliable with numbers. Numbers must come from code that can be tested.

3. **What does the model do in this project?**
   It picks a tool with arguments and explains the returned numbers. It never creates or edits a schedule.

4. **How do you treat the model's output?**
   As untrusted input. Arguments are validated, extra fields are dropped, and the result of the solver is
   validated again.

5. **What does a LangGraph interrupt do?**
   It pauses the graph and saves its state. A later call with `Command(resume=...)` continues from the same
   point and the resume value becomes the return value of `interrupt()`.

6. **Why a Postgres checkpointer?**
   The pause may last a long time. With the state in Postgres a restart does not lose the proposal. A test
   starts a second app instance and finishes a proposal made by the first.

7. **Why is the audit entry not inside the approval node?**
   A node restarts from its first line on resume, so anything before the interrupt would run twice.

8. **How do you prove that nothing is saved without approval?**
   Tests: no decision means no row, reject means no row, and the only code path that writes plans is the
   final step after an approve. I also broke the rule on purpose and saw the tests fail.

9. **How did you measure the agent?**
   30 questions with ground truth from the solver, three metrics (tool, arguments, numbers faithful) and a
   regex baseline for comparison.

10. **Where does the approach fail?**
    Incomplete or ambiguous questions, wrong units (hours instead of the instance's time units), spelled-out
    numbers, and questions that need arithmetic such as "from 400 to 500". The evaluation lists them.

## 4. Glossary

- **Tool calling / function calling**: the model asks for a function by name with arguments.
- **Temperature**: how random a model is. 0 means as repeatable as possible.
- **Hallucination**: a confident answer that is not true or not in the data.
- **Graph (LangGraph)**: steps (nodes) connected by edges, sharing a state.
- **Interrupt**: a pause in the graph that waits for outside input.
- **Checkpointer**: storage that keeps the state of a graph between calls.
- **Thread id**: the name of one conversation, needed to resume it.
- **Human in the loop**: a person must decide before something important happens.
- **Ground truth**: the known correct answer, here computed by the solver.
- **Baseline**: a simple method to compare against.
- **Faithful numbers**: every number in an answer can be found in the tool output.
- **Fallback**: a second model that is used when the first fails.
- **Untrusted input**: data that must be checked before it is used.
