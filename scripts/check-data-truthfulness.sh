#!/usr/bin/env bash
# capability data-quality-gate Requirement 3 + data-truthfulness-enforcement change.
#
# Pre-commit grep 黑名单：阻止合成数据 / null-as-0 兜底 / mock 占位再次溜进
# Dashboard / Stocks / DailyRecommendation / PaperTrading 等数据展示视图。
#
# 豁免：违规行同行或前一行带 `// data-truthfulness:allow reason: <理由>` 注释
# 自动放行，强制 git blame 留痕。
#
# 用法：
#   scripts/check-data-truthfulness.sh                   # 检查全部受保护目录
#   scripts/check-data-truthfulness.sh <file> [<file>]   # 检查指定文件（pre-commit 用）

set -euo pipefail

# 受保护路径（前端数据展示视图 + 顶部 layout）
PROTECTED_PATHS=(
    "frontend/src/views/Dashboard"
    "frontend/src/views/Stocks"
    "frontend/src/views/DailyRecommendation"
    "frontend/src/views/PaperTrading"
    "frontend/src/views/Favorites"
    "frontend/src/components/Layout"
)

# 违规模式（ERE，跨平台 grep -E 兼容）
#
# 设计原则：低误报 + 高真阳。只拦 baseline 接近 0 的"确凿造假"信号。
# `|| 0` 这类粗匹配在金额兜底等合理场景下误报率太高（PaperTrading 视图实测 24 处
# 全是合理金额兜底）—— 这种留给 spec 文字 + review，不进 hook。
PATTERNS=(
    '\b(mockTrend|strSeed|heroTrend)\b'                  # V1+V2 合成 sparkline 残留
    'Math\.random\(\)'                                    # 随机数（合成 fake 数据的强信号）
    '(演示数据|占位数据|未接.*API|示例数据|假数据|fake data|placeholder data)'
)

PATTERN_DESCRIPTIONS=(
    "V1+V2 合成 sparkline 生成器（mockTrend/strSeed/heroTrend）"
    "Math.random()（合成数据强信号）"
    "中文/英文 mock 占位文案"
)

# 构造文件列表
declare -a FILES
if [[ $# -gt 0 ]]; then
    FILES=("$@")
else
    # 默认扫全部受保护路径
    while IFS= read -r f; do
        FILES+=("$f")
    done < <(find "${PROTECTED_PATHS[@]}" -type f \( -name "*.vue" -o -name "*.ts" -o -name "*.tsx" -o -name "*.js" \) 2>/dev/null)
fi

if [[ ${#FILES[@]} -eq 0 ]]; then
    exit 0
fi

VIOLATIONS=0

for f in "${FILES[@]}"; do
    # 只检查受保护路径下的文件
    in_scope=0
    for p in "${PROTECTED_PATHS[@]}"; do
        if [[ "$f" == "$p"/* || "$f" == "./$p"/* ]]; then
            in_scope=1
            break
        fi
    done
    [[ $in_scope -eq 0 ]] && continue
    [[ ! -f "$f" ]] && continue

    for i in "${!PATTERNS[@]}"; do
        pat="${PATTERNS[$i]}"
        desc="${PATTERN_DESCRIPTIONS[$i]}"

        # grep 行号 + 内容
        while IFS=: read -r lineno content; do
            [[ -z "$lineno" ]] && continue

            # 豁免检查：同行或前一行带 // data-truthfulness:allow 注释
            same_line_allow=$(echo "$content" | grep -E "data-truthfulness:allow" || true)
            prev_lineno=$((lineno - 1))
            prev_line_allow=""
            if [[ $prev_lineno -ge 1 ]]; then
                prev_line_allow=$(sed -n "${prev_lineno}p" "$f" | grep -E "data-truthfulness:allow" || true)
            fi

            if [[ -n "$same_line_allow" || -n "$prev_line_allow" ]]; then
                continue  # 豁免
            fi

            # 跳过注释行内的 pattern（启发式：行首是 //, /*, *, <!--, 或 # ）
            trimmed=$(echo "$content" | sed -E 's/^[[:space:]]+//')
            case "$trimmed" in
                '//'*|'/*'*|'*'*|'<!--'*|'#'*)
                    continue ;;  # 注释行，不算违规
            esac

            echo "❌ data-truthfulness 违规：$f:$lineno"
            echo "   规则: $desc"
            echo "   行  : $(echo "$content" | sed -E 's/^[[:space:]]+//' | head -c 120)"
            echo "   豁免: 行内或前一行加 '// data-truthfulness:allow reason: <理由>'"
            echo ""
            VIOLATIONS=$((VIOLATIONS + 1))
        done < <(grep -nE "$pat" "$f" || true)
    done
done

if [[ $VIOLATIONS -gt 0 ]]; then
    echo "总计 $VIOLATIONS 处违规。capability data-quality-gate Requirement 3 禁止"
    echo "前端在数据展示层使用合成 / mock / null-as-0 兜底——"
    echo "「数据采集不到时可以不显示，不能胡编乱造糊弄」。"
    exit 1
fi

exit 0
