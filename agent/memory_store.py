"""The same interface as PlanStore, kept in memory. Used by the evals and by fast tests."""
from datetime import datetime, timezone


class MemoryStore:
    def __init__(self):
        self.plans = []
        self.audit = []

    def add_audit(self, event, thread_id, details):
        self.audit.append({
            "id": len(self.audit) + 1, "created_at": datetime.now(timezone.utc),
            "event": event, "thread_id": thread_id, "details": details,
        })

    def commit_plan(self, thread_id, instance, makespan, schedule, question, reviewer):
        plan = {
            "id": len(self.plans) + 1, "instance": instance, "makespan": makespan, "schedule": schedule,
            "question": question, "reviewer": reviewer, "thread_id": thread_id,
            "committed_at": datetime.now(timezone.utc),
        }
        self.plans.append(plan)
        return plan["id"]

    def latest_schedule(self, instance):
        for plan in reversed(self.plans):
            if plan["instance"] == instance:
                return plan["schedule"]
        return None

    def list_plans(self, limit=20):
        return list(reversed(self.plans))[:limit]

    def get_plan(self, plan_id):
        return next((p for p in self.plans if p["id"] == plan_id), None)

    def list_audit(self, limit=50):
        return list(reversed(self.audit))[:limit]
