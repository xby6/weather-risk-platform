<template>
  <el-dialog :model-value="modelValue" title="算法结果 AI 分析报告" width="1100px" append-to-body
    @update:model-value="$emit('update:modelValue', $event)">
    <div v-if="task" class="report-toolbar">
      <div><strong>{{ task.taskName }}</strong><span class="muted"> · {{ task.taskCode }}</span></div>
      <div class="actions">
        <el-button :loading="busy" :disabled="task.status !== 'success' || !configured" type="primary" @click="generate(false)">生成报告</el-button>
        <el-button :loading="busy" :disabled="task.status !== 'success' || !configured || !reports.length" @click="generate(true)">重新生成新版本</el-button>
        <el-button :disabled="busy" @click="load">刷新</el-button>
      </div>
    </div>
    <el-alert v-if="!configured && !loading" type="info" show-icon :closable="false" class="spaced"
      title="尚未配置默认 LLM，请由具有 AI 模型编辑权限的用户在任务页的“AI 报告设置”中选择模型。" />
    <el-alert v-if="error" type="error" :closable="false" :title="error" class="spaced" />
    <div v-loading="loading">
      <el-select v-if="reports.length" v-model="selectedId" style="width: 100%" class="spaced" @change="loadDetail">
        <el-option v-for="item in reports" :key="item.id" :value="item.id"
          :label="`${item.createTime} · 第${item.version}版 · ${statusLabel(item.status)} · ${item.modelInfo.model_name || item.modelInfo.model_code}`" />
      </el-select>
      <template v-if="report">
        <div class="report-meta spaced">
          <el-tag :type="report.status === 'success' ? 'success' : report.status === 'failed' ? 'danger' : 'warning'">{{ statusLabel(report.status) }}</el-tag>
          <span>{{ report.modelInfo.model_name || report.modelInfo.model_code }} · {{ report.createTime }}</span>
          <el-button v-if="report.status === 'failed'" :loading="busy" @click="retry">重试此报告</el-button>
          <el-button v-if="report.status === 'success'" :loading="downloading" type="success" plain @click="download">下载 Markdown</el-button>
        </div>
        <el-alert v-if="report.error" type="warning" :title="report.error" :closable="false" class="spaced" />
        <el-alert v-if="['queued', 'running'].includes(report.status)" type="info" show-icon :closable="false" class="spaced"
          :title="report.status === 'running' ? '正在整理结果并调用 LLM，请稍候。关闭页面后仍会继续生成。' : '报告已排队，页面会自动刷新。请求失败时会自动重试，最多三次。'" />
        <article v-if="report.analysis" class="report-body">
          <h2>{{ report.title }}</h2>
          <h3>结果概述</h3><p>{{ report.analysis.summary }}</p>
          <section v-for="section in sections" :key="section.key">
            <h3>{{ section.label }}</h3>
            <ul><li v-for="(item, index) in report.analysis[section.key]" :key="index">{{ item }}</li></ul>
          </section>
          <h3>系统说明</h3><ul><li v-for="item in report.facts?.limitations || []" :key="item">{{ item }}</li></ul>
        </article>
        <el-collapse v-if="report.facts" class="spaced">
          <el-collapse-item title="数据依据与统计指标" name="facts">
            <div v-for="source in report.facts.evidence" :key="source.id">
              <h4>[{{ source.id }}] {{ source.title }}</h4>
              <pre class="evidence">{{ JSON.stringify(source.data, null, 2) }}</pre>
            </div>
          </el-collapse-item>
          <el-collapse-item title="查看发送给 LLM 的数据与补充要求" name="prompt"><pre class="evidence">{{ report.prompt }}</pre></el-collapse-item>
        </el-collapse>
      </template>
      <el-empty v-else-if="!loading" description="暂无报告，任务成功后可生成分析报告" />
    </div>
  </el-dialog>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { saveAs } from 'file-saver'
import { createTaskReport, downloadTaskReport, getReportConfig, getTaskReport, listTaskReports, retryTaskReport } from '@/api/algorithmReport'

