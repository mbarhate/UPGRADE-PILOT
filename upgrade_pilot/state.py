"""State definitions for Upgrade-Pilot.

This module defines the AgentState TypedDict that represents the shared state
of the Upgrade-Pilot agentic workflow. It tracks the project metadata, detected
outdated libraries, file progress, error logs, and retry counters to enable
self-healing migration loops.
"""

from typing import List, Optional, TypedDict


class AgentState(TypedDict):
    """Shared state for the Upgrade-Pilot agentic workflow.

    Attributes:
        project_path: Absolute path to the project being migrated.
        language: Programming language/runtime (e.g., 'nodejs', 'python', 'java_maven').
        outdated_libs: List of outdated library versions detected (format: 'lib@old -> new').
        current_file: Path to the file currently being refactored.
        error_logs: Normalized error output from the last failed build/test.
        iteration_count: Number of completed library migration iterations.
        max_retries: Maximum number of retry attempts for a single file (default: 3).
        current_retry_count: Current retry count for the file being validated.
        impacted_files: List of source files affected by the library upgrade.
        current_file_index: Index of the file currently being processed in the impacted_files list.
        manual_intervention_requested: Flag indicating whether manual review is needed.
    """

    project_path: str
    language: str
    outdated_libs: List[str]
    current_file: Optional[str]
    error_logs: str
    iteration_count: int
    max_retries: int
    current_retry_count: int
    impacted_files: List[str]
    current_file_index: int
    manual_intervention_requested: bool


def create_initial_state(project_path: str, language: str) -> AgentState:
    """Initialize a new AgentState for the given project.

    Args:
        project_path: Absolute path to the project being migrated.
        language: Programming language/runtime identifier.

    Returns:
        A fully initialized AgentState with default values.
    """
    return {
        "project_path": project_path,
        "language": language,
        "outdated_libs": [],
        "current_file": None,
        "error_logs": "",
        "iteration_count": 0,
        "max_retries": 3,
        "current_retry_count": 0,
        "impacted_files": [],
        "current_file_index": 0,
        "manual_intervention_requested": False,
    }
