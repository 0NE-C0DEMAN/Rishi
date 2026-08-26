"""Canonical structure of the client's project-plan template.

The uploaded workbook is an IT-delivery WBS plan: a metadata block (project
identity + go-live dates) plus a task table grouped into seven delivery phases.
These constants are the single source of truth shared by the ingest parser
(what to look for) and the sample generator (what to emit).
"""
from __future__ import annotations

# (WBS number, phase name, [activities]) — the seven-phase delivery lifecycle
# exactly as it appears in "Project Plan Template.xlsx".
PHASES: list[tuple[int, str, list[str]]] = [
    (1, "Initiation", [
        "Project Charter",
        "Initiation Meeting SP Tech Internal",
        "Initiation Meeting W Vendors",
        "Stakeholder Identification",
        "Internal & External Meeting Cadence Setup",
    ]),
    (2, "Requirements", [
        "Project Kickoff Meeting",
        "Identify Stakeholders",
        "Gather Business Requirements",
        "Prepare Business Requirements Document (BRD)",
        "Requirements Sign-Off",
    ]),
    (3, "Design", [
        "Solution Design Workshop- SP Tech Internal",
        "Solution Design Workshop- W Vendors",
        "Prepare Functional Requirements Document (FRD)",
        "Process Flow Design",
        "Technical Architecture Review",
        "Security & Compliance Review W Security Team",
        "Integration Design",
    ]),
    (4, "Development", [
        "Environment Setup",
        "Configuration Activities",
        "Custom Development (If any)",
        "Integration Development",
        "Unit Testing",
    ]),
    (5, "Testing", [
        "Test Plan Preparation",
        "Testing Steps & Scenarios",
        "System Testing (SIT)",
        "Integration Testing",
        "QA",
        "User Acceptance Testing (UAT)",
        "UAT Sign Off by Business",
    ]),
    (6, "Implementation", [
        "User Training / Demo",
        "User Training",
        "Cutover Planning",
        "Go-Live Readiness Review",
        "GO NO GO Discussion / Approval",
    ]),
    (7, "Go Live", [
        "Production Deployment",
        "Hypercare Support",
        "Lessons Learnt",
        "Project Closure",
        "Post Go Live Support | 4 weeks",
    ]),
]

PHASE_ORDER: list[str] = [p[1] for p in PHASES]

# Canonical task columns produced by the parser (order matters for exports).
CANONICAL_TASK_COLS = [
    "wbs", "phase", "task_id", "activity", "owner", "team", "status",
    "pct_complete", "priority", "critical_path", "dependency", "risk_level",
    "planned_start", "actual_start", "planned_finish", "actual_finish",
]

# Metadata labels in the template's left block -> canonical keys.
META_LABELS: dict[str, str] = {
    "project id": "project_id",
    "project name": "project_name",
    "planned go live date": "planned_go_live",
    "forcast go live date": "forecast_go_live",   # template's spelling
    "forecast go live date": "forecast_go_live",
    "approved budget": "approved_budget",
    "total approved budget": "approved_budget",
    "actual spend": "actual_spend",
    "actual spend to date": "actual_spend",
    "project owner": "owner",
    "business stakeholder": "stakeholder",
    "project manager": "pm",
}

# Header text -> canonical column. Matched by substring, most-specific first.
TASK_HEADER_MATCHERS: list[tuple[str, list[str]]] = [
    ("wbs", ["wbs"]),
    ("effort_completed", ["effort completed", "hours completed"]),
    ("effort_remaining", ["effort remaining", "hours remaining"]),
    ("effort", ["effort", "budget hours", "planned hours"]),
    ("task_id", ["task id"]),
    ("activity", ["project activity", "activity"]),
    ("pct_complete", ["% complete", "percent complete", "complete"]),
    ("critical_path", ["critical path", "critical"]),
    ("dependency", ["dependency", "predecess"]),
    ("risk_level", ["risk level", "risk"]),
    ("planned_start", ["planned start"]),
    ("actual_start", ["actual start"]),
    ("planned_finish", ["planned finish"]),
    ("actual_finish", ["actual finish"]),
    ("priority", ["priority"]),
    ("owner", ["owner"]),
    ("team", ["team"]),
    ("status", ["status"]),
    ("phase", ["phase"]),
]

# Status vocabulary (normalized).
STATUS_DONE = {"complete", "completed", "done", "closed"}
STATUS_ACTIVE = {"in progress", "in-progress", "ongoing", "wip", "started"}
STATUS_BLOCKED = {"blocked", "on hold", "on-hold", "at risk"}
STATUS_NOT_STARTED = {"not started", "not-started", "new", "planned", ""}

RISK_LEVELS = ["Low", "Medium", "High", "Critical"]

# Activities that represent governance gates / milestones (besides critical path).
MILESTONE_KEYWORDS = [
    "charter", "kickoff", "sign-off", "sign off", "brd", "frd",
    "architecture review", "go no go", "go-live readiness", "readiness review",
    "production deployment", "uat sign", "project closure",
]
