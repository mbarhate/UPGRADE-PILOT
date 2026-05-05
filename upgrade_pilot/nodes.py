"""LangGraph nodes for Upgrade-Pilot.

This module defines the five core workflow nodes that orchestrate the legacy
migration agentic loop:

1. auditor_node: Scans project manifest files to detect outdated dependencies.
2. refactor_node: Uses Ollama Llama 3 to suggest code refactoring for each file.
3. validator_node: Runs build/test commands and captures error logs.
4. manual_intervention_node: Escalates issues exceeding retry limits.
5. git_node: Creates git branches and pull requests with migration changes.

Helper functions support file discovery, error normalization, code parsing,
branch conflict resolution, and library name extraction.
"""

import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from subprocess import CalledProcessError
from typing import Any, Dict, List, Optional

from github import Github
from langchain.chat_models import ChatOllama

from .config import LANGUAGE_CONFIG, OLLAMA_BASE_URL, OLLAMA_MODEL
from .state import AgentState
from .utils import (
    detect_outdated_libraries,
    extract_last_lines,
    parse_package_json,
    parse_requirements_txt,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)
CODE_FENCE_RE = re.compile(r"```(?:python|javascript)?\n(.+?)```", re.DOTALL)


def normalize_error_excerpt(stderr: str) -> str:
    """Extract relevant error lines from stderr output.

    Attempts to identify lines containing Error, Fail, Exception, Traceback,
    or fatal keywords. If found, returns the last 20 of these lines. Otherwise,
    returns the last 20 lines of stderr as fallback.

    Args:
        stderr: Full stderr output from a failed build/test command.

    Returns:
        Normalized error excerpt (up to 20 lines) suitable for LLM context.
    """
    if not stderr:
        return ""

    lines = stderr.strip().splitlines()
    relevant = [
        line
        for line in lines
        if re.search(r"\b(Error|Fail|Exception|Traceback|fatal)\b", line, re.I)
    ]
    if relevant:
        excerpt = relevant[-20:]
    else:
        excerpt = lines[-20:]
    return "\n".join(excerpt)


def parse_code_block(response: str) -> Optional[str]:
    """Extract code from a fenced code block in LLM response.

    Searches for the first occurrence of ```python or ```javascript blocks
    and extracts the content.

    Args:
        response: LLM response text.

    Returns:
        The code content if a fenced block is found, None otherwise.
    """
    match = CODE_FENCE_RE.search(response)
    if not match:
        return None
    return match.group(1).strip()


def get_library_name(outdated_entry: str) -> str:
    """Extract the library name from a version change entry.

    Assumes format: 'library-name@old-version -> new-version'

    Args:
        outdated_entry: Version change entry.

    Returns:
        The library name (everything before the '@' symbol).
    """
    return outdated_entry.split("@", 1)[0].strip()


def find_impacted_files(project_path: Path, extensions: List[str], outdated_libs: List[str]) -> List[str]:
    """Recursively search for files that reference outdated libraries.

    Uses grep to find all source files with specific extensions that contain
    references to any of the outdated library names.

    Args:
        project_path: Root directory of the project.
        extensions: List of file extensions to search (e.g., ['.js', '.py']).
        outdated_libs: List of outdated library entries.

    Returns:
        List of file paths that reference outdated libraries (deduplicated).
    """
    matches: List[str] = []
    for outdated in outdated_libs:
        package = get_library_name(outdated)
        for ext in extensions:
            grep_args = [
                "grep",
                "-R",
                "--exclude-dir=.git",
                "--include",
                f"*{ext}",
                package,
                str(project_path),
            ]
            result = subprocess.run(
                grep_args,
                capture_output=True,
                text=True,
                check=False,
            )
            for line in result.stdout.splitlines():
                path = line.split(":", 1)[0]
                if path and path not in matches:
                    matches.append(path)
    return matches


