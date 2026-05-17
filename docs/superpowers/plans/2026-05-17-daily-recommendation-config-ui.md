# 每日推荐配置可视化编辑 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在「每日推荐」页加一个结构化配置编辑界面，可视化展示并编辑 `config/daily_recommendation.json`，带选股结果预览。

**Architecture:** 后端 `daily_recommendation_service` 加 `save_config()`（校验 + 写文件），`daily_recommendation` router 加 GET/PUT `/config` 两个端点；前端新增 `ConfigDrawer.vue` 结构化表单（字段元数据复用 `/api/screening/fields`、预览复用 `/api/screening/enhanced`），挂到 `DailyRecommendation/index.vue` 的「配置」按钮。

**Tech Stack:** FastAPI + Pydantic（后端）、Vue 3 `<script setup>` + Element Plus（前端）、pytest（`unit` marker）。

设计稿：`docs/superpowers/specs/2026-05-17-daily-recommendation-config-ui-design.md`

**关键约定**（实现者必读）：
- `app/` 与 `frontend/` 是专有授权代码，本功能用户已明确授权新增。
- 后端质量门 STRICT：`ruff check` + `ruff format` + `pyright` 必须 0 error 才能 commit；`pytest -m unit` 在 pre-push 阻塞。
- 前端用 `npm run type-check`（`vue-tsc`）验证；eslint 当前环境损坏，不依赖。
- 中文注释 / 中文 commit body，与项目现有风格一致。
- commit 用 `feat:` / `test:` / `docs:` 前缀。

---

## Task 1: 后端 `save_config()` + 配置校验

**Files:**
- Modify: `app/services/daily_recommendation_service.py`
- Test: `tests/services/test_daily_recommendation_config.py`（新建）

**背景**：`daily_recommendation_service.py` 已有 `load_config()`、模块级 `_CONFIG_PATH`、`_SAFE_DEFAULT`。本任务加 `save_config()` 与校验，sync 函数（无 DB、无 async），便于单元测试。

- [ ] **Step 1: 写失败测试**

新建 `tests/services/test_daily_recommendation_config.py`：

```python
"""每日推荐配置 save_config 校验单元测试。"""
import json

import pytest

from app.services import daily_recommendation_service as drs

pytestmark = pytest.mark.unit


def _valid_config() -> dict:
    return {
        "enabled": True,
        "screening": {
            "conditions": [
                {"field": "pe", "operator": "between", "value": [0, 40]},
                {"field": "roe", "operator": ">=", "value": 2},
            ],
            "order_by": "pe",
            "order_direction": "asc",
            "limit": 5,
        },
        "analysis": {"research_depth": "标准", "market_type": "A股"},
    }


class TestSaveConfigValidation:
    def test_valid_config_written(self, tmp_path, monkeypatch):
        target = tmp_path / "daily_recommendation.json"
        monkeypatch.setattr(drs, "_CONFIG_PATH", target)
        drs.save_config(_valid_config())
        written = json.loads(target.read_text(encoding="utf-8"))
        assert written["screening"]["limit"] == 5
        assert written["screening"]["conditions"][0]["field"] == "pe"

    def test_enabled_must_be_bool(self):
        cfg = _valid_config()
        cfg["enabled"] = "yes"
        with pytest.raises(ValueError, match="enabled"):
            drs.save_config(cfg)

    def test_limit_out_of_range(self):
        cfg = _valid_config()
        cfg["screening"]["limit"] = 0
        with pytest.raises(ValueError, match="limit"):
            drs.save_config(cfg)
        cfg["screening"]["limit"] = 99
        with pytest.raises(ValueError, match="limit"):
            drs.save_config(cfg)

    def test_bad_order_direction(self):
        cfg = _valid_config()
        cfg["screening"]["order_direction"] = "up"
        with pytest.raises(ValueError, match="order_direction"):
            drs.save_config(cfg)

    def test_unknown_condition_field(self):
        cfg = _valid_config()
        cfg["screening"]["conditions"] = [
            {"field": "no_such_field", "operator": ">=", "value": 1}
        ]
        with pytest.raises(ValueError, match="字段"):
            drs.save_config(cfg)

    def test_operator_not_supported_by_field(self):
        cfg = _valid_config()
        # contains 是字符串操作符，不适用于数值字段 pe
        cfg["screening"]["conditions"] = [
            {"field": "pe", "operator": "contains", "value": "x"}
        ]
        with pytest.raises(ValueError, match="操作符"):
            drs.save_config(cfg)

    def test_bad_research_depth(self):
        cfg = _valid_config()
        cfg["analysis"]["research_depth"] = "超深"
        with pytest.raises(ValueError, match="research_depth"):
            drs.save_config(cfg)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/services/test_daily_recommendation_config.py -v`
