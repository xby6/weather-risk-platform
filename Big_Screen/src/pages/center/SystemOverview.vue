<template>
  <div class="system-overview-container">
    <div class="panel-title">算法服务状态</div>
    <div class="status-row">
      <span class="label">服务状态</span>
      <span :class="['status', overview.status === 'online' ? 'online' : 'offline']">
        {{ overview.status === 'online' ? '在线' : '离线' }}
      </span>
    </div>
    <div class="status-row">
      <span class="label">服务名称</span>
      <span class="value">{{ overview.service }}</span>
    </div>
    <div class="status-row">
      <span class="label">服务版本</span>
      <span class="value">{{ overview.version }}</span>
    </div>
    <div class="meter-list">
      <div class="meter-item">
        <span>CPU</span>
        <div class="bar"><i :style="{ width: overview.cpuUsage + '%' }"></i></div>
        <em>{{ overview.cpuUsage }}%</em>
      </div>
      <div class="meter-item">
        <span>GPU</span>
        <div class="bar"><i :style="{ width: overview.gpuUsage + '%' }"></i></div>
        <em>{{ overview.gpuUsage }}%</em>
      </div>
      <div class="meter-item">
        <span>内存</span>
        <div class="bar"><i :style="{ width: overview.memoryUsage + '%' }"></i></div>
        <em>{{ overview.memoryUsage }}%</em>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, reactive } from 'vue';
import { apiGetSystemOverview } from '@/api/index';

const overview = reactive({
  status: 'offline',
  service: 'algorithm-server',
  version: '-',
  cpuUsage: 0,
  gpuUsage: 0,
  memoryUsage: 0
});

let timer: number | null = null;

const fetchData = async () => {
  try {
    const res = await apiGetSystemOverview();
    if (res.code === 200) {
      Object.assign(overview, res.data);
    }
  } catch (e) {
    overview.status = 'offline';
  }
};

onMounted(() => {
  fetchData();
  timer = window.setInterval(fetchData, 10000);
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
});
</script>

<style scoped lang="scss">
.system-overview-container {
  width: 100%;
  height: 100%;
  padding: 15px;
  box-sizing: border-box;
  color: #fff;

  .panel-title {
    color: #eef4ff;
    font-size: 16px;
    font-weight: bold;
    padding-left: 10px;
    border-left: 4px solid #6f9dff;
    margin-bottom: 15px;
  }

  .status-row {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    line-height: 28px;
    border-bottom: 1px dashed rgba(127,190,255,0.10);

    .label { color: #9cacc2; }
    .value { color: #e7f0ff; }
    .status {
      font-weight: bold;
      &.online { color: #8aa5c9; }
      &.offline { color: #e86c5b; }
    }
  }

  .meter-list {
    margin-top: 12px;
    .meter-item {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 12px;
      font-size: 12px;
      span { width: 36px; color: #9cacc2; }
      em { width: 42px; color: #6f9dff; font-style: normal; text-align: right; }
      .bar {
        flex: 1;
        height: 7px;
        background: rgba(127,190,255,0.12);
        border-radius: 4px;
        overflow: hidden;
        i {
          display: block;
          height: 100%;
          background: linear-gradient(90deg, #6f9dff, #7aa7ff);
          border-radius: 4px;
          transition: width 0.3s;
        }
      }
    }
  }
}
</style>
