"""Utilities for Upgrade-Pilot.

This module provides helper functions for logging, retry logic, manifest parsing,
and version lookups.
"""

import json
import logging
import re
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


def setup_logging(log_level: str = "INFO", log_file: str = "upgrade_pilot.log") -> None:
    """Configure logging to console and file.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        log_file: Path to log file for persistent logging.
    """
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=getattr(logging, log_level),
        format=log_format,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )
    logger.info("Logging configured: level=%s, file=%s", log_level, log_file)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
) -> Callable:
    """Decorator for exponential backoff retry logic.

    Retries a function with exponential backoff on exception.
    Delay: base_delay * (backoff_factor ** attempt)

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds before first retry.
        backoff_factor: Multiplier for delay on each retry.

    Returns:
        Decorated function that retries on failure.

    Example:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def call_llm():
            return chat.predict(...)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (backoff_factor ** attempt)
                        logger.warning(
                            "Attempt %d/%d failed: %s. Retrying in %.2fs...",
                            attempt + 1,
                            max_retries,
                            str(e),
                            delay,
                        )
                        time.sleep(delay)
                    else:
                        logger.error("All %d retry attempts exhausted.", max_retries)

            raise last_exception or RuntimeError(f"Function {func.__name__} failed after {max_retries} retries")

        return wrapper

    return decorator


def parse_package_json(manifest_path: Path) -> Dict[str, str]:
    """Parse package.json to extract dependencies.

    Args:
        manifest_path: Path to package.json.

    Returns:
        Dictionary of {package_name: version}.

    Raises:
        FileNotFoundError: If package.json does not exist.
        json.JSONDecodeError: If package.json is not valid JSON.
    """
    if not manifest_path.exists():
        raise FileNotFoundError(f"package.json not found at {manifest_path}")

    with open(manifest_path, "r") as f:
        data = json.load(f)

    dependencies = {}
    for section in ["dependencies", "devDependencies", "peerDependencies"]:
        if section in data:
            dependencies.update(data[section])

    return dependencies


def parse_requirements_txt(manifest_path: Path) -> Dict[str, str]:
    """Parse requirements.txt to extract dependencies.

    Supports format: package-name==version or package-name>=version

    Args:
        manifest_path: Path to requirements.txt.

    Returns:
        Dictionary of {package_name: version}.

    Raises:
        FileNotFoundError: If requirements.txt does not exist.
    """
    if not manifest_path.exists():
        raise FileNotFoundError(f"requirements.txt not found at {manifest_path}")

    dependencies = {}
    with open(manifest_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Match patterns like: package==1.0.0, package>=1.0.0, package~=1.0.0
            match = re.match(r"^([a-zA-Z0-9_-]+)([><=~!]+)(.+?)$", line)
            if match:
                package_name = match.group(1)
                operator = match.group(2)
                version = match.group(3).strip()
                dependencies[package_name] = f"{operator}{version}"
            else:
                # Package without version constraint
                dependencies[line] = "*"

    return dependencies


def get_latest_version(library_name: str, language: str) -> str:
    """Fetch latest version from package registry (mocked for POC).

    For production, this would call:
    - npm registry API for Node.js packages
    - PyPI API for Python packages
    - Maven Central for Java packages

    Args:
        library_name: Name of the library/package.
        language: Programming language (nodejs, python, java_maven, etc.).

    Returns:
        Latest version string (mocked as "latest" for POC).
    """
    logger.debug("Fetching latest version for %s (%s)", library_name, language)

    # Mock implementation for POC
    # In production, call real APIs:
    # if language == "nodejs":
    #     response = requests.get(f"https://registry.npmjs.org/{library_name}")
    #     return response.json().get("dist-tags", {}).get("latest", "unknown")
    # elif language == "python":
    #     response = requests.get(f"https://pypi.org/pypi/{library_name}/json")
    #     return response.json().get("info", {}).get("version", "unknown")

    return "latest"


def detect_outdated_libraries(current_deps: Dict[str, str], language: str) -> List[str]:
    """Detect outdated libraries by comparing with latest versions.

    Args:
        current_deps: Dictionary of {package_name: current_version}.
        language: Programming language.

    Returns:
        List of outdated entries (format: "package@current -> latest").
    """
    outdated = []
    for package, version in current_deps.items():
        latest = get_latest_version(package, language)
        # Mock: Mark all as outdated for POC demonstration
        if latest != "unknown":
            outdated.append(f"{package}@{version} -> {latest}")

    return outdated


def extract_last_lines(text: str, num_lines: int = 20) -> str:
    """Extract the last N lines from text.

    Args:
        text: Input text (often stderr output).
        num_lines: Number of lines to extract.

    Returns:
        Last N lines joined by newline.
    """
    lines = text.strip().splitlines()
    return "\n".join(lines[-num_lines:])
