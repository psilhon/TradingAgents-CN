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