Expected: FAIL — `AttributeError: module 'app.services.daily_recommendation_service' has no attribute 'save_config'`

- [ ] **Step 3: 实现 `save_config` + `_validate_config`**

在 `app/services/daily_recommendation_service.py` 中，`load_config()` 函数之后插入。先在文件顶部 `_SAFE_DEFAULT` 定义之后加常量：

```python
# save_config 校验用的允许值集合
_VALID_DIRECTIONS = {"asc", "desc"}
_VALID_RESEARCH_DEPTHS = {"快速", "标准", "深度"}
_VALID_MARKET_TYPES = {"A股"}
```

然后在 `load_config()` 之后加：

```python
def _validate_config(cfg: dict[str, Any]) -> None:
    """校验配置结构，非法则抛 ValueError（消息面向用户）。"""
    from app.models.screening import BASIC_FIELDS_INFO, OperatorType

    if not isinstance(cfg, dict):
        raise ValueError("配置必须是一个对象")
    if not isinstance(cfg.get("enabled"), bool):
        raise ValueError("enabled 必须是布尔值")

    screening = cfg.get("screening")
    if not isinstance(screening, dict):
        raise ValueError("screening 必须是一个对象")

    limit = screening.get("limit")
    # bool 是 int 的子类，需显式排除
    if not isinstance(limit, int) or isinstance(limit, bool) or not (1 <= limit <= 20):
        raise ValueError("screening.limit 必须是 1-20 的整数")

    if screening.get("order_direction") not in _VALID_DIRECTIONS:
        raise ValueError("screening.order_direction 必须是 asc 或 desc")

    order_by = screening.get("order_by")
    valid_order_fields = set(BASIC_FIELDS_INFO) | {"market_cap"}
    if not isinstance(order_by, str) or order_by not in valid_order_fields:
        raise ValueError(f"screening.order_by 必须是已知字段名，收到: {order_by!r}")

    conditions = screening.get("conditions")
    if not isinstance(conditions, list):
        raise ValueError("screening.conditions 必须是数组")
    for i, cond in enumerate(conditions, 1):
        if not isinstance(cond, dict):
            raise ValueError(f"条件 {i}: 必须是对象")
        if "value" not in cond:
            raise ValueError(f"条件 {i}: 缺少 value")
        field = cond.get("field")
        if field not in BASIC_FIELDS_INFO:
            raise ValueError(f"条件 {i}: 不支持的字段 {field!r}")
        try:
            op = OperatorType(cond.get("operator"))
        except ValueError:
            raise ValueError(f"条件 {i}: 非法操作符 {cond.get('operator')!r}") from None
        if op not in BASIC_FIELDS_INFO[field].supported_operators:
            raise ValueError(
                f"条件 {i}: 字段 {field!r} 不支持操作符 {op.value!r}"
            )

    analysis = cfg.get("analysis")
    if not isinstance(analysis, dict):
        raise ValueError("analysis 必须是一个对象")
    if analysis.get("research_depth") not in _VALID_RESEARCH_DEPTHS:
        raise ValueError("analysis.research_depth 必须是 快速/标准/深度 之一")
    if analysis.get("market_type") not in _VALID_MARKET_TYPES:
        raise ValueError("analysis.market_type 目前仅支持 A股")


def save_config(cfg: dict[str, Any]) -> None:
    """校验 *cfg* 并写入 config/daily_recommendation.json。

    校验不通过抛 ValueError（router 转 400）。写文件用 ensure_ascii=False
    保持中文可读，与现有文件格式一致。
    """
    _validate_config(cfg)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    logger.info("每日推荐配置已保存: %s", _CONFIG_PATH)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/services/test_daily_recommendation_config.py -v`
