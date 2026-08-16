from __future__ import annotations

import json
import tempfile
from pathlib import Path

from run_batched_ollama_reconstruction_calibration import (
    GIB,
    atomic_json,
    initial_checkpoint,
    selected_records,
    should_reset_memory,
    update_checkpoint,
    validate_checkpoint,
)


def manifest(path: Path, count: int = 12) -> dict:
    value = {"records": [
        {"client_id": index + 100, "selection_class": "clean_control",
         "evidence_packet_sha256": f"sha-{index}"}
        for index in range(count)
    ]}
    path.write_text(json.dumps(value), encoding="utf-8")
    return value


def verify_first_batch_selection() -> None:
    records = {"records": [{"client_id": index} for index in range(20)]}
    selected = selected_records(records, start_offset=0, max_records=10)
    assert [index for index, _ in selected] == list(range(10))
    assert [item["client_id"] for _, item in selected] == list(range(10))


def verify_atomic_checkpoint_and_resume_skip() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory); source = root / "manifest.json"; manifest(source)
        checkpoint = initial_checkpoint(run_id="test", model="qwen3.5:9b",
                                        batch_size=10, start_offset=0,
                                        max_records=10, manifest_path=source)
        for index in range(10):
            update_checkpoint(checkpoint, index=index, client_id=index + 100,
                              failed=False, window_end=10)
            atomic_json(root / "checkpoint.json", checkpoint)
            persisted = json.loads((root / "checkpoint.json").read_text())
            assert len(persisted["completed_manifest_indices"]) == index + 1
        validate_checkpoint(persisted, model="qwen3.5:9b", batch_size=10,
                            start_offset=0, max_records=10, manifest_path=source)
        pending = [index for index, _ in selected_records(
            json.loads(source.read_text()), start_offset=0, max_records=10
        ) if index not in set(persisted["completed_manifest_indices"])]
        assert pending == []
        assert persisted["next_manifest_index"] == 10
        assert not (root / "checkpoint.json.tmp").exists()


def verify_checkpoint_mismatch() -> None:
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "manifest.json"; manifest(source)
        checkpoint = initial_checkpoint(run_id="test", model="qwen3.5:9b",
                                        batch_size=10, start_offset=0,
                                        max_records=10, manifest_path=source)
        try:
            validate_checkpoint(checkpoint, model="other", batch_size=10,
                                start_offset=0, max_records=10, manifest_path=source)
        except RuntimeError as error:
            assert "model" in str(error)
        else:
            raise AssertionError("checkpoint mismatch was accepted")


def verify_failure_and_memory_logic() -> None:
    checkpoint = {"completed_manifest_indices": [], "completed_client_ids": [],
                  "failed_client_ids": [], "last_completed_index": None,
                  "next_manifest_index": 0}
    update_checkpoint(checkpoint, index=0, client_id=123, failed=True, window_end=10)
    assert checkpoint["failed_client_ids"] == [123]
    assert should_reset_memory({"wsl_available_bytes": GIB, "ollama_model_bytes": 6 * GIB},
                               previous_model_bytes=6 * GIB)
    assert should_reset_memory({"wsl_available_bytes": 8 * GIB, "ollama_model_bytes": 8 * GIB},
                               previous_model_bytes=6 * GIB)
    assert not should_reset_memory({"wsl_available_bytes": 8 * GIB, "ollama_model_bytes": 6 * GIB},
                                   previous_model_bytes=6 * GIB)


def verify_no_apply_path_and_read_only_contract() -> None:
    source = Path(__file__).with_name("run_batched_ollama_reconstruction_calibration.py").read_text()
    assert 'SET TRANSACTION READ ONLY' in source
    assert "db.rollback()" in source
    for forbidden in ("apply_repairs", "bulk_update", "auto_promote", "db.commit()"):
        assert forbidden not in source
    assert "if window_complete:" in source and "unload(model)" in source


def verify_final_unload_and_zero_call_resume_contract() -> None:
    source = Path(__file__).with_name("run_batched_ollama_reconstruction_calibration.py").read_text()
    assert '"new_inference_calls"] = processed' in source
    assert "pending = [(index, item) for index, item in window if index not in completed]" in source
    assert 'checkpoint["final_unload_completed"] = True' in source
    assert '"keep_alive": 0' in source


def verify_one_attempt_failure_persistence_contract() -> None:
    source = Path(__file__).with_name("run_batched_ollama_reconstruction_calibration.py").read_text()
    assert "for index, manifest_record in pending:" in source
    assert source.count("evaluator.evaluate(packet)") == 1
    assert 'row.update({"status": "failed"' in source
    assert "append_jsonl(results_path, row)" in source
    assert "atomic_json(checkpoint_path, checkpoint)" in source


if __name__ == "__main__":
    verify_first_batch_selection()
    verify_atomic_checkpoint_and_resume_skip()
    verify_checkpoint_mismatch()
    verify_failure_and_memory_logic()
    verify_no_apply_path_and_read_only_contract()
    verify_final_unload_and_zero_call_resume_contract()
    verify_one_attempt_failure_persistence_contract()
    print("BATCHED OLLAMA RECONSTRUCTION CALIBRATION TESTS: OK")
