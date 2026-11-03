#!/usr/bin/env python3
"""Нагрузочный тест для OpenAI-совместимого эндпоинта vLLM."""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time

import httpx

async def _one(client: httpx.AsyncClient, url: str, api_key: str,
               model: str, prompt: str, max_tokens: int) -> tuple[float, float, int]:
    t0 = time.perf_counter()
    ttft: float | None = None
    text = ""

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "stream": True,
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    async with client.stream("POST", url, json=payload, headers=headers, timeout=600.0) as r:
        r.raise_for_status()
        async for line in r.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            if ttft is None:
                ttft = time.perf_counter() - t0
            try:
                obj = json.loads(data)
                text += obj["choices"][0].get("delta", {}).get("content", "")
            except Exception:
                pass

    total = time.perf_counter() - t0
    return (ttft if ttft is not None else total), total, len(text)

def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    k = max(0, min(len(values) - 1, int(round(p * (len(values) - 1)))))
    return sorted(values)[k]

async def _run(args: argparse.Namespace) -> dict:
    url = f"{args.url.rstrip('/')}/v1/chat/completions"
    sem = asyncio.Semaphore(args.concurrency)

    async with httpx.AsyncClient() as client:
        async def worker():
            async with sem:
                return await _one(client, url, args.api_key, args.model, args.prompt, args.max_tokens)

        wall0 = time.perf_counter()
        results = await asyncio.gather(*[worker() for _ in range(args.requests)])
        wall = time.perf_counter() - wall0

    ttfts = [r[0] for r in results]
    lats = [r[1] for r in results]
    out_tokens = sum(r[2] for r in results)

    return {
        "requests": args.requests,
        "concurrency": args.concurrency,
        "ttft_p50_s": round(statistics.median(ttfts), 3),
        "ttft_p95_s": round(_pct(ttfts, 0.95), 3),
        "latency_p50_s": round(statistics.median(lats), 3),
        "latency_p95_s": round(_pct(lats, 0.95), 3),
        "wall_s": round(wall, 3),
        "throughput_rps": round(len(results) / wall, 3),
        "tokens_per_sec": round(out_tokens / wall, 2),
    }

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--api-key", required=True)
    p.add_argument("--model", default="qwen2.5-0.5b-instruct")
    p.add_argument("--prompt", default="Explain what Kubernetes is.")
    p.add_argument("--requests", type=int, default=16)
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--max-tokens", type=int, default=50)
    args = p.parse_args()

    try:
        summary = asyncio.run(_run(args))
    except Exception as e:
        print(f"Ошибка теста: {e}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
