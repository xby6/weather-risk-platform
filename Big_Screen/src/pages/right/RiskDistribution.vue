<template>
    <div class="risk-distribution">
        <div class="component-header flex-l">
            <div class="header-left flex-c">
                <span class="header-title">城市预测风险分布<span class="sub-title">(记录数)</span></span>
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
import { apiGetRiskDistribution } from '@/api/index';
import { screenStore } from '@/store/screenData';

const chartOptions = ref({});
let timer: number | undefined;

const formatCityAxisLabel = (value: string) => {
    const text = String(value || '').replace(/\u5e02$/, '');
    return text.length > 4 ? `${text.slice(0, 4)}...` : text;
};

const updateChart = (data: any) => {
    chartOptions.value = {
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'shadow'
            }
        },
        legend: {
            data: ['高', '较高', '一般', '低'],
            textStyle: { color: '#9cacc2' },
            top: 0,
            itemWidth: 10,
            itemHeight: 10,
            icon: 'rect'
        },
        grid: {
            left: '5%',
            right: '4%',
            bottom: '14%',
            top: '25%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: data.cities,
            axisLine: { lineStyle: { color: 'rgba(127,190,255,0.20)' } },
            axisLabel: {
                color: '#9cacc2',
                interval: 0,
                fontSize: 10,
                rotate: 35,
                margin: 12,
                hideOverlap: true,
                formatter: formatCityAxisLabel
            },
            axisTick: { show: false }
        },
        yAxis: {
            type: 'value',
            splitLine: { lineStyle: { color: 'rgba(127,190,255,0.10)', type: 'dashed' } },
            axisLabel: { color: '#9cacc2' }
        },
        series: [
            {
                name: '高',
                type: 'bar',
                barWidth: 8,
                itemStyle: { color: '#e86c5b', borderRadius: [5, 5, 0, 0] },
                data: data.level1
            },
            {
                name: '较高',
                type: 'bar',
                barWidth: 8,
                itemStyle: { color: '#d99051', borderRadius: [5, 5, 0, 0] },
                data: data.level2
            },
            {
                name: '一般',
                type: 'bar',
                barWidth: 8,
                itemStyle: { color: '#d8a74f', borderRadius: [5, 5, 0, 0] },
                data: data.level3
            },
            {
                name: '低',
                type: 'bar',
                barWidth: 8,
                itemStyle: { color: '#7aa7ff', borderRadius: [5, 5, 0, 0] },
                data: data.level4
            }
        ]
    };
};

const fetchData = async () => {
    try {
        const res = await apiGetRiskDistribution();
        if (res.code === 200) {
            updateChart(res.data);
        }
    } catch (error) {
        console.error('Failed to fetch risk distribution:', error);
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

.risk-distribution {
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
                .sub-title {
                    font-size: 12px;
                    color: rgba(255,255,255,0.6);
                    font-weight: normal;
                    margin-left: 5px;
                }
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
