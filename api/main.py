"""The HTTP API. Open http://localhost:8000/docs for the Swagger page.

Direct tool endpoints (/solve, /disrupt, /compare) never save anything.
Plans are only saved through /ask followed by an approval on /approvals/{thread_id}.
"""
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response
from langgraph.types import Command

from agent import llm_factory, tools
from agent.graph import build_graph
from agent.llm_interface import LLMUnavailable, UnavailableClient
from agent.plan_store import PlanStore
from agent.tools import ToolInputError
from api import schemas
from scheduler import dispatch_rules, instance_loader, planner
from scheduler.gantt import draw_gantt


def make_checkpointer(database_url):
    """LangGraph keeps the paused conversations in Postgres, so they survive a restart."""
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    pool = ConnectionPool(database_url, kwargs={"autocommit": True, "row_factory": dict_row}, open=True)
    saver = PostgresSaver(pool)
    saver.setup()
    return saver


def create_app(store=None, llm=None, checkpointer=None):
    """Build the app. Tests pass their own store, llm and checkpointer."""

    @asynccontextmanager
    async def lifespan(app):
        database_url = os.getenv("DATABASE_URL", "")
        app.state.store = store or PlanStore(database_url)
        app.state.checkpointer = checkpointer or make_checkpointer(database_url)
        app.state.llm = llm
        app.state.graph = None
        yield

    app = FastAPI(title="Scheduling copilot", version="1.0.0", lifespan=lifespan,
                  description="Job-shop what-if questions answered by a real solver (OR-Tools CP-SAT). "
                              "The language model only chooses tools and explains numbers.")

    def get_graph():
        if app.state.graph is None:
            try:
                model = app.state.llm or llm_factory.make_llm_client()
            except LLMUnavailable as error:
                model = UnavailableClient(error)  # /ask answers 503, everything else keeps working
            app.state.llm = model
            app.state.graph = build_graph(model, app.state.store, app.state.checkpointer)
        return app.state.graph

    def clean(tool, **arguments):
        try:
            return tools.check_arguments(tool, arguments)
        except ToolInputError as error:
            raise HTTPException(422, str(error))

    def png(data):
        return Response(content=data, media_type="image/png")

    def graph_state(thread_id):
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = get_graph().get_state(config)
        if not snapshot.values:
            raise HTTPException(404, "unknown thread_id")
        return config, snapshot

    def thread_answer(thread_id, values, waiting):
        result = values.get("result") or {}
        gantt_url = None
        if values.get("tool") == "disrupt" and result.get("feasible"):
            gantt_url = f"/proposals/{thread_id}/gantt.png"
        elif values.get("tool") == "solve":
            gantt_url = f"/instances/{result.get('instance')}/gantt.png"
        return {
            "thread_id": thread_id,
            "status": values.get("status"),
            "awaiting_approval": waiting,
            "tool": values.get("tool"),
            "arguments": values.get("arguments"),
            "answer": values.get("answer"),
            "numbers": values.get("summary"),
            "plan_id": values.get("plan_id"),
            "gantt_url": gantt_url,
        }

    # ----- read-only helpers -----

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/instances")
    def instances():
        known = instance_loader.load_best_known()
        return [{"name": name, "jobs": info["jobs"], "machines": info["machines"], "best_known": info["makespan"]}
                for name, info in known.items()]

    # ----- the three tools, called directly (nothing is saved) -----

    @app.post("/solve")
    def solve(request: schemas.SolveRequest):
        args = clean("solve", instance=request.instance)
        return planner.solve(args["instance"])

    @app.post("/disrupt")
    def disrupt(request: schemas.DisruptRequest):
        args = clean("disrupt", **request.model_dump())
        return planner.disrupt(args["instance"], args["machine"], args["start"], args["duration"],
                               base_schedule=app.state.store.latest_schedule(args["instance"]))

    @app.post("/compare")
    def compare(request: schemas.CompareRequest):
        args = clean("compare", instance=request.instance)
        return planner.compare(args["instance"])

    # ----- Gantt charts -----

    @app.get("/instances/{name}/gantt.png", response_class=Response)
    def instance_gantt(name: str, method: str = "cpsat"):
        args = clean("solve", instance=name)
        instance = instance_loader.load_instance(args["instance"])
        if method == "cpsat":
            schedule = planner.solve(args["instance"])["schedule"]
        elif method.upper() in dispatch_rules.RULES:
            schedule = dispatch_rules.dispatch(instance, method.upper())
        else:
            raise HTTPException(422, "method must be cpsat, fifo or spt")
        return png(draw_gantt(schedule, instance["num_machines"], f"{instance['name']} ({method})"))

    @app.get("/proposals/{thread_id}/gantt.png", response_class=Response)
    def proposal_gantt(thread_id: str):
        _, snapshot = graph_state(thread_id)
        result = snapshot.values.get("result") or {}
        if not result.get("schedule"):
            raise HTTPException(404, "this thread has no proposed plan")
        instance = instance_loader.load_instance(result["instance"])
        title = f"{result['instance']} after breakdown (makespan {result['new_makespan']})"
        return png(draw_gantt(result["schedule"], instance["num_machines"], title, result["window"]))

    @app.get("/plans/{plan_id}/gantt.png", response_class=Response)
    def plan_gantt(plan_id: int):
        plan = app.state.store.get_plan(plan_id)
        if plan is None:
            raise HTTPException(404, "unknown plan")
        instance = instance_loader.load_instance(plan["instance"])
        return png(draw_gantt(plan["schedule"], instance["num_machines"],
                              f"committed plan {plan_id}: {plan['instance']} (makespan {plan['makespan']})"))

    # ----- the copilot: ask, approve -----

    @app.post("/ask")
    def ask(request: schemas.AskRequest):
        graph = get_graph()
        thread_id = uuid.uuid4().hex
        config = {"configurable": {"thread_id": thread_id}}
        try:
            graph.invoke({"thread_id": thread_id, "question": request.question}, config)
        except LLMUnavailable as error:
            raise HTTPException(503, str(error))
        snapshot = graph.get_state(config)
        return thread_answer(thread_id, snapshot.values, waiting=bool(snapshot.next))

    @app.get("/threads/{thread_id}")
    def thread(thread_id: str):
        _, snapshot = graph_state(thread_id)
        return thread_answer(thread_id, snapshot.values, waiting=bool(snapshot.next))

    @app.post("/approvals/{thread_id}")
    def approve_or_reject(thread_id: str, request: schemas.DecisionRequest):
        config, snapshot = graph_state(thread_id)
        if not snapshot.next:
            raise HTTPException(409, "nothing is waiting for approval on this thread")
        graph = get_graph()
        graph.invoke(Command(resume={"decision": request.decision, "reviewer": request.reviewer}), config)
        snapshot = graph.get_state(config)
        return thread_answer(thread_id, snapshot.values, waiting=bool(snapshot.next))

    # ----- stored data -----

    @app.get("/plans")
    def plans(limit: int = 20):
        return app.state.store.list_plans(limit)

    @app.get("/audit")
    def audit(limit: int = 50):
        return app.state.store.list_audit(limit)

    return app


app = create_app()
