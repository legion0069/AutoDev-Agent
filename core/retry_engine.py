"""
retry_engine.py - Self-Healing Retry Engine for AutoDev

Coordinates iterative code regeneration, feedback injection, and automated quality
convergence when generated code contains defects or fails automated test suites.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Ensure project root is available on sys.path for direct execution
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.coder_agent import CoderAgent, GeneratedResult
from agents.file_writer_agent import FileWriterAgent, WriteResult
from agents.reviewer_agent import ReviewerAgent, ReviewResult
from agents.task_planner_agent import Task
from agents.tester_agent import TesterAgent, TestResult

# Module logger
logger = logging.getLogger("AutoDev.RetryEngine")


@dataclass
class AttemptRecord:
    """
    Telemetry record of an individual iteration in the self-healing retry loop.
    """
    attempt_number: int
    quality_score: int
    tests_passed: int
    tests_failed: int
    should_regenerate: bool
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        """Converts attempt record to dictionary representation."""
        return asdict(self)


@dataclass
class RetryResult:
    """
    Aggregated outcome of the multi-attempt self-healing retry cycle.
    """
    __test__ = False

    success: bool
    attempts: int
    max_attempts: int
    final_generated_result: Optional[GeneratedResult] = None
    final_test_result: Optional[TestResult] = None
    final_review_result: Optional[ReviewResult] = None
    execution_history: List[AttemptRecord] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Converts retry result to a serializable dictionary."""
        return {
            "success": self.success,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "final_generated_result": self.final_generated_result.to_dict() if self.final_generated_result else None,
            "final_test_result": self.final_test_result.to_dict() if self.final_test_result else None,
            "final_review_result": self.final_review_result.to_dict() if self.final_review_result else None,
            "execution_history": [r.to_dict() for r in self.execution_history],
            "message": self.message,
        }


