"""Project-plan governance engine: ingest -> normalize -> metrics -> AI.

This package implements the client's workflow:
    Upload Project Plan -> Data Validation -> AI Analysis -> Executive Dashboard
mapping onto the patent's five capabilities (ingestion, normalization,
governance intelligence, explainable AI, executive decision support).
"""
from .ingest import ParsedPlan, PlanParseError, parse_plan
from .metrics import build_portfolio, compute_project

__all__ = [
    "ParsedPlan",
    "PlanParseError",
    "parse_plan",
    "compute_project",
    "build_portfolio",
]
