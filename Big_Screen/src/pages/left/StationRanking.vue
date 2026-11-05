<template>
    <div class="station-ranking">
        <div class="component-header">
            <div class="title-wrap">
                <i class="iconfont icon-monitoring" />
                <span class="header-title">站点气象排行</span>
            </div>
            <div class="ranking-tabs">
                <button class="tab-item" :class="{ active: currentTab === 'temp' }" type="button" @click="switchTab('temp')">温度排行</button>
                <button class="tab-item" :class="{ active: currentTab === 'wind' }" type="button" @click="switchTab('wind')">风速排行</button>
                <button class="tab-item" :class="{ active: currentTab === 'rain' }" type="button" @click="switchTab('rain')">降水排行</button>
            </div>
        </div>

        <div class="ranking-header">
            <div class="col-rank">排名</div>
            <div class="col-name">站点名称</div>
            <div class="col-value">{{ valueLabel }}</div>
            <div class="col-time">时间</div>
        </div>

        <div class="ranking-content">
            <div v-if="rankingRows.length > 0" class="ranking-list">
                <div class="ranking-row" v-for="(item, index) in rankingRows" :key="`${item.name}-${index}`">
                    <div class="col-rank">
                        <span class="rank-num">No.{{ index + 1 }}</span>
                    </div>
                    <div class="col-name" :title="item.name">{{ item.name }}</div>
                    <div class="col-value">
                        <span class="value-text">{{ formatValue(item.value) }}</span>
                        <span class="unit-text">{{ valueUnit }}</span>
                    </div>
                    <div class="col-time" :title="item.time">{{ formatTimeText(item.time) }}</div>
                </div>
            </div>
            <div v-else class="empty-text">暂无排行数据</div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { apiGetStationRanking } from '@/api/index';
import { screenStore } from '@/store/screenData';

interface RankingRow {
    name: string;
    value: number;
    time?: string;
}

const currentTab = ref('temp');
const rankingRows = ref<RankingRow[]>([]);
let timer: number | null = null;

const valueLabel = computed(() => {
    if (currentTab.value === 'temp') return '气温(℃)';
    if (currentTab.value === 'wind') return '风速(m/s)';
    return '降水(mm)';
});

const valueUnit = computed(() => {
    if (currentTab.value === 'temp') return '℃';
    if (currentTab.value === 'wind') return 'm/s';
    return 'mm';
});

const switchTab = (tab: string) => {
    currentTab.value = tab;
    fetchData();
};

const formatValue = (value: number) => {
    const num = Number(value);
    if (!Number.isFinite(num)) return '-';
    return currentTab.value === 'rain' ? num.toFixed(2) : num.toFixed(1);
};

const formatTimeText = (time?: string) => {
    if (!time) return '-';
    const text = String(time);
    return text.includes(' ') ? text.split(' ')[1]?.slice(0, 5) || text : text.slice(0, 5);
};

const fetchData = async () => {
    try {
        const res = await apiGetStationRanking(currentTab.value);
        if (res.code === 200) {
            rankingRows.value = (res.data || []).slice(0, 30).map((item: any) => ({
                name: item.name || '-',
                value: Number(item.value ?? 0),
                time: item.time || ''
            }));
        }
    } catch (error) {
        console.error('Failed to fetch station ranking data', error);
    }
};

watch(() => screenStore.refreshKey, fetchData);

onMounted(() => {
    fetchData();
    timer = window.setInterval(fetchData, 15000);
});

onUnmounted(() => {
    if (timer) {
        clearInterval(timer);
    }
});
</script>

<style lang="scss" scoped>
@import '@/assets/scss/common/variables.scss';

.station-ranking {
    height: 100%;
    background-color: $theme-sub-color;
    border-radius: 10px;
    padding: 10px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    min-width: 0;
}

.component-header {
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 7px;
    min-width: 0;

    .title-wrap {
        display: flex;
        align-items: center;
        min-width: 112px;
        flex: 0 0 auto;

        i {
            color: #7aa7ff;
            font-size: 18px;
            margin-right: 5px;
        }
    }

    .header-title {
        color: #fff;
        font-size: $sm-font-size;
        font-weight: bold;
        white-space: nowrap;
    }
}

.ranking-tabs {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 5px;
    min-width: 0;
    flex: 1;

    .tab-item {
        height: 22px;
        padding: 0 8px;
        color: rgba(255, 255, 255, 0.62);
        font-size: 11px;
        border-radius: 999px;
        cursor: pointer;
        transition: all 0.2s;
        border: 1px solid rgba(112, 150, 205, 0.18);
        background: rgba(255, 255, 255, 0.02);
        white-space: nowrap;

        &.active {
            background-color: rgba(79, 134, 255, 0.18);
            color: #eef4ff;
            border-color: rgba(79, 134, 255, 0.62);
        }

        &:hover {
            color: #eef4ff;
            border-color: rgba(79, 134, 255, 0.42);
        }
    }
}

.ranking-header,
.ranking-row {
    display: grid;
    grid-template-columns: 54px minmax(0, 1fr) 76px 52px;
    align-items: center;
    column-gap: 6px;
}

.ranking-header {
    height: 28px;
    color: #9cacc2;
    font-size: 12px;
    border: 1px solid rgba(112, 150, 205, 0.12);
    background: rgba(79, 134, 255, 0.06);
    border-radius: 6px;
    padding: 0 8px;
    box-sizing: border-box;
    margin-bottom: 4px;
}

.ranking-content {
    flex: 1;
    min-height: 0;
    overflow: hidden;
}

.ranking-list {
    height: 100%;
    overflow-y: auto;
    padding-right: 2px;
}

.ranking-row {
    height: 25px;
    padding: 0 8px;
    box-sizing: border-box;
    color: #e7f0ff;
    font-size: 12px;
    border-bottom: 1px dashed rgba(112, 150, 205, 0.10);

    &:nth-child(even) {
        background: rgba(255, 255, 255, 0.015);
    }
}

.col-rank,
.col-name,
.col-value,
.col-time {
    min-width: 0;
}

.rank-num {
    color: #6f9dff;
    font-family: 'Electronic', sans-serif;
}

.col-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.col-value {
    text-align: right;
    white-space: nowrap;
}

.value-text {
    color: #d8a74f;
    font-family: 'Electronic', sans-serif;
    font-weight: 700;
}

.unit-text {
    color: rgba(220, 236, 255, 0.55);
    font-size: 10px;
    margin-left: 2px;
}

.col-time {
    color: #9cacc2;
    text-align: right;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.empty-text {
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: rgba(220, 236, 255, 0.56);
    font-size: 13px;
}
</style>