Expected: PASS（7 个用例全过）

- [ ] **Step 5: lint + typecheck**

Run: `just lint && just typecheck`
Expected: `ruff` All checks passed；`pyright` 0 errors

- [ ] **Step 6: Commit**

```bash
git add app/services/daily_recommendation_service.py tests/services/test_daily_recommendation_config.py
git commit -m "feat(daily-rec): 加 save_config 配置校验与写入"
```

---

## Task 2: 后端 GET/PUT `/config` 路由端点

**Files:**
- Modify: `app/routers/daily_recommendation.py`

**关键约束**：`daily_recommendation.py` 已有 `@router.get("/{date}")`（路径参数 catch-all）。新加的 `@router.get("/config")` **必须声明在 `@router.get("/{date}")` 之前**，否则 FastAPI 会把 `/config` 当成 `date="config"` 匹配到 `/{date}`。PUT `/config` 与 GET `/{date}` 方法不同、无冲突，但为聚合放一起。

- [ ] **Step 1: 改 import**

把第 16 行：

```python
from app.services.daily_recommendation_service import run_daily_recommendation
```

改为：

```python
from app.services.daily_recommendation_service import (
    load_config,
    run_daily_recommendation,
    save_config,
)
```

- [ ] **Step 2: 插入两个 `/config` 端点**

在 `list_daily_recommendations`（`@router.get("")`）函数结束之后、`get_daily_recommendation`（`@router.get("/{date}")`）函数**之前**，插入：

```python
@router.get("/config", response_model=Dict[str, Any])
async def get_recommendation_config(user: dict = Depends(get_current_user)):
    """读取每日推荐配置（config/daily_recommendation.json）。

    文件缺失 / JSON 损坏时 load_config 返回安全默认（enabled=False），不报错。
    """
    try:
        cfg = load_config()
        return {"success": True, "data": cfg, "message": "配置获取成功"}
    except Exception as e:
        logger.error(f"❌ 获取每日推荐配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config", response_model=Dict[str, Any])
async def update_recommendation_config(
    config: Dict[str, Any],
    user: dict = Depends(get_current_user),
):
    """校验并保存每日推荐配置；校验失败返回 400 + 具体错误。"""
    try:
        save_config(config)
        return {"success": True, "data": config, "message": "配置已保存"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 保存每日推荐配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 3: 验证后端能加载（无语法 / 路由冲突）**

Run: `.venv/bin/python -c "from app.routers.daily_recommendation import router; print([(r.path, list(r.methods)) for r in router.routes])"`
Expected: 输出含 `('/config', ['GET'])` 且排在 `('/{date}', ['GET'])` 之前；含 `('/config', ['PUT'])`

- [ ] **Step 4: lint + typecheck**

Run: `just lint && just typecheck`
Expected: `ruff` All checks passed；`pyright` 0 errors

- [ ] **Step 5: Commit**

```bash
git add app/routers/daily_recommendation.py
git commit -m "feat(daily-rec): 加 GET/PUT /config 配置读写端点"
```

---

## Task 3: 前端 API 封装

**Files:**
- Modify: `frontend/src/api/dailyRecommendation.ts`
- Modify: `frontend/src/api/screening.ts`

- [ ] **Step 1: `dailyRecommendation.ts` 加配置类型与 API**

在 `frontend/src/api/dailyRecommendation.ts` 的 `DailyRecommendationDetail` 接口之后加类型：

```typescript
// 单条筛选条件（对应后端 ScreeningCondition）
export interface ScreeningConditionItem {
  field: string
  operator: string
  value: number | string | Array<number | string>
}

