<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { adminApi } from '@/services/api'
import { normalizeError } from '@/services/http'
import { formatPercent } from '@/utils/format'
import AsyncState from '@/components/ui/AsyncState.vue'

const { t } = useI18n()
const loading = ref(true)
const error = ref(null)
const summary = ref(null)
const funnels = ref([])
const selectedFunnel = ref(null)
const funnelData = ref(null)
const retention = ref(null)
const definitions = ref([])
const events = ref([])
const activeTab = ref('funnel')
const funnelLoading = ref(false)

const maxEventCount = computed(() => Math.max(...(summary.value?.events || []).map((item) => item.count), 1))
const funnelSteps = computed(() => funnelData.value?.steps || [])
const maxFunnelCount = computed(() => Math.max(...funnelSteps.value.map((item) => item.count), 1))
const retentionColumns = computed(() => {
  const length = Math.max(...(retention.value?.cohorts || []).map((item) => item.retention.length), 0)
  return Array.from({ length }, (_, i) => i)
})

async function loadFunnel(id = null) {
  if (!id && !funnels.value.length) return
  funnelLoading.value = true
  try {
    const response = await adminApi.funnel({ funnelId: id || selectedFunnel.value || funnels.value[0]?.id })
    funnelData.value = response.data
    selectedFunnel.value = response.data.funnel.id
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    funnelLoading.value = false
  }
}

async function load() {
  loading.value = true
  error.value = null
  try {
    const [summaryResponse, funnelResponse, retentionResponse, definitionResponse, eventResponse] = await Promise.all([
      adminApi.analyticsSummary({ days: 30 }),
      adminApi.funnels(),
      adminApi.retention({ weeks: 6 }),
      adminApi.definitions(),
      adminApi.events({ pageSize: 12 }),
    ])
    summary.value = summaryResponse.data
    funnels.value = funnelResponse.data.items || []
    retention.value = retentionResponse.data
    definitions.value = definitionResponse.data.items || []
    events.value = eventResponse.data.items || []
    if (funnels.value.length) {
      const preferred = funnels.value.find((item) => item.name.includes('情绪')) || funnels.value[0]
      selectedFunnel.value = preferred.id
      await loadFunnel(selectedFunnel.value)
    }
  } catch (err) {
    error.value = normalizeError(err)
  } finally {
    loading.value = false
  }
}

function chooseFunnel(id) {
  selectedFunnel.value = id
  loadFunnel(id)
}

onMounted(load)
</script>

