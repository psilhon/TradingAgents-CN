#!/usr/bin/env bash
# scripts/dev.sh — 本地开发栈启停脚本（OpenSpec spec: loopback-binding-policy）
#
# 管理：
#   - 原生 mongo + redis，端口 54302/54303（scripts/local-services.sh）
#   - backend (uvicorn)，端口 54301
#   - frontend (vite dev)，端口 54300
#
# State 目录：.dev/{backend,frontend}.{pid,log}（已加入 .gitignore，本地独有）
#
# 用法：
#   scripts/dev.sh start     启动全栈
#   scripts/dev.sh stop      停全栈
#   scripts/dev.sh restart
#   scripts/dev.sh status    端口/进程/服务状态（默认）
#   scripts/dev.sh logs b    tail backend log（或 f = frontend）

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

DEV_DIR=".dev"
BACKEND_PID="$DEV_DIR/backend.pid"
BACKEND_LOG="$DEV_DIR/backend.log"
FRONTEND_PID="$DEV_DIR/frontend.pid"
FRONTEND_LOG="$DEV_DIR/frontend.log"

mkdir -p "$DEV_DIR"

# ANSI colors
RED=$'\033[0;31m'
GRN=$'\033[0;32m'
YEL=$'\033[0;33m'
NC=$'\033[0m'

log()  { echo "${GRN}[dev]${NC} $*"; }
warn() { echo "${YEL}[dev]${NC} $*"; }
err()  { echo "${RED}[dev]${NC} $*" >&2; }

is_alive() {
    local pidfile="$1"
    [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile" 2>/dev/null)" 2>/dev/null
}

port_in_use() {
    lsof -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | grep -q .
}

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || { err "缺命令：$1"; exit 1; }
}

stop_with_children() {
    local pidfile="$1"
    local name="$2"
    if [ -f "$pidfile" ]; then
        local pid
        pid=$(cat "$pidfile" 2>/dev/null || echo "")
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            log "停 $name (PID $pid 及子进程)..."
            pkill -TERM -P "$pid" 2>/dev/null || true
            kill -TERM "$pid" 2>/dev/null || true
            # 给 1.5s 优雅退出，否则 KILL
            sleep 1.5
            if kill -0 "$pid" 2>/dev/null; then
                warn "$name 未优雅退出，发 SIGKILL"
                pkill -KILL -P "$pid" 2>/dev/null || true
                kill -KILL "$pid" 2>/dev/null || true
            fi
        else
            warn "$name PID file 存在但进程已死，清理"
        fi
        rm -f "$pidfile"
    fi
}

cmd_start() {
    require_cmd lsof

    # 1. 原生服务 (mongo + redis)，由 scripts/local-services.sh 自管 PID
    # 不再用 docker，详见 OpenSpec change native-local-deployment
    log "启动原生服务 (mongo + redis)..."
    if ! bash "$(dirname "$0")/local-services.sh" start; then
        err "原生服务启动失败 — 检查 logs/mongod.log 或 logs/redis.log"
        err "首次部署请先运行: ./scripts/setup-native.sh"
        exit 1
    fi

    # 2. Backend (uvicorn)
    if is_alive "$BACKEND_PID"; then
        warn "backend 已在运行 (PID $(cat "$BACKEND_PID"))"
    elif port_in_use 54301; then
        warn "端口 54301 已被占用（非本脚本启动），跳过 backend"
    elif [ ! -x .venv/bin/uvicorn ]; then
        err "缺 .venv/bin/uvicorn——先按 docs/USAGE.md 装环境"; exit 1
    else
        log "启动 backend (uvicorn 127.0.0.1:54301)..."
        nohup .venv/bin/uvicorn app.main:app \
            --host 127.0.0.1 --port 54301 --reload \
            > "$BACKEND_LOG" 2>&1 &
        echo $! > "$BACKEND_PID"
        log "backend PID $(cat "$BACKEND_PID") log=$BACKEND_LOG"
    fi

    # 3. Frontend (vite dev)
    if is_alive "$FRONTEND_PID"; then
        warn "frontend 已在运行 (PID $(cat "$FRONTEND_PID"))"
    elif port_in_use 54300; then
        warn "端口 54300 已被占用（非本脚本启动），跳过 frontend"
    elif [ ! -d frontend/node_modules ]; then
        err "缺 frontend/node_modules——先 cd frontend && npm install"; exit 1
    else
        log "启动 frontend (vite dev 127.0.0.1:54300)..."
        (
            cd frontend
            nohup npm run dev -- --port 54300 > "../$FRONTEND_LOG" 2>&1 &
            echo $! > "../$FRONTEND_PID"
        )
        log "frontend PID $(cat "$FRONTEND_PID") log=$FRONTEND_LOG"
    fi

    echo ""
    log "等 3s 让服务就绪..."
    sleep 3
    cmd_status
}

