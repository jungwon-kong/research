import json
import re
import hashlib
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

path = Path("data/items.json")
rows = json.loads(path.read_text(encoding="utf-8"))

model = None
tokenizer = None
model_name = "facebook/nllb-200-distilled-600M"

def translate(text):
    global model, tokenizer

    if not text:
        return ""

    if re.search(r"[가-힣]", text):
        return text

    if model is None:
        from transformers import (
            AutoTokenizer,
            AutoModelForSeq2SeqLM
        )

        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            src_lang="eng_Latn"
        )

        model = AutoModelForSeq2SeqLM.from_pretrained(
            model_name
        )
        model.eval()

    import torch

    sentences = re.split(r"(?<=[.!?])\s+", text)
    results = []

    for sentence in sentences:
        if not sentence.strip():
            continue

        inputs = tokenizer(
            sentence,
            return_tensors="pt",
            truncation=True,
            max_length=512
        )

        with torch.inference_mode():
            output = model.generate(
                **inputs,
                forced_bos_token_id=tokenizer.convert_tokens_to_ids(
                    "kor_Hang"
                ),
                max_new_tokens=512,
                num_beams=3
            )

        results.append(
            tokenizer.decode(
                output[0],
                skip_special_tokens=True
            )
        )

    return " ".join(results)

def save():
    temp = path.with_suffix(".tmp")
    temp.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    temp.replace(path)

success = 0
failed = 0
missing = 0

for row in rows:
    source = (
        row.get("abstract")
        or row.get("article_excerpt")
        or ""
    ).strip()

    fingerprint = hashlib.sha256(
        source.encode()
    ).hexdigest()

    if (
        row.get("summary_version") == "2.1"
        and row.get("summary_hash") == fingerprint
        and row.get("summary_status") == "완료"
    ):
        continue

    try:
        row["title_ko"] = translate(
            row.get("title", "")
        )

        if source:
            sentences = re.split(
                r"(?<=[.!?])\s+", source
            )

            selected = (
                sentences[:3] + sentences[-3:]
                if len(sentences) > 6
                else sentences
            )

            row["summary_ko"] = translate(
                " ".join(selected)
            )

            row["summary_type"] = (
                "초록 기반 발췌 번역"
                if row.get("abstract")
                else "기사 원문 일부 발췌 번역"
            )

            row["summary_status"] = "완료"
            success += 1

        else:
            row["summary_ko"] = (
                row["title_ko"]
                + "\n\n추가 출처를 검색했으나 "
                "초록 또는 기사 본문을 확보하지 "
                "못했습니다. 원문을 확인해 주세요."
            )

            row["summary_type"] = "제목 번역"
            row["summary_status"] = "원문 정보 부족"
            missing += 1

        row["summary_version"] = "2.1"
        row["summary_hash"] = fingerprint

    except Exception as e:
        row["summary_status"] = "번역 실패 · 재시도 예정"
        failed += 1
        print("Translation error:", e)

    save()

status = {
    "updated_at": datetime.now(
        ZoneInfo("Asia/Seoul")
    ).strftime("%Y-%m-%d %H:%M:%S"),
    "total": len(rows),
    "translated": success,
    "translation_failed": failed,
    "missing_source": missing
}

Path("data/status.json").write_text(
    json.dumps(status, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print(status)