// 每日推荐配置（对应 config/daily_recommendation.json）
export interface DailyRecommendationConfig {
  enabled: boolean
  screening: {
    conditions: ScreeningConditionItem[]
    order_by: string
    order_direction: 'asc' | 'desc'
    limit: number
  }
  analysis: {
    research_depth: string
    market_type: string
  }
}
```

在 `dailyRecommendationApi` 对象里，`run` 之后加两个方法：

```typescript
  /** 读取每日推荐配置 */
  getConfig: () =>
    ApiClient.get<DailyRecommendationConfig>('/api/daily-recommendations/config'),

  /** 保存每日推荐配置（后端校验失败返回 400 + 错误信息） */
  saveConfig: (config: DailyRecommendationConfig) =>
    ApiClient.put<DailyRecommendationConfig>('/api/daily-recommendations/config', config),
```

- [ ] **Step 2: `screening.ts` 加 `enhanced` 方法**

`frontend/src/api/screening.ts` 现有 `screeningApi` 只有 `run`/`getFields`/`getIndustries`。预览需要 `/api/screening/enhanced`（接受 `{field,operator,value}` 条件格式，与配置一致）。

在 `ScreeningOrderBy` 接口之后加请求/响应类型：

```typescript
export interface EnhancedScreeningReq {
  conditions: Array<{ field: string; operator: string; value: unknown }>
  order_by?: ScreeningOrderBy[]
  limit?: number
  offset?: number
}

export interface EnhancedScreeningResp {
  total: number
  items: Array<Record<string, any>>
  took_ms?: number
}
```

在 `screeningApi` 对象里 `getIndustries` 之后加（注意 `getIndustries` 行尾要补逗号）：

```typescript
  enhanced: (payload: EnhancedScreeningReq) =>
    ApiClient.post<EnhancedScreeningResp>('/api/screening/enhanced', payload, { timeout: 60000 }),
```

- [ ] **Step 3: type-check**

Run: `cd frontend && npm run type-check`
Expected: 无错误（仅 npm 前导输出）

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/dailyRecommendation.ts frontend/src/api/screening.ts
git commit -m "feat(daily-rec): 前端加配置读写与增强筛选 API 封装"
```

---

## Task 4: `ConfigDrawer.vue` 配置编辑组件

**Files:**
- Create: `frontend/src/views/DailyRecommendation/ConfigDrawer.vue`

**说明**：结构化表单，4 段（任务开关 / 选股条件 / 排序与数量 / 分析设置）+ 预览。`v-model:visible` 双向绑定显隐。打开时拉配置 + 字段元数据 + 行业列表。`fieldList` 来自 `screeningApi.getFields()`（返回 `{fields: Record<name,FieldInfo>}`），驱动字段下拉与按字段过滤操作符。

- [ ] **Step 1: 创建组件**

创建 `frontend/src/views/DailyRecommendation/ConfigDrawer.vue`，完整内容：

