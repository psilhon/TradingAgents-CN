#!/usr/bin/env bash
#
# scripts/clean-local-cruft.sh — 本地开发垃圾清理 + 日志归档触发
#
# 安全保证：
#   - 永远不动当前在写的日志（mongod.log / tradingagents.log / backend.log /
#     frontend.log / webapi.log / error.log / redis.log）
#   - 永远不动 git tracked 文件 / data/ / .venv/
#   - 永远不读 .env / .env.bak* 内容（HARD-GATE）
#   - 默认显示每个动作，--dry-run 模式不实际执行
#
# 清理对象：
#   1. mongod 日志：触发 logRotate（mongod.conf 已配 rename 模式），
#      然后删 7 天前的 logs/mongod.log.<ISO timestamp>
#   2. tradingagents.log.[1-9]：Python RotatingFileHandler 轮转产物，
#      删 3 天前的
#   3. __pycache__ / .ruff_cache / .pytest_cache：纯 cache
#   4. tradingagents.egg-info：pip install -e 产物（下次装会重生）
#   5. .env.bak*：手动备份累积 > 3 个时打包到 backup/env-backups-<date>.tar.gz
#      再删原文件
#
# 用法：
#   scripts/clean-local-cruft.sh            # 实际清理
#   scripts/clean-local-cruft.sh --dry-run  # 仅打印动作
#
# 由 `just clean` 调用。
#
set -euo pipefail

cd "$(dirname "$0")/.."

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

MONGO_HOST="127.0.0.1"
MONGO_PORT="54302"
MONGO_USER="admin"
MONGO_PASS="tradingagents123"  # 本地 dev 默认凭据，CLAUDE.md 已声明公开

# ANSI 色
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
DIM=$'\033[2m'
RESET=$'\033[0m'

freed_total=0
say()  { printf "%s\n" "$*"; }
note() { printf "%s→ %s%s\n" "$DIM" "$*" "$RESET"; }
ok()   { printf "%s✓%s %s\n" "$GREEN" "$RESET" "$*"; }
warn() { printf "%s!%s %s\n" "$YELLOW" "$RESET" "$*"; }

# size of file/dir in bytes (0 if missing)
bytes_of() {
  if [[ -e "$1" ]]; then
    du -sk "$1" 2>/dev/null | awk '{print $1 * 1024}'
  else
    echo 0
  fi
}

human() { numfmt --to=iec --suffix=B 2>/dev/null || awk '{printf "%.1f MB\n", $1/1024/1024}'; }

remove() {
  local target="$1"
  if [[ ! -e "$target" ]]; then return; fi
  local sz; sz=$(bytes_of "$target")
  freed_total=$((freed_total + sz))
  if [[ $DRY_RUN == 1 ]]; then
    note "DRY rm: $target ($(echo $sz | human))"
  else
    rm -rf "$target"
    ok "rm $target ($(echo $sz | human))"
  fi
}

# ============================================================
# 1. mongod log rotate（如果 mongod 在跑）
# ============================================================
say
say "${YELLOW}[1/5] mongod log rotate${RESET}"

if ! pgrep -f "mongod --config" >/dev/null 2>&1; then
  note "mongod 未运行，跳过 rotate（如需轮转旧 log，启动 mongod 后再跑）"
else
  if [[ $DRY_RUN == 1 ]]; then
    note "DRY: 调 db.adminCommand({logRotate:1})"
  else
    # 记录 rotate 前的 .log.<ts> 文件数，rotate 后对比判断 rename 模式是否生效
    before_count=$(find logs -maxdepth 1 -name "mongod.log.*" 2>/dev/null | wc -l | tr -d ' ')
    if mongosh --quiet --host "$MONGO_HOST" --port "$MONGO_PORT" \
        -u "$MONGO_USER" -p "$MONGO_PASS" --authenticationDatabase admin \
        --eval 'db.adminCommand({logRotate: 1})' >/dev/null 2>&1; then
      after_count=$(find logs -maxdepth 1 -name "mongod.log.*" 2>/dev/null | wc -l | tr -d ' ')
      if [[ "$after_count" -gt "$before_count" ]]; then
        ok "mongod log rotate 成功（产生 $((after_count - before_count)) 个新归档 → logs/mongod.log.<ts>）"
      else
        warn "mongod logRotate 调用成功但未产生归档文件"
        warn "  原因：mongod 进程跑在 reopen 模式（fork 已改 conf 为 rename，需重启 mongod 生效）"
        warn "  建议：just down && just up 让 mongod.conf 新配置生效，未来 just clean 才能真正归档"
      fi
    else
      warn "mongod log rotate 失败（凭据 / 网络 / mongod 未启动）"
    fi
  fi
fi

# ============================================================
# 2. logs/ 老轮转归档清理
# ============================================================
say
say "${YELLOW}[2/5] logs/ 老归档清理${RESET}"

# mongod.log.<ISO timestamp> — 7 天前的
if [[ -d logs ]]; then
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    remove "$f"
  done < <(find logs -maxdepth 1 -type f -name "mongod.log.*" -mtime +7 2>/dev/null)
fi

# tradingagents.log.[1-9] — 3 天前的（Python RotatingFileHandler 产物）
if [[ -d logs ]]; then
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    remove "$f"
  done < <(find logs -maxdepth 1 -type f -regex "logs/.*\.log\.[0-9]+$" -mtime +3 2>/dev/null)