def resolve_branch_name(project_path: Path, base_branch: str) -> str:
    """Resolve a unique branch name, appending timestamp if needed.

    Checks if a branch with the given name already exists. If it does,
    appends a UTC timestamp to avoid conflicts.

    Args:
        project_path: Root directory of the git repository.
        base_branch: Desired branch name.

    Returns:
        The branch name (original or with timestamp suffix if conflict exists).
    """
    branch_name = base_branch
    branch_exists = subprocess.run(
        ["git", "rev-parse", "--verify", branch_name],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if branch_exists.returncode == 0:
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
        branch_name = f"{base_branch}-{timestamp}"
        logger.info("Branch already existed, using branch name %s", branch_name)
    return branch_name


def auditor_node(state: AgentState) -> AgentState:
    """Scan project manifest and detect outdated dependencies.

    This is the entry point of the migration workflow. It:
    1. Locates the language-specific manifest file (package.json, pom.xml, etc.)
    2. Initializes impacted files tracking and retry counters.
    3. Parses the manifest using language-specific logic.
    4. Detects outdated library versions.

    Args:
        state: The current agent state.

    Returns:
        Updated state with detected outdated libraries and manifest path.
    """
    import json
    
    project_path = Path(state["project_path"])
    language_config = LANGUAGE_CONFIG.get(state["language"], {})
    manifest_name = language_config.get("manifest")

    if manifest_name is None:
        logger.warning("No manifest configured for language %s", state["language"])
        state["error_logs"] = "No manifest configuration available."
        return state

    manifest_path = project_path / manifest_name
    if "*" in manifest_name:
        candidates = list(project_path.glob(manifest_name))
        if candidates:
            manifest_path = candidates[0]

    state["current_file"] = str(manifest_path)
    state["impacted_files"] = []
    state["current_file_index"] = 0
    state["current_retry_count"] = 0
    state["manual_intervention_requested"] = False

    if not manifest_path.exists():
        logger.error("Manifest file not found: %s", manifest_path)
        state["error_logs"] = f"Manifest not found: {manifest_path}"
        return state

    logger.info("Scanning manifest file: %s", manifest_path)

    try:
        # Parse manifest based on language
        if state["language"] == "nodejs":
            dependencies = parse_package_json(manifest_path)
        elif state["language"] == "python":
            dependencies = parse_requirements_txt(manifest_path)
        else:
            # Placeholder for other languages
            logger.warning("Real parsing not yet implemented for %s", state["language"])
            dependencies = {}

        # Detect outdated libraries
        outdated = detect_outdated_libraries(dependencies, state["language"])
        state["outdated_libs"] = outdated if outdated else ["example-lib@1.0.0 -> 2.0.0"]

        logger.info("Detected %d outdated libraries", len(state["outdated_libs"]))
        for lib in state["outdated_libs"]:
            logger.debug("  - %s", lib)

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        logger.error("Failed to parse manifest: %s", str(e))
        state["error_logs"] = f"Manifest parse error: {str(e)}"
        state["outdated_libs"] = []

    return state


def refactor_node(state: AgentState) -> AgentState:
    """Use Llama 3 to suggest code refactoring for outdated libraries.

    This node:
    1. Identifies all impacted files (if not already cached).
    2. Processes files sequentially from current_file_index.
    3. Reads file content and builds an LLM prompt with:
       - Current file content
       - Breaking change research context
       - Latest build/test error excerpt
    4. Requests refactor suggestions from ChatOllama (temperature=0, num_ctx=4096).
    5. Parses the LLM response for a fenced code block.
    6. Writes the refactored code to disk if valid.

    Args:
        state: The current agent state.

    Returns:
        Updated state with refactored file or error message.
    """


def validator_node(state: AgentState) -> AgentState:
    """Run build and test commands to validate refactored code.

    This node:
    1. Retrieves language-specific install, build, and test commands.
    2. Executes install, build, and test sequentially.
    3. Captures and normalizes stderr output on failure.
    4. Increments retry counter on any error.
    5. Advances to next impacted file on success.
    6. Provides error excerpt to refactor_node for iterative fixes.

    Args:
        state: The current agent state.

    Returns:
        Updated state with error logs or advanced file index on success.
    """

    def run_command(command: Any, label: str) -> str:
        logger.info("Running %s: %s", label, command)
        if isinstance(command, str):
            result = subprocess.run(
                command,
                cwd=project_path,
                capture_output=True,
                text=True,
                shell=True,
                check=False,
            )
        else:
            result = subprocess.run(
                command,
                cwd=project_path,
                capture_output=True,
                text=True,
                check=False,
            )

        if result.returncode != 0:
            logger.error("%s failed: %s", label, result.stderr)
            return result.stderr
        logger.info("%s succeeded", label)
        return ""

    install_errors = run_command(install_cmd, "install")
    build_errors = run_command(build_cmd, "build")
    test_errors = run_command(test_cmd, "test")
    combined_errors = "".join([install_errors, build_errors, test_errors])

    if combined_errors:
        state["current_retry_count"] += 1
        state["error_logs"] = normalize_error_excerpt(combined_errors)
        logger.warning(
            "Validation failed for %s; retry %d/%d",
            state.get("current_file"),
            state["current_retry_count"],
            state["max_retries"],
        )
    else:
        state["current_retry_count"] = 0
        state["error_logs"] = ""

        if state["impacted_files"] and state["current_file_index"] < len(state["impacted_files"]) - 1:
            state["current_file_index"] += 1
            logger.info("Validation successful; moving to next impacted file index %d.", state["current_file_index"])

    return state


def manual_intervention_node(state: AgentState) -> AgentState:
    """Handle files that exceed the retry limit.

    This node is triggered when current_retry_count > max_retries. It:
    1. Sets manual_intervention_requested flag.
    2. Attempts to advance to the next impacted file if available.
    3. Logs a warning if moving to next file, or error if no more files.
    4. Allows the workflow to continue with remaining files or escalate.

    Args:
        state: The current agent state.

    Returns:
        Updated state with manual_intervention_requested set and next file index.
    """


def git_node(state: AgentState) -> AgentState:
    """Create a git branch and pull request with migration changes.

    This node is executed after all impacted files are successfully migrated. It:
    1. Resolves a unique branch name (with timestamp if conflicts exist).
    2. Parses the GitHub repository URL from git remote origin.
    3. Creates/checks out the migration branch.
    4. Stages and commits all modified files with a descriptive message.
    5. Extracts the list of modified files via git diff.
    6. Constructs a PR body with:
       - Library version changes
       - List of modified files
    7. Creates a GitHub pull request for human review.

    Args:
        state: The current agent state.

    Returns:
        Updated state with git/PR creation status.
    """

    remote_url = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    owner_repo = ""
    if remote_url.startswith("git@github.com:"):
        owner_repo = remote_url.split(":", 1)[1].replace(".git", "")
    elif remote_url.startswith("https://github.com/"):
        owner_repo = remote_url.split("github.com/", 1)[1].replace(".git", "")

    if not owner_repo:
        state["error_logs"] = "Unable to parse GitHub repository from remote URL."
        return state

    github = Github(github_token)
    repo = github.get_repo(owner_repo)

    subprocess.run(["git", "checkout", "-B", branch_name], cwd=project_path, check=False)
    subprocess.run(["git", "add", "."], cwd=project_path, check=False)
    commit_message = f"Upgrade-Pilot migration for {state.get('language')}"
    subprocess.run(["git", "commit", "-m", commit_message], cwd=project_path, check=False)

    modified_files = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip().splitlines()

    file_list = "\n".join(f"- {path}" for path in modified_files if path)
    library_changes = "\n".join(f"- {change}" for change in state.get("outdated_libs", []))
    pr_body = (
        "Upgrade-Pilot migration changes:\n\n"
        f"Library change details:\n{library_changes}\n\n"
        f"Files modified:\n{file_list}\n"
    )

    repo.create_pull(
        title=f"Upgrade-Pilot migration: {state.get('language')}",
        body=pr_body,
        base=repo.default_branch,
        head=branch_name,
    )

    logger.info("Pull request created for branch %s", branch_name)
    state["error_logs"] = ""
    return state
