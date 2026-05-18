<template>
  <el-drawer
    :model-value="visible"
    title="每日推荐配置管理"
    size="880px"
    @update:model-value="$emit('update:visible', $event)"
    @open="onOpen"
  >
    <div v-loading="loading" class="config-manager">
      <!-- 左侧：配置列表 -->
      <div class="config-list-pane">
        <el-button class="new-config-btn" :icon="Plus" @click="newConfig">
          新建配置
        </el-button>
        <el-empty
          v-if="configs.length === 0"
          description="暂无配置"
          :image-size="60"
        />
        <ul v-else class="config-list">
          <li
            v-for="c in configs"
            :key="c.id"
            class="config-item"
            :class="{ active: c.id === selectedId }"
            @click="selectConfig(c)"
          >
            <span class="config-name">{{ c.name }}</span>
            <el-button
              :icon="Delete"
              circle
              size="small"
              @click.stop="removeConfig(c)"
            />
          </li>
        </ul>
      </div>

      <!-- 右侧：配置编辑表单 -->
      <div class="config-editor-pane">
        <el-empty
          v-if="!editing"
          description="从左侧选择一个配置，或新建一个"
        />
        <template v-else>
          <el-form label-width="90px">
            <el-divider content-position="left">配置信息</el-divider>
            <el-form-item label="配置名称">
              <el-input
                v-model="form.name"
                placeholder="如：质量+价值"
                maxlength="30"
                show-word-limit
                style="width: 280px"
              />
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
              <el-select
                v-model="cond.operator"
                placeholder="操作符"
                style="width: 110px"
                @change="onOperatorChange(cond)"
              >
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
                v-model="(cond.value as string)"
                placeholder="包含文本"
                style="width: 230px"
              />
              <el-input-number
                v-else
                :model-value="(cond.value as number)"
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
        </template>
      </div>
    </div>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">关闭</el-button>
      <el-button type="primary" :disabled="!editing" :loading="saving" @click="doSave">
        保存
      </el-button>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Plus } from '@element-plus/icons-vue'
import {
  dailyRecommendationApi,
  type DailyRecommendationConfig,
  type ScreeningConditionItem,
} from '@/api/dailyRecommendation'
import { screeningApi, type FieldInfo } from '@/api/screening'

defineProps<{ visible: boolean }>()
const emit = defineEmits<{ 'update:visible': [boolean]; changed: [] }>()

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

// 所有配置；selectedId 为当前编辑配置的 id（null = 未保存的新配置）
const configs = ref<DailyRecommendationConfig[]>([])
const selectedId = ref<string | null>(null)
const editing = ref(false)

const _defaultForm = (): DailyRecommendationConfig => ({
  name: '',
  screening: { conditions: [], order_by: 'market_cap', order_direction: 'desc', limit: 5 },
  analysis: { research_depth: '标准', market_type: 'A股' },
})

const form = reactive<DailyRecommendationConfig>(_defaultForm())

// 把一个配置的内容拷进 form（深拷贝 conditions，避免编辑表单影响列表项）
const _fillForm = (cfg: DailyRecommendationConfig) => {
  form.name = cfg.name ?? ''
  form.screening = {
    conditions: (cfg.screening?.conditions ?? []).map((c) => ({
      ...c,
      value: Array.isArray(c.value) ? [...c.value] : c.value,
    })),
    order_by: cfg.screening?.order_by ?? 'market_cap',
    order_direction: cfg.screening?.order_direction ?? 'desc',
    limit: cfg.screening?.limit ?? 5,
  }
  form.analysis = {
    research_depth: cfg.analysis?.research_depth ?? '标准',
    market_type: cfg.analysis?.market_type ?? 'A股',
  }
}

const loadConfigs = async () => {
  const res = await dailyRecommendationApi.listConfigs()
  configs.value = res.data ?? []
}

