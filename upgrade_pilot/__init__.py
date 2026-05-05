\"\"\"Upgrade-Pilot: AI-Agentic Legacy Migrator.

A Python framework for automating large-scale dependency upgrades across
multiple languages using LLM-driven code refactoring and self-healing loops.

Key Features:
    - Multi-language support: Node.js, Python, Java, Go, Rust, PHP, Ruby, .NET.
    - Local LLM inference via Ollama (Llama 3) for security.
    - Self-healing migration loops with configurable retry logic.
    - Automatic detection of impacted files and sequential refactoring.
    - Git integration for branch creation and pull request generation.
    - Human-in-the-loop validation with manual intervention fallback.

Usage:
    from upgrade_pilot import build_agent_graph
    from upgrade_pilot.state import create_initial_state

    state = create_initial_state(\"/path/to/project\", \"nodejs\")
    graph = build_agent_graph()
    graph.run(state)
\"\"\"

from .graph import build_agent_graph
from .main import main

__all__ = ["build_agent_graph", "main"]
