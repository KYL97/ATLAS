#!/usr/bin/env bash
# ATLAS 一键启动：同时拉起后端(FastAPI/uvicorn) 与 前端(Vite)
# 用法：  ./start.sh          （首次会自动装依赖）
# 停止：  在本终端按 Ctrl+C，会同时关闭前后端

set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"

# ---------- 后端依赖 ----------
if [ ! -d "$BACKEND/.venv" ]; then
  echo "[后端] 首次运行，创建虚拟环境并安装依赖..."
  python3 -m venv "$BACKEND/.venv"
  "$BACKEND/.venv/bin/pip" install -q -r "$BACKEND/requirements.txt"
fi

if [ ! -f "$BACKEND/.env" ]; then
  echo "⚠️  未找到 backend/.env，请复制 backend/.env.example 为 .env 并填入 DEEPSEEK_API_KEY"
fi

# ---------- 前端依赖 ----------
if [ ! -d "$ROOT/node_modules" ]; then
  echo "[前端] 首次运行，安装 npm 依赖..."
  (cd "$ROOT" && npm install)
fi

# ---------- 启动 ----------
PIDS=()
cleanup() {
  echo ""
  echo "正在关闭前后端..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  exit 0
}
trap cleanup INT TERM

echo "[后端] http://127.0.0.1:8000  启动中..."
( cd "$BACKEND" && ./.venv/bin/uvicorn main:app --reload --port 8000 ) &
PIDS+=($!)

echo "[前端] http://localhost:5173  启动中..."
( cd "$ROOT" && npm run dev ) &
PIDS+=($!)

echo ""
echo "✅ 已启动：前端 http://localhost:5173  后端 http://127.0.0.1:8000"
echo "   按 Ctrl+C 同时停止两者。"
wait
