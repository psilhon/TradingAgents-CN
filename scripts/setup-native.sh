#!/usr/bin/env bash
# scripts/setup-native.sh — 一次性安装/初始化本地部署模式所需的原生依赖
#
# 用法：./scripts/setup-native.sh
#
# 行为：
# 1. 检查 Homebrew，未装则提示用户先装
# 2. 检查并安装 mongodb-community@7.0、redis、mongosh（已装则跳过）
# 3. 创建 data/mongodb、data/redis、logs、.dev 目录
# 4. 初次运行时，临时启动 mongo（无认证）创建 admin/业务 user，然后停掉
# 5. 提示用户后续用 scripts/local-services.sh start 启动正式服务
#
# 设计要点：
# - 与已有的 docker 安装并存，不冲突（端口段位 54302/54303，数据路径项目本地）
# - 不使用 brew services（保持多实例隔离）
# - 凭据与 docker-compose 历史一致（admin/tradingagents123），业务代码无需改

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'
log()  { printf "${G}[setup]${N} %s\n" "$*"; }
warn() { printf "${Y}[setup]${N} %s\n" "$*"; }
err()  { printf "${R}[setup]${N} %s\n" "$*" >&2; }

MONGOD_BIN="/opt/homebrew/opt/mongodb-community@7.0/bin/mongod"
MONGOSH_BIN="/opt/homebrew/bin/mongosh"
REDIS_SERVER_BIN="/opt/homebrew/opt/redis/bin/redis-server"
MONGO_PORT=54302
REDIS_PORT=54303
MONGO_DB="tradingagentscn"
MONGO_ADMIN_USER="admin"
MONGO_ADMIN_PASS="tradingagents123"
MONGO_APP_USER="tradingagents"
MONGO_APP_PASS="tradingagents123"

# ===== 1. Homebrew =====
if ! command -v brew >/dev/null 2>&1; then
  err "未安装 Homebrew。请先运行："
  err "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
  exit 1
fi
log "Homebrew $(brew --version | head -1)"

# ===== 2. 检查端口（仅看 54302/54303，与系统其他 mongo/redis 不冲突） =====
port_busy() {
  local port=$1
  [ "$(lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')" -gt 0 ]
}
for p in $MONGO_PORT $REDIS_PORT; do
  if port_busy "$p"; then
    err "端口 $p 被占用（本项目独占段位 54300-54309）："
    lsof -nP -iTCP:"$p" -sTCP:LISTEN 2>/dev/null | tail -n +2 | head -2 >&2
    err "请释放后重试"
    exit 1
  fi
done
# 提示：default port 上的 mongo/redis 不影响本项目
for p in 27017 6379; do
  if port_busy "$p"; then
    name=$([ "$p" = "27017" ] && echo MongoDB || echo Redis)
    warn "端口 $p 有 $name 在跑（其他项目/brew services），本项目用 ${p/27017/$MONGO_PORT}${p/6379/$REDIS_PORT}，不会冲突"
  fi
done

# ===== 3. 安装 binary =====
brew tap mongodb/brew >/dev/null 2>&1 || true
if ! brew list mongodb-community@7.0 >/dev/null 2>&1; then
  log "安装 mongodb-community@7.0 ..."
  brew install mongodb-community@7.0
else
  log "mongodb-community@7.0 已装 ✓"
fi
if ! brew list redis >/dev/null 2>&1; then
  log "安装 redis ..."
  brew install redis
else
  log "redis 已装 ✓"
fi
if ! brew list mongosh >/dev/null 2>&1; then
  log "安装 mongosh ..."
  brew install mongosh
else
  log "mongosh 已装 ✓"
fi

# ===== 4. 创建目录 =====
mkdir -p data/mongodb data/redis logs .dev config
log "项目目录就绪：data/, logs/, .dev/, config/"

# ===== 5. 检查 config 文件存在 =====
[ -f config/mongod.conf ] || { err "缺失 config/mongod.conf（应已 commit 到 repo）"; exit 1; }
[ -f config/redis.conf  ] || { err "缺失 config/redis.conf";  exit 1; }

