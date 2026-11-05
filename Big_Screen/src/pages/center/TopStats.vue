<template>
  <div class="top-stats-container" :class="{ compact }">
    <div
      class="stat-item"
      v-for="(item, index) in visibleItems"
      :key="index"
      :class="{ clickable: item.key === 'totalStations', active: item.key === 'totalStations' && screenStore.mapPointMenuOpen }"
      :style="{ color: item.iconColor }"
      :title="item.key === 'totalStations' ? '点击打开点位菜单' : ''"
      @click="handleStatClick(item)"
    >
      <div class="icon-wrapper flex-c" :style="{ color: item.iconColor }">
        <i class="iconfont" :class="item.icon"></i>
      </div>
      <div class="content-wrapper">
        <div class="stat-title">{{ item.title }}</div>
        <div class="stat-value">
          <span class="num" :style="{ color: item.numColor }">{{ item.value }}</span>
          <span class="unit" v-if="item.unit">{{ item.unit }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watch } from 'vue';
import { apiGetTopStats } from '@/api/index';
import { screenStore } from '@/store/screenData';
const props = defineProps<{ compact?: boolean }>();

const statItems = ref([
  { title: '气象站点总数', value: 0, unit: '个', key: 'totalStations', icon: 'icon-monitoring', iconColor: '#6f9dff', numColor: '#eef4ff' },
  { title: '输电线路总长', value: 0, unit: 'km', key: 'totalLines', icon: 'icon-diagnose', iconColor: '#7aa7ff', numColor: '#eef4ff' },
  { title: '当前在线站点', value: 0, unit: '个', key: 'onlineStations', icon: 'icon-cloudupload', iconColor: '#8aa5c9', numColor: '#eef4ff' },
  { title: '预警事件总数', value: 0, unit: '条', key: 'warningEvents', icon: 'icon-tongji4', iconColor: '#d8a74f', numColor: '#d8a74f' },
  { title: '今日任务总数', value: 0, unit: '个', key: 'tasksToday', icon: 'icon-clouddownload', iconColor: '#7aa7ff', numColor: '#eef4ff' },
  { title: '系统运行天数', value: 0, unit: '天', key: 'runningDays', icon: 'icon-diagnose', iconColor: '#d97462', numColor: '#eef4ff' }
]);
const visibleItems = computed(() => props.compact ? statItems.value.filter(item => ['totalStations', 'warningEvents', 'tasksToday'].includes(item.key)) : statItems.value);

let timer: number | null = null;

const handleStatClick = (item: any) => {
  if (item.key === 'totalStations') {
    screenStore.mapPointMenuOpen = true;
  }
};

const fetchData = async () => {
  try {
    const res = await apiGetTopStats();
    if (res.code === 200) {
      statItems.value.forEach(item => {
        const key = item.key as keyof typeof res.data;
        if (res.data[key] !== undefined) {
          item.value = res.data[key];
        }
      });
    }
  } catch (error) {
    console.error('Failed to fetch top stats', error);
  }
};

watch(() => screenStore.refreshKey, fetchData);

onMounted(() => {
  fetchData();
  timer = window.setInterval(fetchData, 5000);
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
});
</script>

<style lang="scss" scoped>
.top-stats-container {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;

  .stat-item {
    flex: 1;
    height: 100%;
    display: flex;
    align-items: center;
    position: relative;
    overflow: hidden;
    background:
      linear-gradient(180deg, rgba(14, 37, 58, 0.78), rgba(7, 18, 31, 0.72));
    border: 1px solid rgba(112, 150, 205, 0.18);
    border-radius: 10px;
    padding: 0 12px;
    box-sizing: border-box;
    transition: all 0.3s;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);

    &::before {
      content: "";
      position: absolute;
      left: 0;
      top: 12px;
      bottom: 12px;
      width: 3px;
      background: currentColor;
      opacity: 0.85;
    }

    &:hover {
      background: rgba(18, 49, 73, 0.88);
      border-color: rgba(79, 134, 255, 0.36);
    }

    &.clickable {
      cursor: pointer;
    }

    &.clickable::after {
      content: "点位菜单";
      position: absolute;
      right: 10px;
      bottom: 8px;
      color: rgba(216, 167, 79, 0.74);
      font-size: 10px;
      opacity: 0;
      transition: opacity 0.2s ease;
    }

    &.clickable:hover::after,
    &.clickable.active::after {
      opacity: 1;
    }

    &.clickable.active {
      border-color: rgba(111, 157, 255, 0.56);
      background: rgba(79, 134, 255, 0.14);
    }

    .icon-wrapper {
      width: 40px;
      height: 40px;
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(255, 255, 255, 0.06);
      border-radius: 10px;
      margin-right: 10px;
      flex: 0 0 auto;
      
      i {
        font-size: 20px;
      }
    }

    .content-wrapper {
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: center;

      .stat-title {
        font-size: 12px;
        color: rgba(220, 236, 255, 0.66);
        margin-bottom: 4px;
        white-space: nowrap;
      }

      .stat-value {
        display: flex;
        align-items: baseline;
        
        .num {
          font-size: 24px;
          font-weight: bold;
          font-family: 'Electronic', sans-serif;
          line-height: 1;
        }
        
        .unit {
          font-size: 12px;
          margin-left: 4px;
          color: rgba(220, 236, 255, 0.58);
        }
      }
    }
  }
}

.flex-c {
  display: flex;
  align-items: center;
  justify-content: center;
}
.top-stats-container.compact {
  gap: 24px;
  .stat-item { border: 0 !important; padding: 0 14px; background: transparent !important; }
  .stat-item::before, .icon-wrapper { display: none; }
  .content-wrapper { align-items: center; }
  .stat-title { font-size: 10px !important; letter-spacing: 1px; margin-bottom: 4px !important; }
  .stat-value .num { font-size: 22px !important; color: #d3dfcb !important; }
}
</style>
