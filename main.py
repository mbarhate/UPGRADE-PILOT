"""Entry point for Upgrade-Pilot.

This module provides the command-line interface to run the Upgrade-Pilot
agentic legacy migrator. It initializes the agentic workflow graph and
executes the migration for a specified project.

Usage:
    python main.py /path/to/project nodejs
    python main.py /path/to/project python
    python main.py /path/to/project java_maven

Dependencies:
    - upgrade_pilot.graph: LangGraph workflow orchestration.
    - upgrade_pilot.state: Agent state initialization.
"""

import argparse
import logging

from upgrade_pilot.graph import build_agent_graph
from upgrade_pilot.state import create_initial_state


logger = logging.getLogger(__name__)


def main() -> int:
    """Execute the Upgrade-Pilot migration workflow.

    This function:
    1. Parses command-line arguments for project path and language.
    2. Initializes logging for the migration session.
    3. Creates the initial agent state with project metadata.
    4. Builds and executes the LangGraph migration workflow.

    Returns:
        0 on successful execution, or non-zero error code on failure.

    Raises:
        SystemExit: Returns the exit code via raise SystemExit.
    """
    parser = argparse.ArgumentParser(
        description="Upgrade-Pilot: AI-Agentic Legacy Migrator",
        epilog=(
            "Example: python main.py /path/to/project nodejs\n"
            "Supported languages: nodejs, python, java_maven, java_gradle, "
            "dotnet, go, php, ruby, rust, cordova"
        ),
    )
    parser.add_argument(
        "project_path",
        help="Absolute path to the project to be migrated.",
    )
    parser.add_argument(
        "language",
        choices=[
            "nodejs",
            "python",
            "java_maven",
            "java_gradle",
            "dotnet",
            "go",
            "php",
            "ruby",
            "rust",
            "cordova",
        ],
        help="Programming language or runtime of the project.",
    )
    args = parser.parse_args()

    # Configure logging with timestamp and level information
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Initialize agent state and build the workflow graph
    state = create_initial_state(args.project_path, args.language)
    graph = build_agent_graph()
    logger.info(
        "Starting Upgrade-Pilot for project: %s (language: %s)",
        args.project_path,
        args.language,
    )

    # Execute the migration workflow
    graph.run(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
