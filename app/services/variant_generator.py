import random
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app.models import TaskBank, Variant, VariantTask, User


class VariantGenerator:
    """Генератор вариантов из банка заданий"""

    def __init__(self, db: Session):
        self.db = db

    def get_tasks_by_number(self, number: int) -> List[TaskBank]:
        """Получает задания из банка по номеру задания в КИМ"""
        return (
            self.db.query(TaskBank)
            .filter(TaskBank.task_number == number)  # ← исправлено
            .all()
        )

    def generate_variant(
        self,
        title: str,
        description: str,
        user: User,
        shuffle: bool = True,
        fill_missing: bool = True,
    ) -> Dict:
        """Генерирует новый вариант"""

        variant = Variant(title=title, description=description, created_by=user.id)
        self.db.add(variant)
        self.db.flush()

        selected_tasks = []
        missing_numbers = []

        # Для каждого номера от 1 до 27 выбираем задание
        for number in range(1, 28):
            tasks = self.get_tasks_by_number(number)

            if tasks:
                # Выбираем случайное задание
                task = random.choice(tasks)
                selected_tasks.append({"number": number, "task": task})
            else:
                missing_numbers.append(number)
                selected_tasks.append({"number": number, "task": None})

        # Если нужно заполнить пропуски
        if fill_missing and missing_numbers:
            # Ищем похожие задания из других номеров
            all_tasks = self.db.query(TaskBank).all()
            for number in missing_numbers:
                # Берем случайное задание из других номеров
                available = [t for t in all_tasks if t.task_number != number]
                if available:
                    task = random.choice(available)
                    selected_tasks[number - 1]["task"] = task

        # Перемешиваем задания, если нужно
        if shuffle:
            random.shuffle(selected_tasks)
            # Перенумеровываем
            for i, item in enumerate(selected_tasks, 1):
                item["number"] = i

        # Создаем связи
        for item in selected_tasks:
            if item["task"]:
                variant_task = VariantTask(
                    variant_id=variant.id,
                    task_bank_id=item["task"].id,
                    order_number=item["number"],
                )
                self.db.add(variant_task)

        self.db.commit()
        self.db.refresh(variant)

        return {
            "variant": variant,
            "selected_tasks": selected_tasks,
            "missing_numbers": missing_numbers,
            "total_tasks": len([t for t in selected_tasks if t["task"]]),
        }
