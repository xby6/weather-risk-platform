<template>
    <div class="warning-trends">
        <div class="component-header flex-l">
            <div class="header-left flex-c">
                <span class="header-title">逐小时故障概率趋势</span>
            </div>
            <div class="header-right flex-r">
                <span class="more-link">更多 ></span>
            </div>
        </div>
        <div class="chart-container">
            <mEcharts :options="chartOptions" height="100%" width="100%"></mEcharts>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import { apiGetWarningTrends } from '@/api/index';
import { screenStore } from '@/store/screenData';

const chartOptions = ref({});
let timer: number | undefined;
const colors = ['#6f9dff', '#56c8c0', '#f1bd62', '#e88d5b', '#c68cff', '#72c98a'];

const updateChart = (data: any) => {
    chartOptions.value = {
        tooltip: {
            trigger: 'axis'
        },
        legend: {
            data: (data.series || []).map((item: any) => item.name),
            textStyle: { color: '#9cacc2' },
            top: 0,
            itemWidth: 14,
            itemHeight: 8,
            type: 'scroll'
        },
        grid: {
            left: '5%',
            right: '4%',
            bottom: '5%',
            top: '25%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: (data.hours || []).map((hour: number) => `${hour}h`),
            axisLine: { lineStyle: { color: 'rgba(127,190,255,0.20)' } },
            axisLabel: { color: '#9cacc2', fontSize: 10 },
            axisTick: { show: false }
        },
        yAxis: {
            type: 'value',
            min: 0,
            max: 100,
            splitLine: { lineStyle: { color: 'rgba(127,190,255,0.10)', type: 'solid' } },
            axisLabel: { color: '#9cacc2', formatter: '{value}%' }
        },
        series: (data.series || []).map((item: any, index: number) => ({
                name: item.name,
                type: 'line',
                smooth: true,
                symbol: 'circle',
                symbolSize: 3,
                itemStyle: { color: colors[index % colors.length] },
                lineStyle: { width: 2, color: colors[index % colors.length] },
                data: item.data
            }))
    };
};

const fetchData = async () => {
    try {
        const res = await apiGetWarningTrends();
        if (res.code === 200) {
            updateChart(res.data);
        }
    } catch (error) {
        console.error('Failed to fetch warning trends:', error);
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

<style scoped lang="scss">
@import '@/assets/scss/common/variables.scss';

.warning-trends {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    padding: 10px;
    box-sizing: border-box;
    background-color: $theme-sub-color;
    border-radius: 10px;

    .component-header {
        height: $chart-header-height;
        margin-bottom: 10px;
        justify-content: space-between;
        border-bottom: 1px solid rgba(86, 138, 234, 0.2);

        .header-left {
            .header-title {
                color: #fff;
                font-size: 16px;
                font-weight: bold;
            }
        }

        .header-right {
            .more-link {
                color: rgba(255,255,255,0.6);
                font-size: 12px;
                cursor: pointer;
                &:hover {
                    color: #fff;
                }
            }
        }
    }

    .chart-container {
        flex: 1;
        width: 100%;
        min-height: 200px;
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

.flex-r {
    display: flex;
    align-items: center;
    justify-content: flex-end;
}
</style>
