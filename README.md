# Intelligent Module for Creating Class Schedules

Інтелектуальний модуль на Python 3.10+ для генерації навчального розкладу з підтримкою трьох режимів: щільний (dense), збалансований (balanced) та режим доповнення (append).

## Можливості

- Побудова розкладу без конфліктів груп, викладачів та аудиторій
- Підтримка спеціалізованих кабінетів і автоматичний підбір аудиторій
- Різні стратегії планування для щільного, збалансованого та додаткового режимів
- Валідація вхідних даних та фінального розкладу
- Звіт зі статистикою використання ресурсів
- Логування кроків генерації та CLI-інтерфейс

## Структура проєкту

```
src/
  main.py                # CLI-запуск
  imscheduler/
    config.py            # Завантаження/опис конфігурації
    generator.py         # Основний фасад
    logger.py            # Налаштування логування
    models.py            # @dataclass моделі
    solver.py            # Перевірка обмежень
    validator.py         # Валідація
    modes/
      base.py            # Реалізація режимів

data/
  config.sample.json     # Приклад конфігурації
  input.sample.json      # Приклад даних
```

## Запуск

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt  # якщо потрібно
python src/main.py --config data/config.sample.json --input data/input.sample.json --output output.json
```

## Вхідні файли

- **config.json** – параметри генерації (режим, часові слоти тощо)
- **input.json** – групи, предмети, викладачі, аудиторії, пул уроків та, за потреби, існуючий розклад

Див. зразки у каталозі `data/`.

## Тестування

```powershell
pytest
```

## DRL Lifecycle (Train -> Evaluate -> Promote)

Для протоколу навчання з hold-out оцінкою використовуйте manifest-файл.

1. Відредагуйте [data/dataset_manifest.sample.json](data/dataset_manifest.sample.json):
  - `train` / `test` списки кейсів
  - `seed` для відтворюваності
  - `promotion_policy` для порогів активації моделі
  - за потреби вкажіть `sha256` для перевірки цілісності датасетів

2. Запустіть train+eval пайплайн:

```powershell
python backend/train_eval_pipeline.py --manifest data/dataset_manifest.sample.json --iterations 300 --device cpu
```

3. Автоматичний promote (лише якщо пройдено policy-gating):

```powershell
python backend/train_eval_pipeline.py --manifest data/dataset_manifest.sample.json --iterations 300 --device cpu --promote
```

Після запуску формується звіт `evaluation_report_*.json` з метаданими manifest, dataset-hash, score-margin та перевіркою всіх критеріїв `promotion_policy`.

## Розширення

- Додайте новий режим, успадкувавши `ScheduleMode`
- Реалізуйте додаткові оптимізації у `ConstraintSolver`
- Підключіть OR-Tools для більш просунутих стратегій