```vue
<template>
  <el-drawer
    :model-value="visible"
    title="每日推荐配置"
    size="620px"
    @update:model-value="$emit('update:visible', $event)"
    @open="onOpen"
  >
    <div v-loading="loading">
      <el-form label-width="90px">
        <el-divider content-position="left">任务开关</el-divider>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
          <span class="hint">关闭后定时任务跳过</span>
        </el-form-item>

        <el-divider content-position="left">选股条件（多个条件为 AND 关系）</el-divider>
        <div
          v-for="(cond, idx) in form.screening.conditions"
          :key="idx"
          class="condition-row"
        >
          <el-select
            v-model="cond.field"
            placeholder="字段"
            style="width: 130px"
            @change="onFieldChange(cond)"
          >
            <el-option
              v-for="f in fieldList"
              :key="f.name"
              :label="f.display_name"
              :value="f.name"
            />
          </el-select>
          <el-select v-model="cond.operator" placeholder="操作符" style="width: 110px">
            <el-option
              v-for="op in operatorsFor(cond.field)"
              :key="op"
              :label="OPERATOR_LABELS[op] || op"
              :value="op"
            />
          </el-select>
          <template v-if="cond.operator === 'between'">
            <el-input-number
              :model-value="rangeValue(cond, 0)"
              :controls="false"
              placeholder="下限"
              style="width: 80px"
              @update:model-value="setRangeValue(cond, 0, $event)"
            />
            <span class="tilde">~</span>
            <el-input-number
              :model-value="rangeValue(cond, 1)"
              :controls="false"
              placeholder="上限"
              style="width: 80px"
              @update:model-value="setRangeValue(cond, 1, $event)"
            />
          </template>
          <el-select
            v-else-if="cond.operator === 'in' || cond.operator === 'not_in'"
            v-model="cond.value"
            multiple
            filterable
            placeholder="选择值"
            style="width: 230px"
          >
            <el-option
              v-for="opt in valueOptionsFor(cond.field)"
              :key="opt"
              :label="opt"
              :value="opt"
            />
          </el-select>
          <el-input
            v-else-if="cond.operator === 'contains'"
            v-model="cond.value as string"
            placeholder="包含文本"
            style="width: 230px"
          />
          <el-input-number
            v-else
            :model-value="cond.value as number"
            :controls="false"
            placeholder="数值"
            style="width: 230px"
            @update:model-value="cond.value = ($event ?? 0)"
          />
          <el-button :icon="Delete" circle @click="removeCondition(idx)" />
        </div>
        <el-button :icon="Plus" @click="addCondition">添加条件</el-button>

        <el-divider content-position="left">排序与数量</el-divider>
        <el-form-item label="排序字段">
          <el-select v-model="form.screening.order_by" style="width: 170px">
            <el-option label="市值" value="market_cap" />
            <el-option
              v-for="f in fieldList"
              :key="f.name"
              :label="f.display_name"
              :value="f.name"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="排序方向">
          <el-select v-model="form.screening.order_direction" style="width: 120px">
            <el-option label="降序" value="desc" />
            <el-option label="升序" value="asc" />
          </el-select>
        </el-form-item>
        <el-form-item label="推荐数量">
          <el-input-number v-model="form.screening.limit" :min="1" :max="20" />
        </el-form-item>

        <el-divider content-position="left">分析设置</el-divider>
        <el-form-item label="分析深度">
          <el-select v-model="form.analysis.research_depth" style="width: 120px">
            <el-option label="快速" value="快速" />
            <el-option label="标准" value="标准" />
            <el-option label="深度" value="深度" />
          </el-select>
        </el-form-item>
        <el-form-item label="市场">
          <el-select v-model="form.analysis.market_type" style="width: 120px" disabled>
            <el-option label="A股" value="A股" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-divider content-position="left">选股预览</el-divider>
      <el-button :loading="previewing" @click="doPreview">预览选股结果</el-button>
      <el-table
        v-if="previewResult.length"
        :data="previewResult"
        size="small"
        style="margin-top: 12px"
      >
        <el-table-column prop="code" label="代码" width="90" />
        <el-table-column prop="name" label="名称" />
        <el-table-column label="市值" width="110">
          <template #default="{ row }">
            {{ row.total_mv != null ? row.total_mv.toFixed(0) + '亿' : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="市盈率" width="90">
          <template #default="{ row }">{{ row.pe != null ? row.pe.toFixed(1) : '—' }}</template>
        </el-table-column>
      </el-table>
      <el-empty
        v-else-if="previewed"
        description="当前条件无匹配股票"
        :image-size="60"
      />
    </div>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="doSave">保存</el-button>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Delete, Plus } from '@element-plus/icons-vue'
import {
  dailyRecommendationApi,
  type DailyRecommendationConfig,
  type ScreeningConditionItem,
} from '@/api/dailyRecommendation'
import { screeningApi, type FieldInfo } from '@/api/screening'

defineProps<{ visible: boolean }>()
const emit = defineEmits<{ 'update:visible': [boolean]; saved: [] }>()

const OPERATOR_LABELS: Record<string, string> = {
  '>': '大于',
  '<': '小于',
  '>=': '不小于',
  '<=': '不大于',
  '==': '等于',
  '!=': '不等于',
  between: '区间',
  in: '属于',
  not_in: '不属于',
  contains: '包含',
}

const loading = ref(false)
const saving = ref(false)
const previewing = ref(false)
const previewed = ref(false)
const previewResult = ref<Array<Record<string, any>>>([])
const fieldList = ref<FieldInfo[]>([])
const industryOptions = ref<string[]>([])

const form = reactive<DailyRecommendationConfig>({
  enabled: false,
  screening: { conditions: [], order_by: 'market_cap', order_direction: 'desc', limit: 5 },
  analysis: { research_depth: '标准', market_type: 'A股' },
})

// drawer 打开时加载配置 + 字段元数据 + 行业列表
const onOpen = async () => {
  loading.value = true
  previewed.value = false
  previewResult.value = []
  try {
    const [cfgRes, fieldsRes, indRes] = await Promise.all([
      dailyRecommendationApi.getConfig(),
      screeningApi.getFields(),
      screeningApi.getIndustries(),
    ])
    const cfg = cfgRes.data
    if (cfg) {
      form.enabled = cfg.enabled
      form.screening = {
        conditions: cfg.screening?.conditions ?? [],
        order_by: cfg.screening?.order_by ?? 'market_cap',
        order_direction: cfg.screening?.order_direction ?? 'desc',
        limit: cfg.screening?.limit ?? 5,
      }
      form.analysis = {
        research_depth: cfg.analysis?.research_depth ?? '标准',
        market_type: cfg.analysis?.market_type ?? 'A股',
      }
    }
    fieldList.value = Object.values(fieldsRes.data?.fields ?? {})
    industryOptions.value = (indRes.data?.industries ?? []).map((i) => i.value)
  } catch (error) {
    console.error('加载配置失败:', error)
    ElMessage.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

const operatorsFor = (field: string): string[] => {
  const info = fieldList.value.find((f) => f.name === field)
  return info?.supported_operators ?? []
}

// industry 字段的 in/not_in 用行业列表作为可选值，其他字段返回空（自由输入）
const valueOptionsFor = (field: string): string[] =>
  field === 'industry' ? industryOptions.value : []

const onFieldChange = (cond: ScreeningConditionItem) => {
  // 换字段后操作符 / 值可能不再适用，重置
  cond.operator = ''
  cond.value = 0
}

const addCondition = () => {
  form.screening.conditions.push({ field: '', operator: '', value: 0 })
}
const removeCondition = (idx: number) => {
  form.screening.conditions.splice(idx, 1)
}

// between 的 value 是 [lo, hi]；读写单端时保证 value 是数组
const rangeValue = (cond: ScreeningConditionItem, i: number): number => {
  return Array.isArray(cond.value) ? Number(cond.value[i] ?? 0) : 0
}
const setRangeValue = (cond: ScreeningConditionItem, i: number, v: number | undefined) => {
  if (!Array.isArray(cond.value)) cond.value = [0, 0]
  ;(cond.value as number[])[i] = v ?? 0
}

const doPreview = async () => {
  previewing.value = true
  try {
    const res = await screeningApi.enhanced({
      conditions: form.screening.conditions.map((c) => ({
        field: c.field,
        operator: c.operator,
        value: c.value,
      })),
      order_by: [
        { field: form.screening.order_by, direction: form.screening.order_direction },
      ],
      limit: form.screening.limit,
    })
    previewResult.value = res.data?.items ?? []
    previewed.value = true
  } catch (error) {
    console.error('预览失败:', error)
    ElMessage.error('预览失败，请检查筛选条件')
  } finally {
    previewing.value = false
  }
}

const doSave = async () => {
  saving.value = true
  try {
    await dailyRecommendationApi.saveConfig({
      enabled: form.enabled,
      screening: { ...form.screening },
      analysis: { ...form.analysis },
    })
    ElMessage.success('配置已保存，下次生成时生效')
    emit('saved')
    emit('update:visible', false)
  } catch (error) {
    // 后端 400 校验错误由响应拦截器统一提示具体信息
    console.error('保存配置失败:', error)
  } finally {
    saving.value = false
  }
}
</script>

<style lang="scss" scoped>
.condition-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.tilde {
  color: var(--el-text-color-secondary);
}
.hint {
  margin-left: 12px;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}
</style>
```

