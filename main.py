"""
main.py - AutoDev CLI Interface (Version 1)

Autonomous AI Software Development Agent - Phase 1 Planning Tool.
Interactively collects project requirements and outputs a day-by-day
structured development plan saved to memory/project_plan.json.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from agents.planner_agent import generate_project_plan, save_project_plan


def print_banner() -> None:
    """Prints a friendly ASCII banner for AutoDev."""
    banner = """
============================================================
              AutoDev - AI Software Agent (v1)              
          Autonomous Project Planning & Phasing Tool        
============================================================
"""
    print(banner)


def prompt_for_input(prompt_text: str, default: Optional[str] = None) -> str:
    """
    Prompts the user for a non-empty string input, with optional default.
    """
    while True:
        if default:
            display_prompt = f"{prompt_text} [{default}]: "
        else:
            display_prompt = f"{prompt_text}: "

        try:
            val = input(display_prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nOperation cancelled by user.")
            sys.exit(0)

        if not val and default:
            return default
        if val:
            return val

        print("  [!] Input cannot be empty. Please enter a value.")


def prompt_for_days(prompt_text: str, default: int = 5) -> int:
    """
    Prompts the user for a positive integer representing development days.
    """
    while True:
        display_prompt = f"{prompt_text} [{default}]: "
        try:
            val = input(display_prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nOperation cancelled by user.")
            sys.exit(0)

        if not val:
            return default

        try:
            days = int(val)
            if days > 0:
                return days
            print("  [!] Please enter a positive number of days (at least 1).")
        except ValueError:
            print("  [!] Invalid number. Please enter an integer.")


def display_plan_summary(plan: dict, output_path: Path) -> None:
    """Displays a clean terminal summary of the generated development plan."""
    print("\n" + "=" * 60)
    print("                 GENERATED PROJECT PLAN")
    print("=" * 60)
    print(f"Project Name   : {plan['project_name']}")
    print(f"Description    : {plan['project_description']}")
    print(f"Tech Stack     : {plan['technology_stack']}")
    print(f"Total Duration : {plan['total_days']} day(s)")
    print(f"Saved To       : {output_path.resolve()}")
    print("-" * 60)

    for phase in plan["phases"]:
        day = phase["day"]
        name = phase["phase_name"]
        print(f"\n[ Day {day} ] -> {name}")
        print("  Goals:")
        for g in phase.get("goals", []):
            print(f"    - {g}")
        print("  Tasks:")
        for t in phase.get("tasks", []):
            print(f"    * {t}")
        print("  Deliverables:")
        for d in phase.get("deliverables", []):
            print(f"    + {d}")
        print(f"  Testing Focus  : {phase.get('testing_focus', 'N/A')}")
        print(f"  Git Commit Msg : \"{phase.get('git_commit_message', '')}\"")

    print("\n" + "=" * 60)
    print(f"[OK] Project plan successfully saved to '{output_path.name}'.")
    print("=" * 60 + "\n")


def parse_arguments() -> argparse.Namespace:
    """Configures command line arguments."""
    parser = argparse.ArgumentParser(
        description="AutoDev (v1) - Autonomous AI Software Development Agent Planner"
    )
    parser.add_argument(
        "--name",
        "-n",
        type=str,
        help="Project name",
    )
    parser.add_argument(
        "--desc",
        "-d",
        type=str,
        help="Project description",
    )
    parser.add_argument(
        "--stack",
        "-s",
        type=str,
        help="Technology stack (e.g. 'Python, FastAPI, SQLite')",
    )
    parser.add_argument(
        "--days",
        "-t",
        type=int,
        help="Number of development days",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="memory/project_plan.json",
        help="Output JSON file path (default: memory/project_plan.json)",
    )
    return parser.parse_args()


def main() -> None:
    """Main execution flow."""
    args = parse_arguments()

    print_banner()

    # Retrieve arguments or interactively prompt the user
    project_name = args.name or prompt_for_input("1. Enter Project Name")
    project_desc = args.desc or prompt_for_input("2. Enter Project Description")
    tech_stack = args.stack or prompt_for_input("3. Enter Technology Stack")
    days = args.days or prompt_for_days("4. Enter Number of Development Days", default=3)

    print("\n[*] Synthesizing structured development phases...")

    try:
        plan = generate_project_plan(
            project_name=project_name,
            project_description=project_desc,
            tech_stack=tech_stack,
            days=days,
        )

        output_path = save_project_plan(plan, filepath=args.output)
        display_plan_summary(plan, output_path)

    except Exception as err:
        print(f"\n[!] Error generating plan: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
