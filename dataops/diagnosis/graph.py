from collections.abc import Callable
from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph


class DiagnosisState(TypedDict, total=False):
    experiment_id: str
    scenario_name: str
    evidence: dict
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
            diagnosis = {
                "status": "failure_detected",
                "suspected_rules": failed_rules,
                "summary": ("Quality checks failed: " + ", ".join(failed_rules)),
            }

        return {"diagnosis": diagnosis}

    graph = StateGraph(DiagnosisState)

    graph.add_node("fetch_evidence", fetch_evidence)
    graph.add_node("analyze_failure", analyze_failure)

    graph.add_edge(START, "fetch_evidence")
    graph.add_edge("fetch_evidence", "analyze_failure")
    graph.add_edge("analyze_failure", END)

    return graph.compile()
