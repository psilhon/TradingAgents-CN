#!/usr/bin/env bash
# scripts/local-services.sh — TradingAgents-CN 本地部署模式服务编排
#
# 替代 docker compose，直接以原生进程管理 MongoDB + Redis。
#
# 设计要点（详见 docs/local-deployment.md）：
# - 多版本/多实例隔离：通过绝对路径调 binary，避免 PATH 冲突
# - 不使用 brew services（那会接管全局 launchd 实例，无法多项目并存）
# - PID + 日志 + 数据全部在项目目录，与系统/其他项目零冲突
# - loopback 铁律：mongo bind 54302、redis bind 54303，仅 127.0.0.1
#
# 用法：
#   scripts/local-services.sh start
#   scripts/local-services.sh stop
#   scripts/local-services.sh status
#   scripts/local-services.sh logs mongo|redis [-f]

set -euo pipefail

# 项目根目录（脚本可在任意 cwd 调用）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Binary 路径（绝对路径，避免多版本干扰）
MONGOD_BIN="/opt/homebrew/opt/mongodb-community@7.0/bin/mongod"
MONGOSH_BIN="/opt/homebrew/bin/mongosh"
REDIS_SERVER_BIN="/opt/homebrew/opt/redis/bin/redis-server"
REDIS_CLI_BIN="/opt/homebrew/opt/redis/bin/redis-cli"

# 配置文件
MONGOD_CONF="$PROJECT_ROOT/config/mongod.conf"
REDIS_CONF="$PROJECT_ROOT/config/redis.conf"

# PID 文件目录
PID_DIR="$PROJECT_ROOT/.dev"
MONGOD_PID="$PID_DIR/mongod.pid"
REDIS_PID="$PID_DIR/redis.pid"

# 端口（与配置文件一致，启动前预检冲突）
MONGO_PORT=54302
REDIS_PORT=54303

# Redis 密码（与配置一致，健康检查用）
REDIS_PASS="tradingagents123"

# 颜色
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'
log()  { printf "${G}[svc]${N} %s\n" "$*"; }
warn() { printf "${Y}[svc]${N} %s\n" "$*"; }
err()  { printf "${R}[svc]${N} %s\n" "$*" >&2; }

# ===== 工具函数 =====

# 端口监听检测（返回 0 表示有进程监听）
port_listening() {
  local port=$1
  local count
  count=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')
  [ "$count" -gt 0 ]
}

