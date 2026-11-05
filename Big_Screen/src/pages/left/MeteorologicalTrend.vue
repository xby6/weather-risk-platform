<template>
    <div class="meteorological-trend">
        <div class="component-header flex-l">
            <div class="header-left flex-c">
                <i class="iconfont icon-monitoring" />
            </div>
            <div class="header-right flex-l">
                <span class="header-title">气象变化趋势</span>
                <dv-decoration-3 class="dv-dec-3" />
            </div>
        </div>
        <div class="chart-container">
            <mEcharts :options="chartOptions" height="100%" width="100%"></mEcharts>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import { apiGetWeatherTrend } from '@/api/index';
import { screenStore } from '@/store/screenData';

const chartOptions = ref({
    tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' }
    },
    legend: {
        data: ['温度(℃)', '湿度(%)', '风速(m/s)'],
        textStyle: { color: '#9cacc2', fontSize: 10 },
        itemWidth: 10,
        itemGap: 10,
        itemHeight: 8,
        top: 0
    },
    grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        top: '48px',
        containLabel: true
    },
    xAxis: {
        type: 'category',
        boundaryGap: false,
        data: [] as string[],
        axisLabel: { color: '#9cacc2' },
        axisLine: { lineStyle: { color: 'rgba(112, 150, 205, 0.22)' } }
    },
    yAxis: [
        {
            type: 'value',
            name: '温度/风速',
            nameGap: 10,
            nameTextStyle: { color: '#9cacc2', fontSize: 10 },
            axisLabel: { color: '#9cacc2' },
            splitLine: { lineStyle: { color: 'rgba(112, 150, 205, 0.10)', type: 'dashed' } }
        },
        {
            type: 'value',
            name: '湿度(%)',
            nameGap: 10,
            nameTextStyle: { color: '#9cacc2', fontSize: 10 },
            axisLabel: { color: '#9cacc2' },
            splitLine: { show: false }
        }
    ],
    series: [
        {
            name: '温度(℃)',
            type: 'line',
            smooth: true,
            symbol: 'none',
            lineStyle: { width: 2 },
            itemStyle: { color: '#d99051' },
            areaStyle: {
                color: {
                    type: 'linear',
                    x: 0, y: 0, x2: 0, y2: 1,
                    colorStops: [{ offset: 0, color: 'rgba(255, 179, 138, 0.26)' }, { offset: 1, color: 'rgba(255, 179, 138, 0)' }]
                }
            },
            data: [] as number[]
        },
        {
            name: '湿度(%)',
            type: 'line',
            yAxisIndex: 1,
            smooth: true,
            symbol: 'none',
            lineStyle: { width: 2 },
            itemStyle: { color: '#7aa7ff' },
            areaStyle: {
                color: {
                    type: 'linear',
                    x: 0, y: 0, x2: 0, y2: 1,
                    colorStops: [{ offset: 0, color: 'rgba(95, 183, 255, 0.24)' }, { offset: 1, color: 'rgba(95, 183, 255, 0)' }]
                }
            },
            data: [] as number[]
        },
        {
            name: '风速(m/s)',
            type: 'line',
            smooth: true,
            symbol: 'none',
            lineStyle: { width: 2 },
            itemStyle: { color: '#8aa5c9' },
            data: [] as number[]
        }
    ]
});

let timer: number | null = null;

const fetchData = async () => {
    try {
        const res = await apiGetWeatherTrend();
        if (res.code === 200) {
            const data = res.data;
            chartOptions.value.xAxis.data = data.times;
            chartOptions.value.series[0].data = data.temperature;
            chartOptions.value.series[1].data = data.humidity;
            chartOptions.value.series[2].data = data.windSpeed;
            // Trigger reactivity by re-assigning the whole object or deep reactive properties are usually picked up by mEcharts watcher if it's set up deep
            chartOptions.value = { ...chartOptions.value };
        }
    } catch (error) {
        console.error('Failed to fetch weather trend data', error);
    }
};

watch(() => screenStore.refreshKey, fetchData);

onMounted(() => {
    fetchData();
    timer = window.setInterval(fetchData, 10000); // 实时更新
});

onUnmounted(() => {
    if (timer) {
        clearInterval(timer);
    }
});
</script>

<style lang="scss" scoped>
@import '@/assets/scss/common/variables.scss';

.meteorological-trend {
    height: 100%;
    background-color: $theme-sub-color;
    border-radius: 10px;
    padding: 10px;
    box-sizing: border-box;

    .component-header {
        height: $chart-header-height;
        margin-bottom: 5px;

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

    .chart-container {
        height: calc(100% - 35px);
        width: 100%;
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
