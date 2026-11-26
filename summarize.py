import json
import re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

path = Path("data/items.json")
rows = json.loads(path.read_text(encoding="utf-8"))

translator = None

def translate(text):
    global translator
    if not text:
        return ""
    if re.search(r"[가-힣]", text):
        return text
    if translator is None:
        from transformers import pipeline
        translator = pipeline(
            "translation",
            model="Helsinki-NLP/opus-mt-en-ko",
            device=-1
        )
    sentences = re.split(r"(?<=[.!?])\s+", text)
    result = []
    for sentence in sentences:
        if not sentence.strip():
            continue
        result.append(
            translator(
                sentence,
                max_length=512,
                truncation=True
            )[0]["translation_text"]
        )
    return " ".join(result)

success = 0
failed = 0

for row in rows:
    if row.get("summary_ko"):
        continue

    abstract = row.get("abstract", "").strip()
    title = row.get("title", "").strip()

    try:
        if abstract:
            sentences = re.split(
                r"(?<=[.!?])\s+", abstract
            )
            if len(sentences) > 6:
                selected = sentences[:3] + sentences[-3:]
            else:
                selected = sentences

            row["summary_ko"] = translate(
                " ".join(selected)
            )
            row["summary_type"] = "초록 발췌 및 기계번역"
        else:
            row["summary_ko"] = (
                translate(title)
                + "\n\n원문 초록 또는 기사 본문이 "
                "제공되지 않아 상세 요약은 생략합니다."
            )
            row["summary_type"] = "제목 번역"

        success += 1
    except Exception as error:
        failed += 1
        print("Translation failed:", error)

    temp = path.with_suffix(".tmp")
    temp.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    temp.replace(path)

status = {
    "updated_at": datetime.now(
        ZoneInfo("Asia/Seoul")
    ).strftime("%Y-%m-%d %H:%M:%S"),
    "total": len(rows),
    "translated": success,
    "translation_failed": failed
}

Path("data/status.json").write_text(
    json.dumps(status, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print(status)
