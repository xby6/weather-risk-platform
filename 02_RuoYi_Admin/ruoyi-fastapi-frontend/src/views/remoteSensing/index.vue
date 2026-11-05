<template>
  <div class="app-container weather-explorer" tabindex="0" @contextmenu.prevent="openBlankMenu">
    <input ref="nativeFileInputRef" class="native-file-input" type="file" multiple accept=".xlsx,.xls,.csv" @change="handleNativeUpload" />

    <el-card shadow="never" class="explorer-card">
      <template #header>
        <div class="explorer-header">
          <div>
            <div class="page-title">气象数据管理</div>
            <div class="page-subtitle">以文件夹方式管理真实 Excel/CSV 气象数据文件，支持上传、移动、复制和粘贴。</div>
          </div>
          <div class="header-actions">
            <el-button :icon="Back" :disabled="currentFolderId === 0" @click="goParent">返回上级</el-button>
            <el-button type="success" :icon="FolderAdd" @click="() => handleCreateFolder()">新建文件夹</el-button>
            <el-upload :show-file-list="false" accept=".xlsx,.xls,.csv" :http-request="handleUpload">
              <el-button type="primary" :icon="Upload">上传文件</el-button>
            </el-upload>
            <el-button :icon="Refresh" @click="loadData">刷新</el-button>
          </div>
        </div>
      </template>

      <el-row :gutter="12" class="metric-row">
        <el-col :span="6" v-for="item in metrics" :key="item.label">
          <div class="metric-card">
            <div class="metric-value">{{ item.value }}</div>
            <div class="metric-label">{{ item.label }}</div>
            <div class="metric-desc">{{ item.desc }}</div>
          </div>
        </el-col>
      </el-row>

      <div class="toolbar">
        <div class="breadcrumb-wrap">
          <el-icon><House /></el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>
              <span class="breadcrumb-link" @click="enterFolder(0)">气象数据</span>
            </el-breadcrumb-item>
            <el-breadcrumb-item v-for="item in breadcrumbItems" :key="item.id">
              <span class="breadcrumb-link" @click="enterFolder(item.id)">{{ item.name }}</span>
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="filter-wrap">
          <el-input v-model="queryParams.keyword" clearable :prefix-icon="Search" placeholder="搜索文件夹、文件名、区域或线路" style="width: 280px" />
          <el-select v-model="queryParams.fileType" clearable placeholder="文件类型" style="width: 120px">
            <el-option label="Excel" value="excel" />
            <el-option label="CSV" value="csv" />
          </el-select>
          <el-select v-model="queryParams.status" clearable placeholder="状态" style="width: 130px">
            <el-option label="待校验" value="pending" />
            <el-option label="已入库" value="finished" />
            <el-option label="异常" value="failed" />
          </el-select>
          <el-button @click="resetQuery">重置</el-button>
        </div>
      </div>

      <div class="explorer-body">
        <aside class="folder-tree">
          <div class="pane-title">目录</div>
          <el-tree
            :data="folderTree"
            node-key="id"
            :default-expanded-keys="[0, currentFolderId]"
            :expand-on-click-node="false"
            highlight-current
            @node-click="handleTreeNodeClick"
          >
            <template #default="{ data }">
              <span class="tree-node">
                <el-icon><Folder /></el-icon>
                <span>{{ data.label }}</span>
              </span>
            </template>
          </el-tree>
        </aside>

        <main
          v-loading="loading"
          class="file-area"
          :class="{ 'is-dragover': dragOver }"
          @click="selectItem(null)"
          @dragover.prevent="handleAreaDragOver"
          @dragleave="handleAreaDragLeave"
          @drop.prevent="handleDropToCurrent"
        >
          <div class="area-meta">
            <div>
              <strong>{{ currentFolderName }}</strong>
              <span>{{ searchMode ? '搜索结果' : `${currentItems.length} 个项目` }}</span>
            </div>
            <div class="clipboard-hint" v-if="clipboard.item">
              已复制：{{ clipboard.item.name }}，按 Ctrl+V 粘贴
            </div>
          </div>

          <el-empty v-if="displayItems.length === 0" :description="emptyText" :image-size="96" />

          <div v-else class="file-grid">
            <div
              v-for="item in displayItems"
              :key="item.id"
              class="file-tile"
              :class="{ active: selectedItem?.id === item.id, folder: item.isFolder }"
              draggable="true"
              @click.stop="selectItem(item)"
              @dblclick.stop="handleOpenItem(item)"
              @contextmenu.stop.prevent="openItemMenu($event, item)"
              @dragstart="handleDragStart($event, item)"
              @dragend="handleDragEnd"
              @dragover.prevent="item.isFolder && handleTileDragOver($event)"
              @drop.stop.prevent="item.isFolder && handleDropToFolder($event, item)"
            >
              <div class="tile-icon" :class="{ folder: item.isFolder, csv: item.fileType === 'csv' }">
                <el-icon v-if="item.isFolder"><Folder /></el-icon>
                <el-icon v-else><Document /></el-icon>
              </div>
              <div class="tile-name" :title="item.name">{{ item.name }}</div>
              <div class="tile-meta">
                <template v-if="item.isFolder">文件夹</template>
                <template v-else>{{ fileTypeText(item.fileType) }} · {{ item.size || formatSize(item.fileSize) }}</template>
              </div>
              <el-tag v-if="!item.isFolder" size="small" :type="statusTagType(item.status)">{{ statusText(item.status) }}</el-tag>
            </div>
          </div>
        </main>

        <aside class="detail-pane">
          <div class="pane-title">详细信息</div>
          <template v-if="selectedItem">
            <div class="detail-icon" :class="{ folder: selectedItem.isFolder }">
              <el-icon v-if="selectedItem.isFolder"><Folder /></el-icon>
              <el-icon v-else><Document /></el-icon>
            </div>
            <div class="detail-name">{{ selectedItem.name }}</div>
            <el-descriptions :column="1" size="small" border>
              <el-descriptions-item label="类型">{{ selectedItem.isFolder ? '文件夹' : fileTypeText(selectedItem.fileType) }}</el-descriptions-item>
              <el-descriptions-item v-if="!selectedItem.isFolder" label="数据类型">{{ dataTypeText(selectedItem.dataType) }}</el-descriptions-item>
              <el-descriptions-item v-if="!selectedItem.isFolder" label="区域">{{ selectedItem.region || '-' }}</el-descriptions-item>
              <el-descriptions-item v-if="!selectedItem.isFolder" label="站点/线路">{{ selectedItem.stationOrLine || '-' }}</el-descriptions-item>
              <el-descriptions-item v-if="!selectedItem.isFolder" label="记录/字段">{{ selectedItem.recordCount || 0 }} / {{ selectedItem.fieldCount || 0 }}</el-descriptions-item>
              <el-descriptions-item label="创建时间">{{ selectedItem.createTime || '-' }}</el-descriptions-item>
              <el-descriptions-item label="更新时间">{{ selectedItem.updateTime || '-' }}</el-descriptions-item>
            </el-descriptions>
          </template>
          <el-empty v-else description="选择一个文件或文件夹查看详情" :image-size="80" />
        </aside>
      </div>
    </el-card>

    <div
      v-if="contextMenu.visible"
      class="context-menu"
      :style="{ left: `${contextMenu.x}px`, top: `${contextMenu.y}px` }"
      @click.stop
    >
      <button v-if="contextMenu.item?.isFolder" @click="handleMenuAction('open')">打开</button>
      <button v-if="contextMenu.item && !contextMenu.item.isFolder" @click="handleMenuAction('preview')">查看详情</button>
      <button @click="handleMenuAction('newFolder')">新建文件夹</button>
      <button @click="handleMenuAction('upload')">上传文件</button>
      <button v-if="contextMenu.item" @click="handleMenuAction('copy')">复制</button>
      <button :disabled="!clipboard.item" @click="handleMenuAction('paste')">粘贴</button>
      <button v-if="contextMenu.item && !contextMenu.item.isFolder" @click="handleMenuAction('process')">解析入库</button>
      <button v-if="contextMenu.item && !contextMenu.item.isFolder" @click="handleMenuAction('task')">生成任务</button>
      <button v-if="contextMenu.item" class="danger" @click="handleMenuAction('delete')">删除</button>
    </div>

    <el-dialog v-model="previewVisible" title="气象数据文件详情" width="680px" append-to-body>
      <template v-if="currentRow">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="文件名称">{{ currentRow.name }}</el-descriptions-item>
          <el-descriptions-item label="所在目录">{{ folderPathText(currentRow.parentId) }}</el-descriptions-item>
          <el-descriptions-item label="数据类型">{{ dataTypeText(currentRow.dataType) }}</el-descriptions-item>
          <el-descriptions-item label="文件类型">{{ fileTypeText(currentRow.fileType) }}</el-descriptions-item>
          <el-descriptions-item label="区域">{{ currentRow.region || '-' }}</el-descriptions-item>
          <el-descriptions-item label="站点/线路">{{ currentRow.stationOrLine || '-' }}</el-descriptions-item>
          <el-descriptions-item label="时间范围">{{ currentRow.startTime || '-' }} 至 {{ currentRow.endTime || '-' }}</el-descriptions-item>
          <el-descriptions-item label="记录数 / 字段数">{{ currentRow.recordCount || 0 }} / {{ currentRow.fieldCount || 0 }}</el-descriptions-item>
          <el-descriptions-item label="文件大小">{{ currentRow.size || formatSize(currentRow.fileSize) }}</el-descriptions-item>
          <el-descriptions-item label="文件路径">{{ currentRow.filePath || '-' }}</el-descriptions-item>
          <el-descriptions-item label="字段说明">{{ currentRow.fields || '-' }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ currentRow.remark || '-' }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="RemoteSensing">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Back, Document, Folder, FolderAdd, House, Refresh, Search, Upload } from '@element-plus/icons-vue'
