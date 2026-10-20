"""Reads and writes the committed_plans and audit_log tables in Postgres."""
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class PlanStore:
    def __init__(self, database_url):
        self.database_url = database_url

    def _connect(self):
        return psycopg.connect(self.database_url, autocommit=True, row_factory=dict_row)

    def add_audit(self, event, thread_id, details):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO audit_log (event, thread_id, details) VALUES (%s, %s, %s)",
                (event, thread_id, Jsonb(details)),
            )

    def commit_plan(self, thread_id, instance, makespan, schedule, question, reviewer):
        """Save an approved plan and return its id. Only the approval step calls this."""
        with self._connect() as conn:
            row = conn.execute(
                "INSERT INTO committed_plans (instance, makespan, schedule, question, reviewer, thread_id) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (instance, makespan, Jsonb(schedule), question, reviewer, thread_id),
            ).fetchone()
        return row["id"]

    def latest_schedule(self, instance):
        """The newest committed plan of an instance, or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT schedule FROM committed_plans WHERE instance = %s ORDER BY id DESC LIMIT 1",
                (instance,),
            ).fetchone()
        return row["schedule"] if row else None

    def list_plans(self, limit=20):
        with self._connect() as conn:
            return conn.execute(
                "SELECT id, instance, makespan, question, reviewer, thread_id, committed_at "
                "FROM committed_plans ORDER BY id DESC LIMIT %s", (limit,)
            ).fetchall()

    def get_plan(self, plan_id):
        with self._connect() as conn:
            return conn.execute("SELECT * FROM committed_plans WHERE id = %s", (plan_id,)).fetchone()

    def list_audit(self, limit=50):
        with self._connect() as conn:
            return conn.execute(
                "SELECT id, created_at, event, thread_id, details FROM audit_log ORDER BY id DESC LIMIT %s", (limit,)
            ).fetchall()