<template>
  <div class="analytics-page">
    <div class="page-title">
      <div>
        <p class="eyebrow">BEHAVIOUR / PRIVACY-SAFE</p>
        <h1>{{ t('admin.analyticsTitle') }}</h1>
      </div>
      <span class="mono">HMAC USER HASH · 30D</span>
    </div>

    <AsyncState :loading="loading" :error="error" @retry="load">
      <div class="metric-row">
        <div class="metric-card">
          <span class="mono">TOTAL EVENTS</span>
          <strong>{{ summary?.totalEvents || 0 }}</strong>
          <p>Sessions {{ summary?.sessions || 0 }}</p>
        </div>
        <div class="metric-card">
          <span class="mono">IDENTIFIED</span>
          <strong>{{ summary?.identifiedUsers || 0 }}</strong>
          <p>Hashed users</p>
        </div>
        <div class="metric-card">
          <span class="mono">FUNNELS</span>
          <strong>{{ funnels.length }}</strong>
          <p>{{ funnelData?.funnel.name || '—' }}</p>
        </div>
        <div class="event-bars">
          <div v-for="event in summary?.events.slice(0, 6)" :key="event.key" class="event-bar">
            <span class="event-name mono">{{ event.key }}</span>
            <div class="event-track"><i :style="{ width: `${(event.count / maxEventCount) * 100}%` }"></i></div>
            <span class="mono">{{ event.count }}</span>
          </div>
        </div>
      </div>

      <div class="tabs-row">
        <button :class="{ active: activeTab === 'funnel' }" @click="activeTab = 'funnel'">{{ t('admin.funnel') }}</button>
        <button :class="{ active: activeTab === 'retention' }" @click="activeTab = 'retention'">{{ t('admin.retention') }}</button>
        <button :class="{ active: activeTab === 'definitions' }" @click="activeTab = 'definitions'">{{ t('admin.definitions') }}</button>
        <button :class="{ active: activeTab === 'events' }" @click="activeTab = 'events'">{{ t('admin.recentEvents') }}</button>
      </div>

      <section v-if="activeTab === 'funnel'" class="analysis-panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">FUNNEL / SESSION LINKED</p>
            <h3>{{ t('admin.funnel') }}</h3>
          </div>
          <el-select v-model="selectedFunnel" size="small" @change="chooseFunnel">
            <el-option v-for="item in funnels" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </div>
        <div v-if="funnelData" class="funnel-summary">
          <div><span class="mono">SESSIONS</span><strong>{{ funnelData.sessions }}</strong></div>
          <div><span class="mono">COMPLETED</span><strong>{{ funnelData.completed }}</strong></div>
          <div><span class="mono">OVERALL</span><strong>{{ formatPercent(funnelData.overallConversion) }}</strong></div>
          <div><span class="mono">STEP 1</span><strong>{{ funnelSteps[0]?.count || 0 }}</strong></div>
        </div>
        <div class="funnel-chart">
          <div v-for="(step, index) in funnelSteps" :key="step.eventKey" class="funnel-step">
            <div class="funnel-label">
              <span class="mono">0{{ index + 1 }}</span>
              <strong>{{ step.label }}</strong>
              <span class="mono">{{ step.eventKey }}</span>
            </div>
            <div class="funnel-bar">
              <span :style="{ width: `${Math.max(4, (step.count / maxFunnelCount) * 100)}%` }"></span>
              <em>{{ step.count }}</em>
            </div>
            <div class="funnel-rates">
              <span>{{ formatPercent(step.conversionFromStart) }}</span>
              <span v-if="index" class="negative">-{{ formatPercent(step.dropFromPrevious) }}</span>
            </div>
          </div>
        </div>
        <p class="note">{{ t('extra.funnelNote') }}</p>
      </section>

      <section v-else-if="activeTab === 'retention'" class="analysis-panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">COHORT / WEEKLY</p>
            <h3>{{ t('admin.retention') }}</h3>
          </div>
          <span class="mono">{{ retention?.cohorts.length || 0 }} COHORTS</span>
        </div>
        <div class="retention-wrap">
          <table class="retention-table">
            <thead>
              <tr>
                <th>COHORT</th><th>SIZE</th>
                <th v-for="index in retentionColumns" :key="index">W{{ index }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="cohort in retention?.cohorts" :key="cohort.cohort">
                <td class="mono">{{ cohort.cohort }}</td>
                <td class="mono">{{ cohort.size }}</td>
                <td v-for="index in retentionColumns" :key="index">
                  <span
                    v-if="cohort.retention[index] !== undefined"
                    class="retention-cell"
                    :style="{ background: `color-mix(in srgb, var(--success) ${Math.min(70, cohort.retention[index])}%, var(--surface))` }"
                  >
                    {{ cohort.retention[index] }}%
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="note">{{ retention?.note }}</p>
      </section>

      <section v-else-if="activeTab === 'definitions'" class="analysis-panel">
        <div class="panel-head">
          <div><p class="eyebrow">EVENT REGISTRY</p><h3>{{ t('admin.definitions') }}</h3></div>
          <span class="mono">{{ definitions.length }} EVENTS</span>
        </div>
        <div class="definition-grid">
          <div v-for="item in definitions" :key="item.key" class="definition-card">
            <span class="mono">{{ item.key }}</span>
            <strong>{{ item.name }}</strong>
            <p>{{ item.category }}</p>
            <span class="status-dot-line"><i></i>{{ item.status }}</span>
          </div>
        </div>
      </section>

      <section v-else class="analysis-panel">
        <div class="panel-head">
          <div><p class="eyebrow">STREAM</p><h3>{{ t('admin.recentEvents') }}</h3></div>
          <span class="mono">SANITIZED</span>
        </div>
        <div class="events-list">
          <div v-for="event in events" :key="event.id" class="event-row">
            <span class="mono event-key">{{ event.eventKey }}</span>
            <span class="mono">{{ event.sessionId }}</span>
            <span class="event-route">{{ event.props?.route || '—' }}</span>
            <span class="mono">{{ new Date(event.occurredAt).toLocaleString() }}</span>
          </div>
        </div>
      </section>
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
.metric-row {
  display: grid;
  grid-template-columns: 0.55fr 0.55fr 0.55fr 1.35fr;
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 13px;
}
.metric-card {
  background: var(--surface);
  padding: 13px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.metric-card .mono {
  font-size: 7px;
  color: var(--muted-2);
}
.metric-card strong {
  font-family: var(--font-display);
  font-size: 26px;
  font-weight: 540;
  letter-spacing: -0.04em;
}
.metric-card p {
  font-size: 8px;
  color: var(--muted);
}
.event-bars {
  background: var(--surface);
  padding: 10px 13px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  justify-content: center;
}
.event-bar {
  display: grid;
  grid-template-columns: 112px 1fr 38px;
  align-items: center;
  gap: 6px;
}
.event-name {
  font-size: 7px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.event-track {
  height: 3px;
  background: var(--surface-3);
  border-radius: 2px;
  overflow: hidden;
}
.event-track i {
  display: block;
  height: 100%;
  background: var(--accent);
  border-radius: 2px;
}
.event-bar .mono {
  font-size: 6px;
  color: var(--muted-2);
  text-align: right;
}
.tabs-row {
  display: flex;
  gap: 2px;
  border-bottom: 1px solid var(--line);
  margin-bottom: 13px;
}
.tabs-row button {
  background: transparent;
  border: 0;
  color: var(--muted);
  font-size: 10px;
  padding: 8px 10px;
  position: relative;
}
.tabs-row button.active {
  color: var(--ink);
  font-weight: 650;
}
.tabs-row button.active::after {
  content: '';
  position: absolute;
  left: 8px;
  right: 8px;
  bottom: -1px;
  height: 2px;
  background: var(--accent);
}
.analysis-panel {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  padding: 15px;
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  border-bottom: 1px solid var(--line);
  padding-bottom: 9px;
  margin-bottom: 13px;
}
.panel-head h3 {
  margin-top: 4px;
  font-size: 18px;
}
.panel-head .mono {
  font-size: 7px;
  color: var(--muted-2);
}
.panel-head .el-select {
  width: 180px;
}
.funnel-summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 16px;
}
.funnel-summary > div {
  background: var(--surface-2);
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.funnel-summary .mono {
  font-size: 6px;
  color: var(--muted-2);
}
.funnel-summary strong {
  font-family: var(--font-display);
  font-size: 19px;
  font-weight: 540;
}
.funnel-chart {
  display: flex;
  flex-direction: column;
  gap: 11px;
}
.funnel-step {
  display: grid;
  grid-template-columns: 190px 1fr 92px;
  gap: 13px;
  align-items: center;
}
.funnel-label {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: 9px;
  min-width: 0;
}
.funnel-label .mono {
  font-size: 6px;
  color: var(--muted-2);
}
.funnel-label strong {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.funnel-bar {
  height: 20px;
  background: var(--surface-2);
  border-radius: 3px;
  position: relative;
  overflow: hidden;
}
.funnel-bar span {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, var(--accent), color-mix(in srgb, var(--accent) 45%, var(--surface)));
  border-radius: 3px;
  transition: width 500ms var(--ease);
}
.funnel-bar em {
  position: absolute;
  right: 5px;
  top: 50%;
  transform: translateY(-50%);
  font-style: normal;
  font-family: var(--font-mono);
  font-size: 7px;
  color: var(--ink-2);
}
.funnel-rates {
  display: flex;
  flex-direction: column;
  gap: 1px;
  font-family: var(--font-mono);
  font-size: 7px;
  color: var(--success);
  text-align: right;
}
.funnel-rates .negative {
  color: var(--signal);
}
.note {
  margin-top: 14px;
  padding-top: 9px;
  border-top: 1px solid var(--line);
  font-size: 8px;
  color: var(--muted-2);
  line-height: 1.6;
}
.retention-wrap {
  overflow-x: auto;
}
.retention-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 580px;
}
.retention-table th {
  text-align: left;
  font-family: var(--font-mono);
  font-size: 6px;
  color: var(--muted-2);
  font-weight: 500;
  padding: 5px;
  border-bottom: 1px solid var(--line);
}
.retention-table td {
  padding: 4px;
  border-bottom: 1px solid var(--line);
  font-size: 8px;
}
.retention-cell {
  display: grid;
  place-items: center;
  min-height: 24px;
  border-radius: 3px;
  font-family: var(--font-mono);
  font-size: 7px;
  color: var(--ink);
}
.definition-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}
.definition-card {
  border: 1px solid var(--line);
  border-radius: 5px;
  padding: 9px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.definition-card .mono {
  font-size: 7px;
  color: var(--accent);
  overflow: hidden;
  text-overflow: ellipsis;
}
.definition-card strong {
  font-size: 10px;
}
.definition-card p {
  font-size: 8px;
  color: var(--muted);
}
.status-dot-line {
  display: flex;
  align-items: center;
  gap: 4px;
  font-family: var(--font-mono);
  font-size: 6px;
  color: var(--success);
  margin-top: 2px;
}
.status-dot-line i {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: currentColor;
}
.events-list {
  display: flex;
  flex-direction: column;
}
.event-row {
  display: grid;
  grid-template-columns: 150px 95px 1fr auto;
  gap: 9px;
  align-items: center;
  border-top: 1px solid var(--line);
  padding: 7px 0;
}
.event-key {
  font-size: 7px;
  color: var(--accent);
}
.event-row .mono {
  font-size: 6px;
  color: var(--muted-2);
}
.event-route {
  font-size: 8px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
@media (max-width: 1000px) {
  .metric-row {
    grid-template-columns: repeat(3, 1fr);
  }
  .event-bars {
    grid-column: 1 / -1;
  }
  .definition-grid {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 700px) {
  .funnel-step {
    grid-template-columns: 1fr;
    gap: 3px;
    padding-bottom: 7px;
    border-bottom: 1px solid var(--line);
  }
  .funnel-rates {
    flex-direction: row;
    justify-content: space-between;
    text-align: left;
  }
  .funnel-summary {
    grid-template-columns: 1fr 1fr;
  }
  .definition-grid {
    grid-template-columns: 1fr;
  }
  .event-row {
    grid-template-columns: 1fr auto;
  }
  .event-row > :nth-child(2),
  .event-row > :nth-child(3) {
    display: none;
  }
}
</style>
