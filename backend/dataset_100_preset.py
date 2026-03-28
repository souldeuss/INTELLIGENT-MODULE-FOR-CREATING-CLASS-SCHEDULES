"""One-call preset runner: generate dataset-100 and launch train/eval pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from dataset_generator import generate_dataset_package


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run dataset-100 training preset")
    parser.add_argument("--dataset-name", default="dataset_100")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--skip-generate", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workspace_root = Path(__file__).resolve().parents[1]

    if not args.skip_generate:
        generate_dataset_package(
            workspace_root=workspace_root,
            dataset_name=args.dataset_name,
            count=100,
            seed=args.seed,
            train_ratio=args.train_ratio,
        )

    manifest_path = workspace_root / "data" / args.dataset_name / "dataset_manifest.json"
    manifest_rel = manifest_path.relative_to(workspace_root).as_posix()

    command = [
        sys.executable,
        "backend/train_eval_pipeline.py",
        "--manifest",
        manifest_rel,
        "--iterations",
        str(args.iterations),
        "--iterations-mode",
        "total",
        "--device",
        args.device,
    ]
    if args.promote:
        command.append("--promote")

    print("Running preset command:")
    print(" ".join(command))

    completed = subprocess.run(command, cwd=str(workspace_root), check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