cmd_stop() {
    stop_with_children "$FRONTEND_PID" "frontend"
    stop_with_children "$BACKEND_PID" "backend"

    log "停原生服务 (mongo + redis)..."
    bash "$(dirname "$0")/local-services.sh" stop || true

    log "全部已停"
}

cmd_restart() {
    cmd_stop
    sleep 1
    cmd_start
}

cmd_status() {
    echo "=== 端口监听 ==="
    local ports=("54300:frontend" "54301:backend" "54302:mongodb" "54303:redis")
    for entry in "${ports[@]}"; do
        local port="${entry%%:*}"
        local name="${entry##*:}"
        if port_in_use "$port"; then
            echo "  ${GRN}✓${NC} :$port  $name"
        else
            echo "  ${RED}✗${NC} :$port  $name (未监听)"
        fi
    done
    echo ""

    echo "=== 进程状态 ==="
    if is_alive "$BACKEND_PID"; then
        echo "  ${GRN}✓${NC} backend  PID $(cat "$BACKEND_PID")"
    else
        echo "  ${RED}✗${NC} backend  未运行"
    fi
    if is_alive "$FRONTEND_PID"; then
        echo "  ${GRN}✓${NC} frontend PID $(cat "$FRONTEND_PID")"
    else
        echo "  ${RED}✗${NC} frontend 未运行"
    fi
    echo ""

    echo "=== 原生服务 (mongo + redis) ==="
    bash "$(dirname "$0")/local-services.sh" status 2>/dev/null | tail -n +2 || echo "  local-services.sh 不可用"
    echo ""

    echo "=== 访问地址 ==="
    echo "  frontend: http://127.0.0.1:54300"
    echo "  backend:  http://127.0.0.1:54301"
    echo "  health:   http://127.0.0.1:54301/api/health"
}

cmd_logs() {
    local component="${1:-backend}"
    case "$component" in
        backend|b)
            [ -f "$BACKEND_LOG" ] || { err "$BACKEND_LOG 不存在（backend 未启）"; exit 1; }
            tail -f "$BACKEND_LOG"
            ;;
        frontend|f)
            [ -f "$FRONTEND_LOG" ] || { err "$FRONTEND_LOG 不存在（frontend 未启）"; exit 1; }
            tail -f "$FRONTEND_LOG"
            ;;
        *)
            err "未知组件：$component（用 backend|b 或 frontend|f）"
            exit 1
            ;;
    esac
}

usage() {
    cat <<EOF
Usage: scripts/dev.sh <command>

Commands:
  start | up            启动原生 mongo+redis + backend + frontend
  stop  | down          停止全部（含原生服务）
  restart               stop + start
  status | ps           端口/进程/服务状态（默认）
  logs [b|f]            tail backend (默认) 或 frontend log

依赖（首次部署需先装）：
  ./scripts/setup-native.sh    # 装 mongodb-community@7.0 + redis + mongosh，初始化 mongo 用户

State：.dev/{backend,frontend}.{pid,log}（gitignored）
端口段位 54300-54309（loopback only，OpenSpec spec: loopback-binding-policy）

示例：
  scripts/dev.sh start          # 启全栈，看 status
  scripts/dev.sh logs b         # tail backend log（Ctrl-C 退出）
  scripts/dev.sh restart        # 改了代码 backend 不 hot-reload 时用
  scripts/dev.sh stop           # 关机前清干净

提示：
  - backend 用 --reload，编辑 app/ 自动重启；frontend vite HMR 自动刷新
  - 端口被外部占用时本脚本 skip 不强行抢
  - 原生 mongo+redis 由 scripts/local-services.sh 管理，首次部署先跑 setup-native.sh
EOF
}

case "${1:-status}" in
    start|up)        cmd_start ;;
    stop|down)       cmd_stop ;;
    restart)         cmd_restart ;;
    status|ps)       cmd_status ;;
    logs)            shift; cmd_logs "${1:-backend}" ;;
    -h|--help|help)  usage ;;
    *)               err "未知命令：$1"; usage; exit 1 ;;
esac
