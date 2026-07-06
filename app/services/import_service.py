import re
from typing import List, Dict
from app.database import SessionLocal
from app.models import TaskBank


class ImportService:
    """Сервис для импорта заданий из TXT файлов"""

    def __init__(self):
        self.supported_extensions = [".txt"]

    def extract_tasks_from_text(self, text: str) -> List[Dict]:
        """Извлекает задания из текста"""
        tasks = []
        lines = text.split("\n")

        current_task = None
        current_text = []

        # Паттерн для поиска номера задания в начале строки
        task_pattern = re.compile(r"^(\d+)[\)\.\s\t]")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            match = task_pattern.match(line)

            if match:
                # Сохраняем предыдущее задание
                if current_task is not None:
                    current_task["text"] = "\n".join(current_text).strip()
                    if current_task["text"]:
                        tasks.append(current_task)

                # Начинаем новое задание
                current_task = {"order_in_file": int(match.group(1)), "text": ""}
                current_text = []

                # Добавляем остаток строки после номера
                rest = line[match.end() :].strip()
                if rest:
                    current_text.append(rest)

            elif current_task is not None:
                current_text.append(line)

        # Добавляем последнее задание
        if current_task is not None:
            current_task["text"] = "\n".join(current_text).strip()
            if current_task["text"]:
                tasks.append(current_task)

        return tasks

    def import_from_txt(
        self, file_path: str, source_file: str, task_number: int
    ) -> Dict:
        """Импорт заданий из TXT файла с указанием номера задания"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()

            tasks_data = self.extract_tasks_from_text(text)

            if not tasks_data:
                return {
                    "total": 0,
                    "imported": 0,
                    "skipped": 0,
                    "errors": ["Задания не найдены. Проверьте формат файла."],
                    "tasks": [],
                }

            imported = []
            errors = []
            db = SessionLocal()

            for task_data in tasks_data:
                try:
                    # Проверяем, есть ли уже такое задание
                    existing = (
                        db.query(TaskBank)
                        .filter(
                            TaskBank.source_file == source_file,
                            TaskBank.task_number == task_number,
                            TaskBank.order_in_file == task_data.get("order_in_file"),
                        )
                        .first()
                    )

                    if existing:
                        continue

                    task = TaskBank(
                        task_number=task_number,
                        source_file=source_file,
                        order_in_file=task_data.get("order_in_file"),
                        text=task_data.get("text", ""),
                        correct_answer="0",
                        answer_type="int",
                        answer_count=1,
                        points=1,
                        is_verified=False,
                    )
                    db.add(task)
                    db.commit()
                    db.refresh(task)

                    imported.append(task)

                except Exception as e:
                    errors.append(
                        f"Ошибка при сохранении задания #{task_data.get('order_in_file')}: {str(e)}"
                    )
                    db.rollback()

            db.close()

            return {
                "total": len(tasks_data),
                "imported": len(imported),
                "skipped": len(tasks_data) - len(imported),
                "errors": errors,
                "tasks": imported,
            }

        except Exception as e:
            return {
                "total": 0,
                "imported": 0,
                "skipped": 0,
                "errors": [f"Ошибка импорта: {str(e)}"],
                "tasks": [],
            }
