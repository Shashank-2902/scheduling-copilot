from typing import Literal

from pydantic import BaseModel, Field


class SolveRequest(BaseModel):
    instance: str = Field(examples=["ft06"])


class DisruptRequest(BaseModel):
    instance: str = Field(examples=["ft06"])
    machine: int = Field(description="Machine number, counted from 0.", examples=[2])
    start: int = Field(description="Time when the breakdown starts.", examples=[10])
    duration: int = Field(description="How long the machine is down.", examples=[15])


class CompareRequest(BaseModel):
    instance: str = Field(examples=["ft10"])


class AskRequest(BaseModel):
    question: str = Field(examples=["Machine 2 breaks down at time 10 for 15 units on ft06. What happens?"])


class DecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reviewer: str = Field(default="api-user", description="Who approved or rejected the plan.")
