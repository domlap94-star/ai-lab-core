from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from urllib.request import Request, urlopen


TOOLS = ["client_lookup", "document_search", "mail_search", "activity_search", "visit_lookup", "calculation", "visual_analysis", "knowledge_base"]
CASES = [
    ("R1", "Podsumuj przypadek klienta, jego dokumenty, maile i ostatnią aktywność.", {"client_lookup", "document_search", "mail_search", "activity_search"}),
    ("R2", "Znajdź najnowszy raport geotechniczny.", {"document_search"}),
    ("R3", "Co klient napisał w ostatnim mailu?", {"mail_search"}),
    ("R4", "Co sprawdzono podczas ostatniej wizji?", {"visit_lookup"}),
    ("R5", "Oblicz P=F/A dla podanych danych.", {"calculation"}),
    ("R6", "Co widać na załączonym zdjęciu rysy?", {"visual_analysis"}),
    ("R7", "Porównaj wymaganie normowe z pomiarem.", {"knowledge_base", "document_search"}),
    ("R8", "Jaki problem ma klient i czy potwierdza go ostatni mail?", {"client_lookup", "mail_search"}),
    ("R9", "Pokaż chronologię ostatnich zmian i kontaktów.", {"activity_search", "mail_search"}),
    ("R10", "Połącz zdjęcia, raport, wizję i historię klienta.", {"visual_analysis", "document_search", "visit_lookup", "client_lookup", "activity_search"}),
]
SCHEMA = {"type": "object", "properties": {"tools": {"type": "array", "uniqueItems": True, "items": {"type": "string", "enum": TOOLS}}, "reason": {"type": "string"}}, "required": ["tools", "reason"], "additionalProperties": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default="http://ollama:11434")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = []
    for case_id, question, expected in CASES:
        prompt = "Jesteś planistą narzędzi NEXT Stabil. Nie odpowiadaj na pytanie. Wybierz minimalny zestaw narzędzi konieczny do zebrania danych przed odpowiedzią. Zwróć tylko JSON. PYTANIE: " + question
        payload = json.dumps({"model": args.model, "prompt": prompt, "stream": False, "format": SCHEMA, "think": False, "keep_alive": "5m", "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 100}}, ensure_ascii=False).encode("utf-8")
        started = time.perf_counter()
        try:
            with urlopen(Request(args.base_url.rstrip("/") + "/api/generate", data=payload, headers={"Content-Type": "application/json"}), timeout=600) as response:
                envelope = json.loads(response.read().decode("utf-8"))
            parsed = json.loads(envelope.get("response") or "{}")
            selected = set(map(str, parsed.get("tools") or []))
            union = selected | expected
            score = 100.0 * len(selected & expected) / max(1, len(union))
            row = {"case_id": case_id, "expected": sorted(expected), "selected": sorted(selected), "score": round(score, 2), "latency_seconds": round(time.perf_counter()-started, 2)}
        except Exception as exc:
            row = {"case_id": case_id, "expected": sorted(expected), "error": type(exc).__name__ + ": " + str(exc)[:200], "score": 0.0}
        rows.append(row)
        print(args.model, case_id, row["score"], flush=True)
    summary = {"model": args.model, "cases": len(rows), "tool_selection_score": round(statistics.mean(row["score"] for row in rows), 2), "exact_match_percent": 10 * sum(set(row.get("selected", [])) == set(row["expected"]) for row in rows), "median_latency_seconds": round(statistics.median(row.get("latency_seconds", 0) for row in rows), 2)}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