import {
  copyWeatherFile,
  createWeatherFolder,
  deleteWeatherFile,
  listWeatherFiles,
  moveWeatherFile,
  processWeatherFile,
  uploadWeatherFile
} from '@/api/weatherFile'

const loading = ref(false)
const previewVisible = ref(false)
const currentRow = ref(null)
const currentFolderId = ref(0)
const selectedItem = ref(null)
const dataList = ref([])
const dragOver = ref(false)
const dragItem = ref(null)
const nativeFileInputRef = ref(null)
const uploadTargetFolderId = ref(0)
const clipboard = reactive({ mode: '', item: null })
const contextMenu = reactive({ visible: false, x: 0, y: 0, item: null })
const queryParams = ref({ keyword: '', fileType: '', status: '' })

const itemMap = computed(() => {
  const map = new Map()
  dataList.value.forEach(item => map.set(Number(item.id), item))
  return map
})

const folders = computed(() => dataList.value.filter(item => item.isFolder || item.itemType === 'folder'))
const files = computed(() => dataList.value.filter(item => !(item.isFolder || item.itemType === 'folder')))
const currentFolderName = computed(() => currentFolderId.value ? itemMap.value.get(Number(currentFolderId.value))?.name || '未知目录' : '气象数据')
const searchMode = computed(() => Boolean(queryParams.value.keyword || queryParams.value.fileType || queryParams.value.status))

