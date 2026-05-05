# Upgrade-Pilot Architecture

## Overview

Upgrade-Pilot is an AI-agentic legacy migrator that automates large-scale dependency upgrades across multiple programming languages. It uses a self-healing migration loop powered by LangGraph, Ollama (Llama 3), and PyGithub.

## Core Concepts

### Agentic Workflow

The migration process is implemented as a **directed cyclic graph** (DAG) with conditional edges. The workflow automatically detects and fixes build errors by looping back through the refactoring node.

```
auditor → refactor → validator → [conditions]
                        ↓
                    success? yes → git (create PR)
                        ↓
                    success? no → manual_intervention or refactor (retry)
```

### State Management

All state is managed through the `AgentState` TypedDict, which tracks:
- **Project metadata**: `project_path`, `language`, `iteration_count`
- **Library info**: `outdated_libs` (detected breaking changes)
- **File progress**: `impacted_files`, `current_file_index`, `current_file`
- **Validation state**: `error_logs`, `current_retry_count`, `max_retries`
- **Control flags**: `manual_intervention_requested`

### Configuration-Driven

The `LANGUAGE_CONFIG` dictionary is the single source of truth for all language-specific behavior:
- Manifest filenames (e.g., `package.json`, `pom.xml`)
- Build/test/install commands
- Source file extensions
- Research context for the LLM (domain-specific hints)

## Node Architecture

### 1. Auditor Node (`auditor_node`)
**Purpose**: Entry point; detects outdated dependencies.

**Responsibilities**:
- Locates the project's manifest file (handles glob patterns like `*.csproj`)
- Initializes state tracking variables (file index, retry count, intervention flag)
- Parses manifest to detect outdated library versions
- Sets up the initial `impacted_files` list

**Output**: Updated state with `outdated_libs` and initial manifest path.

### 2. Refactor Node (`refactor_node`)
**Purpose**: AI-driven code migration.

**Responsibilities**:
- Discovers all impacted files via `find_impacted_files()` (uses recursive grep)
- Processes files sequentially by `current_file_index`
- Reads file content and builds LLM prompt containing:
  - Current file content
  - Breaking change research (from `research_context`)
  - Latest build error excerpt
- Calls ChatOllama with:
  - `model="llama3"`
  - `temperature=0` (consistency)
  - `num_ctx=4096` (larger context window)
- Parses response for fenced code blocks (```python or ```javascript)
- Writes refactored code to disk

**Output**: Refactored source files; sets `error_logs` to empty on success or parsing failure message.

### 3. Validator Node (`validator_node`)
**Purpose**: Validate refactored code through build/test.

**Responsibilities**:
- Executes `install_cmd`, `build_cmd`, and `test_cmd` sequentially
- Captures stderr output
- Normalizes error output via `normalize_error_excerpt()`:
  - Searches for lines with "Error", "Fail", "Exception", "Traceback", "fatal"
  - Returns last 20 of these lines, or last 20 lines overall
- On **failure**:
  - Increments `current_retry_count`
  - Stores normalized error in `error_logs`
- On **success**:
  - Resets retry counter
  - Advances `current_file_index` if more files remain
  - Clears `error_logs`

**Output**: Updated retry state or advanced file index.

### 4. Manual Intervention Node (`manual_intervention_node`)
**Purpose**: Escalation for persistent failures.

**Responsibilities**:
- Triggered when `current_retry_count > max_retries`
- Sets `manual_intervention_requested = True`
- Attempts to skip to the next impacted file
- Logs warning/error for documentation
- Allows workflow to continue with remaining files or terminate

**Output**: Advanced file index or final escalation flag.

### 5. Git Node (`git_node`)
**Purpose**: Create PR with migration changes.

**Responsibilities**:
- Resolves unique branch name (appends timestamp if conflict detected)
- Parses GitHub repository URL from `git remote origin`
- Creates/checks out migration branch
- Stages all changes (`git add .`)
- Commits with message like "Upgrade-Pilot migration for nodejs"
- Extracts modified file list via `git diff --name-only HEAD`
- Constructs PR body with:
  - Library version changes
  - Modified file list
- Creates pull request via PyGithub API

**Output**: PR created; workflow terminates.

## Edge Conditions and Routing

### Success Path (All files validated)
```
validator → success & (current_file_index >= len(impacted_files) - 1) → git
```

### Retryable Failure Path
```
validator → error & (current_retry_count <= max_retries) → refactor (loop)
```

### Manual Intervention Path
```
validator → error & (current_retry_count > max_retries) → manual_intervention
manual_intervention → (more files) → refactor (next file)
manual_intervention → (no more files) → [terminate]
```

## Helper Functions

### `normalize_error_excerpt(stderr: str) -> str`
Extracts relevant error lines from build/test output. Prioritizes lines with error keywords.

### `parse_code_block(response: str) -> Optional[str]`
Parses LLM response for fenced code blocks (```python or ```javascript).

### `get_library_name(outdated_entry: str) -> str`
Extracts library name from version entry (e.g., "lib@old -> new" → "lib").

### `find_impacted_files(project_path, extensions, outdated_libs) -> List[str]`
Recursively searches project for files referencing outdated libraries using grep.

### `resolve_branch_name(project_path, base_branch) -> str`
Ensures unique git branch name by appending timestamp if needed.

## Language Configuration

Each language entry in `LANGUAGE_CONFIG` defines:

```python
{
    "manifest": "package.json",                    # Dependency manifest
    "install_cmd": "npm install",                  # Install dependencies
    "build_cmd": "npm run build",                  # Compile/build
    "test_cmd": "npm test",                        # Run tests
    "extensions": [".js", ".jsx", ".ts", ".tsx"],  # Source file types
    "research_context": "npm ecosystem and CommonJS/ESM modules"  # LLM hint
}
```

## Supported Languages

- **nodejs**: npm, yarn
- **python**: pip, pytest
- **java_maven**: Maven
- **java_gradle**: Gradle
- **dotnet**: .NET Core/Framework
- **go**: Go modules
- **php**: Composer
- **ruby**: Bundler
- **rust**: Cargo
- **cordova**: Mobile hybrid apps

## Security & Privacy

- **Local inference**: Llama 3 runs on the local machine via Ollama; no code leaves your environment
- **Human-in-the-loop**: Generated PRs require manual review before merge
- **Git integration**: Changes are staged on a feature branch, not pushed to main

## Error Handling

1. **Missing Manifest**: Logged as error; workflow terminates
2. **Parse Failure**: LLM response without fenced code block; error logged; refactor retried
3. **Build Failure**: Error excerpt captured; refactor node retried with new error context
4. **Retry Exhaustion**: Manual intervention node logs failure; skips to next file if available
5. **Git Failure**: Logged; PR creation may fail if token is missing

## Future Enhancements

- Real manifest parsing (currently uses placeholder)
- Multi-branch support (currently single feature branch)
- Dependency graph analysis for optimal refactoring order
- Custom LLM prompt templates per language
- Metrics and telemetry for migration success rate
