"""Graph definition and orchestration for Upgrade-Pilot.

This module builds and configures the LangGraph state machine that orchestrates
the migration workflow. The graph connects five key nodes in a cyclic flow:

1. auditor_node: Scans the project manifest and detects outdated dependencies.
2. refactor_node: Uses Llama 3 to suggest code changes for each impacted file.
3. validator_node: Runs build/test commands and captures errors.
4. manual_intervention_node: Escalates failures that exceed the retry limit.
5. git_node: Creates a git branch and pull request with the migration changes.

Edge conditions route the flow based on:
- Success: Move to next impacted file or git (if all files done).
- Retryable failure: Loop back to refactor_node.
- Exhausted retries: Move to manual_intervention_node and skip to next file.
"""

import logging

from langgraph import StateGraph

from .nodes import (
    auditor_node,
    git_node,
    manual_intervention_node,
    refactor_node,
    validator_node,
)
from .state import AgentState

logger = logging.getLogger(__name__)


def build_agent_graph() -> StateGraph:
    """Build and initialize the Upgrade-Pilot agentic workflow graph.

    The graph implements the self-healing migration loop:
    - Detects outdated dependencies via auditor_node.
    - Identifies impacted files via grep and file discovery.
    - Refactors files sequentially using LLM suggestions.
    - Validates changes using language-specific build/test commands.
    - Retries up to max_retries (default 3) on validation failure.
    - Escalates to manual_intervention_node if retries are exhausted.
    - Creates a PR via git_node after all files are successfully migrated.

    Returns:
        A compiled StateGraph ready to execute the migration workflow.

    Raises:
        Configuration errors if language is not supported in LANGUAGE_CONFIG.
    """
    graph = StateGraph()

    graph.add_node("auditor", auditor_node)
    graph.add_node("refactor", refactor_node)
    graph.add_node("validator", validator_node)
    graph.add_node("manual_intervention", manual_intervention_node)
    graph.add_node("git", git_node)

    graph.add_edge("auditor", "refactor")
    graph.add_edge("refactor", "validator")
    graph.add_edge(
        "validator",
        "git",
        condition=lambda state: not state.get("error_logs")
        and state.get("current_file_index", 0) >= len(state.get("impacted_files", [])) - 1,
    )
    graph.add_edge(
        "validator",
        "manual_intervention",
        condition=lambda state: bool(state.get("error_logs"))
        and state.get("current_retry_count", 0) > state.get("max_retries", 3),
    )
    graph.add_edge(
        "validator",
        "refactor",
        condition=lambda state: bool(state.get("error_logs"))
        and state.get("current_retry_count", 0) <= state.get("max_retries", 3),
    )
    graph.add_edge(
        "manual_intervention",
        "refactor",
        condition=lambda state: state.get("current_file_index", 0) < len(state.get("impacted_files", [])),
    )

    logger.info(
        "Agent graph initialized with auditor, refactor, validator, manual intervention, and git nodes"
    )
    return graph
