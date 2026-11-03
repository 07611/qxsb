<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { toDateString } from '@/utils/format'
import AsyncState from '@/components/ui/AsyncState.vue'

const { t, locale } = useI18n()
const reportType = ref('overview')
const groupBy = ref('day')
const loading = ref(true)
const error = ref(null)
const report = ref(null)
const exporting = ref(false)
const today = new Date()
const start = new Date(today.getTime() - 29 * 86400000)
const range = ref([toDateString(start), toDateString(today)])

const types = ['overview', 'emotions', 'users', 'content', 'music', 'feedback']
const typeLabels = computed(() => {
  const map = {}
  for (const type of types) map[type] = t(`admin.reportTypes.${type}`)
  return map
})
const chartRows = computed(() => report.value?.series || [])
const maxValue = computed(() => {
  let max = 1
  for (const row of chartRows.value) {
    for (const [key, value] of Object.entries(row)) {
      if (key !== 'date' && typeof value === 'number') max = Math.max(max, value)
    }
  }
  return max
})
const numericKeys = computed(() => {
  if (!chartRows.value.length) return []
  return Object.keys(chartRows.value[0]).filter((key) => key !== 'date')
})
const summaryEntries = computed(() => Object.entries(report.value?.meta?.summary || {}))
const labelFor = (key) => report.value?.meta?.labels?.[key] || key

async function load() {
  if (!range.value?.[0] || !range.value?.[1]) return
  loading.value = true
  error.value = null
  try {
    const response = await adminApi.report(reportType.value, {
      from: range.value[0],
      to: range.value[1],
      groupBy: groupBy.value,
    })
    report.value = response.data
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    loading.value = false
  }
}

function changeType(type) {
  reportType.value = type
  load()
}

