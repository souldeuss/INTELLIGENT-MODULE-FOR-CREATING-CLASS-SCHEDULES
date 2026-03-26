"""CLI для запуску генератора розкладу."""
from __future__ import annotations

import argparse
from pathlib import Path

from imscheduler.generator import ScheduleGenerator
from imscheduler.logger import configure_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Інтелектуальний модуль складання розкладу")
    parser.add_argument("--config", required=True, help="Шлях до config.json")
    parser.add_argument("--input", required=True, help="Шлях до input.json")
    parser.add_argument("--output", required=True, help="Шлях до output.json")
    parser.add_argument("--log-level", default="INFO", help="Рівень логування (INFO/DEBUG/WARNING)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)
    generator = ScheduleGenerator(config_path=Path(args.config), data_path=Path(args.input))
    try:
        generator.load_config()
        generator.load_data()
        results = generator.generate_schedule()
        generator.save_schedule(results, Path(args.output))
    except Exception as exc:
        print(f"Сталася помилка: {exc}")
        raise


if __name__ == "__main__":
    main()