const currentItems = computed(() => {
  const parentId = Number(currentFolderId.value || 0)
  return dataList.value
    .filter(item => Number(item.parentId || 0) === parentId)
    .sort(itemSort)
})

const displayItems = computed(() => {
  const keyword = queryParams.value.keyword?.trim()
  const source = searchMode.value ? dataList.value : currentItems.value
  return source
    .filter(item => {
      const isFolder = item.isFolder || item.itemType === 'folder'
      const keywordHit = !keyword || [item.name, item.region, item.stationOrLine, item.filePath, item.fields].some(value => String(value || '').includes(keyword))
      const fileTypeHit = isFolder || !queryParams.value.fileType || item.fileType === queryParams.value.fileType
      const statusHit = isFolder || !queryParams.value.status || item.status === queryParams.value.status
      return keywordHit && fileTypeHit && statusHit
    })
    .sort(itemSort)
})

const folderTree = computed(() => [{
  id: 0,
  label: '气象数据',
  children: buildFolderChildren(0)
}])

const breadcrumbItems = computed(() => {
  const path = []
  let id = Number(currentFolderId.value || 0)
  const guard = new Set()
  while (id && !guard.has(id)) {
    guard.add(id)
    const item = itemMap.value.get(id)
    if (!item) break
    path.unshift(item)
    id = Number(item.parentId || 0)
  }
  return path
})

