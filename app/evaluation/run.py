"""CLI Benchmark Evaluation Execution Script."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import get_settings
from app.persistence.models.base import Base
from app.persistence.seed import seed_database_async
from .dataset_generator import write_datasets
from .metrics import MetricsCalculator
from .models import EvaluationMetrics, PerCaseResult
from .runner import EvaluationRunner


async def run_evaluation(
    dataset_path: Optional[str] = None,
    mode: str = "all",
    output_dir: str = "artifacts/evaluation",
) -> Dict[str, Any]:
    """Execute evaluation suites and write all machine-readable reports."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Ensure datasets exist on disk
    if not Path("data/evaluation/calibration/calibration.jsonl").exists():
        write_datasets()

    settings = get_settings()

    # Use SQLite eval database for standalone reproducibility
    db_file = Path("data/evaluation/eval.db")
    db_file.parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file.as_posix()}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    runner = EvaluationRunner()
    summary: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runs": {},
        "ablations": {},
    }

    calib_results: List[PerCaseResult] = []
    holdout_results: List[PerCaseResult] = []
    chal_results: List[PerCaseResult] = []

    async with session_factory() as session:
        await seed_database_async(session)

        # 1. Run Calibration Set
        if mode in ("calibration", "all"):
            print("Running Calibration Set Evaluation (110 cases)...")
            calib_metrics, calib_results = await runner.run_dataset(
                "data/evaluation/calibration/calibration.jsonl", session, dataset_name="calibration"
            )
            with open(out_path / "calibration_results.json", "w", encoding="utf-8") as f:
                f.write(calib_metrics.model_dump_json(indent=2))
            summary["runs"]["calibration"] = calib_metrics.model_dump()
            print(f" -> Calibration Accuracy: {calib_metrics.overall_accuracy*100:.1f}% ({calib_metrics.passed_cases}/{calib_metrics.total_cases})")

        # 2. Run Holdout Set
        if mode in ("holdout", "all"):
            print("Running Holdout Set Evaluation (50 cases)...")
            holdout_metrics, holdout_results = await runner.run_dataset(
                "data/evaluation/holdout/holdout.jsonl", session, dataset_name="holdout"
            )
            with open(out_path / "holdout_results.json", "w", encoding="utf-8") as f:
                f.write(holdout_metrics.model_dump_json(indent=2))
            summary["runs"]["holdout"] = holdout_metrics.model_dump()
            print(f" -> Holdout Accuracy: {holdout_metrics.overall_accuracy*100:.1f}% ({holdout_metrics.passed_cases}/{holdout_metrics.total_cases})")

        # 3. Run Challenge Set
        if mode in ("challenge", "all"):
            print("Running Challenge Set Evaluation (20 cases)...")
            chal_metrics, chal_results = await runner.run_dataset(
                "data/evaluation/challenge/challenge.jsonl", session, dataset_name="challenge"
            )
            with open(out_path / "challenge_results.json", "w", encoding="utf-8") as f:
                f.write(chal_metrics.model_dump_json(indent=2))
            summary["runs"]["challenge"] = chal_metrics.model_dump()
            print(f" -> Challenge Accuracy: {chal_metrics.overall_accuracy*100:.1f}% ({chal_metrics.passed_cases}/{chal_metrics.total_cases})")

        # 4. Run Task 8 Ablations
        if mode in ("ablations", "all"):
            print("Running Architecture Ablations on Holdout Set...")
            ablations = await runner.run_ablations("data/evaluation/holdout/holdout.jsonl", session)
            summary["ablations"] = [a.model_dump() for a in ablations]
            print(f" -> Completed {len(ablations)} architectural ablations.")

        # 5. Export Per-Case Results and Confusion Matrices
        if mode == "all":
            all_results: List[PerCaseResult] = calib_results + holdout_results + chal_results
            with open(out_path / "per_case_results.jsonl", "w", encoding="utf-8") as f:
                for r in all_results:
                    f.write(r.model_dump_json() + "\n")

            failures = [r.model_dump() for r in all_results if not r.passed]
            with open(out_path / "failure_cases.json", "w", encoding="utf-8") as f:
                json.dump(failures, f, indent=2)

            # Confusion Matrix calculation
            confusion_matrix: Dict[str, Dict[str, int]] = {}
            for r in all_results:
                confusion_matrix.setdefault(r.expected_final_action, {})
                confusion_matrix[r.expected_final_action][r.actual_final_action] = (
                    confusion_matrix[r.expected_final_action].get(r.actual_final_action, 0) + 1
                )
            with open(out_path / "confusion_matrices.json", "w", encoding="utf-8") as f:
                json.dump(confusion_matrix, f, indent=2)

        # Write top-level summary.json
        with open(out_path / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    await engine.dispose()
    print(f"\n=======================================================")
    print(f"EVALUATION RUN COMPLETE. Artifacts saved to: {out_path.resolve()}")
    print(f"=======================================================")
    return summary


def main():
    parser = argparse.ArgumentParser(description="ControlPlane Benchmark Evaluation Runner")
    parser.add_argument("--dataset", type=str, default=None, help="Path to benchmark JSONL dataset")
    parser.add_argument("--mode", type=str, default="all", choices=["calibration", "holdout", "challenge", "ablations", "all"])
    parser.add_argument("--output-dir", type=str, default="artifacts/evaluation", help="Directory for output reports")
    args = parser.parse_args()

    asyncio.run(run_evaluation(dataset_path=args.dataset, mode=args.mode, output_dir=args.output_dir))


if __name__ == "__main__":
    main()
