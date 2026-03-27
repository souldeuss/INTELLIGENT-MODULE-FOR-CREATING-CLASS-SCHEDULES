"""Generate varied timetable dataset cases and manifest for DRL training."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

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

SUBJECT_TEMPLATES: Sequence[Dict[str, Any]] = (
    {"name": "Mathematics", "difficulty": 3, "requires_specialized": False, "classroom_type": "general"},
    {"name": "Physics", "difficulty": 4, "requires_specialized": True, "classroom_type": "physics_lab"},
    {"name": "Informatics", "difficulty": 3, "requires_specialized": True, "classroom_type": "computer_lab"},
    {"name": "Chemistry", "difficulty": 4, "requires_specialized": True, "classroom_type": "chemistry_lab"},
    {"name": "Biology", "difficulty": 3, "requires_specialized": True, "classroom_type": "biology_lab"},
    {"name": "History", "difficulty": 2, "requires_specialized": False, "classroom_type": "general"},
    {"name": "Geography", "difficulty": 2, "requires_specialized": False, "classroom_type": "general"},
    {"name": "Literature", "difficulty": 2, "requires_specialized": False, "classroom_type": "general"},
    {"name": "English", "difficulty": 2, "requires_specialized": False, "classroom_type": "general"},
    {"name": "Economics", "difficulty": 3, "requires_specialized": False, "classroom_type": "general"},
    {"name": "Art", "difficulty": 1, "requires_specialized": False, "classroom_type": "general"},
    {"name": "PhysicalEducation", "difficulty": 1, "requires_specialized": True, "classroom_type": "gym"},
)

CLASSROOM_TYPES: Sequence[str] = (
    "general",
    "general",
    "general",
    "computer_lab",
    "physics_lab",
    "chemistry_lab",
    "biology_lab",
    "gym",
)


@dataclass(frozen=True)
class DatasetLayout:
    root: Path
    cases_dir: Path
    manifest_path: Path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _choice_without_replacement(rng: random.Random, values: Sequence[Dict[str, Any]], count: int) -> List[Dict[str, Any]]:
    return [dict(item) for item in rng.sample(list(values), count)]


def _build_groups(rng: random.Random, case_index: int) -> List[Dict[str, Any]]:
    group_count = rng.randint(2, 6)
    year = rng.randint(1, 4)
    groups: List[Dict[str, Any]] = []
    for idx in range(group_count):
        code = f"Y{year}-G{idx + 1:02d}-C{case_index:03d}"
        groups.append(
            {
                "id": code,
                "students_count": rng.randint(16, 34),
                "year": year,
            }
        )
    return groups


def _build_subjects(rng: random.Random, case_index: int) -> List[Dict[str, Any]]:
    subject_count = rng.randint(5, 10)
    selected = _choice_without_replacement(rng, SUBJECT_TEMPLATES, subject_count)

    subjects: List[Dict[str, Any]] = []
    for idx, template in enumerate(selected, start=1):
        subject = dict(template)
        subject_id = f"SUBJ_{case_index:03d}_{idx:02d}"
        subject["id"] = subject_id
        subject["name"] = f"{template['name']}_{case_index:03d}_{idx:02d}"
        subjects.append(subject)
    return subjects


def _build_teachers(rng: random.Random, subjects: List[Dict[str, Any]], case_index: int) -> List[Dict[str, Any]]:
    teacher_count = max(4, min(12, len(subjects) + rng.randint(1, 3)))
    teachers: List[Dict[str, Any]] = []

    subject_ids = [subject["id"] for subject in subjects]
    for idx in range(teacher_count):
        specialties = rng.sample(subject_ids, k=rng.randint(1, min(4, len(subject_ids))))
        teachers.append(
            {
                "id": f"T{case_index:03d}_{idx + 1:02d}",
                "name": f"Teacher_{case_index:03d}_{idx + 1:02d}",
                "subjects": specialties,
                "max_hours_per_week": rng.randint(18, 30),
            }
        )

    # Ensure every subject has at least one teacher.
    for subject_id in subject_ids:
        if any(subject_id in teacher.get("subjects", []) for teacher in teachers):
            continue
        teachers[rng.randrange(len(teachers))]["subjects"].append(subject_id)

    return teachers


def _build_classrooms(rng: random.Random, groups: List[Dict[str, Any]], case_index: int) -> List[Dict[str, Any]]:
    room_count = max(5, min(14, len(groups) + rng.randint(2, 7)))
    min_capacity = max(18, min(group["students_count"] for group in groups) - 2)
    max_capacity = max(28, max(group["students_count"] for group in groups) + 8)

    classrooms: List[Dict[str, Any]] = []
    for idx in range(room_count):
        room_type = rng.choice(CLASSROOM_TYPES)
        classrooms.append(
            {
                "id": f"R{case_index:03d}_{idx + 1:02d}",
                "capacity": rng.randint(min_capacity, max_capacity),
                "type": room_type,
            }
        )

    return classrooms


def _build_lessons_pool(
    rng: random.Random,
    groups: List[Dict[str, Any]],
    subjects: List[Dict[str, Any]],
    teachers: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    teachers_by_subject: Dict[str, List[Dict[str, Any]]] = {}
    for teacher in teachers:
        for subject_id in teacher.get("subjects", []):
            teachers_by_subject.setdefault(subject_id, []).append(teacher)

    lessons_pool: List[Dict[str, Any]] = []
    for group in groups:
        min_subjects = max(3, min(6, len(subjects)))
        max_subjects = min(len(subjects), max(min_subjects, 8))
        selected_subjects = rng.sample(subjects, k=rng.randint(min_subjects, max_subjects))

        for subject in selected_subjects:
            subject_id = subject["id"]
            teacher_candidates = teachers_by_subject.get(subject_id)
            if not teacher_candidates:
                continue
            teacher = rng.choice(teacher_candidates)
            lessons_pool.append(
                {
                    "subject": subject_id,
                    "teacher": teacher["id"],
                    "group": group["id"],
                    "count": rng.randint(1, 4),
                }
            )

    if not lessons_pool:
        group = groups[0]
        subject = subjects[0]
        teacher = next(
            t for t in teachers if subject["id"] in t.get("subjects", [])
        )
        lessons_pool.append(
            {
                "subject": subject["id"],
                "teacher": teacher["id"],
                "group": group["id"],
                "count": 2,
            }
        )

    return lessons_pool


def build_case_payload(case_index: int, rng: random.Random) -> Dict[str, Any]:
    groups = _build_groups(rng, case_index)
    subjects = _build_subjects(rng, case_index)
    teachers = _build_teachers(rng, subjects, case_index)
    classrooms = _build_classrooms(rng, groups, case_index)
    lessons_pool = _build_lessons_pool(rng, groups, subjects, teachers)

    return {
        "groups": groups,
        "subjects": subjects,
        "teachers": teachers,
        "classrooms": classrooms,
        "lessons_pool": lessons_pool,
        "constraints": {
            "max_daily_lessons": rng.randint(5, 8),
        },
    }


def build_dataset_layout(workspace_root: Path, dataset_name: str) -> DatasetLayout:
    root = workspace_root / "data" / dataset_name
    cases_dir = root / "cases"
    manifest_path = root / "dataset_manifest.json"
    return DatasetLayout(root=root, cases_dir=cases_dir, manifest_path=manifest_path)


def _split_train_test(paths: List[str], train_ratio: float, rng: random.Random) -> tuple[List[str], List[str]]:
    shuffled = list(paths)
    rng.shuffle(shuffled)

    train_size = int(round(len(shuffled) * train_ratio))
    train_size = max(1, min(len(shuffled) - 1, train_size))

    train = shuffled[:train_size]
    test = shuffled[train_size:]
    return train, test


def generate_dataset_package(
    *,
    workspace_root: Path,
    dataset_name: str = "dataset_100",
    count: int = 100,
    seed: int = 42,
    train_ratio: float = 0.8,
) -> Dict[str, Any]:
    if count < 2:
        raise ValueError("count must be >= 2")
    if train_ratio <= 0.0 or train_ratio >= 1.0:
        raise ValueError("train_ratio must be in (0, 1)")

    rng = random.Random(seed)
    layout = build_dataset_layout(workspace_root, dataset_name)
    layout.cases_dir.mkdir(parents=True, exist_ok=True)

    relative_case_paths: List[str] = []
    for index in range(1, count + 1):
        case_rng = random.Random((seed * 10_000) + index)
        payload = build_case_payload(index, case_rng)

        case_path = layout.cases_dir / f"case_{index:03d}.json"
        with open(case_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, ensure_ascii=False)

        relative_case_paths.append(case_path.relative_to(workspace_root).as_posix())

    train_paths, test_paths = _split_train_test(relative_case_paths, train_ratio, rng)

    train_entries = [
        {"path": case_path, "sha256": _sha256_file(workspace_root / case_path)}
        for case_path in train_paths
    ]
    test_entries = [
        {"path": case_path, "sha256": _sha256_file(workspace_root / case_path)}
        for case_path in test_paths
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
        },
    }

    with open(layout.manifest_path, "w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2, ensure_ascii=False)

    return {
        "dataset_root": layout.root,
        "cases_dir": layout.cases_dir,
        "manifest_path": layout.manifest_path,
        "train_count": len(train_entries),
        "test_count": len(test_entries),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate DRL timetable dataset package")
    parser.add_argument(
        "--workspace-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Workspace root directory (default: repository root)",
    )
    parser.add_argument("--dataset-name", default="dataset_100", help="Dataset folder name inside data/")
    parser.add_argument("--count", type=int, default=100, help="Number of case files to generate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--train-ratio", type=float, default=0.8, help="Train split ratio")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workspace_root = Path(args.workspace_root).resolve()

    result = generate_dataset_package(
        workspace_root=workspace_root,
        dataset_name=args.dataset_name,
        count=args.count,
        seed=args.seed,
        train_ratio=args.train_ratio,
    )

    print("Dataset generation completed")
    print(f"Dataset root: {result['dataset_root']}")
    print(f"Manifest: {result['manifest_path']}")
    print(f"Cases: train={result['train_count']}, test={result['test_count']}")


if __name__ == "__main__":
    main()