const metrics = computed(() => {
  const finished = files.value.filter(item => item.status === 'finished').length
  const records = files.value.reduce((sum, item) => sum + Number(item.recordCount || 0), 0)
  return [
    { label: '文件夹', value: `${folders.value.length} 个`, desc: '目录化管理气象文件' },
    { label: '气象文件', value: `${files.value.length} 个`, desc: 'Excel/CSV 真实文件记录' },
    { label: '已解析入库', value: `${finished} 个`, desc: '可直接用于任务选择' },
    { label: '观测记录数', value: `${records.toLocaleString()} 条`, desc: '由上传文件解析统计' }
  ]
})

const emptyText = computed(() => searchMode.value ? '没有匹配的气象数据文件' : '当前文件夹为空，可上传文件或新建文件夹')

function normalizeItem(item) {
  const itemType = item.itemType || (item.isFolder ? 'folder' : 'file')
  return {
    ...item,
    itemType,
    isFolder: itemType === 'folder',
    parentId: Number(item.parentId || 0)
  }
}

function itemSort(a, b) {
  const af = a.isFolder || a.itemType === 'folder'
  const bf = b.isFolder || b.itemType === 'folder'
  if (af !== bf) return af ? -1 : 1
  return String(a.name || '').localeCompare(String(b.name || ''), 'zh-CN')
}

function buildFolderChildren(parentId) {
  return folders.value
    .filter(item => Number(item.parentId || 0) === Number(parentId || 0))
    .sort(itemSort)
    .map(item => ({
      id: Number(item.id),
      label: item.name,
      children: buildFolderChildren(item.id)
    }))
}