class RetryEngine:
    """
    Coordinates the self-healing regeneration loop across CoderAgent, FileWriterAgent,
    TesterAgent, and ReviewerAgent until stopping criteria are satisfied or max retries reached.
    """
    __test__ = False

    def __init__(
        self,
        coder_agent: Optional[CoderAgent] = None,
        file_writer: Optional[FileWriterAgent] = None,
        tester_agent: Optional[TesterAgent] = None,
        reviewer_agent: Optional[ReviewerAgent] = None,
        default_max_attempts: int = 3,
        default_minimum_quality_score: int = 85,
        project_root: Optional[Union[str, Path]] = None,
    ) -> None:
        """
        Initializes the RetryEngine with injectable agent dependencies and thresholds.

        Args:
            coder_agent: CoderAgent instance for code synthesis.
            file_writer: FileWriterAgent instance for disk materialization.
            tester_agent: TesterAgent instance for test execution.
            reviewer_agent: ReviewerAgent instance for AI code review.
            default_max_attempts: Maximum iteration attempts (default: 3).
            default_minimum_quality_score: Passing score threshold (default: 85).
            project_root: Workspace root directory.
        """
        self.coder_agent = coder_agent or CoderAgent()
        self.file_writer = file_writer or FileWriterAgent(project_root=project_root or Path.cwd())
        self.tester_agent = tester_agent or TesterAgent()
        self.reviewer_agent = reviewer_agent or ReviewerAgent()
        self.default_max_attempts = default_max_attempts
        self.default_minimum_quality_score = default_minimum_quality_score
        self.project_root = Path(project_root).resolve() if project_root else Path.cwd()

    def _build_retry_feedback(
        self,
        attempt: int,
        previous_review: Optional[ReviewResult],
        previous_test: Optional[TestResult],
    ) -> Dict[str, Any]:
        """
        Structures actionable feedback from prior attempt review and test failures.
        """
        feedback: Dict[str, Any] = {"attempt": attempt}

        if previous_review is not None:
            feedback["previous_review"] = {
                "score": previous_review.overall_quality_score,
                "summary": previous_review.summary,
                "issues": [i.to_dict() for i in previous_review.issues],
                "recommendations": previous_review.recommendations,
            }

        if previous_test is not None:
            feedback["previous_tests"] = {
                "passed": previous_test.passed,
                "failed": previous_test.failed,
                "stdout": previous_test.stdout,
                "stderr": previous_test.stderr,
                "message": previous_test.message,
            }

        return feedback

    def execute(
        self,
        context: Dict[str, Any],
        task: Task,
        max_attempts: Optional[int] = None,
        minimum_quality_score: Optional[int] = None,
    ) -> RetryResult:
        """
        Executes the self-healing retry loop for an atomic task.

        Args:
            context: Project context dictionary from ContextBuilder.
            task: Target atomic Task to implement.
            max_attempts: Optional override for max attempts.
            minimum_quality_score: Optional override for passing score threshold.

        Returns:
            RetryResult containing final agent artifacts and execution history.
        """
        limit = max_attempts if max_attempts is not None else self.default_max_attempts
        min_score = minimum_quality_score if minimum_quality_score is not None else self.default_minimum_quality_score

        logger.info(
            "Starting Self-Healing Retry Loop for Task [%s] (Max Attempts: %d, Min Score: %d/100)...",
            task.id,
            limit,
            min_score,
        )

        execution_history: List[AttemptRecord] = []
        last_generated: Optional[GeneratedResult] = None
        last_test: Optional[TestResult] = None
        last_review: Optional[ReviewResult] = None
        success = False

        for attempt_idx in range(1, limit + 1):
            logger.info("--- [Attempt %d / %d] Executing Task [%s] ---", attempt_idx, limit, task.id)

            # Build enriched context with previous attempt feedback
            current_context = dict(context)
            if attempt_idx > 1 and (last_review or last_test):
                current_context["retry_feedback"] = self._build_retry_feedback(
                    attempt=attempt_idx,
                    previous_review=last_review,
                    previous_test=last_test,
                )
                logger.info(
                    "Injected retry feedback from Attempt %d into prompt context.",
                    attempt_idx - 1,
                )

            # 1. CoderAgent: Synthesize code
            logger.info("Step 1: Running CoderAgent...")
            last_generated = self.coder_agent.execute(context=current_context, task=task)

            # 2. FileWriterAgent: Write files
            logger.info("Step 2: Writing files with FileWriterAgent...")
            write_res = self.file_writer.write(last_generated, target_dir=self.project_root)
            if not write_res.success:
                logger.error("FileWriterAgent failure during retry attempt %d: %s", attempt_idx, write_res.failed_files)
                raise RuntimeError(
                    f"FileWriterAgent failed on attempt {attempt_idx}: {write_res.failed_files}"
                )

            # 3. TesterAgent: Run test suite (non-blocking for review)
            logger.info("Step 3: Running test suite with TesterAgent...")
            last_test = self.tester_agent.run_tests(project_root=self.project_root)

            # 4. ReviewerAgent: Evaluate code and test telemetry
            logger.info("Step 4: Performing code review with ReviewerAgent...")
            last_review = self.reviewer_agent.review(
                context=current_context,
                generated_result=last_generated,
                test_result=last_test,
            )

            # 5. Record attempt telemetry
            record = AttemptRecord(
                attempt_number=attempt_idx,
                quality_score=last_review.overall_quality_score,
                tests_passed=last_test.passed if last_test else 0,
                tests_failed=last_test.failed if last_test else 0,
                should_regenerate=last_review.should_regenerate,
                summary=last_review.summary,
            )
            execution_history.append(record)

            logger.info(
                "Attempt %d Results: Score: %d/100 (Threshold: %d), Tests Passed: %d, Tests Failed: %d, Regenerate: %s",
                attempt_idx,
                last_review.overall_quality_score,
                min_score,
                record.tests_passed,
                record.tests_failed,
                last_review.should_regenerate,
            )

            # 6. Evaluate stopping criteria
            tests_ok = (last_test is None or last_test.success or last_test.total_tests == 0)
            score_ok = (last_review.overall_quality_score >= min_score)
            no_regen = not last_review.should_regenerate

            if tests_ok and score_ok and no_regen:
                success = True
                msg = (
                    f"Task [{task.id}] self-healed successfully on attempt {attempt_idx}/{limit} "
                    f"with quality score {last_review.overall_quality_score}/100."
                )
                logger.info("Success stopping condition satisfied: %s", msg)
                break
            else:
                reasons: List[str] = []
                if not tests_ok:
                    reasons.append(f"test failures ({last_test.failed} failed)" if last_test else "tests failed")
                if not score_ok:
                    reasons.append(f"low quality score ({last_review.overall_quality_score} < {min_score})")
                if not no_regen:
                    reasons.append("reviewer requested regeneration")

                logger.warning(
                    "Attempt %d did not meet criteria due to: %s.",
                    attempt_idx,
                    ", ".join(reasons),
                )

        if not success:
            msg = (
                f"Task [{task.id}] reached maximum retry limit ({limit} attempts) "
                f"without satisfying all quality criteria (Final score: {last_review.overall_quality_score if last_review else 0}/100)."
            )
            logger.warning("Retry loop finished without full convergence: %s", msg)

        return RetryResult(
            success=success,
            attempts=len(execution_history),
            max_attempts=limit,
            final_generated_result=last_generated,
            final_test_result=last_test,
            final_review_result=last_review,
            execution_history=execution_history,
            message=msg,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-5s] %(message)s")

    from core.context_builder import build_context

    ctx = build_context()
    sample_task = Task(
        id="DAY1-TASK01",
        title="Implement self-healing core logic",
        description="Write resilient self-healing engine components.",
    )

    engine = RetryEngine()
    result = engine.execute(context=ctx, task=sample_task)

    print("\n" + "=" * 60)
    print("               RETRY ENGINE EXECUTION RESULT")
    print("=" * 60)
    print(f"Success          : {result.success}")
    print(f"Attempts Made    : {result.attempts}/{result.max_attempts}")
    print(f"Final Score      : {result.final_review_result.overall_quality_score if result.final_review_result else 0}/100")
    print(f"History Entries  : {len(result.execution_history)}")
    for record in result.execution_history:
        print(f"  - Attempt {record.attempt_number}: Score {record.quality_score}/100, Passed: {record.tests_passed}, Failed: {record.tests_failed}, Regenerate: {record.should_regenerate}")
    print(f"Summary Message  : {result.message}")
    print("=" * 60 + "\n")