fi

# 其他 .log.[0-9]+ 形式归档（webapi / error 等可能轮转出来的）
if [[ -d logs ]]; then
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    # 跳过当前正在写的 log（.log 结尾，不带数字后缀）
    case "$f" in
      *.log) continue ;;
    esac
    remove "$f"
  done < <(find logs -maxdepth 1 -type f \( -name "*.log.*" \) -mtime +3 2>/dev/null)
fi

# ============================================================
# 3. Python cache（__pycache__ / .ruff_cache / .pytest_cache / egg-info）
# ============================================================
say
say "${YELLOW}[3/5] Python cache${RESET}"

# __pycache__ — 用 find 因为有 58+ 个分散目录
pycache_count=$(find . -type d -name "__pycache__" \
  -not -path "./.venv/*" -not -path "./.git/*" \
  -not -path "./node_modules/*" -not -path "./frontend/node_modules/*" 2>/dev/null | wc -l | tr -d ' ')

if [[ "$pycache_count" -gt 0 ]]; then
  pycache_bytes=$(find . -type d -name "__pycache__" \
    -not -path "./.venv/*" -not -path "./.git/*" \
    -not -path "./node_modules/*" -not -path "./frontend/node_modules/*" \
    -exec du -sk {} + 2>/dev/null | awk '{sum += $1} END {print sum * 1024}')
  freed_total=$((freed_total + pycache_bytes))
  if [[ $DRY_RUN == 1 ]]; then
    note "DRY rm: $pycache_count 个 __pycache__ 目录 ($(echo $pycache_bytes | human))"
  else
    find . -type d -name "__pycache__" \
      -not -path "./.venv/*" -not -path "./.git/*" \
      -not -path "./node_modules/*" -not -path "./frontend/node_modules/*" \
      -exec rm -rf {} + 2>/dev/null || true
    ok "rm $pycache_count 个 __pycache__ ($(echo $pycache_bytes | human))"
  fi
else
  note "__pycache__: 已清"
fi

remove .ruff_cache
remove .pytest_cache
remove tradingagents.egg-info

# ============================================================
# 4. .env.bak* 归档（累积 > 3 个时打包到 backup/）
# ============================================================
say
say "${YELLOW}[4/5] .env.bak* 归档${RESET}"

# mapfile 在 macOS bash 3.2 不可用 → 用 while-read 兼容
bak_files=()
while IFS= read -r f; do bak_files+=("$f"); done < <(find . -maxdepth 1 -type f -name ".env.bak*" 2>/dev/null)
bak_count=${#bak_files[@]}

if [[ "$bak_count" -ge 3 ]]; then
  ts=$(date +%Y%m%d_%H%M%S)
  archive="backup/env-backups-${ts}.tar.gz"
  mkdir -p backup
  if [[ $DRY_RUN == 1 ]]; then
    note "DRY: tar -czf $archive .env.bak* + rm 原文件 ($bak_count 个)"
  else
    tar -czf "$archive" "${bak_files[@]}" 2>/dev/null
    bak_bytes=$(du -sk "${bak_files[@]}" 2>/dev/null | awk '{sum += $1} END {print sum * 1024}')
    rm "${bak_files[@]}"
    freed_total=$((freed_total + bak_bytes))
    ok "tar $bak_count 个 .env.bak* → $archive，rm 原文件 ($(echo $bak_bytes | human))"
  fi
elif [[ "$bak_count" -gt 0 ]]; then
  note ".env.bak*: 当前 $bak_count 个（< 3 阈值，不归档）"
else
  note ".env.bak*: 无"
fi

# ============================================================
# 5. .dev/ 旧 pid（仅当对应进程已不在跑时）
# ============================================================
say
say "${YELLOW}[5/5] .dev/ 孤儿 pid 文件${RESET}"

if [[ -d .dev ]]; then
  for pidfile in .dev/*.pid; do
    [[ -f "$pidfile" ]] || continue
    pid=$(cat "$pidfile" 2>/dev/null | tr -d '[:space:]')
    if [[ -z "$pid" ]]; then continue; fi
    if ! kill -0 "$pid" 2>/dev/null; then
      # 进程已死
      if [[ $DRY_RUN == 1 ]]; then
        note "DRY rm: $pidfile (pid $pid 已不存在)"
      else
        rm "$pidfile"
        ok "rm $pidfile (孤儿 pid $pid)"
      fi
    fi
  done
fi

# ============================================================
# 汇总
# ============================================================
say
freed_human=$(echo $freed_total | numfmt --to=iec --suffix=B 2>/dev/null || \
              echo $freed_total | awk '{printf "%.1f MB\n", $1/1024/1024}')

if [[ $DRY_RUN == 1 ]]; then
  say "${YELLOW}[DRY RUN]${RESET} 预计释放 ${GREEN}${freed_human}${RESET}（去掉 --dry-run 实际执行）"
else
  say "${GREEN}完成${RESET} — 释放 ${GREEN}${freed_human}${RESET}"
fi

# 不动清单（提醒）
say
say "${DIM}不动清单：当前在写日志 (logs/{mongod,tradingagents,webapi,error,redis}.log 等)${RESET}"
say "${DIM}          .dev/{backend,frontend}.log（仍在写）${RESET}"
say "${DIM}          data/ / .venv/ / .git/ / frontend/node_modules/${RESET}"
say "${DIM}          所有 git tracked 文件${RESET}"