async function loadData() {
  loading.value = true
  try {
    const res = await listWeatherFiles()
    dataList.value = (res.data?.rows || []).map(normalizeItem)
    if (currentFolderId.value && !itemMap.value.has(Number(currentFolderId.value))) {
      currentFolderId.value = 0
    }
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  queryParams.value = { keyword: '', fileType: '', status: '' }
}

function handleTreeNodeClick(data) {
  enterFolder(data.id)
}

function enterFolder(id) {
  currentFolderId.value = Number(id || 0)
  selectedItem.value = null
  hideContextMenu()
}

function goParent() {
  if (!currentFolderId.value) return
  const current = itemMap.value.get(Number(currentFolderId.value))
  enterFolder(current?.parentId || 0)
}

function handleOpenItem(item) {
  if (item.isFolder) {
    enterFolder(item.id)
  } else {
    handlePreview(item)
  }
}

function selectItem(item) {
  selectedItem.value = item
}

async function handleCreateFolder(targetParentId = currentFolderId.value) {
  hideContextMenu()
  const numericParentId = Number(targetParentId)
  const parentId = Number.isFinite(numericParentId) ? numericParentId : currentFolderId.value
  try {
    const { value } = await ElMessageBox.prompt('请输入文件夹名称', '新建文件夹', {
      confirmButtonText: '创建',
      cancelButtonText: '取消',
      inputPattern: /^(?!\s*$).+/,
      inputErrorMessage: '文件夹名称不能为空'
    })
    await createWeatherFolder({ name: value.trim(), parentId })
    ElMessage.success('文件夹已创建')
    await loadData()
  } catch (error) {
    if (error !== 'cancel') console.error(error)
  }
}

async function handleUpload(options) {
  await uploadWeatherFile(options.file, currentFolderId.value)
  ElMessage.success('文件上传成功')
  await loadData()
}

function openNativeUpload(targetParentId = currentFolderId.value) {
  uploadTargetFolderId.value = Number(targetParentId || 0)
  nativeFileInputRef.value?.click()
}

async function handleNativeUpload(event) {
  const files = Array.from(event.target.files || [])
  if (!files.length) return
  await uploadFiles(files, uploadTargetFolderId.value)
  event.target.value = ''
}

async function uploadFiles(files, parentId) {
  loading.value = true
  try {
    for (const file of files) {
      await uploadWeatherFile(file, parentId)
    }
    ElMessage.success(`已上传 ${files.length} 个文件`)
    await loadData()
  } finally {
    loading.value = false
  }
}

async function handleProcess(row) {
  await processWeatherFile(row.id)
  ElMessage.success('解析入库状态已更新')
  await loadData()
}

function handlePreview(row) {
  currentRow.value = row
  previewVisible.value = true
}

function handleCreateTask(row) {
  const taskSeed = { id: row.id, source: 'weather_file', dataName: row.name, region: row.region || '', lineCode: row.stationOrLine || '', filePath: row.filePath || '', dataType: row.dataType, startTime: row.startTime || '', endTime: row.endTime || '', fields: row.fields || '' }
  sessionStorage.setItem('lpw_task_seed_from_weather_data', JSON.stringify(taskSeed))
  ElMessage.success('已生成任务参数，请前往任务管理页面创建算法任务')
}

async function handleDelete(row) {
  const message = row.isFolder ? `确认删除文件夹「${row.name}」及其中所有内容吗？` : `确认删除气象数据文件「${row.name}」吗？`
  await ElMessageBox.confirm(message, '提示', { type: 'warning' })
  await deleteWeatherFile(row.id)
  if (selectedItem.value?.id === row.id) selectedItem.value = null
  ElMessage.success('删除成功')
  await loadData()
}

function handleDragStart(event, item) {
  dragItem.value = item
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', String(item.id))
}

function handleDragEnd() {
  dragItem.value = null
  dragOver.value = false
}

function handleAreaDragOver() {
  dragOver.value = true
}

function handleAreaDragLeave() {
  dragOver.value = false
}

function handleTileDragOver(event) {
  event.dataTransfer.dropEffect = 'move'
}

async function handleDropToCurrent(event) {
  dragOver.value = false
  const files = Array.from(event.dataTransfer.files || [])
  if (files.length) {
    await uploadFiles(files, currentFolderId.value)
    return
  }
  if (dragItem.value && Number(dragItem.value.parentId || 0) !== Number(currentFolderId.value || 0)) {
    await moveItemToFolder(dragItem.value, currentFolderId.value)
  }
}

async function handleDropToFolder(event, folder) {
  const files = Array.from(event.dataTransfer.files || [])
  if (files.length) {
    await uploadFiles(files, folder.id)
    return
  }
  if (dragItem.value) {
    await moveItemToFolder(dragItem.value, folder.id)
  }
}

async function moveItemToFolder(item, targetParentId) {
  if (Number(item.id) === Number(targetParentId)) return
  await moveWeatherFile({ id: item.id, targetParentId })
  ElMessage.success(`已移动到「${targetParentId ? itemMap.value.get(Number(targetParentId))?.name : '气象数据'}」`)
  dragItem.value = null
  await loadData()
}

function copySelected(item = selectedItem.value) {
  if (!item) return ElMessage.info('请选择要复制的文件或文件夹')
  clipboard.mode = 'copy'
  clipboard.item = item
  ElMessage.success(`已复制「${item.name}」`)
}

async function pasteToFolder(targetParentId = currentFolderId.value) {
  if (!clipboard.item) return ElMessage.info('剪贴板为空')
  await copyWeatherFile({ id: clipboard.item.id, targetParentId })
  ElMessage.success('粘贴成功')
  await loadData()
}

function openItemMenu(event, item) {
  selectItem(item)
  showContextMenu(event, item)
}

function openBlankMenu(event) {
  if (event.target.closest?.('.context-menu')) return
  selectItem(null)
  showContextMenu(event, null)
}

function showContextMenu(event, item) {
  contextMenu.visible = true
  contextMenu.x = event.clientX
  contextMenu.y = event.clientY
  contextMenu.item = item
}

function hideContextMenu() {
  contextMenu.visible = false
  contextMenu.item = null
}

async function handleMenuAction(action) {
  const item = contextMenu.item
  const targetFolderId = item?.isFolder ? item.id : currentFolderId.value
  hideContextMenu()
  if (action === 'open' && item) return handleOpenItem(item)
  if (action === 'preview' && item) return handlePreview(item)
  if (action === 'newFolder') return handleCreateFolder(targetFolderId)
  if (action === 'upload') return openNativeUpload(targetFolderId)
  if (action === 'copy' && item) return copySelected(item)
  if (action === 'paste') return pasteToFolder(targetFolderId)
  if (action === 'process' && item) return handleProcess(item)
  if (action === 'task' && item) return handleCreateTask(item)
  if (action === 'delete' && item) return handleDelete(item)
}

function handleKeydown(event) {
  const target = event.target
  const tagName = String(target?.tagName || '').toLowerCase()
  if (['input', 'textarea'].includes(tagName) || target?.isContentEditable) return
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'c') {
    event.preventDefault()
    copySelected()
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'v') {
    event.preventDefault()
    pasteToFolder()
  }
  if (event.key === 'Delete' && selectedItem.value) {
    event.preventDefault()
    handleDelete(selectedItem.value)
  }
  if (event.key === 'Enter' && selectedItem.value) {
    event.preventDefault()
    handleOpenItem(selectedItem.value)
  }
}