# PID 是否存活
pid_alive() {
  local pid=$1
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

# 等端口监听（最多 N 秒）
wait_port() {
  local port=$1 timeout=$2 name=$3
  local i=0
  while [ "$i" -lt "$timeout" ]; do
    if port_listening "$port"; then
      log "$name 端口 $port 就绪"
      return 0
    fi
    sleep 1
    i=$((i + 1))
  done
  err "$name 端口 $port 在 ${timeout}s 内未就绪"
  return 1
}

# 优雅停止 PID 进程（先 SIGTERM，超时后 SIGKILL）
graceful_kill() {
  local pid=$1 name=$2
  if ! pid_alive "$pid"; then return 0; fi
  kill -TERM "$pid" 2>/dev/null || true
  local i=0
  while [ "$i" -lt 15 ]; do
    if ! pid_alive "$pid"; then
      log "$name (PID $pid) 已优雅退出"
      return 0
    fi
    sleep 0.5
    i=$((i + 1))
  done
  warn "$name 未优雅退出，发 SIGKILL"
  kill -KILL "$pid" 2>/dev/null || true
}

# ===== 启动前预检 =====

precheck() {
  # binary 检测
  [ -x "$MONGOD_BIN" ] || {
    err "未找到 mongod: $MONGOD_BIN"
    err "请先运行: brew install mongodb-community@7.0"
    exit 1
  }
  [ -x "$REDIS_SERVER_BIN" ] || {
    err "未找到 redis-server: $REDIS_SERVER_BIN"
    err "请先运行: brew install redis"
    exit 1
  }
  # 配置文件
  [ -f "$MONGOD_CONF" ] || { err "缺失 $MONGOD_CONF"; exit 1; }
  [ -f "$REDIS_CONF" ]  || { err "缺失 $REDIS_CONF";  exit 1; }
  # 目录
  mkdir -p "$PID_DIR" "$PROJECT_ROOT/data/mongodb" "$PROJECT_ROOT/data/redis" "$PROJECT_ROOT/logs"
}

# 端口冲突预检（启动前调，已被本项目占用则 skip 该服务）
port_conflict_check() {
  local port=$1 name=$2 our_pid_file=$3
  if ! port_listening "$port"; then return 0; fi
  # 端口被占，但如果是我们自己的 PID 在跑则 OK
  if [ -f "$our_pid_file" ]; then
    local our_pid; our_pid=$(cat "$our_pid_file" 2>/dev/null || true)
    if pid_alive "$our_pid"; then
      warn "$name 已在跑 (PID $our_pid, port $port)，跳过启动"
      return 1  # 1 表示 already running, skip
    fi
  fi
  # 端口被其他进程占用 → 致命
  err "端口 $port 被占用，$name 无法启动："
  lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | tail -n +2 | head -3 >&2
  err "请释放该端口或停止占用进程"
  exit 1
}

# ===== 启动 =====

start_mongo() {
  if ! port_conflict_check "$MONGO_PORT" mongodb "$MONGOD_PID"; then return 0; fi
  log "启动 mongodb ($MONGOD_BIN)..."
  nohup "$MONGOD_BIN" --config "$MONGOD_CONF" >> "$PROJECT_ROOT/logs/mongod.stdout.log" 2>&1 &
  local pid=$!
  echo "$pid" > "$MONGOD_PID"
  log "mongod PID=$pid log=logs/mongod.log"
  wait_port "$MONGO_PORT" 30 mongodb || { stop_mongo; exit 1; }
}

start_redis() {
  if ! port_conflict_check "$REDIS_PORT" redis "$REDIS_PID"; then return 0; fi
  log "启动 redis ($REDIS_SERVER_BIN)..."
  # redis 配置文件里的相对路径（logfile / dir）经 nohup 启动时 cwd 不一致，
  # 用 CLI 参数显式传绝对路径覆盖
  nohup "$REDIS_SERVER_BIN" "$REDIS_CONF" \
    --logfile "$PROJECT_ROOT/logs/redis.log" \
    --dir "$PROJECT_ROOT/data/redis" \
    >> "$PROJECT_ROOT/logs/redis.stdout.log" 2>&1 &
  local pid=$!
  echo "$pid" > "$REDIS_PID"
  log "redis PID=$pid log=logs/redis.log"
  wait_port "$REDIS_PORT" 10 redis || { stop_redis; exit 1; }
}

# ===== 停止 =====

stop_mongo() {
  if [ -f "$MONGOD_PID" ]; then
    local pid; pid=$(cat "$MONGOD_PID" 2>/dev/null || true)
    log "停 mongodb (PID $pid)..."
    graceful_kill "$pid" mongodb
    rm -f "$MONGOD_PID"
  else
    log "mongodb 未运行"
  fi
}

stop_redis() {
  if [ -f "$REDIS_PID" ]; then
    local pid; pid=$(cat "$REDIS_PID" 2>/dev/null || true)
    log "停 redis (PID $pid)..."
    graceful_kill "$pid" redis
    rm -f "$REDIS_PID"
  else
    log "redis 未运行"
  fi
}

# ===== 状态 =====

status() {
  echo "=== 原生服务状态 ==="
  for svc_pair in "mongodb:$MONGOD_PID:$MONGO_PORT" "redis:$REDIS_PID:$REDIS_PORT"; do
    local name="${svc_pair%%:*}"
    local rest="${svc_pair#*:}"
    local pid_file="${rest%:*}"
    local port="${rest##*:}"
    if [ -f "$pid_file" ]; then
      local pid; pid=$(cat "$pid_file" 2>/dev/null || true)
      if pid_alive "$pid"; then
        if port_listening "$port"; then
          printf "  ${G}✓${N} %-9s PID=%-7s port=%-5s\n" "$name" "$pid" "$port"
        else
          printf "  ${Y}!${N} %-9s PID=%-7s port=%-5s (PID存活但端口未监听)\n" "$name" "$pid" "$port"
        fi
      else
        printf "  ${R}✗${N} %-9s (stale PID file)\n" "$name"
      fi
    else
      printf "  ${R}✗${N} %-9s 未运行\n" "$name"
    fi
  done
}

# ===== 日志 =====

show_logs() {
  local svc=$1; shift
  local follow=""
  for arg in "$@"; do
    [ "$arg" = "-f" ] && follow="-f"
  done
  case "$svc" in
    mongo|mongodb)
      tail -n 50 $follow "$PROJECT_ROOT/logs/mongod.log"
      ;;
    redis)
      tail -n 50 $follow "$PROJECT_ROOT/logs/redis.log"
      ;;
    *)
      err "未知服务: $svc，可选: mongo | redis"
      exit 1
      ;;
  esac
}

# ===== 健康检查（导出供 dev.sh 用） =====

health_check() {
  local ok=1
  if "$MONGOSH_BIN" --quiet --port "$MONGO_PORT" \
       --eval "db.adminCommand({ping: 1}).ok" >/dev/null 2>&1; then
    log "mongodb ping ok"
  else
    err "mongodb ping 失败"
    ok=0
  fi
  if "$REDIS_CLI_BIN" -p "$REDIS_PORT" -a "$REDIS_PASS" --no-auth-warning ping 2>/dev/null | grep -q PONG; then
    log "redis ping ok"
  else
    err "redis ping 失败"
    ok=0
  fi
  [ "$ok" = "1" ]
}

# ===== 主入口 =====

case "${1:-}" in
  start)
    precheck
    start_mongo
    start_redis
    log "全部原生服务已启动"
    ;;
  stop)
    stop_redis
    stop_mongo
    log "全部原生服务已停"
    ;;
  restart)
    stop_redis; stop_mongo
    sleep 1
    precheck; start_mongo; start_redis
    ;;
  status)
    status
    ;;
  health)
    health_check
    ;;
  logs)
    shift
    show_logs "$@"
    ;;
  *)
    cat <<EOF
用法: $(basename "$0") <command>

命令:
  start     启动 mongodb + redis（原生进程，PID 文件管理）
  stop      优雅停止两个服务
  restart   stop + start
  status    显示 PID/端口状态
  health    通过 mongosh/redis-cli ping 验证连接
  logs <mongo|redis> [-f]   tail 日志（-f 跟随）
EOF
    exit 1
    ;;
esac