// drawer 打开时加载配置列表 + 字段元数据 + 行业列表
const onOpen = async () => {
  loading.value = true
  editing.value = false
  selectedId.value = null
  previewed.value = false
  previewResult.value = []
  try {
    const [, fieldsRes, indRes] = await Promise.all([
      loadConfigs(),
      screeningApi.getFields(),
      screeningApi.getIndustries(),
    ])
    // /api/screening/* 端点直接返回裸响应体（无 {success,data} 包裹），
    // 与 /api/daily-recommendations/* 不同 —— 防御性解包，兼容两种形态。
    const fieldsBody = ((fieldsRes as any)?.data ?? fieldsRes) as any
    const indBody = ((indRes as any)?.data ?? indRes) as any
    fieldList.value = Object.values(fieldsBody?.fields ?? {})
    industryOptions.value = (indBody?.industries ?? []).map((i: any) => i.value)
    if (configs.value.length > 0) selectConfig(configs.value[0])
  } catch (error) {
    console.error('加载配置失败:', error)
    ElMessage.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

const selectConfig = (cfg: DailyRecommendationConfig) => {
  selectedId.value = cfg.id ?? null
  _fillForm(cfg)
  editing.value = true
  previewed.value = false
  previewResult.value = []
}

const newConfig = () => {
  selectedId.value = null
  _fillForm(_defaultForm())
  editing.value = true
  previewed.value = false
  previewResult.value = []
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

const onOperatorChange = (cond: ScreeningConditionItem) => {
  // 切换操作符后把 value 归一化成新操作符期望的形状，
  // 避免遗留上一个操作符的值形状（如 between 的数组）被发往预览/保存。
  const op = cond.operator
  const v = cond.value
  if (op === 'between') {
    const ok =
      Array.isArray(v) && v.length === 2 && v.every((x) => typeof x === 'number')
    cond.value = ok ? v : [0, 0]
  } else if (op === 'in' || op === 'not_in') {
    cond.value = Array.isArray(v) ? v : []
  } else if (op === 'contains') {
    cond.value = typeof v === 'string' ? v : ''
  } else {
    cond.value = typeof v === 'number' ? v : 0
  }
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
    const previewBody = ((res as any)?.data ?? res) as any
    previewResult.value = previewBody?.items ?? []
    previewed.value = true
  } catch (error) {
    console.error('预览失败:', error)
    ElMessage.error('预览失败，请检查筛选条件')
  } finally {
    previewing.value = false
  }
}

const doSave = async () => {
  if (!form.name.trim()) {
    ElMessage.warning('请填写配置名称')
    return
  }
  saving.value = true
  try {
    const payload: DailyRecommendationConfig = {
      name: form.name.trim(),
      screening: {
        conditions: form.screening.conditions.map((c) => ({ ...c })),
        order_by: form.screening.order_by,
        order_direction: form.screening.order_direction,
        limit: form.screening.limit,
      },
      analysis: { ...form.analysis },
    }
    let savedId = selectedId.value
    if (selectedId.value) {
      await dailyRecommendationApi.updateConfig(selectedId.value, payload)
    } else {
      const res = await dailyRecommendationApi.createConfig(payload)
      savedId = res.data?.id ?? null
    }
    ElMessage.success('配置已保存')
    emit('changed')
    await loadConfigs()
    const target = configs.value.find((c) => c.id === savedId)
    if (target) selectConfig(target)
  } catch (error) {
    // 后端 400 校验错误由响应拦截器统一提示具体信息
    console.error('保存配置失败:', error)
  } finally {
    saving.value = false
  }
}

const removeConfig = async (cfg: DailyRecommendationConfig) => {
  try {
    await ElMessageBox.confirm(
      `确定删除配置「${cfg.name}」？该配置的历史推荐结果会保留。`,
      '删除确认',
      { type: 'warning' },
    )
  } catch {
    return // 用户取消
  }
  try {
    if (cfg.id) await dailyRecommendationApi.deleteConfig(cfg.id)
    ElMessage.success('配置已删除')
    emit('changed')
    await loadConfigs()
    if (selectedId.value === cfg.id) {
      editing.value = false
      selectedId.value = null
    }
  } catch (error) {
    console.error('删除配置失败:', error)
  }
}
</script>

<style lang="scss" scoped>
.config-manager {
  display: flex;
  gap: 16px;
  min-height: 360px;
}

.config-list-pane {
  flex-shrink: 0;
  width: 200px;
  border-right: 1px solid var(--el-border-color-lighter);
  padding-right: 12px;

  .new-config-btn {
    width: 100%;
    margin-bottom: 12px;
  }

  .config-list {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .config-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 6px;
    cursor: pointer;
    transition: background-color 0.2s;

    &:hover {
      background-color: var(--el-fill-color-light);
    }

    &.active {
      background-color: var(--el-color-primary-light-9);

      .config-name {
        color: var(--el-color-primary);
        font-weight: 600;
      }
    }

    .config-name {
      flex: 1;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 14px;
      color: var(--el-text-color-primary);
    }
  }
}

.config-editor-pane {
  flex: 1;
  min-width: 0;
}

.condition-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.tilde {
  color: var(--el-text-color-secondary);
}
</style>
