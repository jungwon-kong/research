import json
import re
import time
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime

path = Path("data/items.json")
rows = json.loads(path.read_text(encoding="utf-8"))

headers = {
    "User-Agent": "ResearchObservatory/2.1"
}

def get_json(url, params=None):
    response = requests.get(
        url, params=params,
        headers=headers, timeout=25
    )
    response.raise_for_status()
    return response.json()

def clean(text):
    return " ".join(
        BeautifulSoup(
            text or "", "html.parser"
        ).get_text(" ").split()
    )

def openalex_abstract(doi):
    data = get_json(
        "https://api.openalex.org/works/https://doi.org/" + doi
    )
    index = data.get("abstract_inverted_index") or {}
    words = sorted(
        (position, word)
        for word, positions in index.items()
        for position in positions
    )
    return " ".join(word for _, word in words)

def semantic_abstract(doi):
    data = get_json(
        "https://api.semanticscholar.org/graph/v1/paper/DOI:" + doi,
        {"fields": "abstract"}
    )
    return data.get("abstract") or ""

def enrich_paper(row):
    doi = row["url"].split("doi.org/", 1)[-1]
    row["doi"] = doi

    try:
        data = get_json(
            "https://api.crossref.org/works/" + doi
        )["message"]

        if not row.get("authors"):
            row["authors"] = ", ".join(
                " ".join([
                    a.get("given", ""),
                    a.get("family", "")
                ]).strip()
                for a in data.get("author", [])
            )

        if not row.get("date"):
            parts = data.get(
                "published", {}
            ).get("date-parts", [[]])[0]
            row["date"] = "-".join(
                str(v).zfill(2) for v in parts
            )

        if not row.get("abstract"):
            row["abstract"] = clean(
                data.get("abstract", "")
            )
            if row["abstract"]:
                row["abstract_source"] = "Crossref"

    except Exception as e:
        print("Crossref:", e)

    if row.get("abstract"):
        row.setdefault("abstract_source", "Crossref")
        return

    for name, finder in [
        ("OpenAlex", openalex_abstract),
        ("Semantic Scholar", semantic_abstract)
    ]:
        try:
            abstract = finder(doi)
            if abstract:
                row["abstract"] = clean(abstract)
                row["abstract_source"] = name
                break
        except Exception as e:
            print(name, e)
        time.sleep(1)

def enrich_news(row):
    import trafilatura

    url = row.get("url", "")

    if "news.google.com" in url:
        try:
            from googlenewsdecoder import gnewsdecoder
            result = gnewsdecoder(url, interval=1)
            if result.get("status"):
                url = result["decoded_url"]
        except Exception as e:
            print("News URL:", e)

    if "news.google.com" in url:
        return

    row["original_url"] = url

    try:
        response = requests.get(
            url, headers=headers, timeout=25
        )
        response.raise_for_status()

        body = trafilatura.extract(
            response.text,
            include_comments=False,
            include_tables=False
        )

        if body and len(body) > 200:
            # Store only a limited source excerpt.
            row["article_excerpt"] = body[:350]
            row["abstract_source"] = "기사 원문 발췌"

    except Exception as e:
        print("Article extraction:", e)

def save():
    temp = path.with_suffix(".tmp")
    temp.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    temp.replace(path)

for row in rows:
    try:
        if "doi.org/" in row.get("url", ""):
            if not all(row.get(k) for k in [
                "authors", "date", "abstract"
            ]):
                enrich_paper(row)
            row.setdefault(
                "doi", row["url"].split("doi.org/", 1)[-1]
            )
        else:
            if not row.get("article_excerpt"):
                enrich_news(row)
            try:
                row["date"] = parsedate_to_datetime(
                    row["date"]
                ).date().isoformat()
            except Exception:
                pass

        row["source_status"] = (
            "확보" if row.get("abstract")
            or row.get("article_excerpt")
            else "원문 정보 부족"
        )

        save()

    except Exception as e:
        print(row.get("title"), e)

print("Enrichment complete:", len(rows))
