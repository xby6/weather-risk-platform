<template>
  <div class="computing-page">
    <el-alert
      v-if="pageError"
      class="mb16"
      type="error"
      show-icon
      :closable="false"
      :title="pageError"
    />

    <el-card shadow="never" class="main-card">
      <div class="page-header">
        <div>
          <h2>算力平台管理</h2>
          <p>管理真实算力平台、可执行算法包与静态模型，数据来自后端接口和 MySQL。</p>
        </div>
        <div class="header-actions">
          <el-button type="primary" @click="openPlatformDialog">添加算力平台</el-button>
          <el-button type="success" :loading="healthLoading" :disabled="!serverUrl" @click="checkServer()">测试连接</el-button>
          <el-button type="warning" plain :loading="modelLoading" :disabled="!serverUrl" @click="syncModels">同步算法/模型</el-button>
          <el-button type="primary" plain :disabled="!currentPlatformId" @click="openModelDialog">添加算法/模型</el-button>
          <el-button type="info" plain :disabled="!currentPlatformId" @click="openUploadDialog">上传算法/模型</el-button>
          <el-button :loading="loading" @click="reloadAll">刷新</el-button>
        </div>
      </div>

      <el-row :gutter="16" class="metric-row">
        <el-col :xs="24" :sm="8" :md="8" :lg="8">
          <el-card shadow="hover" class="metric-card">
            <div class="metric-label">算力平台数</div>
            <div class="metric-number">{{ platforms.length }}</div>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="8" :md="8" :lg="8">
          <el-card shadow="hover" class="metric-card">
            <div class="metric-label">连接状态</div>
            <el-tag :type="serverOnline ? 'success' : 'info'">{{ health.status || '未检测' }}</el-tag>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="8" :md="8" :lg="8">
          <el-card shadow="hover" class="metric-card">
            <div class="metric-label">算法/模型</div>
            <div class="metric-number">{{ models.length }}</div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="section-header">
              <span>算力平台连接</span>
              <el-button link type="primary" @click="loadPlatforms">刷新平台</el-button>
            </div>
          </template>

          <el-form label-width="92px">
            <el-form-item label="选择平台">
              <el-select v-model="currentPlatformId" clearable placeholder="请选择算力平台" style="width: 100%" @change="switchPlatform">
                <el-option v-for="item in platforms" :key="item.id" :label="item.name || item.url" :value="String(item.id)" />
              </el-select>
            </el-form-item>
            <el-form-item label="服务地址">
              <el-input v-model="serverUrl" clearable placeholder="例如：http://127.0.0.1:8000" />
            </el-form-item>
          </el-form>

          <el-empty v-if="!platforms.length && !platformLoading" description="MySQL 暂无算力平台，请先添加" />
          <el-descriptions v-else :column="1" border>
            <el-descriptions-item label="平台名称">{{ currentPlatform?.name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="服务地址">{{ serverUrl || '-' }}</el-descriptions-item>
            <el-descriptions-item label="库内状态">
              <el-tag :type="platformStatusType(currentPlatform?.status)">{{ currentPlatform?.status || 'unknown' }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="连接检测">
              <el-tag :type="serverOnline ? 'success' : 'info'">{{ health.status || '未检测' }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="服务名称">{{ health.service || '-' }}</el-descriptions-item>
            <el-descriptions-item label="版本">{{ health.version || '-' }}</el-descriptions-item>
            <el-descriptions-item label="CPU">{{ formatPercent(health.cpu_usage ?? health.cpuUsage) }}</el-descriptions-item>
            <el-descriptions-item label="内存">{{ formatPercent(health.memory_usage ?? health.memoryUsage) }}</el-descriptions-item>
            <el-descriptions-item label="检测时间">{{ lastCheckTime || '-' }}</el-descriptions-item>
          </el-descriptions>

          <div class="quick-actions">
            <el-button type="primary" plain :disabled="!serverUrl" @click="openDocs">打开接口文档</el-button>
            <el-button type="danger" plain :disabled="!currentPlatformId" @click="removePlatform">删除当前平台</el-button>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="16">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="section-header">
              <span>算法与模型登记</span>
              <span class="hint">MySQL 表：algorithm_model</span>
            </div>
          </template>
          <el-table :data="models" v-loading="modelLoading" height="420" empty-text="暂无已登记算法/模型">
            <el-table-column prop="algorithmId" label="算法编号" min-width="150" show-overflow-tooltip />
            <el-table-column prop="algorithmName" label="算法/模型名称" min-width="180" show-overflow-tooltip />
            <el-table-column prop="algorithmType" label="类型" width="110" align="center" />
            <el-table-column prop="version" label="版本" width="90" align="center" />
            <el-table-column label="状态" width="100" align="center">
              <template #default="scope">
                <el-tag :type="scope.row.status === 'enabled' ? 'success' : 'info'">
                  {{ scope.row.status === 'enabled' ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="runApi" label="运行接口" min-width="130" show-overflow-tooltip />
            <el-table-column prop="description" label="说明/路径" min-width="260" show-overflow-tooltip />
            <el-table-column label="操作" fixed="right" width="170" align="center">
              <template #default="scope">
                <el-button link type="primary" @click="toggleModelStatus(scope.row)">
                  {{ scope.row.status === 'enabled' ? '停用' : '启用' }}
                </el-button>
                <el-button link type="danger" @click="removeModel(scope.row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="platformDialogVisible" title="添加算力平台" width="560px" destroy-on-close>
      <el-form :model="platformForm" label-width="100px">
        <el-form-item label="平台名称" required>
          <el-input v-model="platformForm.name" placeholder="例如：本地算法服务器" />
        </el-form-item>
        <el-form-item label="服务地址" required>
          <el-input v-model="platformForm.url" placeholder="例如：http://127.0.0.1:8000" />
        </el-form-item>
        <el-form-item label="访问密钥">
          <el-input v-model="platformForm.token" show-password placeholder="没有可不填" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="platformForm.remark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="platformDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingPlatform" @click="savePlatform">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="modelDialogVisible" title="添加算法/模型记录" width="720px" destroy-on-close>
      <el-alert class="mb16" type="info" show-icon :closable="false" title="此操作只写入 MySQL algorithm_model 表；需要实际执行的算法请上传算法包或模型文件。" />
      <el-form :model="modelForm" label-width="120px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="算法编号" required>
              <el-input v-model="modelForm.algorithmId" placeholder="例如：icing_forecast" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="算法名称" required>
              <el-input v-model="modelForm.algorithmName" placeholder="例如：覆冰厚度预测模型" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="算法类型">
              <el-select v-model="modelForm.algorithmType" style="width: 100%">
                <el-option label="覆冰预测" value="icing" />
                <el-option label="大风预警" value="wind" />
                <el-option label="综合风险" value="composite" />
                <el-option label="文件型算法" value="file_algorithm" />
                <el-option label="表格交叉验证" value="tabular_cv" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="版本">
              <el-input v-model="modelForm.version" placeholder="v1.0" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="运行接口">
          <el-input v-model="modelForm.runApi" placeholder="/api/tasks/run" />
        </el-form-item>
        <el-form-item label="输入参数">
          <el-input v-model="modelForm.inputSchema" type="textarea" :rows="3" placeholder="temperature, humidity, wind_speed, wind_direction, precipitation, history_icing_thickness" />
        </el-form-item>
        <el-form-item label="输出结果">
          <el-input v-model="modelForm.outputSchema" type="textarea" :rows="3" placeholder="future_icing_thickness, risk_level, used_real_model" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="modelForm.remark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="modelDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingModel" @click="saveModel">保存记录</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="uploadDialogVisible" title="上传可执行算法包或模型" width="760px" destroy-on-close>
      <el-alert class="mb16" type="info" show-icon :closable="false" title="算法包使用 .zip/.py，并提供入口 runner.py:run；静态模型可使用 .pkl/.joblib/.pt/.pth/.json。" />
      <el-form :model="uploadForm" label-width="120px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="模型编号" required>
              <el-input v-model="uploadForm.algorithmId" placeholder="例如：icing_linear_v1" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模型名称" required>
              <el-input v-model="uploadForm.algorithmName" placeholder="例如：覆冰线性预测模型" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="算法类型">
              <el-input v-model="uploadForm.algorithmType" placeholder="例如：file_algorithm" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="输入类型">
              <el-select v-model="uploadForm.inputType" style="width: 100%" @change="syncUploadRunApi">
                <el-option label="原始文件" value="file" />
                <el-option label="JSON参数" value="json" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="输出类型">
              <el-input v-model="uploadForm.outputType" placeholder="xlsx / csv / json / zip" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="运行接口">
              <el-input v-model="uploadForm.runApi" placeholder="/api/tasks/run-file" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="执行入口">
              <el-input v-model="uploadForm.entrypoint" placeholder="runner.py:run（静态模型留空）" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="版本">
              <el-input v-model="uploadForm.version" placeholder="v1.0" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="输入特征">
              <el-input v-model="uploadForm.featureOrder" placeholder="逗号分隔；使用气象文件全部数值列时填写 __file_columns__" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="模型文件" required>
          <input type="file" @change="onModelFileSelected" />
          <span v-if="selectedModelFile" class="file-name">{{ selectedModelFile.name }}</span>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="uploadForm.remark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploadingModel" @click="uploadModel">上传并登记</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  checkAlgorithmServer,
  createAlgorithmModel,
  createAlgorithmServer,
  deleteAlgorithmModel,
  deleteAlgorithmServer,
  listAlgorithmModels,
  listAlgorithmServers,
  syncAlgorithmModels,
  updateAlgorithmModelStatus,
  uploadAlgorithmModel
} from '@/api/algorithm'

const platforms = ref([])
const currentPlatformId = ref('')
const serverUrl = ref('')
const health = ref({})
const models = ref([])
const pageError = ref('')
const lastCheckTime = ref('')

const platformDialogVisible = ref(false)
const modelDialogVisible = ref(false)
const uploadDialogVisible = ref(false)
const platformForm = ref({ name: '', url: 'http://127.0.0.1:8000', token: '', remark: '' })
const modelForm = ref(defaultModelForm())
const uploadForm = ref(defaultUploadForm())
const selectedModelFile = ref(null)

const platformLoading = ref(false)
const healthLoading = ref(false)
const modelLoading = ref(false)
const savingPlatform = ref(false)
const savingModel = ref(false)
const uploadingModel = ref(false)

const loading = computed(() => platformLoading.value || healthLoading.value || modelLoading.value)
const currentPlatform = computed(() => platforms.value.find(item => String(item.id) === String(currentPlatformId.value)) || null)
const serverOnline = computed(() => ['online', 'ok', 'success', 'healthy'].includes(String(health.value?.status || '').toLowerCase()))

function defaultModelForm() {
  return {
    algorithmId: '',
    algorithmName: '',
    algorithmType: 'icing',
    version: 'v1.0',
    runApi: '/api/tasks/run',
    inputSchema: 'temperature,humidity,wind_speed,wind_direction,precipitation,history_icing_thickness',
    outputSchema: 'future_icing_thickness,risk_level,used_real_model',
    remark: ''
  }
}

function defaultUploadForm() {
  return {
    algorithmId: '',
    algorithmName: '',
    algorithmType: 'file_algorithm',
    version: 'v1.0',
    inputType: 'file',
    outputType: 'xlsx',
    runApi: '/api/tasks/run-file',
    entrypoint: 'runner.py:run',
    featureOrder: '',
    remark: ''
  }
}

function unwrap(res) {
  return res && Object.prototype.hasOwnProperty.call(res, 'data') ? res.data : (res || {})
}

function getRows(res) {
  const data = unwrap(res)
  if (Array.isArray(data?.rows)) return data.rows
  if (Array.isArray(res?.rows)) return res.rows
  if (Array.isArray(data)) return data
  if (Array.isArray(res)) return res
  return []
}

function getErrorMessage(error) {
  return error?.response?.data?.msg || error?.response?.data?.message || error?.msg || error?.message || String(error || '未知错误')
}

function normalizeUrl(url) {
  return String(url || '').trim().replace(/\/+$/, '')
}

function normalizeServer(item) {
  return {
    ...item,
    id: String(item.id ?? item.serverId ?? item.server_id ?? ''),
    name: item.name || item.serverName || item.server_name || '',
    url: normalizeUrl(item.url || item.serverUrl || item.server_url || ''),
    status: item.status || 'unknown'
  }
}

function normalizeModel(item) {
  return {
    ...item,
    id: String(item.id ?? ''),
    serverId: item.serverId || item.server_id || '',
    serverUrl: item.serverUrl || item.server_url || '',
    algorithmId: item.algorithmId || item.algorithm_id || '',
    algorithmName: item.algorithmName || item.algorithm_name || '',
    algorithmType: item.algorithmType || item.algorithm_type || item.type || '',
    version: item.version || item.algorithm_version || '',
    runApi: item.runApi || item.run_api || '',
    status: item.status || 'enabled',
    description: item.description || item.remark || ''
  }
}

function nowText() {
  const date = new Date()
  const pad = n => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

function formatPercent(value) {
  if (value === null || value === undefined || value === '') return '-'
  const number = Number(value)
  return Number.isNaN(number) ? String(value) : `${number.toFixed(1)}%`
}

function platformStatusType(status) {
  const value = String(status || '').toLowerCase()
  if (['online', 'ok', 'success'].includes(value)) return 'success'
  if (value === 'offline') return 'danger'
  return 'info'
}

async function loadPlatforms() {
  platformLoading.value = true
  try {
    const res = await listAlgorithmServers()
    platforms.value = getRows(res).map(normalizeServer).filter(item => item.id || item.url)
    if (platforms.value.length) {
      if (!currentPlatformId.value || !platforms.value.some(item => String(item.id) === String(currentPlatformId.value))) {
        currentPlatformId.value = String(platforms.value[0].id)
      }
      serverUrl.value = currentPlatform.value?.url || platforms.value[0].url || ''
    } else {
      currentPlatformId.value = ''
      serverUrl.value = ''
    }
    pageError.value = ''
  } catch (error) {
    platforms.value = []
    currentPlatformId.value = ''
    serverUrl.value = ''
    pageError.value = `加载算力平台失败：${getErrorMessage(error)}`
  } finally {
    platformLoading.value = false
  }
}

async function loadModels() {
  modelLoading.value = true
  try {
    const params = currentPlatformId.value ? { serverId: currentPlatformId.value } : (serverUrl.value ? { serverUrl: serverUrl.value } : {})
    const res = await listAlgorithmModels(params)
    models.value = getRows(res).map(normalizeModel)
  } catch (error) {
    models.value = []
    pageError.value = `加载算法模型失败：${getErrorMessage(error)}`
  } finally {
    modelLoading.value = false
  }
}

async function reloadAll() {
  pageError.value = ''
  await loadPlatforms()
  await loadModels()
}

function switchPlatform(id) {
  const item = platforms.value.find(platform => String(platform.id) === String(id))
  serverUrl.value = normalizeUrl(item?.url || '')
  health.value = {}
  loadModels()
}

async function checkServer({ notify = true } = {}) {
  if (!serverUrl.value) return ElMessage.warning('请先选择或填写算法服务地址')
  healthLoading.value = true
  try {
    const res = await checkAlgorithmServer(serverUrl.value)
    health.value = unwrap(res) || {}
    lastCheckTime.value = nowText()
    if (notify) ElMessage.success('连接成功')
  } catch (error) {
    health.value = { status: 'offline' }
    lastCheckTime.value = nowText()
    if (notify) ElMessage.error(`连接失败：${getErrorMessage(error)}`)
  } finally {
    healthLoading.value = false
  }
}

async function syncModels() {
  if (!serverUrl.value) return ElMessage.warning('请先选择或填写算法服务地址')
  modelLoading.value = true
  try {
    await syncAlgorithmModels(serverUrl.value)
    await loadModels()
    ElMessage.success('同步完成')
  } catch (error) {
    ElMessage.error(`同步失败：${getErrorMessage(error)}`)
  } finally {
    modelLoading.value = false
  }
}

function openPlatformDialog() {
  platformForm.value = { name: '', url: serverUrl.value || 'http://127.0.0.1:8000', token: '', remark: '' }
  platformDialogVisible.value = true
}

function openModelDialog() {
  if (!currentPlatformId.value) return ElMessage.warning('请先选择算力平台')
  modelForm.value = defaultModelForm()
  modelDialogVisible.value = true
}

function openUploadDialog() {
  if (!currentPlatformId.value) return ElMessage.warning('请先选择算力平台')
  uploadForm.value = defaultUploadForm()
  selectedModelFile.value = null
  uploadDialogVisible.value = true
}

async function savePlatform() {
  const name = String(platformForm.value.name || '').trim()
  const url = normalizeUrl(platformForm.value.url)
  if (!name) return ElMessage.warning('请填写平台名称')
  if (!/^https?:\/\//.test(url)) return ElMessage.warning('服务地址必须以 http:// 或 https:// 开头')
  savingPlatform.value = true
  try {
    const res = await createAlgorithmServer({ ...platformForm.value, name, url, serverUrl: url })
    const created = normalizeServer(unwrap(res) || {})
    platformDialogVisible.value = false
    await loadPlatforms()
    if (created.id) currentPlatformId.value = created.id
    if (created.url) serverUrl.value = created.url
    await loadModels()
    ElMessage.success('算力平台已保存')
  } catch (error) {
    ElMessage.error(`保存失败：${getErrorMessage(error)}`)
  } finally {
    savingPlatform.value = false
  }
}

async function saveModel() {
  if (!modelForm.value.algorithmId) return ElMessage.warning('请填写算法编号')
  if (!modelForm.value.algorithmName) return ElMessage.warning('请填写算法名称')
  savingModel.value = true
  try {
    await createAlgorithmModel({
      ...modelForm.value,
      serverId: currentPlatformId.value,
      serverUrl: serverUrl.value,
      status: 'enabled'
    })
    modelDialogVisible.value = false
    await loadModels()
    ElMessage.success('算法/模型已登记')
  } catch (error) {
    ElMessage.error(`保存失败：${getErrorMessage(error)}`)
  } finally {
    savingModel.value = false
  }
}

function onModelFileSelected(event) {
  selectedModelFile.value = event.target.files?.[0] || null
}

function syncUploadRunApi(inputType) {
  uploadForm.value.runApi = inputType === 'file' ? '/api/tasks/run-file' : '/api/tasks/run'
}

async function uploadModel() {
  if (!uploadForm.value.algorithmId) return ElMessage.warning('请填写模型编号')
  if (!uploadForm.value.algorithmName) return ElMessage.warning('请填写模型名称')
  if (!selectedModelFile.value) return ElMessage.warning('请选择模型文件')
  const fd = new FormData()
  fd.append('file', selectedModelFile.value)
  fd.append('serverId', currentPlatformId.value)
  fd.append('serverUrl', serverUrl.value)
  Object.entries(uploadForm.value).forEach(([key, value]) => fd.append(key, value || ''))
  uploadingModel.value = true
  try {
    const res = await uploadAlgorithmModel(fd)
    uploadDialogVisible.value = false
    await loadModels()
    const remoteError = unwrap(res)?.remoteError
    if (remoteError) ElMessage.warning(`模型已保存，但同步算法服务失败：${remoteError}`)
    else ElMessage.success('模型已上传、登记并同步到 algorithm-server')
  } catch (error) {
    ElMessage.error(`上传失败：${getErrorMessage(error)}`)
  } finally {
    uploadingModel.value = false
  }
}

async function toggleModelStatus(row) {
  const next = row.status === 'enabled' ? 'disabled' : 'enabled'
  await updateAlgorithmModelStatus(row.id, next)
  await loadModels()
  ElMessage.success('状态已更新')
}

async function removeModel(row) {
  await ElMessageBox.confirm(`确认逻辑删除 ${row.algorithmName || row.algorithmId} 吗？删除后同步算法也不会自动恢复。`, '提示', { type: 'warning' })
  await deleteAlgorithmModel(row.id)
  await loadModels()
  ElMessage.success('已逻辑删除')
}

async function removePlatform() {
  if (!currentPlatformId.value) return ElMessage.warning('请先选择算力平台')
  await ElMessageBox.confirm('确认删除当前算力平台吗？', '提示', { type: 'warning' })
  await deleteAlgorithmServer(currentPlatformId.value)
  health.value = {}
  ElMessage.success('已删除')
  await reloadAll()
}

function openDocs() {
  if (serverUrl.value) window.open(`${normalizeUrl(serverUrl.value)}/docs`, '_blank')
}

onMounted(async () => {
  await reloadAll()
  if (serverUrl.value) await checkServer({ notify: false })
})
</script>

<style scoped>
.computing-page { padding: 20px; }
.main-card, .section-card { margin-bottom: 16px; }
.page-header, .section-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.page-header h2 { margin: 0 0 8px; font-size: 22px; font-weight: 600; }
.page-header p { margin: 0; color: #606266; }
.header-actions { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 8px; }
.metric-row { margin-top: 16px; }
.metric-card { min-height: 98px; }
.metric-label { color: #606266; margin-bottom: 12px; }
.metric-number { font-size: 30px; font-weight: 700; color: #303133; }
.mb16 { margin-bottom: 16px; }
.hint { color: #909399; font-size: 13px; }
.quick-actions { margin-top: 16px; display: flex; gap: 8px; flex-wrap: wrap; }
.file-name { margin-left: 12px; color: #606266; }
</style>
