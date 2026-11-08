from collections.abc import Callable
from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph


class DiagnosisState(TypedDict, total=False):
    experiment_id: str
    scenario_name: str
    evidence: dict
    findings: list[dict]
    diagnosis: dict


EvidenceLoader = Callable[[UUID, str], dict | None]


def build_diagnosis_graph(load_evidence: EvidenceLoader):
    """Build a diagnosis workflow with restricted evidence access."""

    def fetch_evidence(state: DiagnosisState) -> dict:
        evidence = load_evidence(
            UUID(state["experiment_id"]),
            state["scenario_name"],
        )

        if evidence is None:
            raise ValueError("Scenario evidence not found")

        return {"evidence": evidence}

    def investigate_failure(state: DiagnosisState) -> dict:
        """Analyze observable quality violations."""

        findings = []

        for check in state["evidence"].get("failed_checks", []):
            checked_rows = check["checked_rows"]
            failed_rows = check["failed_rows"]

            violation_rate = round(failed_rows / checked_rows, 4) if checked_rows > 0 else None

            findings.append(
                {
                    "rule_id": check["rule_id"],
                    "rule_type": check["rule_type"],
                    "failed_rows": failed_rows,
                    "checked_rows": checked_rows,
                    "violation_rate": violation_rate,
                }
            )

        return {"findings": findings}

    def analyze_failure(state: DiagnosisState) -> dict:
        evidence = state["evidence"]
        failed_rules = evidence["failed_rules"]

        if not failed_rules:
            diagnosis = {
                "status": "no_failure_detected",
                "suspected_rules": [],
                "summary": "No failed quality rules found.",
            }
        else:
            hypotheses = []
            for finding in state.get("findings", []):
                if finding["rule_type"] == "unique":
                    hypotheses.extend(
                        [
                            "Duplicate records may exist in the source dataset.",
                            "The ingestion pipeline may have processed the same record multiple times.",
                            "A pipeline retry may have caused duplicate records to be inserted.",
                        ]
                    )
            diagnosis = {
                "status": "failure_detected",
                "suspected_rules": failed_rules,
                "summary": ("Quality checks failed: " + ", ".join(failed_rules)),
                "hypotheses": hypotheses,
            }

        return {"diagnosis": diagnosis}

    graph = StateGraph(DiagnosisState)

    graph.add_node("fetch_evidence", fetch_evidence)
    graph.add_node("investigate_failure", investigate_failure)
    graph.add_node("analyze_failure", analyze_failure)

    graph.add_edge(START, "fetch_evidence")
    graph.add_edge("fetch_evidence", "investigate_failure")
    graph.add_edge("investigate_failure", "analyze_failure")
    graph.add_edge("analyze_failure", END)

    return graph.compile()
