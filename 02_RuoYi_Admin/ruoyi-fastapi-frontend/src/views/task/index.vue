<template>
  <div class="app-container task-page">
    <el-alert v-if="pageError" class="mb16" type="error" show-icon :closable="false" :title="pageError" />

    <div class="page-heading">
      <div>
        <h2>算法任务管理</h2>
        <p>统一管理算力连接、算法选择、任务运行与结果文件。</p>
      </div>
      <el-button type="primary" @click="handleAdd">新增任务</el-button>
    </div>

    <div class="overview-grid">
      <div v-for="(item, index) in taskMetrics" :key="item.label" class="metric-card" :class="`metric-${index}`">
        <div class="metric-accent" />
        <div class="metric-content">
          <div class="metric-title">{{ item.label }}</div>
          <div class="metric-main">
            <strong>{{ item.value }}</strong>
            <span>{{ item.desc }}</span>
          </div>
        </div>
      </div>
    </div>

    <el-card shadow="never" class="workspace-card">
      <template #header>
        <div class="card-header">
          <div>
            <span class="card-title">算法任务管理</span>
            <span class="card-subtitle">共 {{ filteredTaskList.length }} 条任务记录</span>
          </div>
          <div class="header-actions">
            <el-button v-hasPermi="['ai:model:edit']" @click="reportSettingsVisible = true">AI 报告设置</el-button>
            <el-button :disabled="loading || !filteredTaskList.length" @click="exportTaskRecords">导出筛选记录</el-button>
            <el-button @click="batchRefreshStatus">批量刷新状态</el-button>
            <el-button @click="loadTasks">刷新列表</el-button>
          </div>
        </div>
      </template>

      <section class="service-section">
        <div class="section-label">
          <span class="status-dot" :class="{ online: serverOnline }" />
          <div>
            <strong>算法服务</strong>
            <span>{{ serverOnline ? '连接正常' : '请选择平台并测试连接' }}</span>
          </div>
        </div>
        <div class="service-controls">
          <el-select v-model="currentPlatformId" clearable placeholder="选择算力平台" class="platform-select" @change="handlePlatformChange">
            <el-option v-for="item in platforms" :key="item.id" :label="item.name || item.url" :value="String(item.id)" />
          </el-select>
          <el-input v-model="serverUrl" placeholder="algorithm-server 地址" class="server-url-input" />
          <el-tag :type="serverOnline ? 'success' : 'info'" effect="light">{{ serverOnline ? '在线' : '未检测' }}</el-tag>
        </div>
        <div class="service-actions">
          <el-button type="success" plain :disabled="!serverUrl" @click="handleCheckServer()">测试连接</el-button>
          <el-button type="primary" plain :disabled="!serverUrl" @click="handleSyncAlgorithms">同步算法</el-button>
          <el-button @click="openAlgorithmDrawer">算法列表</el-button>
          <el-button :disabled="!serverUrl" @click="openApiDocs">接口文档</el-button>
        </div>
      </section>
      <el-alert v-if="serverStatus" :title="serverStatus" :type="serverOnline ? 'success' : 'error'" show-icon :closable="false" class="server-alert" />

      <div class="filter-section">
        <el-form :model="queryParams" :inline="true" class="filter-form">
          <el-form-item>
            <el-input v-model="queryParams.keyword" clearable placeholder="搜索任务号、名称或线路" class="keyword-input" @keyup.enter="handleQuery" />
          </el-form-item>
          <el-form-item>
            <el-select v-model="queryParams.status" clearable placeholder="任务状态" class="filter-select">
              <el-option label="已创建" value="created" />
              <el-option label="运行中" value="running" />
              <el-option label="已完成" value="success" />
              <el-option label="失败" value="failed" />
              <el-option label="已停止" value="stopped" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-select v-model="queryParams.algorithmId" clearable placeholder="算法模型" class="algorithm-select">
              <el-option v-for="item in algorithmOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-input v-model="queryParams.region" clearable placeholder="区域" class="region-input" />
          </el-form-item>
          <el-form-item>
            <el-date-picker v-model="queryParams.createDateRange" type="daterange" value-format="YYYY-MM-DD"
              start-placeholder="创建开始日期" end-placeholder="创建结束日期" range-separator="至" />
          </el-form-item>
          <el-form-item class="filter-actions">
            <el-button type="primary" @click="handleQuery">查询</el-button>
            <el-button @click="resetQuery">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="pagedTaskList" class="task-table" v-loading="loading" border stripe empty-text="暂无真实算法任务">
        <el-table-column prop="taskCode" label="任务号" align="center" min-width="170" show-overflow-tooltip />
        <el-table-column prop="taskName" label="任务名称" min-width="190" show-overflow-tooltip />
        <el-table-column prop="algorithmName" label="算法模型" align="center" min-width="190" show-overflow-tooltip />
        <el-table-column prop="region" label="区域" align="center" width="90" />
        <el-table-column prop="lineCode" label="线路" align="center" width="110" />
        <el-table-column prop="forecastHours" label="时长/h" align="center" width="88" />
        <el-table-column prop="priority" label="优先级" align="center" width="90">
          <template #default="scope">
            <el-tag :type="scope.row.priority === 'high' ? 'danger' : scope.row.priority === 'low' ? 'info' : 'warning'">
              {{ priorityText(scope.row.priority) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" align="center" width="110">
          <template #default="scope">
            <el-tag :type="statusTagType(scope.row.status)">{{ statusText(scope.row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" align="center" width="160">
          <template #default="scope">
            <el-progress :percentage="Number(scope.row.progress || 0)" :stroke-width="12" />
          </template>
        </el-table-column>
        <el-table-column prop="message" label="运行信息" min-width="180" show-overflow-tooltip />
        <el-table-column prop="createTime" label="创建时间" align="center" width="170" />
        <el-table-column label="操作" align="center" width="450" fixed="right">
          <template #default="scope">
            <el-button link type="primary" :disabled="isTaskActive(scope.row) || submittingTaskCodes.has(scope.row.taskCode)" @click="handleRun(scope.row)">运行</el-button>
            <el-button link type="primary" @click="handleHistory(scope.row)">运行记录</el-button>
            <el-button link type="primary" @click="openTaskReport(scope.row)">AI 报告</el-button>
            <el-button link type="warning" @click="handleStatus(scope.row)">状态</el-button>
            <el-button link type="success" @click="handleResult(scope.row)">结果</el-button>
            <el-button v-if="scope.row.status === 'success' && isFileTaskRow(scope.row)" link type="success" @click="handleDownload(scope.row)">下载</el-button>
            <el-button link type="info" @click="handleDetail(scope.row)">详情</el-button>
            <el-button link type="danger" @click="handleDelete(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pageNum"
          v-model:page-size="pageSize"
          :page-sizes="[5, 10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="filteredTaskList.length"
        />
      </div>
    </el-card>

    <ReportSettingsDialog v-model="reportSettingsVisible" />
    <TaskReportDialog v-model="reportVisible" :task="reportTask" />

    <el-dialog v-model="historyVisible" title="任务运行记录" width="960px" append-to-body>
      <template v-if="historyTask">
        <p>{{ historyTask.taskName }} · {{ historyTask.taskCode }}</p>
        <el-alert type="info" :closable="false" show-icon class="mb16"
          title="按最新时间排序，记录状态、进度、运行信息和错误的变化。历史任务从本功能启用后的首次变化开始记录。" />
        <div class="header-actions mb16">
          <el-button :loading="historyLoading" @click="loadHistory">刷新记录</el-button>
          <el-button :disabled="historyLoading || !historyRows.length" @click="exportHistoryRecords">导出当前页记录</el-button>
        </div>
        <el-alert v-if="historyError" type="error" :closable="false" :title="historyError" class="mb16" />
        <el-table v-loading="historyLoading" :data="historyRows" border stripe empty-text="暂无运行记录" max-height="460">
          <el-table-column prop="eventTime" label="记录时间" width="180" />
          <el-table-column label="状态" width="110">
            <template #default="scope"><el-tag :type="statusTagType(scope.row.status)">{{ statusText(scope.row.status) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="进度" width="90">
            <template #default="scope">{{ scope.row.progress }}%</template>
          </el-table-column>
          <el-table-column prop="message" label="运行信息" min-width="220" />
          <el-table-column prop="error" label="错误详情" min-width="260" />
        </el-table>
        <div class="pagination-wrapper">
          <el-pagination v-model:current-page="historyPageNum" v-model:page-size="historyPageSize"
            :page-sizes="[10, 20, 50, 100]" :total="historyTotal" layout="total, sizes, prev, pager, next"
            @current-change="loadHistory" @size-change="handleHistorySizeChange" />
        </div>
      </template>
    </el-dialog>

    <el-dialog title="新增算法任务" v-model="dialogVisible" width="900px" append-to-body>
      <el-form :model="taskForm" label-width="130px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="任务名称" required>
              <el-input v-model="taskForm.taskName" placeholder="请输入任务名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="任务类型" required>
              <el-select v-model="taskForm.taskType" style="width: 100%">
                <el-option label="覆冰预测" value="icing" />
                <el-option label="文件型算法任务" value="file_algorithm" />
                <el-option label="杆塔故障概率预测" value="tabular_forecast" />
                <el-option label="大风风险" value="wind" />
                <el-option label="综合风险评估" value="composite" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="算力平台">
              <el-select v-model="taskForm.serverId" clearable placeholder="选择算力平台" style="width: 100%" @change="handleTaskServerChange">
                <el-option v-for="item in platforms" :key="item.id" :label="item.name || item.url" :value="String(item.id)" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="算法服务地址" required>
              <el-input v-model="taskForm.serverUrl" placeholder="http://127.0.0.1:8000" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="算法模型" required>
              <el-select v-model="taskForm.algorithmId" placeholder="请选择算法/模型" style="width: 100%" @change="handleAlgorithmChange">
                <el-option
                  v-for="item in enabledAlgorithms"
                  :key="item.algorithm_id"
                  :label="item.algorithm_name"
                  :value="item.algorithm_id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级" required>
              <el-select v-model="taskForm.priority" style="width: 100%">
                <el-option label="高" value="high" />
                <el-option label="普通" value="normal" />
                <el-option label="低" value="low" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="isTabPfnForecastAlgorithm" :span="24">
            <el-form-item label="历史训练文件" required>
              <el-select v-model="taskForm.trainingFileId" clearable filterable placeholder="请选择包含“是否为故障杆塔”标签的历史 Excel" style="width: 100%">
                <el-option
                  v-for="item in weatherFiles"
                  :key="item.id"
                  :label="`${item.name}（${item.recordCount || 0}条 / ${item.fieldCount || 0}字段）`"
                  :value="String(item.id)"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item :label="isTabPfnForecastAlgorithm ? '待预测数据文件' : '气象数据文件'" :required="isFileAlgorithm">
              <el-select
                v-model="taskForm.fileId"
                clearable
                filterable
                :placeholder="isTabPfnForecastAlgorithm ? '请选择特征列与训练文件一致的新气象 Excel' : (isFileAlgorithm ? '请选择算法需要的输入文件' : '选择已上传的 Excel/CSV；不选择则使用下方手动参数')"
                style="width: 100%"
                @change="handleWeatherFileChange"
              >
                <el-option
                  v-for="item in weatherFiles"
                  :key="item.id"
                  :label="`${item.name}（${item.recordCount || 0}条 / ${item.fieldCount || 0}字段）`"
                  :value="String(item.id)"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="selectedWeatherFile" :span="24">
            <el-alert
              type="success"
              show-icon
              :closable="false"
              :title="isTabPfnForecastAlgorithm
                ? `模型将使用 ${selectedTrainingFile?.name || '所选历史文件'} 训练，并预测 ${selectedWeatherFile.name}`
                : isFileAlgorithm
                ? `algorithm-server 将把原始文件 ${selectedWeatherFile.name} 交给当前算法自己的入口函数处理`
                : `运行时将解析真实文件：${selectedWeatherFile.name}，共 ${selectedWeatherFile.recordCount || 0} 条记录`"
            />
          </el-col>
          <template v-if="isTabPfnAlgorithm">
            <el-col :span="24">
              <el-alert
                type="info"
                show-icon
                :closable="false"
                :title="isTabPfnForecastAlgorithm
                  ? '训练文件须包含“是否为故障杆塔”，待预测文件须包含一致的数值特征列；新算法会自动识别前 5 行中的表头。'
                  : '文件格式与原脚本一致：读取第一个工作表，第 2 行作为表头，目标列为“是否为故障杆塔”。'"
              />
            </el-col>
            <el-col :span="8">
              <el-form-item label="重复次数" required>
                <el-input-number v-model="taskForm.nRepeats" :min="1" :max="100" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="交叉验证折数" required>
                <el-input-number v-model="taskForm.nSplits" :min="2" :max="10" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="随机种子" required>
                <el-input-number v-model="taskForm.randomSeed" :min="0" :max="999999" style="width: 100%" />
              </el-form-item>
            </el-col>
            <template v-if="isTabPfnForecastAlgorithm">
              <el-col :span="12">
                <el-form-item label="预测时长" required>
                  <el-input-number v-model="taskForm.forecastHours" :min="1" :max="168" style="width: 100%" />
                  <span class="unit">小时</span>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="故障判定阈值" required>
                  <el-input-number v-model="taskForm.faultThreshold" :min="0.01" :max="0.99" :step="0.05" :precision="2" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-alert type="warning" show-icon :closable="false" title="概率等级固定为：低＜25%，一般25%-50%，较高50%-75%，高≥75%；结果 Excel 内同时提供预测表、评估表和可视化图表。" />
              </el-col>
            </template>
          </template>
          <template v-else-if="isFileAlgorithm">
            <el-col :span="24">
              <el-alert
                type="info"
                show-icon
                :closable="false"
                :title="`当前算法按 ${selectedAlgorithm?.run_api || '/api/tasks/run-file'} 执行，参数将原样传给算法入口 run(input_data)。`"
              />
            </el-col>
            <el-col :span="24">
              <el-form-item label="算法参数 JSON">
                <el-input v-model="taskForm.algorithmParamsText" type="textarea" :rows="5" placeholder='例如：{"threshold": 0.5}' />
              </el-form-item>
            </el-col>
          </template>
          <template v-if="!taskForm.fileId && !isFileAlgorithm">
          <el-col :span="8">
            <el-form-item label="区域">
              <el-input v-model="taskForm.region" placeholder="例如：辽宁" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="线路编号">
              <el-input v-model="taskForm.lineCode" placeholder="例如：LN-500-001" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="预测时长">
              <el-input-number v-model="taskForm.forecastHours" :min="1" :max="168" style="width: 140px" />
              <span class="unit">小时</span>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="开始时间">
              <el-date-picker v-model="taskForm.startTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" placeholder="选择开始时间" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束时间">
              <el-date-picker v-model="taskForm.endTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" placeholder="选择结束时间" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="温度">
              <el-input-number v-model="taskForm.temperature" :step="0.1" />
              <span class="unit">℃</span>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="湿度">
              <el-input-number v-model="taskForm.humidity" :min="0" :max="100" />
              <span class="unit">%</span>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="风速">
              <el-input-number v-model="taskForm.windSpeed" :min="0" :step="0.1" />
              <span class="unit">m/s</span>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="风向">
              <el-input-number v-model="taskForm.windDirection" :min="0" :max="360" :step="1" />
              <span class="unit">°</span>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="降水">
              <el-input-number v-model="taskForm.precipitation" :min="0" :step="0.1" />
              <span class="unit">mm</span>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="历史覆冰厚度">
              <el-input-number v-model="taskForm.historyIcingThickness" :min="0" :step="0.1" />
              <span class="unit">mm</span>
            </el-form-item>
          </el-col>
          </template>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="taskForm.remark" type="textarea" :rows="3" placeholder="任务说明、数据来源或运行备注" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTask">保存任务</el-button>
        <el-button type="success" @click="submitAndRunTask">保存并运行</el-button>
      </template>
    </el-dialog>

    <el-drawer title="算法列表" v-model="algorithmDrawerVisible" size="50%">
      <div class="drawer-toolbar">
        <el-button type="primary" :disabled="!serverUrl" @click="handleSyncAlgorithms">重新同步</el-button>
      </div>
      <el-table :data="algorithmList" border stripe empty-text="暂无算法/模型，请先在算力平台管理页登记或上传">
        <el-table-column prop="algorithm_id" label="算法编号" align="center" min-width="160" />
        <el-table-column prop="algorithm_name" label="算法名称" align="center" min-width="190" />
        <el-table-column prop="algorithm_type" label="类型" align="center" width="120" />
        <el-table-column prop="status" label="状态" align="center" width="100" />
        <el-table-column prop="version" label="版本" align="center" width="100" />
        <el-table-column prop="description" label="说明" show-overflow-tooltip />
      </el-table>
    </el-drawer>

    <el-dialog title="任务详情" v-model="detailVisible" width="760px" append-to-body>
      <el-descriptions v-if="currentTask" :column="2" border>
        <el-descriptions-item label="任务号" :span="2">{{ currentTask.taskCode }}</el-descriptions-item>
        <el-descriptions-item label="任务名称" :span="2">{{ currentTask.taskName }}</el-descriptions-item>
        <el-descriptions-item label="算法模型">{{ currentTask.algorithmName }}</el-descriptions-item>
        <el-descriptions-item label="任务状态">{{ statusText(currentTask.status) }}</el-descriptions-item>
        <el-descriptions-item label="区域">{{ currentTask.region }}</el-descriptions-item>
        <el-descriptions-item label="线路">{{ currentTask.lineCode }}</el-descriptions-item>
        <el-descriptions-item :label="currentTask.algorithmId === 'tabpfn_fault_forecast' ? '待预测文件' : '气象文件'">{{ weatherFileName(currentTask.fileId) }}</el-descriptions-item>
        <el-descriptions-item v-if="currentTask.algorithmId === 'tabpfn_fault_forecast'" label="历史训练文件">
          {{ weatherFileName(currentTask.params?.training_file_id) }}
        </el-descriptions-item>
        <el-descriptions-item label="任务类型">{{ currentTask.taskType || '-' }}</el-descriptions-item>
        <el-descriptions-item label="进度">{{ currentTask.progress || 0 }}%</el-descriptions-item>
        <el-descriptions-item label="运行信息" :span="2">{{ currentTask.message || '暂无' }}</el-descriptions-item>
        <el-descriptions-item label="错误信息" :span="2">{{ currentTask.error || '无' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <el-dialog title="任务结果" v-model="resultVisible" width="1180px" top="5vh" append-to-body class="task-result-dialog" @closed="disposeResultCharts">
      <template v-if="isFileResult">
        <el-alert :title="`${resultPayload.algorithm_name || '算法'} 已运行完成，结果文件由算法自身生成。`" type="success" show-icon :closable="false" class="result-summary" />
        <el-tabs v-model="resultActiveTab" class="result-tabs" @tab-change="handleResultTabChange">
          <el-tab-pane label="结果概览" name="overview">
            <el-descriptions :column="3" border class="result-descriptions">
              <el-descriptions-item label="结果文件" :span="3">{{ resultPayload.output_filename || '-' }}</el-descriptions-item>
              <el-descriptions-item label="样本数">{{ resultStats.sample_count ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="特征数">{{ resultStats.feature_count ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="总折数">{{ resultStats.total_folds ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="重复次数">{{ resultStats.n_repeats ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="每次折数">{{ resultStats.n_splits ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="运行耗时">{{ formatDuration(resultStats.duration_seconds) }}</el-descriptions-item>
              <el-descriptions-item v-if="isForecastResult" label="待预测记录">{{ resultStats.prediction_count ?? '-' }}</el-descriptions-item>
              <el-descriptions-item v-if="isForecastResult" label="预测故障数">{{ resultStats.predicted_fault_count ?? '-' }}</el-descriptions-item>
              <el-descriptions-item v-if="isForecastResult" label="预测时长">{{ resultStats.forecast_hours ?? '-' }} 小时</el-descriptions-item>
              <el-descriptions-item v-if="isForecastResult" label="平均故障概率">{{ formatProbability(resultStats.average_fault_probability) }}</el-descriptions-item>
              <el-descriptions-item v-if="isForecastResult" label="最大故障概率">{{ formatProbability(resultStats.max_fault_probability) }}</el-descriptions-item>
              <el-descriptions-item v-if="isForecastResult" label="高概率记录">{{ resultStats.risk_distribution?.高 ?? 0 }}</el-descriptions-item>
              <el-descriptions-item label="工作表" :span="3">{{ (resultPayload.sheets || []).join('、') || '-' }}</el-descriptions-item>
            </el-descriptions>
            <el-table v-if="resultMetrics.length" :data="resultMetrics" border stripe class="metric-result-table" empty-text="暂无指标数据">
              <el-table-column prop="Metric" label="指标" min-width="120" />
              <el-table-column label="平均值" min-width="110"><template #default="scope">{{ formatMetric(scope.row.Mean) }}</template></el-table-column>
              <el-table-column label="标准差" min-width="110"><template #default="scope">{{ formatMetric(scope.row.Std) }}</template></el-table-column>
              <el-table-column label="最小值" min-width="110"><template #default="scope">{{ formatMetric(scope.row.Min) }}</template></el-table-column>
              <el-table-column label="最大值" min-width="110"><template #default="scope">{{ formatMetric(scope.row.Max) }}</template></el-table-column>
              <el-table-column label="95%置信区间" min-width="190">
                <template #default="scope">{{ formatMetric(scope.row.CI95_Lower) }} - {{ formatMetric(scope.row.CI95_Upper) }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane v-if="isForecastResult" label="未来故障预测" name="predictions">
            <el-alert v-if="!resultPreviewAvailable" :title="resultPreviewMessage" type="warning" show-icon :closable="false" />
            <template v-else>
              <div class="result-section-toolbar">
                <span>共 {{ resultPreview.prediction_total || resultPredictionRows.length }} 条逐小时预测记录</span>
                <span v-if="resultPreview.prediction_truncated">页面仅展示前 {{ resultPredictionRows.length }} 条，完整结果请下载 Excel</span>
              </div>
              <el-table :data="pagedPredictionRows" border stripe height="430" empty-text="暂无未来故障预测数据">
                <el-table-column prop="city" label="城市" width="80" fixed="left" />
                <el-table-column prop="line_name" label="线路" min-width="150" show-overflow-tooltip />
                <el-table-column prop="tower_code" label="杆塔点位" min-width="160" show-overflow-tooltip />
                <el-table-column prop="forecast_hour" label="时效/h" width="82" align="center" />
                <el-table-column prop="forecast_time" label="预测时间" width="165" />
                <el-table-column label="温度/℃" width="90" align="right"><template #default="scope">{{ formatResultNumber(scope.row.temperature) }}</template></el-table-column>
                <el-table-column label="湿度/%" width="88" align="right"><template #default="scope">{{ formatResultNumber(scope.row.humidity) }}</template></el-table-column>
                <el-table-column label="风速/(m/s)" width="105" align="right"><template #default="scope">{{ formatResultNumber(scope.row.wind_speed) }}</template></el-table-column>
                <el-table-column label="降水/mm" width="92" align="right"><template #default="scope">{{ formatResultNumber(scope.row.precipitation) }}</template></el-table-column>
                <el-table-column label="故障概率" width="100" align="right"><template #default="scope"><strong class="probability-value">{{ formatProbabilityPercent(scope.row.probability_percent) }}</strong></template></el-table-column>
                <el-table-column label="概率等级" width="92" align="center"><template #default="scope"><el-tag :type="riskTagType(scope.row.risk_level)" size="small">{{ scope.row.risk_level || '-' }}</el-tag></template></el-table-column>
                <el-table-column prop="predicted_fault" label="故障判定" width="88" align="center" />
              </el-table>
              <div class="result-pagination">
                <el-pagination v-model:current-page="resultPageNum" v-model:page-size="resultPageSize" :page-sizes="[10, 20, 50, 100]" layout="total, sizes, prev, pager, next" :total="resultPredictionRows.length" />
              </div>
            </template>
          </el-tab-pane>

          <el-tab-pane v-if="isForecastResult" label="概率等级统计" name="risks">
            <el-alert v-if="!resultPreviewAvailable" :title="resultPreviewMessage" type="warning" show-icon :closable="false" />
            <template v-else>
              <div class="risk-summary-grid">
                <div v-for="item in resultRiskRows" :key="item.risk_level" class="risk-summary-item" :class="`risk-${item.risk_level}`">
                  <span>{{ item.risk_level }}</span>
                  <strong>{{ item.count }}</strong>
                  <small>{{ formatRatio(item.ratio) }}</small>
                </div>
              </div>
              <el-table :data="resultRiskRows" border stripe class="risk-result-table" empty-text="暂无概率等级统计数据">
                <el-table-column prop="risk_level" label="概率等级" min-width="160" align="center">
                  <template #default="scope"><el-tag :type="riskTagType(scope.row.risk_level)">{{ scope.row.risk_level }}</el-tag></template>
                </el-table-column>
                <el-table-column prop="count" label="记录数" min-width="160" align="center" />
                <el-table-column label="占比" min-width="180" align="center"><template #default="scope">{{ formatRatio(scope.row.ratio) }}</template></el-table-column>
              </el-table>
            </template>
          </el-tab-pane>

          <el-tab-pane v-if="isForecastResult" label="可视化图表" name="charts">
            <el-alert v-if="!resultPreviewAvailable" :title="resultPreviewMessage" type="warning" show-icon :closable="false" />
            <div v-else class="result-chart-grid">
              <section class="result-chart-panel"><h4>逐小时故障概率趋势</h4><div ref="hourlyChartRef" class="result-chart" /></section>
              <section class="result-chart-panel"><h4>概率等级分布</h4><div ref="riskChartRef" class="result-chart" /></section>
              <section class="result-chart-panel"><h4>交叉验证指标</h4><div ref="metricChartRef" class="result-chart" /></section>
              <section class="result-chart-panel"><h4>交叉验证混淆矩阵</h4><div ref="confusionChartRef" class="result-chart" /></section>
            </div>
          </el-tab-pane>
        </el-tabs>
      </template>
      <template v-else-if="resultSummary">
        <el-alert :title="resultSummary" :type="resultUsedRealModel ? 'success' : 'warning'" show-icon :closable="false" class="result-summary" />
        <el-descriptions :column="2" border>
          <el-descriptions-item label="未来覆冰厚度">{{ resultPayload.summary?.future_icing_thickness ?? '-' }} mm</el-descriptions-item>
          <el-descriptions-item label="风险等级">{{ resultPayload.summary?.risk_level || '-' }}</el-descriptions-item>
          <el-descriptions-item label="真实模型执行">{{ resultUsedRealModel ? '是' : '否' }}</el-descriptions-item>
          <el-descriptions-item label="结果条数">{{ resultSeries.length }}</el-descriptions-item>
        </el-descriptions>
      </template>
      <el-empty v-else description="任务尚未生成结果" />
      <template #footer>
        <el-button @click="resultVisible = false">关闭</el-button>
        <el-button v-if="isFileResult" type="primary" @click="handleDownload(resultData)">下载算法结果文件</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="Task">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import { saveAs } from 'file-saver'
import { filterTaskRecords, recordsToCsv } from '@/utils/taskRecords'
import ReportSettingsDialog from '@/components/AlgorithmReport/ReportSettingsDialog.vue'
import TaskReportDialog from '@/components/AlgorithmReport/TaskReportDialog.vue'
import {
  checkAlgorithmServer,
  createAlgorithmTask,
  deleteAlgorithmTask,
  downloadAlgorithmTaskResult,
  getAlgorithmTaskResult,
  getAlgorithmTaskStatus,
  getAlgorithmTaskHistory,
  listAlgorithmModels,
  listAlgorithmServers,
  listAlgorithmTasks,
  runAlgorithmTask,
  syncAlgorithmModels
} from '@/api/algorithm'
import { listWeatherFiles } from '@/api/weatherFile'

const loading = ref(false)
const pageError = ref('')
const dialogVisible = ref(false)
const detailVisible = ref(false)
const resultVisible = ref(false)
const resultActiveTab = ref('overview')
const resultPageNum = ref(1)
const resultPageSize = ref(10)
const hourlyChartRef = ref(null)
const riskChartRef = ref(null)
const metricChartRef = ref(null)
const confusionChartRef = ref(null)
const algorithmDrawerVisible = ref(false)
const resultData = ref(null)
const currentTask = ref(null)
const platforms = ref([])
const currentPlatformId = ref('')
const serverUrl = ref('')
const serverStatus = ref('')
const serverOnline = ref(false)
const algorithmList = ref([])
const weatherFiles = ref([])
const taskList = ref([])
const reportSettingsVisible = ref(false)
const reportVisible = ref(false)
const reportTask = ref(null)
function openTaskReport(row) { reportTask.value = row; reportVisible.value = true }
const submittingTaskCodes = ref(new Set())
const historyVisible = ref(false)
const historyTask = ref(null)
const historyLoading = ref(false)
const historyError = ref('')
const historyRows = ref([])
const historyTotal = ref(0)
const historyPageNum = ref(1)
const historyPageSize = ref(20)
let historyRequestId = 0
let taskStatusTimer = null
let taskStatusPolling = false
let hourlyChartInstance = null
let riskChartInstance = null
let metricChartInstance = null
let confusionChartInstance = null
const pageNum = ref(1)
const pageSize = ref(10)

const queryParams = ref({
  keyword: '',
  status: '',
  algorithmId: '',
  region: '',
  createDateRange: []
})

const taskForm = ref(createDefaultForm())
const selectedWeatherFile = computed(() => weatherFiles.value.find(item => String(item.id) === String(taskForm.value.fileId)) || null)
const selectedTrainingFile = computed(() => weatherFiles.value.find(item => String(item.id) === String(taskForm.value.trainingFileId)) || null)
const selectedAlgorithm = computed(() => algorithmList.value.find(item => item.algorithm_id === taskForm.value.algorithmId) || null)
const isTabPfnCvAlgorithm = computed(() => taskForm.value.algorithmId === 'tabpfn_fault_cv')
const isTabPfnForecastAlgorithm = computed(() => taskForm.value.algorithmId === 'tabpfn_fault_forecast')
const isTabPfnAlgorithm = computed(() => isTabPfnCvAlgorithm.value || isTabPfnForecastAlgorithm.value)
const isFileAlgorithm = computed(() => {
  const item = selectedAlgorithm.value
  return isTabPfnAlgorithm.value
    || ['tabular_cv', 'tabular_forecast'].includes(item?.algorithm_type)
    || String(item?.run_api || '').endsWith('/api/tasks/run-file')
})

const taskMetrics = computed(() => {
  const total = taskList.value.length
  const running = taskList.value.filter(item => ['running', 'queued', 'submitted'].includes(item.status)).length
  const success = taskList.value.filter(item => item.status === 'success').length
  const failed = taskList.value.filter(item => item.status === 'failed').length
  return [
    { label: '任务总数', value: total, desc: 'MySQL 任务记录' },
    { label: '运行中', value: running, desc: '正在执行或排队任务' },
    { label: '已完成', value: success, desc: '已返回预测结果' },
    { label: '异常任务', value: failed, desc: '提交或运行失败任务' }
  ]
})

const enabledAlgorithms = computed(() => algorithmList.value.filter(item => item.status !== 'disabled'))
const algorithmOptions = computed(() => {
  const options = new Map(algorithmList.value.map(item => [item.algorithm_id, { label: item.algorithm_name, value: item.algorithm_id }]))
  taskList.value.forEach(item => {
    if (item.algorithmId && !options.has(item.algorithmId)) options.set(item.algorithmId, { label: item.algorithmName || item.algorithmId, value: item.algorithmId })
  })
  return [...options.values()]
})

const filteredTaskList = computed(() => filterTaskRecords(taskList.value, queryParams.value))

watch(queryParams, () => { pageNum.value = 1 }, { deep: true })
watch([() => filteredTaskList.value.length, pageSize], () => {
  pageNum.value = Math.min(pageNum.value, Math.max(1, Math.ceil(filteredTaskList.value.length / pageSize.value)))
})

const pagedTaskList = computed(() => {
  const start = (pageNum.value - 1) * pageSize.value
  return filteredTaskList.value.slice(start, start + pageSize.value)
})

const resultPayload = computed(() => resultData.value?.result || resultData.value || {})
const resultSeries = computed(() => Array.isArray(resultPayload.value?.result) ? resultPayload.value.result : [])
const resultUsedRealModel = computed(() => Boolean(resultPayload.value?.used_real_model || resultPayload.value?.summary?.used_real_model))
const isFileResult = computed(() => resultPayload.value?.result_type === 'file')
const resultStats = computed(() => resultPayload.value?.summary || {})
const resultMetrics = computed(() => Array.isArray(resultStats.value?.metrics) ? resultStats.value.metrics : [])
const isForecastResult = computed(() => resultPayload.value?.algorithm_id === 'tabpfn_fault_forecast' || resultStats.value?.mode === 'train_and_forecast')
const resultPreview = computed(() => resultPayload.value?.preview || {})
const resultPreviewAvailable = computed(() => resultPreview.value?.available === true)
const resultPreviewMessage = computed(() => resultPreview.value?.message || '暂时无法读取结果文件预览，请确认 RuoYi 后端保存的结果文件仍然存在。')
const resultPredictionRows = computed(() => Array.isArray(resultPreview.value?.predictions) ? resultPreview.value.predictions : [])
const resultRiskRows = computed(() => Array.isArray(resultPreview.value?.risk_statistics) ? resultPreview.value.risk_statistics : [])
const resultChartData = computed(() => resultPreview.value?.charts || {})
const pagedPredictionRows = computed(() => {
  const start = (resultPageNum.value - 1) * resultPageSize.value
  return resultPredictionRows.value.slice(start, start + resultPageSize.value)
})
const resultSummary = computed(() => {
  const summary = resultPayload.value?.summary
  if (summary) {
    if (summary.data_mode === 'weather_file_batch') {
      const real = summary.used_real_model ? '已执行上传模型' : '模型未执行'
      const accuracy = summary.accuracy == null ? '' : `，有标签样本准确率 ${(Number(summary.accuracy) * 100).toFixed(2)}%`
      return `文件 ${summary.source_file_name || '-'} 共执行 ${summary.sample_count || 0} 条样本、${summary.feature_count || 0} 个特征，${real}${accuracy}`
    }
    const real = summary.used_real_model ? '真实上传模型' : '规则兜底'
    return `未来覆冰厚度 ${Number(summary.future_icing_thickness || summary.max_icing_thickness || 0).toFixed(3)} mm，风险等级 ${summary.risk_level || summary.max_risk_level || '-'}，执行方式：${real}`
  }
  if (!resultSeries.value.length) return ''
  const maxIce = Math.max(...resultSeries.value.map(item => Number(item.future_icing_thickness ?? item.icing_thickness ?? 0)))
  const maxLevel = resultSeries.value.find(item => Number(item.future_icing_thickness ?? item.icing_thickness ?? 0) === maxIce)?.risk_level || '未知'
  return `预测结果共 ${resultSeries.value.length} 条，最大覆冰厚度 ${maxIce.toFixed(3)} mm，最高风险等级 ${maxLevel}`
})

function createDefaultForm() {
  return {
    taskName: '',
    taskType: '',
    serverId: '',
    serverUrl: '',
    algorithmId: '',
    algorithmName: '',
    priority: '',
    region: '',
    lineCode: '',
    forecastHours: undefined,
    startTime: '',
    endTime: '',
    temperature: undefined,
    humidity: undefined,
    windSpeed: undefined,
    windDirection: undefined,
    precipitation: undefined,
    historyIcingThickness: undefined,
    nRepeats: undefined,
    nSplits: undefined,
    randomSeed: undefined,
    algorithmParamsText: '',
    dataSource: '',
    fileId: undefined,
    trainingFileId: undefined,
    faultThreshold: undefined,
    remark: ''
  }
}

function normalizeUrl(url) {
  return String(url || '').trim().replace(/\/+$/, '')
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

function normalizeServer(item) {
  return {
    ...item,
    id: String(item.id ?? item.serverId ?? item.server_id ?? ''),
    name: item.name || item.serverName || item.server_name || '',
    url: normalizeUrl(item.url || item.serverUrl || item.server_url || ''),
    status: item.status || 'unknown'
  }
}

function normalizeAlgorithm(item) {
  return {
    ...item,
    algorithm_id: item.algorithm_id || item.algorithmId || item.model_id || item.modelId || '',
    algorithm_name: item.algorithm_name || item.algorithmName || item.name || item.algorithm_id || item.algorithmId || '',
    algorithm_type: item.algorithm_type || item.algorithmType || item.type || '',
    run_api: item.run_api || item.runApi || '',
    version: item.version || item.algorithm_version || '',
    status: item.status || 'enabled',
    description: item.description || item.remark || ''
  }
}

function normalizeTask(item) {
  return {
    ...item,
    taskCode: item.taskCode || item.task_code || '',
    taskName: item.taskName || item.task_name || '',
    algorithmId: item.algorithmId || item.algorithm_id || '',
    algorithmName: item.algorithmName || item.algorithm_name || '',
    taskType: item.taskType || item.task_type || '',
    region: item.region || item.regionName || item.region_name || '',
    lineCode: item.lineCode || item.line_code || '',
    fileId: item.fileId || item.file_id || undefined,
    forecastHours: item.forecastHours || item.forecast_hours || 24,
    priority: item.priority || 'normal',
    status: item.status || item.task_status || 'created',
    progress: item.progress || 0,
    message: item.message || '',
    createTime: item.createTime || item.create_time || '',
    error: item.error || item.error_message || ''
  }
}

function weatherFileName(fileId) {
  if (!fileId) return '未选择'
  return weatherFiles.value.find(item => String(item.id) === String(fileId))?.name || `文件ID ${fileId}`
}

function statusText(status) {
  const map = {
    created: '已创建',
    submitted: '已提交',
    queued: '排队中',
    running: '运行中',
    success: '已完成',
    failed: '失败',
    stopped: '已停止'
  }
  return map[status] || status || '未知'
}

function statusTagType(status) {
  if (status === 'success') return 'success'
  if (['running', 'queued', 'submitted'].includes(status)) return 'warning'
  if (status === 'failed') return 'danger'
  return 'info'
}

function priorityText(priority) {
  return { high: '高', normal: '普通', low: '低' }[priority] || '普通'
}

function handleQuery() {
  pageNum.value = 1
}

function resetQuery() {
  queryParams.value = { keyword: '', status: '', algorithmId: '', region: '', createDateRange: [] }
  pageNum.value = 1
}

async function loadPlatforms() {
  try {
    const res = await listAlgorithmServers()
    platforms.value = getRows(res).map(normalizeServer).filter(item => item.id || item.url)
    if (platforms.value.length) {
      if (!currentPlatformId.value || !platforms.value.some(item => String(item.id) === String(currentPlatformId.value))) {
        currentPlatformId.value = String(platforms.value[0].id)
      }
      serverUrl.value = platforms.value.find(item => String(item.id) === String(currentPlatformId.value))?.url || platforms.value[0].url || ''
    }
  } catch (error) {
    platforms.value = []
    pageError.value = `加载算力平台失败：${getErrorMessage(error)}`
  }
}

function handlePlatformChange(id) {
  const hit = platforms.value.find(item => String(item.id) === String(id))
  serverUrl.value = hit?.url || ''
  serverOnline.value = false
  serverStatus.value = ''
  loadAlgorithmModels().catch(() => {})
}

function handleTaskServerChange(id) {
  const hit = platforms.value.find(item => String(item.id) === String(id))
  taskForm.value.serverUrl = hit?.url || ''
}

async function handleCheckServer({ notify = true } = {}) {
  if (!serverUrl.value) {
    if (notify) ElMessage.warning('请先选择算力平台')
    return
  }
  try {
    const res = await checkAlgorithmServer(serverUrl.value)
    const data = unwrap(res)
    serverOnline.value = true
    serverStatus.value = `algorithm-server 在线：${data.service || 'algorithm-server'}，CPU ${data.cpu_usage ?? '-'}%，内存 ${data.memory_usage ?? '-'}%`
    if (notify) ElMessage.success('algorithm-server 连接成功')
  } catch (error) {
    serverOnline.value = false
    serverStatus.value = `algorithm-server 连接失败：${getErrorMessage(error)}`
    if (notify) ElMessage.error(`连接失败：${getErrorMessage(error)}`)
  }
}

async function loadAlgorithmModels() {
  if (!serverUrl.value) {
    algorithmList.value = []
    return
  }
  try {
    const params = currentPlatformId.value ? { serverId: currentPlatformId.value } : { serverUrl: serverUrl.value }
    const res = await listAlgorithmModels(params)
    algorithmList.value = getRows(res).map(normalizeAlgorithm).filter(item => item.algorithm_id)
  } catch (error) {
    algorithmList.value = []
    pageError.value = `加载算法模型失败：${getErrorMessage(error)}`
  }
}

async function handleSyncAlgorithms() {
  if (!serverUrl.value) {
    algorithmList.value = []
    return
  }
  try {
    await syncAlgorithmModels(serverUrl.value)
  } catch {
    // If algorithm-server is down, still read already registered MySQL models below.
  }
  try {
    await loadAlgorithmModels()
    if (algorithmList.value.length) {
      ElMessage.success(`当前可用 ${algorithmList.value.length} 个算法/模型`)
    } else {
      ElMessage.warning('未获取到算法，请先在算力平台管理页面添加或上传模型')
    }
  } catch (error) {
    algorithmList.value = []
    pageError.value = `加载算法模型失败：${getErrorMessage(error)}`
  }
}

async function loadTasks() {
  loading.value = true
  try {
    const res = await listAlgorithmTasks()
    taskList.value = getRows(res).map(normalizeTask)
  } catch (error) {
    taskList.value = []
    pageError.value = `加载任务失败：${getErrorMessage(error)}`
  } finally {
    loading.value = false
  }
}

async function loadWeatherFiles() {
  try {
    const res = await listWeatherFiles()
    weatherFiles.value = getRows(res).filter(item => item.itemType !== 'folder' && !item.isFolder)
  } catch (error) {
    weatherFiles.value = []
    pageError.value = `加载气象数据文件失败：${getErrorMessage(error)}`
  }
}

function openAlgorithmDrawer() {
  algorithmDrawerVisible.value = true
  if (!algorithmList.value.length) handleSyncAlgorithms().catch(() => {})
}

function openApiDocs() {
  if (serverUrl.value) window.open(`${normalizeUrl(serverUrl.value)}/docs`, '_blank')
}

function handleAdd() {
  taskForm.value = createDefaultForm()
  dialogVisible.value = true
}

function handleAlgorithmChange(value) {
  const hit = algorithmList.value.find(item => item.algorithm_id === value)
  taskForm.value.algorithmName = hit?.algorithm_name || value
  if (value === 'tabpfn_fault_cv') {
    taskForm.value.taskType = 'tabular_cv'
  } else if (value === 'tabpfn_fault_forecast') {
    taskForm.value.taskType = 'tabular_forecast'
  } else if (hit?.algorithm_type === 'file_algorithm' || String(hit?.run_api || '').endsWith('/api/tasks/run-file')) {
    taskForm.value.taskType = 'file_algorithm'
  } else taskForm.value.taskType = hit?.algorithm_type || ''
}

function handleWeatherFileChange(fileId) {
  const file = weatherFiles.value.find(item => String(item.id) === String(fileId))
  if (!file) {
    taskForm.value.dataSource = ''
    return
  }
  if (isTabPfnForecastAlgorithm.value) taskForm.value.taskType = 'tabular_forecast'
  else if (isTabPfnCvAlgorithm.value) taskForm.value.taskType = 'tabular_cv'
  else if (isFileAlgorithm.value) taskForm.value.taskType = 'file_algorithm'
  else taskForm.value.taskType = 'tabular_batch'
  taskForm.value.dataSource = 'weather_file'
}

function syncAlgorithmName() {
  const item = algorithmList.value.find(i => i.algorithm_id === taskForm.value.algorithmId)
  taskForm.value.algorithmName = item?.algorithm_name || taskForm.value.algorithmId || ''
}

function buildPayload() {
  syncAlgorithmName()
  let algorithmParams = {}
  if (isFileAlgorithm.value && !isTabPfnAlgorithm.value) {
    try {
      algorithmParams = JSON.parse(taskForm.value.algorithmParamsText || '{}')
    } catch {
      throw new Error('算法参数 JSON 格式不正确')
    }
  }
  const params = isTabPfnAlgorithm.value
    ? {
        n_repeats: taskForm.value.nRepeats,
        n_splits: taskForm.value.nSplits,
        random_seed: taskForm.value.randomSeed,
        target_column: '是否为故障杆塔',
        ...(isTabPfnForecastAlgorithm.value
          ? {
              training_file_id: taskForm.value.trainingFileId,
              fault_threshold: taskForm.value.faultThreshold,
              forecast_hours: taskForm.value.forecastHours
            }
          : {})
      }
    : isFileAlgorithm.value
      ? algorithmParams
      : {
          temperature: taskForm.value.temperature,
          humidity: taskForm.value.humidity,
          wind_speed: taskForm.value.windSpeed,
          wind_direction: taskForm.value.windDirection,
          precipitation: taskForm.value.precipitation,
          history_icing_thickness: taskForm.value.historyIcingThickness,
          forecast_hours: taskForm.value.forecastHours
        }
  return {
    taskName: taskForm.value.taskName,
    taskType: taskForm.value.taskType,
    serverId: taskForm.value.serverId,
    serverUrl: normalizeUrl(taskForm.value.serverUrl),
    algorithmId: taskForm.value.algorithmId,
    algorithmName: taskForm.value.algorithmName,
    priority: taskForm.value.priority,
    region: taskForm.value.region,
    lineCode: taskForm.value.lineCode,
    forecastHours: taskForm.value.forecastHours,
    startTime: taskForm.value.startTime,
    endTime: taskForm.value.endTime,
    fileId: taskForm.value.fileId,
    dataSource: taskForm.value.dataSource,
    remark: taskForm.value.remark,
    params
  }
}

async function submitTask() {
  if (!taskForm.value.taskName) return ElMessage.warning('请输入任务名称')
  if (!taskForm.value.taskType) return ElMessage.warning('请选择任务类型')
  if (!taskForm.value.serverUrl) return ElMessage.warning('请输入算法服务器地址')
  if (!taskForm.value.algorithmId) return ElMessage.warning('请选择算法模型')
  if (!taskForm.value.priority) return ElMessage.warning('请选择优先级')
  if (isFileAlgorithm.value && !taskForm.value.fileId) return ElMessage.warning('文件型算法任务必须选择输入文件')
  if (isTabPfnForecastAlgorithm.value && !taskForm.value.trainingFileId) return ElMessage.warning('请选择历史训练文件')
  if (isTabPfnForecastAlgorithm.value && String(taskForm.value.trainingFileId) === String(taskForm.value.fileId)) {
    return ElMessage.warning('历史训练文件和待预测文件不能相同')
  }
  if (isTabPfnAlgorithm.value && (taskForm.value.nRepeats == null || taskForm.value.nSplits == null || taskForm.value.randomSeed == null)) {
    return ElMessage.warning('请填写重复次数、交叉验证折数和随机种子')
  }
  if (isTabPfnForecastAlgorithm.value && (taskForm.value.forecastHours == null || taskForm.value.faultThreshold == null)) {
    return ElMessage.warning('请填写预测时长和故障判定阈值')
  }
  let payload
  try {
    payload = buildPayload()
  } catch (error) {
    return ElMessage.warning(getErrorMessage(error))
  }
  const res = await createAlgorithmTask(payload)
  const task = unwrap(res)
  dialogVisible.value = false
  ElMessage.success('任务创建成功')
  await loadTasks()
  return task
}

async function submitAndRunTask() {
  const task = await submitTask()
  if (task?.taskCode) await handleRun(task)
}

async function handleRun(row) {
  if (isTaskActive(row) || submittingTaskCodes.value.has(row.taskCode)) return
  submittingTaskCodes.value.add(row.taskCode)
  try {
    await runAlgorithmTask(row.taskCode)
    ElMessage.success('任务已提交到 algorithm-server')
  } finally {
    await loadTasks()
    submittingTaskCodes.value.delete(row.taskCode)
  }
}

function isTaskActive(row) {
  return ['running', 'queued', 'submitted'].includes(row.status)
}

function downloadRecords(headers, rows, filename) {
  saveAs(new Blob([recordsToCsv(headers, rows)], { type: 'text/csv;charset=utf-8;' }), filename)
}

function exportTaskRecords() {
  downloadRecords(
    ['任务号', '任务名称', '算法模型', '区域', '线路', '优先级', '状态', '进度(%)', '创建时间', '更新时间', '运行信息', '错误详情'],
    filteredTaskList.value.map(task => [task.taskCode, task.taskName, task.algorithmName, task.region, task.lineCode,
      priorityText(task.priority), statusText(task.status), task.progress, task.createTime, task.updateTime, task.message, task.error]),
    '算法任务记录.csv'
  )
}

function handleHistory(row) {
  historyTask.value = row
  historyPageNum.value = 1
  historyRows.value = []
  historyTotal.value = 0
  historyVisible.value = true
  loadHistory()
}

async function loadHistory() {
  if (!historyTask.value) return
  const requestId = ++historyRequestId
  historyLoading.value = true
  historyError.value = ''
  try {
    const res = await getAlgorithmTaskHistory(historyTask.value.taskCode, { pageNum: historyPageNum.value, pageSize: historyPageSize.value })
    if (requestId !== historyRequestId) return
    const data = unwrap(res)
    historyRows.value = data.rows || []
    historyTotal.value = data.total || 0
  } catch (error) {
    if (requestId !== historyRequestId) return
    historyRows.value = []
    historyTotal.value = 0
    historyError.value = `加载运行记录失败：${getErrorMessage(error)}`
  } finally {
    if (requestId === historyRequestId) historyLoading.value = false
  }
}

function handleHistorySizeChange() {
  historyPageNum.value = 1
  loadHistory()
}

function exportHistoryRecords() {
  downloadRecords(['任务号', '记录时间', '状态', '进度(%)', '运行信息', '错误详情'],
    historyRows.value.map(row => [historyTask.value.taskCode, row.eventTime, statusText(row.status), row.progress, row.message, row.error]),
    `${historyTask.value.taskCode}_运行记录_第${historyPageNum.value}页.csv`)
}

async function handleStatus(row) {
  await getAlgorithmTaskStatus(row.taskCode)
  ElMessage.success('任务状态已更新')
  await loadTasks()
}

async function batchRefreshStatus() {
  const rows = taskList.value.filter(item => ['running', 'queued', 'submitted'].includes(item.status))
  if (!rows.length) return ElMessage.info('当前没有运行中的任务')
  for (const row of rows) {
    await getAlgorithmTaskStatus(row.taskCode).catch(() => {})
  }
  ElMessage.success(`已刷新 ${rows.length} 个任务状态`)
  await loadTasks()
}

async function refreshActiveTaskStatus() {
  if (taskStatusPolling) return
  const rows = taskList.value.filter(item => ['running', 'queued', 'submitted'].includes(item.status))
  if (!rows.length) return
  taskStatusPolling = true
  try {
    for (const row of rows) {
      await getAlgorithmTaskStatus(row.taskCode).catch(() => {})
    }
    await loadTasks()
  } finally {
    taskStatusPolling = false
  }
}

async function handleResult(row) {
  disposeResultCharts()
  resultActiveTab.value = 'overview'
  resultPageNum.value = 1
  const res = await getAlgorithmTaskResult(row.taskCode)
  resultData.value = unwrap(res)
  resultVisible.value = true
  await loadTasks()
}

function isFileTaskRow(row) {
  return row?.taskType === 'file_algorithm' || row?.taskType === 'tabular_cv' || row?.taskType === 'tabular_forecast' || row?.result?.result_type === 'file'
}

function formatProbability(value) {
  const number = Number(value)
  return Number.isFinite(number) ? `${(number * 100).toFixed(2)}%` : '-'
}

function formatMetric(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number.toFixed(4) : '-'
}

function formatDuration(value) {
  const number = Number(value)
  return Number.isFinite(number) ? `${number.toFixed(2)} 秒` : '-'
}

function formatResultNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number.toFixed(2) : '-'
}

function formatProbabilityPercent(value) {
  const number = Number(value)
  return Number.isFinite(number) ? `${number.toFixed(2)}%` : '-'
}

function formatRatio(value) {
  const number = Number(value)
  return Number.isFinite(number) ? `${(number * 100).toFixed(2)}%` : '-'
}

function riskTagType(level) {
  return { 低: 'success', 一般: 'info', 较高: 'warning', 高: 'danger' }[level] || 'info'
}

function disposeResultCharts() {
  hourlyChartInstance?.dispose()
  riskChartInstance?.dispose()
  metricChartInstance?.dispose()
  confusionChartInstance?.dispose()
  hourlyChartInstance = null
  riskChartInstance = null
  metricChartInstance = null
  confusionChartInstance = null
}

function resizeResultCharts() {
  hourlyChartInstance?.resize()
  riskChartInstance?.resize()
  metricChartInstance?.resize()
  confusionChartInstance?.resize()
}

async function initResultCharts() {
  await nextTick()
  if (!resultVisible.value || resultActiveTab.value !== 'charts' || !resultPreviewAvailable.value) return
  disposeResultCharts()

  const hourly = resultChartData.value?.hourly_probability || {}
  if (hourlyChartRef.value) {
    hourlyChartInstance = echarts.init(hourlyChartRef.value)
    hourlyChartInstance.setOption({
      color: ['#409eff', '#f56c6c'],
      tooltip: { trigger: 'axis', valueFormatter: value => `${Number(value).toFixed(2)}%` },
      legend: { top: 0, data: ['平均概率', '最高概率'] },
      grid: { left: 50, right: 20, top: 42, bottom: 38 },
      xAxis: { type: 'category', name: '时效', data: (hourly.hours || []).map(item => `${item}h`) },
      yAxis: { type: 'value', name: '概率', min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
      series: [
        { name: '平均概率', type: 'line', smooth: true, symbolSize: 6, data: hourly.average || [] },
        { name: '最高概率', type: 'line', smooth: true, symbolSize: 6, data: hourly.maximum || [] }
      ]
    })
  }

  const riskData = Array.isArray(resultChartData.value?.risk_distribution) ? resultChartData.value.risk_distribution : []
  if (riskChartRef.value) {
    riskChartInstance = echarts.init(riskChartRef.value)
    riskChartInstance.setOption({
      color: ['#67c23a', '#909399', '#e6a23c', '#f56c6c'],
      tooltip: { trigger: 'item', formatter: '{b}: {c} 条（{d}%）' },
      legend: { bottom: 0 },
      series: [{ name: '概率等级', type: 'pie', radius: ['42%', '68%'], center: ['50%', '44%'], label: { formatter: '{b}\n{c}条' }, data: riskData }]
    })
  }

  const metrics = Array.isArray(resultChartData.value?.validation_metrics) ? resultChartData.value.validation_metrics : []
  if (metricChartRef.value) {
    metricChartInstance = echarts.init(metricChartRef.value)
    metricChartInstance.setOption({
      color: ['#409eff'],
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: value => `${(Number(value) * 100).toFixed(2)}%` },
      grid: { left: 54, right: 18, top: 24, bottom: 38 },
      xAxis: { type: 'category', data: metrics.map(item => item.name) },
      yAxis: { type: 'value', min: 0, max: 1, axisLabel: { formatter: value => `${Math.round(value * 100)}%` } },
      series: [{ type: 'bar', barMaxWidth: 42, data: metrics.map(item => item.value), label: { show: true, position: 'top', formatter: params => `${(Number(params.value) * 100).toFixed(1)}%` } }]
    })
  }

  const confusion = resultChartData.value?.confusion_matrix || {}
  const confusionValues = [Number(confusion.tn || 0), Number(confusion.fp || 0), Number(confusion.fn || 0), Number(confusion.tp || 0)]
  if (confusionChartRef.value) {
    confusionChartInstance = echarts.init(confusionChartRef.value)
    confusionChartInstance.setOption({
      tooltip: { position: 'top', formatter: params => `${params.name}: ${params.value[2]}` },
      grid: { left: 82, right: 46, top: 28, bottom: 58 },
      xAxis: { type: 'category', name: '预测类别', data: ['正常', '故障'], splitArea: { show: true } },
      yAxis: { type: 'category', name: '实际类别', data: ['正常', '故障'], splitArea: { show: true } },
      visualMap: { min: 0, max: Math.max(...confusionValues, 1), calculable: false, orient: 'horizontal', left: 'center', bottom: 0, inRange: { color: ['#eef5ff', '#409eff'] } },
      series: [{
        type: 'heatmap',
        data: [[0, 0, confusionValues[0]], [1, 0, confusionValues[1]], [0, 1, confusionValues[2]], [1, 1, confusionValues[3]]],
        label: { show: true, fontSize: 16, fontWeight: 600 },
        emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,.2)' } }
      }]
    })
  }
}

function handleResultTabChange(name) {
  if (name === 'charts') initResultCharts()
}

async function handleDownload(row) {
  const taskCode = row?.taskCode || resultData.value?.taskCode
  if (!taskCode) return ElMessage.warning('未找到任务编号')
  try {
    const data = await downloadAlgorithmTaskResult(taskCode)
    const blob = data instanceof Blob ? data : new Blob([data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    if (blob.type.includes('application/json')) {
      const message = JSON.parse(await blob.text())?.msg || '结果文件下载失败'
      throw new Error(message)
    }
    const filename = row?.result?.output_filename || resultPayload.value?.output_filename || `${taskCode}_result.bin`
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

function handleDetail(row) {
  currentTask.value = row
  detailVisible.value = true
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确认删除任务 ${row.taskCode} 吗？`, '提示', { type: 'warning' })
  await deleteAlgorithmTask(row.taskCode)
  ElMessage.success('删除成功')
  await loadTasks()
}

onMounted(async () => {
  await loadPlatforms()
  await Promise.all([loadTasks(), loadWeatherFiles(), loadAlgorithmModels()])
  await handleCheckServer({ notify: false })
  taskStatusTimer = window.setInterval(refreshActiveTaskStatus, 5000)
  window.addEventListener('resize', resizeResultCharts)
})

onUnmounted(() => {
  if (taskStatusTimer) window.clearInterval(taskStatusTimer)
  window.removeEventListener('resize', resizeResultCharts)
  disposeResultCharts()
})
</script>

<style scoped>
.task-page { padding: 20px; background: #f5f7fa; min-height: calc(100vh - 84px); }
.mb16 { margin-bottom: 16px; }
.page-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 16px; }
.page-heading h2 { margin: 0; color: #1f2937; font-size: 22px; font-weight: 650; }
.page-heading p { margin: 6px 0 0; color: #7b8494; font-size: 13px; }
.overview-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
.metric-card { position: relative; display: flex; min-height: 88px; overflow: hidden; border: 1px solid #e3e8ef; border-radius: 7px; background: #fff; }
.metric-accent { width: 4px; background: #409eff; }
.metric-1 .metric-accent { background: #e6a23c; }
.metric-2 .metric-accent { background: #67c23a; }
.metric-3 .metric-accent { background: #f56c6c; }
.metric-content { flex: 1; padding: 14px 16px; min-width: 0; }
.metric-title { color: #6b7280; font-size: 13px; }
.metric-main { display: flex; align-items: baseline; gap: 12px; margin-top: 8px; }
.metric-main strong { color: #1f2937; font-size: 26px; line-height: 1; }
.metric-main span { overflow: hidden; color: #9aa2af; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.workspace-card { border-radius: 7px; }
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.header-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.card-title { color: #303133; font-size: 17px; font-weight: 600; }
.card-subtitle { margin-left: 12px; color: #909399; font-size: 13px; }
.service-section { display: grid; grid-template-columns: 150px minmax(420px, 1fr) auto; align-items: center; gap: 16px; padding: 14px 16px; border: 1px solid #e4e9f0; border-radius: 6px; background: #f8fafc; }
.section-label { display: flex; align-items: center; gap: 10px; min-width: 0; }
.section-label div { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.section-label strong { color: #303133; font-size: 14px; }
.section-label span:last-child { overflow: hidden; color: #909399; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.status-dot { flex: 0 0 auto; width: 9px; height: 9px; border-radius: 50%; background: #c0c4cc; box-shadow: 0 0 0 4px rgb(192 196 204 / 18%); }
.status-dot.online { background: #67c23a; box-shadow: 0 0 0 4px rgb(103 194 58 / 16%); }
.service-controls, .service-actions { display: flex; align-items: center; gap: 8px; min-width: 0; }
.platform-select { width: 220px; flex: 0 0 auto; }
.server-url-input { min-width: 220px; flex: 1; }
.service-actions { justify-content: flex-end; flex-wrap: wrap; }
.server-alert { margin-top: 10px; }
.filter-section { margin: 14px 0; padding: 12px 16px 0; border: 1px solid #e8ecf2; border-radius: 6px; background: #fff; }
.filter-form { display: flex; align-items: flex-start; flex-wrap: wrap; gap: 0 10px; }
.filter-form :deep(.el-form-item) { margin-right: 0; margin-bottom: 12px; }
.keyword-input { width: 260px; }
.filter-select { width: 150px; }
.algorithm-select { width: 220px; }
.region-input { width: 140px; }
.filter-actions { margin-left: auto; }
.task-table { width: 100%; }
.pagination-wrapper { display: flex; justify-content: flex-end; margin-top: 14px; }
.drawer-toolbar { margin-bottom: 12px; }
.result-summary { margin-bottom: 12px; }
.result-tabs :deep(.el-tabs__content) { min-height: 470px; }
.result-descriptions { margin-bottom: 14px; }
.metric-result-table { margin-top: 14px; }
.result-section-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 10px; color: #606266; font-size: 13px; }
.result-section-toolbar span:last-child { color: #e6a23c; }
.result-pagination { display: flex; justify-content: flex-end; margin-top: 12px; }
.probability-value { color: #e6a23c; font-weight: 650; }
.risk-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
.risk-summary-item { position: relative; display: grid; grid-template-columns: 1fr auto; align-items: center; min-height: 84px; padding: 14px 16px; overflow: hidden; border: 1px solid #e4e7ed; border-radius: 7px; background: #fff; }
.risk-summary-item::before { position: absolute; inset: 0 auto 0 0; width: 4px; content: ''; background: #909399; }
.risk-summary-item span { color: #606266; font-size: 14px; }
.risk-summary-item strong { grid-row: span 2; color: #303133; font-size: 28px; }
.risk-summary-item small { margin-top: 6px; color: #909399; font-size: 12px; }
.risk-summary-item.risk-低::before { background: #67c23a; }
.risk-summary-item.risk-一般::before { background: #909399; }
.risk-summary-item.risk-较高::before { background: #e6a23c; }
.risk-summary-item.risk-高::before { background: #f56c6c; }
.risk-result-table { width: 100%; }
.result-chart-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.result-chart-panel { min-width: 0; padding: 12px 14px 8px; border: 1px solid #e4e7ed; border-radius: 7px; background: #fff; }
.result-chart-panel h4 { margin: 0 0 4px; color: #303133; font-size: 14px; font-weight: 600; }
.result-chart { width: 100%; height: 280px; }
.task-result-dialog { max-width: calc(100vw - 32px); }
.task-result-dialog :deep(.el-dialog__body) { max-height: 78vh; overflow-y: auto; }
.result-box { min-height: 360px; max-height: 560px; overflow: auto; padding: 16px; background: #0b1220; color: #d6e4ff; border-radius: 6px; font-size: 13px; line-height: 1.6; }
.unit { margin-left: 8px; color: #606266; }

@media (max-width: 1280px) {
  .service-section { grid-template-columns: 140px 1fr; }
  .service-actions { grid-column: 1 / -1; justify-content: flex-start; padding-left: 156px; }
  .overview-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 768px) {
  .task-page { padding: 12px; }
  .page-heading { align-items: center; }
  .overview-grid { grid-template-columns: 1fr; }
  .service-section { grid-template-columns: 1fr; }
  .service-controls, .service-actions { flex-wrap: wrap; }
  .service-actions { grid-column: auto; padding-left: 0; }
  .platform-select, .server-url-input, .keyword-input, .filter-select, .algorithm-select, .region-input { width: 100%; flex: 1 1 100%; }
  .filter-form { display: block; }
  .filter-actions { margin-left: 0; }
  .card-subtitle { display: block; margin: 4px 0 0; }
  .pagination-wrapper { justify-content: flex-start; overflow-x: auto; }
  .risk-summary-grid, .result-chart-grid { grid-template-columns: 1fr; }
  .result-section-toolbar { align-items: flex-start; flex-direction: column; }
}
</style>