async function exportCsv() {
  try {
    await ElMessageBox.confirm(t('admin.exportCsv'), t('admin.reportsTitle'), {
      confirmButtonText: t('admin.exportCsv'),
      cancelButtonText: t('common.cancel'),
      type: 'info',
    })
  } catch {
    return
  }
  exporting.value = true
  try {
    const blob = await adminApi.reportCsv(reportType.value, {
      from: range.value[0],
      to: range.value[1],
      groupBy: groupBy.value,
    })
    const url = URL.createObjectURL(blob instanceof Blob ? blob : new Blob([blob]))
    const link = document.createElement('a')
    link.href = url
    link.download = `moodwave-${reportType.value}-${range.value[0]}-${range.value[1]}.csv`
    link.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    ElMessage.error(normalizeError(err).message)
  } finally {
    exporting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="reports-page">
    <div class="page-title">
      <div>
        <p class="eyebrow">ANALYTICS / REPORTS</p>
        <h1>{{ t('admin.reportsTitle') }}</h1>
      </div>
      <span class="mono">DAILY PRE-AGGREGATED</span>
    </div>

    <div class="report-controls">
      <div class="type-tabs">
        <button v-for="type in types" :key="type" :class="{ active: reportType === type }" @click="changeType(type)">
          {{ typeLabels[type] }}
        </button>
      </div>
      <div class="filter-controls">
        <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" size="small" :start-placeholder="t('common.today')" :end-placeholder="t('common.today')" />
        <el-select v-model="groupBy" size="small">
          <el-option :label="t('admin.groupOptions.day')" value="day" />
          <el-option :label="t('admin.groupOptions.week')" value="week" />
          <el-option :label="t('admin.groupOptions.month')" value="month" />
        </el-select>
        <button class="btn ghost small" @click="load">{{ t('common.search') }}</button>
        <button class="btn ghost small" :disabled="exporting" @click="exportCsv">{{ t('admin.exportCsv') }}</button>
      </div>
    </div>

    <AsyncState :loading="loading" :error="error" :empty="!loading && !report" @retry="load">
      <div v-if="report" class="report-body">
        <div class="summary-grid">
          <div v-for="[label, value] in summaryEntries" :key="label" class="summary-card">
            <span>{{ label }}</span>
            <strong>{{ value }}</strong>
          </div>
        </div>

        <section class="chart-panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow">{{ report.meta.title }} / {{ report.meta.groupBy.toUpperCase() }}</p>
              <h3>{{ report.meta.from }} → {{ report.meta.to }}</h3>
            </div>
            <span class="mono">{{ chartRows.length }} BUCKETS</span>
          </div>
          <div v-if="chartRows.length" class="bar-chart">
            <div v-for="row in chartRows" :key="row.date" class="bar-group">
              <div class="bar-stack">
                <span
                  v-for="key in numericKeys"
                  :key="key"
                  class="bar-seg"
                  :style="{ height: `${Math.max(2, (row[key] / maxValue) * 100)}%`, background: key === numericKeys[0] ? 'var(--accent)' : 'var(--signal)' }"
                  :title="`${labelFor(key)}: ${row[key]}`"
                ></span>
              </div>
              <span class="bar-date mono">{{ row.date.slice(5) }}</span>
            </div>
          </div>
          <p v-else class="empty-line">{{ t('admin.noData') }}</p>
          <div class="legend">
            <span v-for="(key, index) in numericKeys" :key="key">
              <i :style="{ background: index === 0 ? 'var(--accent)' : 'var(--signal)' }"></i>{{ labelFor(key) }}
            </span>
          </div>
        </section>

        <div class="report-grid">
          <section v-if="report.breakdown?.length" class="table-panel">
            <div class="panel-head">
              <div><p class="eyebrow">BREAKDOWN</p><h3>{{ t('admin.reportTypes.emotions') }}</h3></div>
              <span class="mono">%</span>
            </div>
            <div class="breakdown-list">
              <div v-for="entry in report.breakdown" :key="entry.emotion" class="breakdown-row">
                <span class="breakdown-label">{{ entry.label }}</span>
                <div class="breakdown-bar"><i :style="{ width: `${entry.percentage}%` }"></i></div>
                <span class="mono">{{ entry.count }}</span>
                <span class="mono">{{ entry.percentage }}%</span>
              </div>
            </div>
          </section>
          <section class="table-panel">
            <div class="panel-head">
              <div><p class="eyebrow">DATA TABLE</p><h3>{{ t('admin.value') }}</h3></div>
              <span class="mono">CSV READY</span>
            </div>
            <el-table :data="chartRows" max-height="330" size="small">
              <el-table-column prop="date" label="TIME" width="110" />
              <el-table-column v-for="key in numericKeys" :key="key" :label="labelFor(key)" min-width="90">
                <template #default="{ row }">{{ row[key] ?? 0 }}</template>
              </el-table-column>
            </el-table>
          </section>
        </div>

        <div class="report-note">
          <span class="mono">DEFINITION</span>
          <p>{{ t('extra.reportNote') }}</p>
        </div>
      </div>
    </AsyncState>
  </div>
</template>

<style scoped>
.page-title {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 18px;
}
.page-title h1 {
  font-size: clamp(32px, 4vw, 48px);
  margin-top: 8px;
}
.page-title .mono {
  font-size: 8px;
  color: var(--muted-2);
}
.report-controls {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  padding: 9px 0;
  margin-bottom: 16px;
}
.type-tabs {
  display: flex;
  gap: 2px;
  flex-wrap: wrap;
}
.type-tabs button {
  border: 0;
  background: transparent;
  padding: 6px 10px;
  color: var(--muted);
  font-size: 10px;
  border-radius: 4px;
}
.type-tabs button.active {
  background: var(--surface-2);
  color: var(--ink);
  font-weight: 650;
}
.filter-controls {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}
.filter-controls .el-date-editor {
  width: 230px;
}
.filter-controls .el-select {
  width: 100px;
}
.small {
  min-height: 31px;
  font-size: 9px;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 13px;
}
.summary-card {
  background: var(--surface);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.summary-card span {
  font-size: 8px;
  color: var(--muted);
}
.summary-card strong {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 540;
  letter-spacing: -0.04em;
}
.chart-panel,
.table-panel {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  padding: 15px;
}
.chart-panel {
  margin-bottom: 13px;
}
.panel-head {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid var(--line);
  padding-bottom: 9px;
  margin-bottom: 11px;
}
.panel-head h3 {
  margin-top: 4px;
  font-size: 16px;
}
.panel-head .mono {
  font-size: 7px;
  color: var(--muted-2);
}
.bar-chart {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  height: 220px;
  padding: 0 3px;
  overflow-x: auto;
}
.bar-group {
  flex: 1;
  min-width: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.bar-stack {
  flex: 1;
  width: 100%;
  max-width: 36px;
  display: flex;
  align-items: flex-end;
  gap: 2px;
}
.bar-seg {
  flex: 1;
  border-radius: 2px 2px 0 0;
  min-height: 2px;
  opacity: 0.84;
}
.bar-date {
  font-size: 6px;
  color: var(--muted-2);
  white-space: nowrap;
}
.legend {
  display: flex;
  gap: 12px;
  margin-top: 9px;
  padding-top: 8px;
  border-top: 1px solid var(--line);
}
.legend span {
  font-size: 8px;
  color: var(--muted);
  display: flex;
  align-items: center;
  gap: 4px;
}
.legend i {
  width: 6px;
  height: 6px;
  border-radius: 1px;
}
.empty-line {
  color: var(--muted-2);
  font-size: 10px;
  padding: 26px 0;
  text-align: center;
}
.report-grid {
  display: grid;
  grid-template-columns: 0.7fr 1.3fr;
  gap: 13px;
}
.breakdown-list {
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.breakdown-row {
  display: grid;
  grid-template-columns: 61px 1fr 28px 36px;
  gap: 7px;
  align-items: center;
}
.breakdown-label {
  font-size: 9px;
  color: var(--muted);
}
.breakdown-bar {
  height: 4px;
  background: var(--surface-3);
  border-radius: 2px;
  overflow: hidden;
}
.breakdown-bar i {
  display: block;
  height: 100%;
  background: var(--accent);
  border-radius: 2px;
}
.breakdown-row .mono {
  font-size: 7px;
  color: var(--muted-2);
  text-align: right;
}
.report-note {
  margin-top: 13px;
  display: flex;
  gap: 10px;
  padding: 11px;
  border: 1px dashed var(--line);
  border-radius: 6px;
  background: var(--surface-2);
}
.report-note .mono {
  font-size: 7px;
  color: var(--accent);
  flex-shrink: 0;
}
.report-note p {
  font-size: 9px;
  color: var(--muted);
  line-height: 1.6;
}
@media (max-width: 800px) {
  .report-grid {
    grid-template-columns: 1fr;
  }
  .bar-chart {
    height: 170px;
    gap: 4px;
  }
}
@media (max-width: 600px) {
  .page-title {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
  .filter-controls > * {
    flex: 1 1 100%;
  }
  .filter-controls .el-date-editor,
  .filter-controls .el-select {
    width: 100%;
  }
}
</style>
