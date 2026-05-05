# Upgrade-Pilot Development Guide

## Getting Started

### Prerequisites

- Python 3.10+
- Ollama 2.0+ with Llama 3 model
- Git 2.30+
- GitHub PAT (Personal Access Token) for PR creation

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/upgrade-pilot.git
cd upgrade-pilot

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install langchain langgraph langchain_community pygithub streamlit

# Verify Ollama is running
ollama list  # Should show llama3
```

### Environment Variables

```bash
# Required for GitHub PR creation
export GITHUB_TOKEN=your_github_pat_here

# Optional: Custom Ollama endpoint (defaults to http://localhost:11434)
export OLLAMA_BASE_URL=http://localhost:11434
```

## Running Upgrade-Pilot

### Basic Usage

```bash
# Run migration for a Node.js project
python main.py /path/to/nodejs-project nodejs

# Run migration for a Python project
python main.py /path/to/python-project python

# Run migration for a Java Maven project
python main.py /path/to/java-project java_maven
```

### Command Output

```
2024-05-04 10:15:32 [INFO] upgrade_pilot.main: Starting Upgrade-Pilot for project: /path/to/project (language: nodejs)
2024-05-04 10:15:32 [INFO] upgrade_pilot.nodes: Scanning manifest file: /path/to/project/package.json
2024-05-04 10:15:33 [INFO] upgrade_pilot.nodes: Detected outdated libraries: [...] 
2024-05-04 10:15:34 [INFO] upgrade_pilot.nodes: Found impacted files: [...] 
2024-05-04 10:15:45 [INFO] upgrade_pilot.nodes: Updated file written: /path/to/project/src/app.js
2024-05-04 10:15:52 [INFO] upgrade_pilot.nodes: Validation succeeded; moving to next impacted file index 1.
...
2024-05-04 10:20:15 [INFO] upgrade_pilot.nodes: Pull request created for branch upgrade-pilot/migration-0
```

## Project Structure

```
upgrade-pilot/
├── main.py                     # CLI entry point
├── README.md                   # Project overview
├── ARCHITECTURE.md             # System design documentation
├── DEVELOPMENT.md              # This file
├── upgrade_pilot/
│   ├── __init__.py             # Package initialization with module docstring
│   ├── config.py               # LANGUAGE_CONFIG definitions
│   ├── state.py                # AgentState TypedDict and initialization
│   ├── nodes.py                # Workflow node implementations
│   └── graph.py                # LangGraph workflow definition
└── .gitignore                  # Git ignore rules
```

## Module Reference

### `config.py`
Defines `LANGUAGE_CONFIG`, the master configuration for all supported languages. Add new languages by adding entries here.

**Example**: Adding a new language

```python
LANGUAGE_CONFIG["kotlin"] = {
    "manifest": "build.gradle.kts",
    "install_cmd": "./gradlew build -x test",
    "build_cmd": "./gradlew assemble",
    "test_cmd": "./gradlew test",
    "extensions": [".kt"],
    "research_context": "Kotlin DSL and Gradle ecosystem",
}
```

### `state.py`
Defines `AgentState` TypedDict and `create_initial_state()` helper. The state object flows through all nodes in the graph.

**Extending State**: Add new fields to the TypedDict and initialize them in `create_initial_state()`:

```python
class AgentState(TypedDict):
    # ... existing fields ...
    custom_metadata: Dict[str, Any]  # New field
    
def create_initial_state(...):
    return {
        # ... existing values ...
        "custom_metadata": {},
    }
```

### `nodes.py`
Implements the five core nodes and helper functions.

**Extending Nodes**: Create a new node function with the signature `(state: AgentState) -> AgentState`:

```python
def my_custom_node(state: AgentState) -> AgentState:
    """Custom node documentation.
    
    Args:
        state: The current agent state.
        
    Returns:
        Updated state.
    """
    # Your logic here
    return state
