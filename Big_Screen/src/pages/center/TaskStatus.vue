<template>
  <div class="task-status-container">
    <div class="component-header flex-l">
      <div class="header-left flex-c">
        <i class="iconfont icon-diagnose" />
      </div>
      <div class="header-right flex-l">
        <span class="header-title">任务运行状态</span>
        <dv-decoration-3 class="dv-dec-3" />
      </div>
    </div>
    
    <div class="task-table-content" ref="scrollContainer">
      <div class="scroll-wrapper" :style="{ transform: `translateY(-${scrollTop}px)` }">
        <div
          class="task-row"
          v-for="(item, index) in taskList"
          :key="`${item.id || item.name}-${index}`"
          :title="formatTaskDetails(item)"
          @mouseenter="isHovering = true"
          @mouseleave="isHovering = false"
        >
          <div class="task-main">
            <span class="task-name">{{ item.name }}</span>
            <span class="task-status" :class="statusClass(item.status)">{{ item.status }}</span>
            <span class="progress-text">{{ item.progress }}%</span>
          </div>
          <div class="task-meta">
            <span class="task-model">{{ item.model }}</span>
            <span class="task-type">{{ formatTaskType(item.type) }}</span>
            <span class="task-time">{{ formatTaskTime(item.time) }}</span>
          </div>
          <div class="progress-bar-bg">
            <div class="progress-bar-fill" :style="{ width: item.progress + '%' }" :class="progressClass(item.status)"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import { apiGetTaskStatus } from '@/api/index';
import { screenStore } from '@/store/screenData';

const taskList = ref<any[]>([]);
const sourceTaskCount = ref(0);
let timer: number | null = null;
let scrollTimer: number | null = null;
const scrollTop = ref(0);
const scrollContainer = ref<HTMLElement | null>(null);
const isHovering = ref(false);

const fetchData = async () => {
  try {
    const res = await apiGetTaskStatus();
    if (res.code === 200) {
      const uniqueRows = Array.from(
        new Map((Array.isArray(res.data) ? res.data : []).map((item: any) => [item.id || `${item.name}-${item.time}`, item])).values()
      );
      sourceTaskCount.value = uniqueRows.length;
      taskList.value = uniqueRows.length > 3 ? [...uniqueRows, ...uniqueRows] : uniqueRows;
      scrollTop.value = 0;
      if (uniqueRows.length > 3) startScroll();
      else if (scrollTimer) {
        clearInterval(scrollTimer);
        scrollTimer = null;
      }
    }
  } catch (error) {
    console.error('Failed to fetch task status', error);
  }
};

watch(() => screenStore.refreshKey, fetchData);

const startScroll = () => {
  if (scrollTimer) clearInterval(scrollTimer);
  scrollTimer = window.setInterval(() => {
    if (isHovering.value) return;
    scrollTop.value += 1;
    if (scrollTop.value >= sourceTaskCount.value * 52) {
      scrollTop.value = 0;
    }
  }, 50);
};

const formatTaskDetails = (item: any) => [
  `任务名称：${item.name || '-'}`,
  `算法模型：${item.model || '-'}`,
  `任务类型：${item.type || '-'}`,
  `任务状态：${item.status || '-'}`,
  `开始时间：${item.time || '-'}`,
  `执行进度：${Number.isFinite(Number(item.progress)) ? `${item.progress}%` : '-'}`
].join('\n');

const formatTaskTime = (value: string) => {
  const text = String(value || '');
  return text.length >= 16 ? text.slice(5, 16) : text || '--';
};

const formatTaskType = (value: string) => ({
  tabular_forecast: '概率预测',
  tabular_cv: '交叉验证',
  file_algorithm: '文件算法'
}[value] || value || '-');

const statusClass = (status: string) => ({
  '已完成': 'status-done',
  '运行中': 'status-running',
  '排队中': 'status-running',
  '已提交': 'status-running',
  '失败': 'status-failed',
  '已停止': 'status-stopped',
  '已创建': 'status-created'
}[status] || 'status-created');

const progressClass = (status: string) => ({
  '已完成': 'fill-done',
  '失败': 'fill-failed',
  '已停止': 'fill-stopped'
}[status] || 'fill-running');

onMounted(() => {
  fetchData();
  timer = window.setInterval(fetchData, 5000);
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
  if (scrollTimer) clearInterval(scrollTimer);
});
</script>

<style lang="scss" scoped>
@import '@/assets/scss/common/variables.scss';

.task-status-container {
  width: 100%;
  height: 100%;
  background-color: transparent;
  padding: 15px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;

  .component-header {
    height: $chart-header-height;
    margin-bottom: 10px;

    .header-left {
      width: 30px;
      i {
        color: #fff;
        font-size: 18px;
      }
    }

    .header-right {
      width: calc(100% - 30px);

      .header-title {
        color: #fff;
        font-size: $sm-font-size;
        font-weight: bold;
      }

      .dv-dec-3 {
        width: 100px;
        height: 20px;
        margin-left: 10px;
      }
    }
  }

  .task-table-content {
    flex: 1;
    overflow: hidden;
    position: relative;

    .scroll-wrapper {
      position: absolute;
      width: 100%;
      transition: transform 0.05s linear;
    }

    .task-row {
      height: 52px;
      padding: 6px 4px 5px;
      box-sizing: border-box;
      color: #eef4ff;
      font-size: 12px;
      border-bottom: 1px dashed rgba(112, 150, 205, 0.08);
      cursor: help;

      .task-main,
      .task-meta {
        display: flex;
        align-items: center;
        min-width: 0;
      }

      .task-main {
        height: 18px;
        gap: 8px;

        .task-name {
          flex: 1;
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          color: #eef4ff;
          font-weight: 600;
        }

        .task-status {
          flex: 0 0 auto;
          font-size: 11px;

          &.status-done { color: #7aa7ff; }
          &.status-running { color: #d8a74f; }
          &.status-failed { color: #ff7272; }
          &.status-stopped { color: #8793a6; }
          &.status-created { color: #78a7ff; }
        }

        .progress-text {
          width: 34px;
          flex: 0 0 34px;
          text-align: right;
          font-size: 10px;
          color: #9cacc2;
          font-variant-numeric: tabular-nums;
        }
      }

      .task-meta {
        height: 17px;
        gap: 10px;
        color: #8193ab;
        font-size: 10px;

        .task-model {
          flex: 1;
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .task-type {
          flex: 0 0 auto;
          color: #94a9c3;
        }

        .task-time {
          flex: 0 0 68px;
          text-align: right;
          white-space: nowrap;
          font-variant-numeric: tabular-nums;
        }
      }

      .progress-bar-bg {
        width: 100%;
        height: 3px;
        margin-top: 2px;
        background: rgba(127,190,255,0.10);
        border-radius: 2px;
        overflow: hidden;

        .progress-bar-fill {
          height: 100%;
          border-radius: 2px;

          &.fill-done { background: linear-gradient(90deg, #6f9dff, #8aa5c9); }
          &.fill-running { background: linear-gradient(90deg, #d8a74f, #d99051); }
          &.fill-failed { background: #ff7272; }
          &.fill-stopped { background: #8793a6; }
        }
      }

    }
  }
}

.flex-l {
  display: flex;
  align-items: center;
}

.flex-c {
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
