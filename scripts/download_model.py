#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from huggingface_hub import snapshot_download

MODEL_ID = os.environ.get("VLLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
CACHE = Path(os.environ.get("HF_HUB_CACHE", "/models/hub"))
TOKEN = os.environ.get("HF_TOKEN") or None

def main() -> int:
    marker = CACHE / ("models--" + MODEL_ID.replace("/", "--"))
    if marker.exists() and any(marker.iterdir()):
        print(f"[init] Модель уже скачана в {marker} — пропускаем", flush=True)
        return 0
    CACHE.mkdir(parents=True, exist_ok=True)
    print(f"[init] Скачивание {MODEL_ID} -> {CACHE}", flush=True)
    snapshot_download(
        repo_id=MODEL_ID,
        cache_dir=str(CACHE),
        token=TOKEN,
        resume_download=True,
        ignore_patterns=["*.gguf", "*.onnx", "*.msgpack", "*.h5"],
    )
    print("[init] Скачивание завершено", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