function folderPathText(parentId) {
  const names = ['气象数据']
  let id = Number(parentId || 0)
  const guard = new Set()
  const chain = []
  while (id && !guard.has(id)) {
    guard.add(id)
    const item = itemMap.value.get(id)
    if (!item) break
    chain.unshift(item.name)
    id = Number(item.parentId || 0)
  }
  return [...names, ...chain].join(' / ')
}

function formatSize(size) {
  const value = Number(size || 0)
  if (value >= 1024 * 1024) return `${(value / 1024 / 1024).toFixed(2)}MB`
  if (value >= 1024) return `${(value / 1024).toFixed(1)}KB`
  return `${value}B`
}

function dataTypeText(type) { return { folder: '文件夹', station_observation: '气象站观测', grid_forecast: '网格预报', icing_monitor: '覆冰监测', line_weather: '线路气象', disaster_history: '历史灾情' }[type] || type }
function fileTypeText(type) { return { folder: '文件夹', excel: 'Excel', csv: 'CSV' }[type] || type || '-' }
function statusText(status) { return { pending: '待校验', uploaded: '待校验', processing: '解析中', finished: '已入库', parsed: '已解析', imported: '已入库', failed: '异常' }[status] || status || '-' }
function statusTagType(status) { if (['finished', 'parsed', 'imported'].includes(status)) return 'success'; if (status === 'processing') return 'warning'; if (status === 'failed') return 'danger'; return 'info' }

