import pytest
from fastapi.testclient import TestClient

from agent.plan_store import PlanStore
from agent.scripted_client import ScriptedClient
from api.main import create_app, make_checkpointer

BREAKDOWN = {"instance": "ft06", "machine": 2, "start": 10, "duration": 15}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def database(clean_tables):
    return clean_tables


def make_client(database_url, llm=None):
    app = create_app(store=PlanStore(database_url), llm=llm, checkpointer=make_checkpointer(database_url))
    return TestClient(app)


def disrupt_llm():
    return ScriptedClient(tool="disrupt", arguments=BREAKDOWN)


def test_health_and_instances(database):
    with make_client(database) as client:
        assert client.get("/health").json() == {"status": "ok"}
        instances = client.get("/instances").json()
        assert len(instances) == 13
        assert {"name": "ft06", "jobs": 6, "machines": 6, "best_known": 55} in instances


def test_direct_tools_work_without_a_model(database):
    with make_client(database) as client:
        solved = client.post("/solve", json={"instance": "ft06"}).json()
        assert solved["makespan"] == 55 and solved["gap_to_best_known_percent"] == 0

        table = client.post("/compare", json={"instance": "la01"}).json()
        assert [row["method"] for row in table["rows"]] == ["FIFO", "SPT", "CP-SAT"]

        moved = client.post("/disrupt", json=BREAKDOWN).json()
        assert moved["feasible"] and moved["operations_frozen"] > 0


def test_direct_disrupt_saves_nothing(database):
    with make_client(database) as client:
        client.post("/disrupt", json=BREAKDOWN)
        assert client.get("/plans").json() == []


def test_bad_input_gives_422(database):
    with make_client(database) as client:
        assert client.post("/solve", json={"instance": "xyz99"}).status_code == 422
        assert client.post("/disrupt", json=dict(BREAKDOWN, machine=99)).status_code == 422


def test_ask_without_a_model_gives_503_and_the_rest_still_works(database):
    with make_client(database) as client:
        assert client.post("/ask", json={"question": "Solve ft06"}).status_code == 503
        assert client.post("/solve", json={"instance": "ft06"}).status_code == 200


def test_unapproved_plan_is_never_written(database):
    with make_client(database, disrupt_llm()) as client:
        reply = client.post("/ask", json={"question": "Machine 2 is down at 10 for 15 on ft06"}).json()
        assert reply["awaiting_approval"] is True
        assert reply["status"] == "awaiting_approval"
        assert client.get("/plans").json() == []


def test_approve_flow_writes_the_plan_and_the_audit_log(database):
    with make_client(database, disrupt_llm()) as client:
        reply = client.post("/ask", json={"question": "Machine 2 is down at 10 for 15 on ft06"}).json()
        thread_id = reply["thread_id"]

        final = client.post(f"/approvals/{thread_id}", json={"decision": "approve", "reviewer": "shashank"}).json()
        assert final["status"] == "committed"
        assert final["awaiting_approval"] is False

        plans = client.get("/plans").json()
        assert len(plans) == 1
        assert plans[0]["makespan"] == reply["numbers"]["new_makespan"]
        assert plans[0]["reviewer"] == "shashank"

        events = [row["event"] for row in reversed(client.get("/audit").json())]
        assert events == ["question", "approval_requested", "approved", "committed"]


def test_reject_flow_writes_no_plan(database):
    with make_client(database, disrupt_llm()) as client:
        thread_id = client.post("/ask", json={"question": "x on ft06"}).json()["thread_id"]
        final = client.post(f"/approvals/{thread_id}", json={"decision": "reject"}).json()
        assert final["status"] == "rejected"
        assert client.get("/plans").json() == []


def test_a_decision_can_only_be_given_once(database):
    with make_client(database, disrupt_llm()) as client:
        thread_id = client.post("/ask", json={"question": "x on ft06"}).json()["thread_id"]
        assert client.post(f"/approvals/{thread_id}", json={"decision": "approve"}).status_code == 200
        assert client.post(f"/approvals/{thread_id}", json={"decision": "approve"}).status_code == 409
        assert len(client.get("/plans").json()) == 1


def test_unknown_thread_gives_404(database):
    with make_client(database, disrupt_llm()) as client:
        assert client.post("/approvals/doesnotexist", json={"decision": "approve"}).status_code == 404
        assert client.get("/threads/doesnotexist").status_code == 404


def test_a_waiting_proposal_survives_an_api_restart(database):
    """The paused conversation is stored in Postgres, so a second app instance can finish it."""
    with make_client(database, disrupt_llm()) as first_app:
        thread_id = first_app.post("/ask", json={"question": "x on ft06"}).json()["thread_id"]

    with make_client(database, disrupt_llm()) as second_app:
        assert second_app.get(f"/threads/{thread_id}").json()["awaiting_approval"] is True
        final = second_app.post(f"/approvals/{thread_id}", json={"decision": "approve"}).json()
        assert final["status"] == "committed"
        assert len(second_app.get("/plans").json()) == 1


def test_a_question_without_a_tool_asks_back(database):
    llm = ScriptedClient(tool=None, reply="Which instance do you mean?")
    with make_client(database, llm) as client:
        reply = client.post("/ask", json={"question": "What is the makespan?"}).json()
        assert reply["status"] == "needs_clarification"
        assert reply["answer"] == "Which instance do you mean?"
        assert reply["awaiting_approval"] is False


def test_gantt_images(database):
    with make_client(database, disrupt_llm()) as client:
        instance_chart = client.get("/instances/ft06/gantt.png?method=fifo")
        assert instance_chart.headers["content-type"] == "image/png"
        assert instance_chart.content.startswith(PNG_SIGNATURE)

        thread_id = client.post("/ask", json={"question": "x on ft06"}).json()["thread_id"]
        proposal = client.get(f"/proposals/{thread_id}/gantt.png")
        assert proposal.content.startswith(PNG_SIGNATURE)

        client.post(f"/approvals/{thread_id}", json={"decision": "approve"})
        plan_id = client.get("/plans").json()[0]["id"]
        assert client.get(f"/plans/{plan_id}/gantt.png").content.startswith(PNG_SIGNATURE)
        assert client.get("/plans/999/gantt.png").status_code == 404
