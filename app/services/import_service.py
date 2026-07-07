import re
import os
import zipfile
import uuid
from typing import List, Dict
from app.database import SessionLocal
from app.models import TaskBank

UPLOAD_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "uploads"
))
os.makedirs(UPLOAD_DIR, exist_ok=True)


class ImportService:
    SUPPORTED_IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}

    def extract_tasks_from_text(self, text: str) -> List[Dict]:
        tasks = []
        lines = text.split("\n")
        current_task = None
        current_text = []
        task_pattern = re.compile(r"^(\d+)[\)\.\s\t]")

        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = task_pattern.match(line)
            if match:
                if current_task is not None:
                    current_task["text"] = "\n".join(current_text).strip()
                    if current_task["text"]:
                        tasks.append(current_task)
                current_task = {"order_in_file": int(match.group(1)), "text": ""}
                current_text = []
                rest = line[match.end():].strip()
                if rest:
                    current_text.append(rest)
            elif current_task is not None:
                current_text.append(line)

        if current_task is not None:
            current_task["text"] = "\n".join(current_text).strip()
            if current_task["text"]:
                tasks.append(current_task)
        return tasks

    def _save_image(self, zip_file, name: str) -> str:
        ext = os.path.splitext(name)[1].lower()
        if ext not in self.SUPPORTED_IMAGES:
            return None
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(zip_file.read(name))
        return f"/uploads/{filename}"

    def _get_text_content(self, zip_file, name: str) -> str:
        try:
            return zip_file.read(name).decode("utf-8").strip()
        except:
            return ""

    def import_from_zip(self, file_path: str, source_file: str, task_number: int) -> Dict:
        imported = []
        errors = []
        db = SessionLocal()

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                names = zf.namelist()
                task_dirs = set()

                for name in names:
                    parts = name.rstrip("/").split("/")
                    if len(parts) >= 1 and parts[0].isdigit():
                        task_dirs.add(parts[0])

                for tid in sorted(task_dirs, key=int):
                    try:
                        order = int(tid)
                        prefix = f"{tid}/"
                        txt_candidates = [n for n in names if n.startswith(prefix) and n.endswith(".txt")]
                        img_candidates = [n for n in names if n.startswith(prefix) and os.path.splitext(n)[1].lower() in self.SUPPORTED_IMAGES]

                        text = ""
                        answer = ""
                        image_url = None

                        for tc in txt_candidates:
                            content = self._get_text_content(zf, tc)
                            fname = os.path.basename(tc).lower()
                            if "answer" in fname or "otvet" in fname:
                                answer = content
                            else:
                                text = content

                        for ic in img_candidates:
                            url = self._save_image(zf, ic)
                            if url:
                                image_url = url
                            break

                        if not text:
                            errors.append(f"Задание #{order}: не найден файл с текстом")
                            continue

                        existing = db.query(TaskBank).filter(
                            TaskBank.source_file == source_file,
                            TaskBank.task_number == task_number,
                            TaskBank.order_in_file == order
                        ).first()

                        if existing:
                            continue

                        task = TaskBank(
                            task_number=task_number,
                            source_file=source_file,
                            order_in_file=order,
                            text=text,
                            image_url=image_url,
                            correct_answer=answer or "0",
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
                        errors.append(f"Задание #{tid}: {str(e)}")
                        db.rollback()

                db.close()
                return {
                    "total": len(task_dirs),
                    "imported": len(imported),
                    "skipped": len(task_dirs) - len(imported),
                    "errors": errors,
                    "tasks": imported,
                }

        except Exception as e:
            db.close()
            return {
                "total": 0, "imported": 0, "skipped": 0,
                "errors": [f"Ошибка ZIP: {str(e)}"],
                "tasks": [],
            }

    def import_from_txt(self, file_path: str, source_file: str, task_number: int) -> Dict:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            tasks_data = self.extract_tasks_from_text(text)
            if not tasks_data:
                return {
                    "total": 0, "imported": 0, "skipped": 0,
                    "errors": ["Задания не найдены"],
                    "tasks": [],
                }

            imported = []
            errors = []
            db = SessionLocal()

            for task_data in tasks_data:
                try:
                    existing = db.query(TaskBank).filter(
                        TaskBank.source_file == source_file,
                        TaskBank.task_number == task_number,
                        TaskBank.order_in_file == task_data.get("order_in_file"),
                    ).first()
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
                    errors.append(f"Ошибка #{task_data.get('order_in_file')}: {str(e)}")
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
                "total": 0, "imported": 0, "skipped": 0,
                "errors": [f"Ошибка импорта: {str(e)}"],
                "tasks": [],
            }