onMounted(() => {
  loadData()
  window.addEventListener('click', hideContextMenu)
  window.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('click', hideContextMenu)
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.weather-explorer {
  padding: 16px;
  min-height: calc(100vh - 84px);
  outline: none;
}
.native-file-input {
  display: none;
}
.explorer-card {
  min-height: calc(100vh - 116px);
}
.explorer-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}
.page-title {
  font-size: 20px;
  font-weight: 700;
  color: #1f2937;
}
.page-subtitle {
  margin-top: 6px;
  color: #667085;
  font-size: 13px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.metric-row {
  margin-bottom: 14px;
}
.metric-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 14px 16px;
  background: linear-gradient(180deg, #fff, #f8fbff);
}
.metric-value {
  font-size: 24px;
  font-weight: 700;
  color: #1f7ae0;
}
.metric-label {
  margin-top: 4px;
  font-weight: 600;
  color: #303133;
}
.metric-desc {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fbfdff;
}
.breadcrumb-wrap,
.filter-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}
.breadcrumb-link {
  cursor: pointer;
  color: #2f74d0;
}
.breadcrumb-link:hover {
  color: #165dba;
}
.explorer-body {
  display: grid;
  grid-template-columns: 250px minmax(0, 1fr) 300px;
  gap: 12px;
  margin-top: 12px;
  min-height: 590px;
}
.folder-tree,
.file-area,
.detail-pane {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}
.folder-tree,
.detail-pane {
  padding: 12px;
  overflow: auto;
}
.pane-title {
  margin-bottom: 10px;
  color: #344054;
  font-weight: 700;
}
.tree-node {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.file-area {
  position: relative;
  padding: 12px;
  min-height: 590px;
  transition: border-color .15s, background-color .15s;
}
.file-area.is-dragover {
  border-color: #409eff;
  background: #ecf5ff;
}
.area-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 32px;
  margin-bottom: 12px;
  color: #667085;
  font-size: 13px;
}
.area-meta strong {
  margin-right: 8px;
  color: #1f2937;
  font-size: 15px;
}
.clipboard-hint {
  color: #b7791f;
}
.file-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
  gap: 12px;
}
.file-tile {
  position: relative;
  min-height: 148px;
  padding: 16px 10px 12px;
  border: 1px solid transparent;
  border-radius: 8px;
  text-align: center;
  cursor: default;
  background: #fff;
  transition: background-color .15s, border-color .15s, box-shadow .15s;
}
.file-tile:hover {
  border-color: #b8d7ff;
  background: #f4f9ff;
}
.file-tile.active {
  border-color: #409eff;
  background: #ecf5ff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, .12);
}
.file-tile.folder {
  cursor: pointer;
}
.tile-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 58px;
  height: 58px;
  margin-bottom: 10px;
  border-radius: 14px;
  color: #3b82f6;
  background: #edf5ff;
  font-size: 38px;
}
.tile-icon.folder {
  color: #e6a23c;
  background: #fff7e6;
}
.tile-icon.csv {
  color: #17a673;
  background: #eafaf4;
}
.tile-name {
  height: 38px;
  line-height: 19px;
  color: #1f2937;
  font-weight: 600;
  word-break: break-all;
  overflow: hidden;
}
.tile-meta {
  margin: 6px 0;
  color: #909399;
  font-size: 12px;
}
.detail-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 78px;
  height: 78px;
  margin: 8px auto 10px;
  border-radius: 18px;
  color: #3b82f6;
  background: #edf5ff;
  font-size: 48px;
}
.detail-icon.folder {
  color: #e6a23c;
  background: #fff7e6;
}
.detail-name {
  margin-bottom: 14px;
  text-align: center;
  color: #1f2937;
  font-weight: 700;
  word-break: break-all;
}
.context-menu {
  position: fixed;
  z-index: 4000;
  min-width: 168px;
  padding: 6px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 12px 32px rgba(15, 23, 42, .16);
}
.context-menu button {
  display: block;
  width: 100%;
  padding: 8px 10px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #303133;
  text-align: left;
  cursor: pointer;
}
.context-menu button:hover:not(:disabled) {
  background: #ecf5ff;
  color: #1677ff;
}
.context-menu button:disabled {
  color: #c0c4cc;
  cursor: not-allowed;
}
.context-menu button.danger {
  color: #f56c6c;
}

@media (max-width: 1400px) {
  .explorer-body {
    grid-template-columns: 220px minmax(0, 1fr);
  }
  .detail-pane {
    display: none;
  }
}

@media (max-width: 980px) {
  .explorer-header,
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .filter-wrap {
    flex-wrap: wrap;
  }
  .explorer-body {
    grid-template-columns: 1fr;
  }
  .folder-tree {
    max-height: 260px;
  }
}
</style>
