#!/usr/bin/env bash
set -euo pipefail

root=/data/downloads/kanishk-persona
exec "$root/llama.cpp/build/bin/llama-server" \
  --model "$root/qwen38-27b/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q4_K_P.gguf" \
  --ctx-size 8192 \
  --n-gpu-layers 999 \
  --flash-attn on \
  --parallel 1 \
  --host 127.0.0.1 \
  --port 8081 \
  --jinja \
  --threads 8
