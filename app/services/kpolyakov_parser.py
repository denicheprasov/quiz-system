import re
import os
import uuid
import urllib.request
from typing import List, Dict, Optional
from bs4 import BeautifulSoup, Tag
from app.database import SessionLocal
from app.models import TaskBank

UPLOAD_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "uploads"
))
os.makedirs(UPLOAD_DIR, exist_ok=True)

BASE_URL = "https://kpolyakov.spb.ru/school/ege"
IMAGE_BASE_URL = "https://kpolyakov.spb.ru/cms/images"
FILE_BASE_URL = "https://kpolyakov.spb.ru/cms/files"


class KpolyakovParser:

    def _fetch_html(self, url: str) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8")

    def _extract_from_script(self, script_tag: Tag) -> str:
        text = script_tag.get_text()
        match = re.search(r"changeImageFilePath\('(.*)'\s*\)", text, re.DOTALL)
        if match:
            raw = match.group(1)
            raw = raw.replace("<br/>", "\n").replace("<br>", "\n")
            raw = re.sub(r'<a\s+href="[^"]+"[^>]*>([^<]+)</a>', r'\1', raw)
            raw = re.sub(r"<(?!sup>|/sup>|sub>|/sub>|br>|br/>)[^>]+>", "", raw)
            raw = re.sub(r"<(?!sup>|/sup>|sub>|/sub>|br>)", "&lt;", raw)
            raw = raw.replace("&nbsp;", " ").replace("&gt;", ">")
            raw = raw.replace("&amp;", "&").replace("&middot;", "·")
            raw = raw.replace("&le;", "≤").replace("&ge;", "≥").replace("&ne;", "≠")
            raw = raw.replace("&and;", "∧").replace("&or;", "∨").replace("&not;", "¬")
            raw = raw.replace("&rarr;", "→").replace("&equiv;", "≡")
            raw = raw.replace("&minus;", "−")
            return raw.strip()
        return ""

    def _download_image(self, img_src: str) -> Optional[str]:
        if not img_src:
            return None
        img_url = img_src
        if img_url.startswith("/"):
            img_url = f"https://kpolyakov.spb.ru{img_url}"
        elif not img_url.startswith("http"):
            img_url = f"{IMAGE_BASE_URL}/{img_url}"

        ext = os.path.splitext(img_url)[1].lower()
        if ext not in (".gif", ".png", ".jpg", ".jpeg"):
            return None

        if img_url.startswith("http"):
            return img_url
        return None

    def _extract_images_from_html(self, html_text: str) -> List[str]:
        urls = []
        for match in re.finditer(r'<img\s+src="([^"]+)"', html_text):
            src = match.group(1)
            url = self._download_image(src)
            if url:
                urls.append(url)
        return urls

    def _extract_files(self, topic_td: Tag) -> Optional[str]:
        for script in topic_td.find_all("script"):
            text = script.get_text()
            match = re.search(r'<a\s+href="([^"]+)"', text)
            if match:
                href = match.group(1)
                if href.startswith("http"):
                    return href
                if href.startswith("/"):
                    return f"https://kpolyakov.spb.ru{href}"
                return f"{FILE_BASE_URL}/{href}"
        return None

    def _extract_images(self, topic_td: Tag) -> List[str]:
        images = self._extract_images_from_html(str(topic_td))
        for script in topic_td.find_all("script"):
            script_text = script.get_text()
            images.extend(self._extract_images_from_html(script_text))
        return images

    def parse_page(self, url: str = None, html: str = None, task_number: int = 0, db_session=None) -> Dict:
        imported = []
        errors = []

        close_db = False
        if db_session is None:
            db_session = SessionLocal()
            close_db = True

        try:
            if html:
                pass
            elif url:
                html = self._fetch_html(url)
            else:
                if close_db:
                    db_session.close()
                return {"total": 0, "imported": 0, "skipped": 0, "errors": ["Укажите URL или вставьте HTML"], "tasks": []}
        except Exception as e:
            if close_db:
                db_session.close()
            return {"total": 0, "imported": 0, "skipped": 0, "errors": [f"Ошибка загрузки страницы: {str(e)}"], "tasks": []}

        try:
            soup = BeautifulSoup(html, "html.parser")
            rows = soup.find_all("tr")
            i = 0
            while i < len(rows):
                row = rows[i]
                egeno_td = row.find("td", class_="egeno")
                topic_td = row.find("td", class_="topicview")
                if egeno_td is None or topic_td is None:
                    i += 1
                    continue

                task_text = ""
                for script in topic_td.find_all("script"):
                    part = self._extract_from_script(script)
                    if part:
                        task_text += part + " "
                task_text = task_text.strip()

                images = self._extract_images(topic_td)
                file_url = self._extract_files(topic_td)

                task_id = None
                answer = "0"
                has_answer = False

                if i + 1 < len(rows):
                    next_row = rows[i + 1]
                    answer_td = next_row.find("td", class_="answer")
                    if answer_td:
                        has_answer = True
                        answer_link = answer_td.find("a", {"onclick": re.compile(r"showDiv\('(\d+)'\)")})
                        if answer_link:
                            onclick = answer_link.get("onclick", "")
                            task_id = re.search(r"'(\d+)'", onclick).group(1)
                        hidedata = answer_td.find("div", class_="hidedata")
                        if hidedata:
                            script = hidedata.find("script")
                            if script:
                                ans_text = script.get_text()
                                ans_match = re.search(r"changeImageFilePath\('([^']*)'\)", ans_text)
                                if ans_match:
                                    answer = ans_match.group(1).strip()

                if not task_text or not has_answer:
                    i += 1
                    continue

                answer_type = "int" if answer.isdigit() else "string"

                try:
                    existing = None
                    if task_id:
                        existing = db_session.query(TaskBank).filter(
                            TaskBank.source_file == f"kpolyakov_{task_id}.html",
                            TaskBank.task_number == task_number,
                        ).first()

                    if existing:
                        errors.append(f"Задание #{task_id} уже существует, пропущено")
                        i += 2
                        continue

                    task = TaskBank(
                        task_number=task_number,
                        order_in_file=len(imported) + 1,
                        source_file=f"kpolyakov_{task_id}.html" if task_id else f"kpolyakov_{uuid.uuid4().hex}.html",
                        text=task_text,
                        image_url=images[0] if images else None,
                        file_url=file_url,
                        correct_answer=answer,
                        answer_type=answer_type,
                        answer_count=1,
                        points=1,
                    )
                    db_session.add(task)
                    db_session.commit()
                    db_session.refresh(task)
                    imported.append(task)
                    i += 2

                except Exception as e:
                    errors.append(f"Ошибка сохранения #{task_id or '?'}: {str(e)}")
                    db_session.rollback()
                    i += 2

            db_session.commit()
            return {
                "total": len(imported) + len([e for e in errors if "уже существует" in e]),
                "imported": len(imported),
                "skipped": len([e for e in errors if "уже существует" in e]),
                "errors": [e for e in errors if "уже существует" not in e],
                "tasks": imported,
            }

        except Exception as e:
            db_session.rollback()
            return {
                "total": 0, "imported": 0, "skipped": 0,
                "errors": [str(e)], "tasks": [],
            }
        finally:
            if close_db:
                db_session.close()
