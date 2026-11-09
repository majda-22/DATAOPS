from collections.abc import Callable
from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


class DiagnosisState(TypedDict, total=False):
    experiment_id: str
    scenario_name: str
    evidence: dict
    findings: list[dict]
    diagnosis: dict
    pipeline_run_id: str | None
    pipeline_run: dict | None
    incident_id: int | None
    incident: dict | None


EvidenceLoader = Callable[[UUID, str], dict | None]
PipelineRunLoader = Callable[[UUID], dict | None]
IncidentLoader = Callable[[int], dict | None]
IncidentEvindenceLoader = Callable[[int], dict | None]


def build_diagnosis_graph(
    load_evidence: EvidenceLoader,
    load_pipeline_run: PipelineRunLoader | None = None,
    load_incident: IncidentLoader | None = None,
    load_incident_evidence: IncidentEvindenceLoader | None = None,
) -> CompiledStateGraph[DiagnosisState]:
    """Build a diagnosis workflow with restricted evidence access."""

    def fetch_evidence(state: DiagnosisState) -> dict:
        """Load evidence from either an incident or an experiment."""

        incident_id = state.get("incident_id")

        if incident_id is not None:
            if load_incident_evidence is None:
                raise ValueError("Incident evidence loader is not configured")

            evidence = load_incident_evidence(incident_id)

        else:
            experiment_id = state.get("experiment_id")
            scenario_name = state.get("scenario_name")

            if not experiment_id or not scenario_name:
                raise ValueError("Experiment ID and scenario name are required")

            evidence = load_evidence(
                UUID(experiment_id),
                scenario_name,
            )

        if evidence is None:
            raise ValueError("Quality evidence not found")

        return {"evidence": evidence}

    def fetch_incident(state: DiagnosisState) -> dict:
        """Load incident context and its explicitly linked pipeline run."""

        incident_id = state.get("incident_id")

        if incident_id is None:
            return {"incident": None}

        if load_incident is None:
            raise ValueError("Incident loader is not configured")

        incident = load_incident(incident_id)

        if incident is None:
            raise ValueError(f"Incident not found: {incident_id}")

        explicit_run_id = state.get("pipeline_run_id")
        incident_run_id = incident["pipeline_run_id"]

        if explicit_run_id is not None and explicit_run_id != incident_run_id:
            raise ValueError("Pipeline run conflicts with incident association")

        return {
            "incident": incident,
            "pipeline_run_id": incident_run_id,
        }

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

    def inspect_pipeline_run(state: DiagnosisState) -> dict:
        """Inspect only an explicitly associated pipeline run."""

        run_id = state.get("pipeline_run_id")

        if run_id is None or load_pipeline_run is None:
            return {"pipeline_run": None}

        pipeline_run = load_pipeline_run(UUID(run_id))

        return {"pipeline_run": pipeline_run}

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
    graph.add_node("fetch_incident", fetch_incident)
    graph.add_node("analyze_failure", analyze_failure)
    graph.add_node("inspect_pipeline_run", inspect_pipeline_run)

    graph.add_edge(START, "fetch_incident")
    graph.add_edge("fetch_incident", "fetch_evidence")
    graph.add_edge("fetch_evidence", "investigate_failure")
    graph.add_edge("investigate_failure", "inspect_pipeline_run")
    graph.add_edge("inspect_pipeline_run", "analyze_failure")
    graph.add_edge("analyze_failure", END)

    return graph.compile()