# ===== 6. 初次运行时创建 mongo 用户 =====
# 判断标准：data/mongodb/ 是否已有数据
if [ -z "$(ls -A data/mongodb 2>/dev/null)" ]; then
  log "首次部署，临时启动 mongod 创建用户 ..."
  "$MONGOD_BIN" --dbpath ./data/mongodb \
    --port "$MONGO_PORT" --bind_ip 127.0.0.1 \
    --logpath ./logs/mongod.init.log --fork >/dev/null
  sleep 2
  "$MONGOSH_BIN" --quiet --port "$MONGO_PORT" <<EOF
use admin
db.createUser({
  user: "$MONGO_ADMIN_USER",
  pwd: "$MONGO_ADMIN_PASS",
  roles: [{ role: "root", db: "admin" }]
})
use $MONGO_DB
db.createUser({
  user: "$MONGO_APP_USER",
  pwd: "$MONGO_APP_PASS",
  roles: [{ role: "readWrite", db: "$MONGO_DB" }]
})
db.createCollection("system_config")
EOF
  log "用户已创建：admin / $MONGO_APP_USER (密码 $MONGO_ADMIN_PASS)"
  # 关掉临时 mongo（用 mongosh 因为没装 mongod CLI shutdown）
  "$MONGOSH_BIN" --quiet --port "$MONGO_PORT" \
    -u "$MONGO_ADMIN_USER" -p "$MONGO_ADMIN_PASS" --authenticationDatabase admin \
    --eval "db.adminCommand({shutdown: 1})" 2>/dev/null || true
  sleep 1
  log "临时 mongod 已停"
else
  log "data/mongodb/ 已有数据，跳过用户创建"
fi

# ===== 7. 创建默认 admin 业务用户（应用层登录，独立于 mongo DB 用户）=====
# 启动正式 mongod 临时一次，插入 users 集合记录后再关
log "检查/创建默认 admin 业务用户 ..."
"$MONGOD_BIN" --config ./config/mongod.conf &
MONGOD_PID=$!
sleep 2
.venv/bin/python3 - <<EOF
import hashlib, sys
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId

URI = "mongodb://$MONGO_ADMIN_USER:$MONGO_ADMIN_PASS@127.0.0.1:$MONGO_PORT/$MONGO_DB?authSource=admin"
db = MongoClient(URI)["$MONGO_DB"]
if db["users"].find_one({"username": "admin"}):
    print("  ✓ admin 业务用户已存在，跳过")
    sys.exit(0)
db["users"].insert_one({
    "_id": ObjectId(),
    "username": "admin",
    "email": "admin@example.com",
    "hashed_password": hashlib.sha256(b"admin123").hexdigest(),
    "is_active": True,
    "is_admin": True,
    "role": "admin",
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow(),
})
print("  ✓ 已创建 admin/admin123 业务用户")
EOF
# 关临时 mongod
"$MONGOSH_BIN" --quiet --port "$MONGO_PORT" \
  -u "$MONGO_ADMIN_USER" -p "$MONGO_ADMIN_PASS" --authenticationDatabase admin \
  --eval "db.adminCommand({shutdown: 1})" 2>/dev/null || true
wait $MONGOD_PID 2>/dev/null || true

# ===== 8. 完成提示 =====
cat <<EOF

${G}✅ 本地部署模式初始化完成${N}

下一步：
  ./scripts/local-services.sh start    # 启动 mongodb + redis
  just up                              # 启动全栈（如 dev.sh 已切到 native）
  http://127.0.0.1:54301/api/health    # 验证后端

凭据：
  Web 登录         admin / admin123                  ← 应用层（users 集合）
  MongoDB DB       admin / $MONGO_ADMIN_PASS         ← 127.0.0.1:$MONGO_PORT
                   $MONGO_APP_USER / $MONGO_APP_PASS @ $MONGO_DB
  Redis            密码 tradingagents123              ← 127.0.0.1:$REDIS_PORT

特点：
  - 不使用 brew services，PID 由项目自管，多实例可并存
  - 数据存项目内 data/mongodb 和 data/redis
  - 系统/其他项目已有的 mongo/redis (27017/6379) 不受影响
EOF
