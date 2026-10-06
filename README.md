# AutoDev (Version 1) 🚀

> **Autonomous AI Software Development Agent** — Modular Architecture

AutoDev is an autonomous software development system designed to translate high-level software requirements into actionable, day-by-day development phases. In future versions, specialized execution agents will implement each phase sequentially, run tests, commit code, and push changes to GitHub.

---

## 📁 Project Architecture & Directory Structure

```
autodev-agent/
├── agents/
│   ├── __init__.py
│   ├── planner_agent.py      # Core planning engine and multi-day phase synthesizer
│   ├── developer_agent.py    # Code implementation agent (Placeholder)
│   ├── tester_agent.py       # Automated testing and validation agent (Placeholder)
│   └── git_agent.py          # Version control and commit/push agent (Placeholder)
├── core/
│   ├── __init__.py
│   ├── config.py             # System configuration and environment settings (Placeholder)
│   └── llm.py                # Foundation model / LLM client interface (Placeholder)
├── memory/
│   ├── project_plan.json     # Structured multi-day development plan output
│   └── state.json            # Agent lifecycle and execution state
├── projects/                 # Target workspace for generated projects
├── logs/                     # Execution run logs and operational traces
├── main.py                   # CLI application and user input orchestrator
├── requirements.txt          # Dependency specification (Zero external deps for v1)
└── README.md                 # Project documentation and architecture guide
```

### Detailed Component Overview

| Component | Path | Purpose |
| :--- | :--- | :--- |
| **CLI Orchestrator** | [`main.py`](file:///c:/Users/veruk/Desktop/autodev-agent/main.py) | Guided CLI prompt handling, argument parsing (`--name`, `--desc`, `--stack`, `--days`, `--output`), and orchestration. |
| **Planner Agent** | [`agents/planner_agent.py`](file:///c:/Users/veruk/Desktop/autodev-agent/agents/planner_agent.py) | Multi-phase plan synthesis, task decomposition, milestone assignment, commit message generation, and JSON serialization. |
| **Developer Agent** | [`agents/developer_agent.py`](file:///c:/Users/veruk/Desktop/autodev-agent/agents/developer_agent.py) | Code generation and feature implementation worker. |
| **Tester Agent** | [`agents/tester_agent.py`](file:///c:/Users/veruk/Desktop/autodev-agent/agents/tester_agent.py) | Test runner, code verification, and regression tester. |
| **Git Agent** | [`agents/git_agent.py`](file:///c:/Users/veruk/Desktop/autodev-agent/agents/git_agent.py) | Automated git operations (branching, commits, remote sync). |
| **Core Config & LLM**| [`core/`](file:///c:/Users/veruk/Desktop/autodev-agent/core/) | Central settings and AI model provider interfaces. |
| **Memory Store** | [`memory/`](file:///c:/Users/veruk/Desktop/autodev-agent/memory/) | Persistent state and generated `project_plan.json`. |

---

## ⚙️ Requirements

- **Python**: 3.8 or higher (zero external dependencies required for Version 1)

---

## 🚀 Quickstart & Usage

### 1. Interactive Mode
Run the CLI without arguments to enter the guided interactive prompt:

```bash
python main.py
```

### 2. Command-Line Arguments Mode
You can also generate plans directly using CLI flags:

```bash
python main.py --name "TaskFlow API" \
               --desc "A collaborative task management backend" \
               --stack "Python, FastAPI, SQLite, Pytest" \
               --days 3 \
               --output "memory/project_plan.json"
```

---

## 📋 Structured Plan Format (`memory/project_plan.json`)

The planner generates a structured schema ready for autonomous agent execution:

```json
{
  "project_name": "AutoDev Agent",
  "project_description": "Autonomous AI Software Development Agent",
  "technology_stack": "Python, OpenAI API, Git, Pytest",
  "total_days": 3,
  "created_at": "2026-10-04T23:15:30",
  "phases": [
    {
      "day": 1,
      "phase_name": "Project Setup & Architectural Skeleton",
      "goals": [
        "Initialize repository structure for AutoDev Agent",
        "Configure development environment and tooling",
        "Establish base architectural patterns"
      ],
      "tasks": [
        "Create directory structure and initialize dependency management",
        "Implement configuration management and environment variables handling",
        "Create base application entry point with health check"
      ],
      "deliverables": [
        "Project repository scaffold",
        "Dependency configuration file",
        "Base entry point"
      ],
      "testing_focus": "Environment sanity checks and initial boot-up test",
      "git_commit_message": "chore(setup): scaffold project architecture and dependencies"
    }
  ]
}
```