const props = defineProps({ modelValue: Boolean, task: Object })
defineEmits(['update:modelValue'])
const reports = ref([])
const report = ref(null)
const selectedId = ref('')
const loading = ref(false)
const busy = ref(false)
const downloading = ref(false)
const error = ref('')
const configured = ref(false)
const sections = [{ key: 'analysis', label: '结果分析' }, { key: 'risks', label: '风险说明' },
  { key: 'recommendations', label: '处理建议' }, { key: 'limitations', label: '数据局限' }]
let timer = null
let requestId = 0
let detailRequestId = 0
let polling = false
function statusLabel(status) { return { queued: '待生成', running: '生成中', success: '已完成', failed: '失败' }[status] || status }
watch(() => props.modelValue, visible => {
  stopPolling()
  requestId++
  detailRequestId++
  if (visible) {
    reports.value = []
    report.value = null
    selectedId.value = ''
    configured.value = false
    load()
    timer = window.setInterval(async () => {
      if (polling || busy.value || !props.modelValue || !reports.value.some(item => ['queued', 'running'].includes(item.status))) return
      polling = true
      try { await load(false) } finally { polling = false }
    }, 4000)
  }
}, { immediate: true })
async function load(showLoading = true) {
  if (!props.task) return
  const id = ++requestId
  if (showLoading) loading.value = true
  error.value = ''
  try {
    const [config, response] = await Promise.all([getReportConfig(), listTaskReports(props.task.taskCode)])
    if (id !== requestId || !props.modelValue) return
    configured.value = Boolean(config.data?.modelId)
    reports.value = response.data?.rows || []
    if (!reports.value.some(item => item.id === selectedId.value)) selectedId.value = reports.value[0]?.id || ''
    await loadDetail()
  } catch (err) {
    if (id === requestId) error.value = err.message || '报告加载失败'
  } finally {
    if (id === requestId) loading.value = false
  }
}
async function loadDetail() {
  const id = ++detailRequestId
  if (!selectedId.value) { report.value = null; return }
  try {
    const response = await getTaskReport(selectedId.value)
    if (id === detailRequestId && props.modelValue) report.value = response.data
  } catch (err) {
    if (id === detailRequestId) error.value = err.message || '报告详情加载失败'
  }
}
async function generate(regenerate) {
  busy.value = true
  error.value = ''
  try {
    const response = await createTaskReport(props.task.taskCode, regenerate)
    selectedId.value = response.data.id
    ElMessage.success('报告已加入生成队列')
    await load()
  } catch (err) { error.value = err.message || '生成报告失败' } finally { busy.value = false }
}
async function retry() {
  busy.value = true
  try { await retryTaskReport(selectedId.value); await load() }
  catch (err) { error.value = err.message || '重试失败' }
  finally { busy.value = false }
}
async function download() {
  downloading.value = true
  try {
    const blob = await downloadTaskReport(selectedId.value)
    if (blob.type.includes('json')) {
      const payload = JSON.parse(await blob.text())
      throw new Error(payload.msg || '下载报告失败')
    }
    saveAs(blob, `${props.task.taskCode}_报告_${selectedId.value}.md`)
  } catch (err) { error.value = err.message || '下载失败' } finally { downloading.value = false }
}
function stopPolling() { if (timer) window.clearInterval(timer); timer = null }
onBeforeUnmount(() => { stopPolling(); requestId++; detailRequestId++ })
</script>

<style scoped>
.report-toolbar, .report-meta { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.actions, .report-meta { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.spaced { margin: 16px 0; }
.muted, .report-meta span { color: var(--el-text-color-secondary); font-size: 13px; }
.report-body { padding: 24px; border: 1px solid var(--el-border-color); border-radius: 8px; line-height: 1.85; }
.report-body h2 { margin-top: 0; font-size: 22px; }
.report-body h3 { margin-bottom: 8px; font-size: 17px; color: var(--el-color-primary); }
.report-body p, .report-body li { white-space: pre-wrap; overflow-wrap: anywhere; }
.report-body li { margin-bottom: 8px; }
.evidence { padding: 14px; background: var(--el-fill-color-light); white-space: pre-wrap; overflow-wrap: anywhere; max-height: 360px; overflow-y: auto; }
</style>
