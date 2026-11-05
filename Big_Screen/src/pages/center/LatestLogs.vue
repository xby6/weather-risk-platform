<template>
  <div class="latest-logs-container">
    <div class="panel-title">最新日志</div>
    <div class="logs-wrapper">
      <div class="log-list" :style="{ transform: `translateY(${offset}px)`, transition: isTransition ? 'all 0.5s' : 'none' }">
        <div
          class="log-item"
          v-for="(log, idx) in displayLogs"
          :key="idx"
          :title="formatLogDetails(log)"
          @mouseenter="isHovering = true"
          @mouseleave="isHovering = false"
        >
          <span class="log-type" :class="log.type === '预警' ? 'warn' : 'info'">[{{ log.type }}]</span>
          <span class="log-content">{{ log.content }}</span>
          <span class="log-time">{{ formatLogTime(log.time) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import { apiGetLatestLogs } from '@/api/index';
import { screenStore } from '@/store/screenData';

const logs = ref<any[]>([]);
const displayLogs = ref<any[]>([]);
const offset = ref(0);
const isTransition = ref(true);
const isHovering = ref(false);

let fetchTimer: number | null = null;
let scrollTimer: number | null = null;

const fetchData = async () => {
  try {
    const res = await apiGetLatestLogs();
    if (res.code === 200) {
      logs.value = res.data;
      // Copy to displayLogs to allow seamless scrolling
      displayLogs.value = [...logs.value, ...logs.value];
    }
  } catch (error) {
    console.error('Failed to fetch latest logs', error);
  }
};

watch(() => screenStore.refreshKey, fetchData);

const startScroll = () => {
  scrollTimer = setInterval(() => {
    if (isHovering.value || logs.value.length === 0) return;
    isTransition.value = true;
    offset.value -= 30; // height of one log item
    
    setTimeout(() => {
      if (Math.abs(offset.value) >= logs.value.length * 30) {
        isTransition.value = false;
        offset.value = 0;
      }
    }, 500);
  }, 2000) as unknown as number;
};

const formatLogDetails = (log: any) => [
  `日志类型：${log.type || '-'}`,
  `日志内容：${log.content || '-'}`,
  `记录时间：${log.time || '-'}`
].join('\n');

const formatLogTime = (value: string) => {
  const text = String(value || '');
  return text.length >= 16 ? text.slice(5, 16) : text || '--';
};

onMounted(() => {
  fetchData();
  fetchTimer = setInterval(fetchData, 10000) as unknown as number; // refresh data less frequently
  startScroll();
});

onUnmounted(() => {
  if (fetchTimer) clearInterval(fetchTimer);
  if (scrollTimer) clearInterval(scrollTimer);
});
</script>

<style lang="scss" scoped>
.latest-logs-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 10px;
  
  .panel-title {
    color: #eef4ff;
    font-size: 16px;
    font-weight: bold;
    padding-left: 10px;
    border-left: 4px solid #6f9dff;
    margin-bottom: 10px;
  }
  
  .logs-wrapper {
    flex: 1;
    overflow: hidden;
    position: relative;
    
    .log-list {
      width: 100%;
      
      .log-item {
        height: 30px;
        line-height: 30px;
        display: flex;
        font-size: 12px;
        color: #9cacc2;
        border-bottom: 1px dashed rgba(112, 150, 205, 0.06);
        cursor: help;
        
        .log-type {
          width: 46px;
          flex-shrink: 0;
          &.warn { color: #d8a74f; }
          &.info { color: #6f9dff; }
        }
        
        .log-content {
          flex: 1;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          margin-right: 6px;
          color: #e7f0ff;
        }
        
        .log-time {
          width: 68px;
          flex-shrink: 0;
          text-align: right;
          white-space: nowrap;
          font-variant-numeric: tabular-nums;
        }
      }
    }
  }
}
</style>
