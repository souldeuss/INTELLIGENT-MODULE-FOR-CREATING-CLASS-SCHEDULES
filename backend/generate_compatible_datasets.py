"""Generate dimension-compatible datasets from a reference case.

This keeps the same structural cardinalities (groups/subjects/teachers/classrooms)
across all generated cases, which helps produce model artifacts compatible with
that target profile.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

DEFAULT_SCORING: Dict[str, float] = {
    "reward_weight": 1.0,
    "completion_weight": 100.0,
    "hard_violation_penalty": 25.0,
    "soft_violation_penalty": 5.0,
}

DEFAULT_PROMOTION_POLICY: Dict[str, float] = {
    "min_completion_rate": 0.9,
    "max_hard_violations": 0,
    "max_soft_violations": 25,
    "min_score_margin": 0.0,
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _split_train_test(paths: List[str], train_ratio: float, rng: random.Random) -> Tuple[List[str], List[str]]:
    shuffled = list(paths)
    rng.shuffle(shuffled)
    train_size = int(round(len(shuffled) * train_ratio))
    train_size = max(1, min(len(shuffled) - 1, train_size))
    return shuffled[:train_size], shuffled[train_size:]


def _renumber_tokens(value: Any, old_token: str, new_token: str) -> Any:
    if isinstance(value, str):
        return value.replace(old_token, new_token)
    if isinstance(value, list):
        return [_renumber_tokens(item, old_token, new_token) for item in value]
    if isinstance(value, dict):
        return {k: _renumber_tokens(v, old_token, new_token) for k, v in value.items()}
    return value


def _bounded_int(base_value: int, delta: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(max_value, base_value + delta))


def _perturb_case(
    payload: Dict[str, Any],
    rng: random.Random,
    *,
    perturb_max_daily_lessons: bool = False,
) -> Dict[str, Any]:
    case = copy.deepcopy(payload)

    for group in case.get("groups", []):
        count = int(group.get("students_count", 25))
        group["students_count"] = _bounded_int(count, rng.randint(-2, 2), 10, 80)

    for teacher in case.get("teachers", []):
        max_hours = int(teacher.get("max_hours_per_week", 24))
        teacher["max_hours_per_week"] = _bounded_int(max_hours, rng.randint(-2, 2), 10, 40)

    for room in case.get("classrooms", []):
        capacity = int(room.get("capacity", 30))
        room["capacity"] = _bounded_int(capacity, rng.randint(-3, 3), 10, 200)

    for lesson in case.get("lessons_pool", []):
        lesson_count = int(lesson.get("count", 2))
        lesson["count"] = _bounded_int(lesson_count, rng.randint(-1, 1), 1, 6)

    constraints = case.get("constraints")
    if perturb_max_daily_lessons and isinstance(constraints, dict) and "max_daily_lessons" in constraints:
        mdl = int(constraints.get("max_daily_lessons", 6))
        constraints["max_daily_lessons"] = _bounded_int(mdl, rng.randint(-1, 1), 4, 9)

    return case


def _extract_reference_token(reference_file: Path, reference_payload: Dict[str, Any]) -> str:
    stem = reference_file.stem
    match = re.search(r"(\d+)$", stem)
    if match:
        return match.group(1).zfill(3)

    # Fallback from first group id suffix if file name does not include numeric token.
    groups = reference_payload.get("groups")
    if isinstance(groups, list) and groups:
        first_group_id = str(groups[0].get("id", ""))
        gm = re.search(r"(\d+)$", first_group_id)
        if gm:
            return gm.group(1).zfill(3)

    return "000"


def generate_compatible_dataset(
    *,
    workspace_root: Path,
    reference_case_path: Path,
    dataset_name: str,
    count: int,
    seed: int,
    train_ratio: float,
    perturb_max_daily_lessons: bool = False,
) -> Dict[str, Any]:
    if count < 2:
        raise ValueError("count must be >= 2")
    if not (0.0 < train_ratio < 1.0):
        raise ValueError("train_ratio must be in (0, 1)")

    with open(reference_case_path, "r", encoding="utf-8") as file:
        reference_payload = json.load(file)

    old_token = _extract_reference_token(reference_case_path, reference_payload)

    dataset_root = workspace_root / "data" / dataset_name
    cases_dir = dataset_root / "cases"
    manifest_path = dataset_root / "dataset_manifest.json"
    cases_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    relative_case_paths: List[str] = []

    for index in range(1, count + 1):
        case_rng = random.Random((seed * 1_000_000) + index)
        token = f"{index:03d}"

        case_payload = _renumber_tokens(reference_payload, old_token, token)
        case_payload = _perturb_case(
            case_payload,
            case_rng,
            perturb_max_daily_lessons=perturb_max_daily_lessons,
        )

        case_path = cases_dir / f"case_{token}.json"
        with open(case_path, "w", encoding="utf-8") as file:
            json.dump(case_payload, file, indent=2, ensure_ascii=False)

        relative_case_paths.append(case_path.relative_to(workspace_root).as_posix())

    train_paths, test_paths = _split_train_test(relative_case_paths, train_ratio, rng)

    train_entries = [
        {"path": rel_path, "sha256": _sha256_file(workspace_root / rel_path)}
        for rel_path in train_paths
    ]
    test_entries = [
        {"path": rel_path, "sha256": _sha256_file(workspace_root / rel_path)}
        for rel_path in test_paths
    ]

    manifest = {
        "manifest_version": "v2",
        "dataset_policy": "train_test_holdout",
        "seed": seed,
        "train": train_entries,
        "test": test_entries,
        "scoring": dict(DEFAULT_SCORING),
        "promotion_policy": dict(DEFAULT_PROMOTION_POLICY),
        "metadata": {
            "dataset_name": dataset_name,
            "total_cases": count,
            "train_ratio": train_ratio,
            "train_cases": len(train_entries),
            "test_cases": len(test_entries),
            "compatible_template": str(reference_case_path.relative_to(workspace_root)).replace("\\", "/"),
            "reference_token": old_token,
            "reference_sha256": _sha256_file(reference_case_path),
        },
    }

    with open(manifest_path, "w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2, ensure_ascii=False)

    return {
        "dataset_root": str(dataset_root),
        "cases_dir": str(cases_dir),
        "manifest_path": str(manifest_path),
        "train_count": len(train_entries),
        "test_count": len(test_entries),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate dimension-compatible datasets from a reference case")
    parser.add_argument(
        "--workspace-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Workspace root directory",
    )
    parser.add_argument(
        "--reference-case",
        required=True,
        help="Reference case path (relative to workspace root or absolute)",
    )
    parser.add_argument("--dataset-name", required=True, help="Output dataset name under data/")
    parser.add_argument("--count", type=int, default=100, help="Number of cases")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--train-ratio", type=float, default=0.8, help="Train split ratio")
    parser.add_argument(
        "--perturb-max-daily-lessons",
        action="store_true",
        help="Allow varying constraints.max_daily_lessons across generated cases",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workspace_root = Path(args.workspace_root).resolve()
    reference_case = Path(args.reference_case)
    if not reference_case.is_absolute():
        reference_case = workspace_root / reference_case
    reference_case = reference_case.resolve()

    result = generate_compatible_dataset(
        workspace_root=workspace_root,
        reference_case_path=reference_case,
        dataset_name=args.dataset_name,
        count=args.count,
        seed=args.seed,
        train_ratio=args.train_ratio,
        perturb_max_daily_lessons=args.perturb_max_daily_lessons,
    )

    print("Compatible dataset generation completed")
    print(f"Dataset root: {result['dataset_root']}")
    print(f"Manifest: {result['manifest_path']}")
    print(f"Cases: train={result['train_count']}, test={result['test_count']}")


if __name__ == "__main__":
    main()
