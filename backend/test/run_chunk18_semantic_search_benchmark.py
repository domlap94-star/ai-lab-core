from __future__ import annotations

import json
import os

from test.support.chunk18_benchmark import (
    ensure_finite_metrics,
    quality_threshold_met,
    run_benchmark,
)


def main() -> None:
    host = os.environ.get("CHUNK18_QDRANT_HOST", "").strip()
    port_text = os.environ.get("CHUNK18_QDRANT_PORT", "").strip()
    prefix = os.environ.get("CHUNK18_QDRANT_COLLECTION_PREFIX", "").strip()
    if not host or not port_text or not prefix:
        raise RuntimeError("chunk18_explicit_isolated_qdrant_required")
    result = run_benchmark(
        qdrant_host=host,
        qdrant_port=int(port_text),
        collection_prefix=prefix,
    )
    ensure_finite_metrics(result)
    result["threshold_met_current_v1"] = quality_threshold_met(result, "current_v1")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
