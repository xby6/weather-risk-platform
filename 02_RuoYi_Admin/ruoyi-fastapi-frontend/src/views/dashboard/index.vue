<template>
  <div class="dashboard-real">
    <el-alert
      v-if="loadError"
      :title="loadError"
      type="warning"
      show-icon
      :closable="false"
      class="dashboard-alert"
    />

    <el-row :gutter="16" class="stat-row">
      <el-col :span="6" v-for="item in stats" :key="item.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ item.value }}</div>
          <div class="stat-label">{{ item.label }}</div>
          <div class="stat-desc">{{ item.desc }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="chart-row">
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="card-title">
              <span>城市预测风险分布</span>
              <small>记录数</small>
            </div>
          </template>
          <div v-show="hasRiskDistribution" ref="riskChartRef" class="dashboard-chart" />
          <el-empty v-if="!hasRiskDistribution" description="暂无城市预测风险数据" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="card-title">
              <span>逐小时故障概率趋势</span>
              <small>来自最新预测任务</small>
            </div>
          </template>
          <div v-show="hasHourlyTrend" ref="hourlyChartRef" class="dashboard-chart" />
          <el-empty v-if="!hasHourlyTrend" description="暂无逐小时故障概率数据" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="table-row">
      <el-col :span="12">
        <el-card shadow="never" header="最近算法任务">
          <el-table :data="taskRows" height="320" empty-text="暂无真实算法任务">
            <el-table-column prop="taskCode" label="任务编号" min-width="150" show-overflow-tooltip />
            <el-table-column prop="taskName" label="任务名称" min-width="180" show-overflow-tooltip />
            <el-table-column prop="algorithmName" label="算法模型" min-width="150" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="100" align="center">
              <template #default="scope"><el-tag :type="statusTagType(scope.row.status)">{{ statusText(scope.row.status) }}</el-tag></template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" header="当前预警信息">
          <el-table :data="warningRows" height="320" empty-text="暂无真实预警信息">
            <el-table-column prop="time" label="时间" width="170" />
            <el-table-column prop="region" label="区域" width="120" />
            <el-table-column prop="line_code" label="线路" width="120" />
            <el-table-column prop="name" label="预警类型" min-width="150" show-overflow-tooltip />
            <el-table-column prop="level" label="等级" width="100" align="center" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup name="DashBoard">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import request from '@/utils/request'

const screenData = ref({})
const taskRows = ref([])
const loadError = ref('')
const riskChartRef = ref(null)
const hourlyChartRef = ref(null)
let riskChart = null
let hourlyChart = null

const warningRows = computed(() => screenData.value.warning_list || [])
const riskDistribution = computed(() => screenData.value.risk_distribution_by_region || {})
const hourlyTrend = computed(() => screenData.value.prediction_hourly_trend || {})
const hasRiskDistribution = computed(() => Array.isArray(riskDistribution.value.cities) && riskDistribution.value.cities.length > 0)
const hasHourlyTrend = computed(() => Array.isArray(hourlyTrend.value.hours) && hourlyTrend.value.hours.length > 0 && Array.isArray(hourlyTrend.value.series) && hourlyTrend.value.series.length > 0)
const stats = computed(() => [
  { label: '气象文件数', value: screenData.value.file_count || 0, desc: '后端真实气象文件记录' },
  { label: '已入库文件', value: screenData.value.finished_file_count || 0, desc: '解析入库状态为已完成' },
  { label: '算法任务数', value: taskRows.value.length, desc: '本地任务记录' },
  { label: '当前预警数', value: screenData.value.warning_count || 0, desc: '由任务结果生成' }
])

function unwrap(res) {
  if (!res) return {}
  if (res.code === 200) return res.data || {}
  if (res.data?.code === 200) return res.data.data || {}
  return res.data || res
}

async function loadData() {
  loadError.value = ''
  try {
    const screenRes = await request({ url: '/monitor/screen-all-data', method: 'get' })
    screenData.value = unwrap(screenRes)
    const taskRes = await request({ url: '/algorithm/task/list', method: 'get' })
    taskRows.value = unwrap(taskRes).rows || []
    await nextTick()
    renderCharts()
  } catch (error) {
    console.error('首页数据加载失败:', error)
    loadError.value = '首页真实数据加载失败，请检查后端 /monitor/screen-all-data 与 /algorithm/task/list 接口'
    screenData.value = {}
    taskRows.value = []
    await nextTick()
    renderCharts()
  }
}

function statusText(status) {
  return { created: '已创建', submitted: '已提交', queued: '排队中', running: '运行中', success: '已完成', failed: '失败', stopped: '已停止' }[status] || status || '未知'
}
function statusTagType(status) {
  if (status === 'success') return 'success'
  if (['running', 'queued', 'submitted'].includes(status)) return 'warning'
  if (status === 'failed') return 'danger'
  return 'info'
}

function cityLabel(value) {
  const text = String(value || '').replace(/市$/, '')
  return text.length > 5 ? `${text.slice(0, 5)}...` : text
}

function numberList(values) {
  return Array.isArray(values) ? values.map(item => Number(item || 0)) : []
}

function renderRiskChart() {
  if (!riskChartRef.value || !hasRiskDistribution.value) {
    riskChart?.clear()
    return
  }
  if (!riskChart) riskChart = echarts.init(riskChartRef.value)
  const data = riskDistribution.value
  const seriesConfig = [
    { name: '高', field: 'level1', color: '#f56c6c' },
    { name: '较高', field: 'level2', color: '#e6a23c' },
    { name: '一般', field: 'level3', color: '#f3c969' },
    { name: '低', field: 'level4', color: '#409eff' },
    { name: '正常', field: 'level5', color: '#67c23a' }
  ].filter(item => numberList(data[item.field]).some(value => value > 0) || item.field !== 'level5')

  riskChart.setOption({
    color: seriesConfig.map(item => item.color),
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: {
      top: 0,
      right: 8,
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: '#606266' }
    },
    grid: { left: 36, right: 20, top: 46, bottom: 58, containLabel: true },
    xAxis: {
      type: 'category',
      data: data.cities || [],
      axisTick: { show: false },
      axisLabel: { interval: 0, rotate: 32, color: '#606266', formatter: cityLabel }
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: '#606266' },
      splitLine: { lineStyle: { color: '#edf0f5' } }
    },
    series: seriesConfig.map(item => ({
      name: item.name,
      type: 'bar',
      stack: 'risk',
      barMaxWidth: 22,
      emphasis: { focus: 'series' },
      data: numberList(data[item.field])
    }))
  }, true)
}