```

Register it in `graph.py`:

```python
graph.add_node("my_custom_node", my_custom_node)
graph.add_edge("validator", "my_custom_node", condition=lambda state: some_condition(state))
```

### `graph.py`
Builds the LangGraph state machine. Defines node registration and edge conditions.

**Modifying Routing**: Update edge conditions in `build_agent_graph()`:

```python
# Example: Route to a new node based on a custom condition
graph.add_edge(
    "validator",
    "my_custom_node",
    condition=lambda state: state.get("custom_flag") == True,
)
```

### `main.py`
CLI entry point. Parses arguments and initializes the workflow.

**Adding CLI Options**:

```python
parser.add_argument(
    "--max-retries",
    type=int,
    default=3,
    help="Maximum retry attempts per file.",
)
args = parser.parse_args()
state = create_initial_state(args.project_path, args.language)
state["max_retries"] = args.max_retries  # Pass to state
```

## Testing

### Manual Testing

```bash
# Test against a local Node.js project
mkdir -p /tmp/test-node-project
cd /tmp/test-node-project
npm init -y
echo "import oldLib from 'old-lib';" > index.js
python main.py /tmp/test-node-project nodejs
```

### Debug Logging

Set log level to DEBUG:

```python
# In main.py, modify:
logging.basicConfig(level=logging.DEBUG, ...)
```

## Debugging

### Common Issues

#### Issue: "No manifest configured for language X"
**Solution**: Add the language to `LANGUAGE_CONFIG` in `config.py`.

#### Issue: "Ollama connection refused"
**Solution**: Ensure Ollama is running:
```bash
ollama serve  # In one terminal
python main.py /path/to/project nodejs  # In another
```

#### Issue: "GitHub token not configured"
**Solution**: Set the `GITHUB_TOKEN` environment variable:
```bash
export GITHUB_TOKEN=ghp_XXXXXXXXXXXX...
```

#### Issue: "No impacted files found"
**Cause**: The grep search didn't find references to outdated libraries.
**Debug**: Manually search for the library name in the project:
```bash
grep -r "library-name" /path/to/project --include="*.js" --include="*.py"
```

### Inspecting State

Add logging to any node:

```python
def debug_auditor_node(state: AgentState) -> AgentState:
    logger.debug("State snapshot: %s", json.dumps(state, indent=2))
    # ... rest of logic
```

## Contributing

### Code Style

- Follow PEP 8
- Use type hints for all function parameters and returns
- Document all functions with docstrings
- Use `logger` (not `print`) for output

### Commit Messages

```
<type>: <subject>

<body>

Fixes #<issue_number>
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`

### Pull Request Checklist

- [ ] Code follows PEP 8
- [ ] All docstrings are present
- [ ] New nodes have proper edge conditions
- [ ] Error handling is comprehensive
- [ ] Logging is at appropriate levels (INFO, WARNING, ERROR, DEBUG)

## Performance Considerations

1. **Grep Performance**: `find_impacted_files()` uses recursive grep. For large repos, consider caching results or implementing a file indexing strategy.

2. **LLM Context**: `num_ctx=4096` may be insufficient for large files. Adjust in `refactor_node`:
   ```python
   chat = ChatOllama(model="llama3", temperature=0, num_ctx=8192)
   ```

3. **Retry Loops**: `max_retries=3` prevents infinite loops. Adjust in state initialization if needed.

## Monitoring and Observability

### Key Metrics

- **Files processed**: Count of `impacted_files` processed
- **Retry rate**: `current_retry_count / max_retries` ratio
- **Success rate**: Files with `error_logs == ""` / total files
- **Manual interventions**: Count of times `manual_intervention_requested` was set

### Logging Best Practices

```python
# At key decision points
logger.info("Moving to git node after successful validation.")

# On errors
logger.error("Validator failed with: %s", error_snippet)

# For debugging
logger.debug("Impacted files: %s", state["impacted_files"])
```

## Future Enhancements

- [ ] Parallel file processing (currently sequential)
- [ ] Custom LLM prompt templates per language
- [ ] Real dependency manifest parsing (currently placeholder)
- [ ] Migration strategy suggestion (major vs. minor upgrades)
- [ ] Web UI for monitoring and manual PR approval
- [ ] Integration with CI/CD systems
- [ ] Cost tracking for cloud LLM usage