- [ ] **Step 2: type-check**

Run: `cd frontend && npm run type-check`
Expected: 无错误。若 `FieldInfo` 未从 `screening.ts` 导出会报错——`screening.ts` 已 `export interface FieldInfo`，正常。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/DailyRecommendation/ConfigDrawer.vue
git commit -m "feat(daily-rec): 新增配置编辑 drawer 组件"
```

---

## Task 5: 接入 `DailyRecommendation/index.vue`

**Files:**
- Modify: `frontend/src/views/DailyRecommendation/index.vue`

操作栏现有「立即生成」「刷新」两个按钮（`action-buttons` div 内）。加「配置」按钮，点击打开 `ConfigDrawer`。

- [ ] **Step 1: 模板加按钮 + 组件**

在 `index.vue` 模板里，`action-buttons` div 内、`<el-button @click="loadList">` 刷新按钮之后加配置按钮：

```vue
          <el-button @click="configVisible = true">
            <el-icon><Setting /></el-icon>
            配置
          </el-button>
```

在最外层 `<div class="daily-recommendation">` 闭合 `</div>` 之前加组件：

```vue
    <ConfigDrawer v-model:visible="configVisible" @saved="loadList" />
```

- [ ] **Step 2: script 加 import 与状态**

`index.vue` 的 `<script setup>` 中：

把图标 import（现为 `import { Sunrise, VideoPlay, Refresh } from '@element-plus/icons-vue'`）改为：

```typescript
import { Sunrise, VideoPlay, Refresh, Setting } from '@element-plus/icons-vue'
```

在 import 区加组件 import：

```typescript
import ConfigDrawer from './ConfigDrawer.vue'
```

在 `running` ref 声明之后加状态：

```typescript
const configVisible = ref(false)
```

- [ ] **Step 3: type-check**

Run: `cd frontend && npm run type-check`
Expected: 无错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/DailyRecommendation/index.vue
git commit -m "feat(daily-rec): 每日推荐页接入配置编辑入口"
```

---

## Task 6: 更新 CHANGELOG

**Files:**
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: 加变更条目**

打开 `docs/CHANGELOG.md`，在 `[Unreleased]` 段的 `### Added`（若无则新建该子节，置于 `[Unreleased]` 标题下）加一行：

```markdown
- 每日推荐：新增配置可视化编辑界面（DailyRecommendation 页「配置」按钮 → drawer 结构化表单），可编辑 `config/daily_recommendation.json` 的选股条件 / 排序 / 数量 / 分析深度，带选股结果预览；后端加 `GET/PUT /api/daily-recommendations/config` 端点与 `save_config` 校验。
```

如 `[Unreleased]` 段已有 `### Added`，追加到其下；保持与文件现有 Keep a Changelog 格式一致。

- [ ] **Step 2: Commit**

```bash
git add docs/CHANGELOG.md
git commit -m "docs(changelog): 记录每日推荐配置编辑界面"
```

---

## 收尾

全部 6 个 task 完成后：
- 跑一次 `just lint && just typecheck` + `.venv/bin/python -m pytest tests/services/test_daily_recommendation_config.py -v` + `cd frontend && npm run type-check`，确认全绿。
- 不 push——push 由用户确认（HARD-GATE）。