function renderHourlyChart() {
  if (!hourlyChartRef.value || !hasHourlyTrend.value) {
    hourlyChart?.clear()
    return
  }
  if (!hourlyChart) hourlyChart = echarts.init(hourlyChartRef.value)
  const data = hourlyTrend.value
  const colors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#8b5cf6', '#14b8a6']

  hourlyChart.setOption({
    color: colors,
    tooltip: {
      trigger: 'axis',
      valueFormatter: value => `${Number(value || 0).toFixed(1)}%`
    },
    legend: {
      top: 0,
      right: 8,
      type: 'scroll',
      itemWidth: 14,
      itemHeight: 8,
      textStyle: { color: '#606266' }
    },
    grid: { left: 42, right: 24, top: 48, bottom: 34, containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: (data.hours || []).map(hour => `${hour}h`),
      axisTick: { show: false },
      axisLabel: { color: '#606266' }
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: { color: '#606266', formatter: '{value}%' },
      splitLine: { lineStyle: { color: '#edf0f5' } }
    },
    series: (data.series || []).map((item, index) => ({
      name: item.name,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { width: 2 },
      itemStyle: { color: colors[index % colors.length] },
      areaStyle: { opacity: 0.06 },
      data: numberList(item.data)
    }))
  }, true)
}

function renderCharts() {
  renderRiskChart()
  renderHourlyChart()
}

function resizeCharts() {
  riskChart?.resize()
  hourlyChart?.resize()
}

onMounted(() => {
  loadData()
  window.addEventListener('resize', resizeCharts)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  riskChart?.dispose()
  hourlyChart?.dispose()
  riskChart = null
  hourlyChart = null
})
</script>

<style scoped>
.dashboard-real { padding: 16px; }
.dashboard-alert { margin-bottom: 16px; }
.stat-row { margin-bottom: 16px; }
.stat-card { min-height: 110px; }
.stat-value { font-size: 30px; font-weight: 700; color: #1677ff; }
.stat-label { margin-top: 8px; font-weight: 600; }
.stat-desc { margin-top: 6px; color: #909399; font-size: 12px; }
.chart-row { margin-bottom: 16px; }
.table-row { margin-bottom: 16px; }
.chart-card { height: 360px; }
.chart-card :deep(.el-card__body) {
  height: calc(100% - 57px);
  box-sizing: border-box;
}
.card-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-weight: 600;
}
.card-title small {
  color: #909399;
  font-size: 12px;
  font-weight: 400;
}
.dashboard-chart {
  width: 100%;
  height: 100%;
  min-height: 280px;
}
</style>
