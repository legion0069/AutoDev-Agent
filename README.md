# AutoDev (Version 1) 🚀

> **Autonomous AI Software Development Agent** — Project Phasing & Planning Engine

AutoDev is an autonomous software development system designed to translate high-level software requirements into actionable, day-by-day development phases. In future versions, specialized execution agents will implement each phase sequentially, run tests, commit code, and push changes to GitHub.

**Version 1** provides the foundational Python CLI and deterministic planning engine that collects project specifications and synthesizes a structured development plan stored in `project_plan.json`.

---

## 📁 Project Architecture & Files

```
autodev-agent/
├── main.py             # CLI application and user input orchestrator
├── planner.py          # Core planning engine and JSON export utilities
├── project_plan.json   # Structured multi-day development plan output
├── requirements.txt    # Dependency specification (Zero external deps for v1)
└── README.md           # Project documentation and architecture guide
```

### Detailed File Overview

| File | Purpose | Key Responsibilities |
| :--- | :--- | :--- |
| [`main.py`](file:///c:/Users/veruk/Desktop/autodev-agent/main.py) | **CLI Entry Point** | Interactive CLI prompt handling, argument parsing (`--name`, `--desc`, `--stack`, `--days`), terminal formatting, and orchestration. |
| [`planner.py`](file:///c:/Users/veruk/Desktop/autodev-agent/planner.py) | **Planning Engine** | Heuristic phase synthesis, task decomposition, milestone assignment, commit message generation, and JSON serialization. |
| [`project_plan.json`](file:///c:/Users/veruk/Desktop/autodev-agent/project_plan.json) | **Plan Data Store** | The structured output contract consumed by subsequent agent stages (Day 1..N phases, goals, tasks, deliverables, testing focus). |
| [`requirements.txt`](file:///c:/Users/veruk/Desktop/autodev-agent/requirements.txt) | **Dependencies** | Python environment definition (built with pure Python 3.8+ standard library). |
| [`README.md`](file:///c:/Users/veruk/Desktop/autodev-agent/README.md) | **Documentation** | System overview, setup guide, usage instructions, and roadmap. |

---

## ⚙️ Requirements

- **Python**: 3.8 or higher (no third-party dependencies required for Version 1)

---

## 🚀 Quickstart & Usage

### 1. Interactive Mode
Run the CLI without arguments to enter the guided interactive prompt:

```bash
python main.py
```

You will be prompted for:
1. **Project Name** (e.g., `TaskFlow API`)
2. **Project Description** (e.g., `A collaborative task management backend`)
3. **Technology Stack** (e.g., `Python, FastAPI, SQLite, Pytest`)
4. **Number of Development Days** (e.g., `3`)

### 2. Command-Line Arguments Mode
You can also generate plans directly using CLI flags:

```bash
python main.py --name "TaskFlow API" \
               --desc "A collaborative task management backend" \
               --stack "Python, FastAPI, SQLite, Pytest" \
               --days 3 \
               --output "project_plan.json"
```

---

## 📋 Structured Plan Format (`project_plan.json`)

The planner generates a schema ready for autonomous agent execution:

```json
{
  "project_name": "TaskFlow API",
  "project_description": "A collaborative task management backend",
  "technology_stack": "Python, FastAPI, SQLite, Pytest",
  "total_days": 3,
  "created_at": "2026-10-04T23:15:30",
  "phases": [
    {
      "day": 1,
      "phase_name": "Project Setup & Architectural Skeleton",
      "goals": [
        "Initialize repository structure for TaskFlow API",
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

---

## 🛣️ Roadmap

- **Version 1 (Current)**: CLI input collector & structured day-by-day JSON planner.
- **Version 2**: LLM-augmented planning agent (OpenAI / Gemini / Anthropic API integration) for domain-specific deep code task generation.
- **Version 3**: Autonomous Execution Agent (reads `project_plan.json`, writes code per day, executes unit tests, automatically creates Git commits).
- **Version 4**: GitHub integration & CI/CD workflow automation (PR creation, automated reviews, GitHub Actions dispatch).
