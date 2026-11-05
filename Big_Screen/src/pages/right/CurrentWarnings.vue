<template>
    <div class="current-warnings">
        <div class="header">
            <span class="title">最新预测风险</span>
        </div>
        <div class="content">
            <div class="list-header">
                <span>杆塔点位</span>
                <span>风险</span>
                <span>概率</span>
                <span>预测时间</span>
            </div>
            <div class="list-body">
                <div class="list-item" v-for="(item, index) in warnings" :key="index">
                    <span class="point" :title="`${item.area} ${item.point}`">{{ item.point }}</span>
                    <span :class="['level', getLevelClass(item.level)]">{{ item.level }}</span>
                    <span class="probability">{{ formatProbability(item.probability) }}</span>
                    <span class="time" :title="item.time">{{ formatTime(item.time) }}</span>
                </div>
                <div v-if="!warnings.length" class="empty-state">暂无预测数据</div>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import { apiGetCurrentWarnings } from '@/api/index';
import { screenStore } from '@/store/screenData';

interface WarningItem {
    point: string;
    level: string;
    probability: number;
    area: string;
    time: string;
    forecastHour: number;
}

const warnings = ref<WarningItem[]>([]);
let timer: number | undefined;

const fetchData = async () => {
    try {
        const res = await apiGetCurrentWarnings();
        if (res.code === 200) {
            warnings.value = res.data;
        }
    } catch (error) {
        console.error('Failed to fetch current warnings:', error);
    }
};

watch(() => screenStore.refreshKey, fetchData);

const getLevelClass = (level: string) => {
    if (level.includes('较高') || level.includes('橙')) return 'level-2';
    if (level === '高' || level.includes('红')) return 'level-1';
    if (level.includes('一般') || level.includes('黄')) return 'level-3';
    if (level.includes('低') || level.includes('蓝')) return 'level-4';
    return 'level-default';
};

const formatProbability = (value: number) => Number.isFinite(value) ? `${value.toFixed(1)}%` : '--';
const formatTime = (value: string) => {
    const text = String(value || '');
    return text.length >= 16 ? text.slice(5, 16) : text || '--';
};

onMounted(() => {
    fetchData();
    timer = window.setInterval(fetchData, 5000); // Update every 5s
});

onUnmounted(() => {
    if (timer) clearInterval(timer);
});
</script>

<style scoped lang="scss">
.current-warnings {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    color: #fff;
    padding: 12px;
    box-sizing: border-box;

    .header {
        font-size: 16px;
        font-weight: bold;
        margin-bottom: 10px;
        padding-left: 10px;
        border-left: 4px solid #6f9dff;
    }

    .content {
        flex: 1;
        display: flex;
        flex-direction: column;
        background: rgba(5, 16, 28, 0.38);
        border: 1px solid rgba(112, 150, 205, 0.10);
        border-radius: 8px;
        overflow: hidden;

        .list-header {
            display: grid;
            grid-template-columns: 1.35fr 0.62fr 0.72fr 1fr;
            background: rgba(79, 134, 255, 0.08);
            padding: 8px 0;
            font-size: 13px;
            color: #9fdedb;

            span {
                text-align: center;
            }
        }

        .list-body {
            flex: 1;
            overflow-y: auto;
            
            .list-item {
                display: grid;
                grid-template-columns: 1.35fr 0.62fr 0.72fr 1fr;
                padding: 8px 0;
                font-size: 13px;
                border-bottom: 1px solid rgba(112, 150, 205, 0.08);

                &:nth-child(even) {
                    background: rgba(255, 255, 255, 0.018);
                }

                &:hover {
                    background: rgba(79, 134, 255, 0.08);
                }

                span {
                    text-align: center;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }

                .level {
                    font-weight: bold;
                    &.level-1 { color: #e86c5b; }
                    &.level-2 { color: #d99051; }
                    &.level-3 { color: #d8a74f; }
                    &.level-4 { color: #7aa7ff; }
                    &.level-default { color: #8aa5c9; }
                }

                .point {
                    color: #eef4ff;
                    justify-content: flex-start;
                    padding-left: 8px;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }

                .time {
                    color: #9cacc2;
                }

                .probability {
                    color: #f1bd62;
                    font-variant-numeric: tabular-nums;
                }
            }

            .empty-state {
                height: 100%;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #6f829c;
                font-size: 13px;
            }
        }
    }
}
</style>
