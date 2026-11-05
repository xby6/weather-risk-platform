<template>
    <div class="warning-stats">
        <div class="component-header flex-l">
            <div class="header-left flex-c">
                <i class="iconfont icon-diagnose" />
            </div>
            <div class="header-right flex-l">
                <span class="header-title">预警级别统计</span>
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
import { apiGetWarningLevels } from '@/api/index';
import { screenStore } from '@/store/screenData';

const chartOptions = ref({
    color: ['#e86c5b', '#d99051', '#d8a74f', '#7aa7ff', '#8aa5c9'],
    tooltip: {
        trigger: 'item',
        formatter: '{b}: {c} ({d}%)'
    },
    legend: {
        orient: 'vertical',
        right: '5%',
        top: 'center',
        textStyle: { color: '#9cacc2' },
        itemWidth: 10,
        itemHeight: 10,
        icon: 'circle'
    },
    series: [
        {
            name: '预警级别',
            type: 'pie',
            radius: ['44%', '70%'],
            center: ['38%', '52%'],
            avoidLabelOverlap: false,
            itemStyle: {
                borderRadius: 5,
                borderColor: '#07121f',
                borderWidth: 2
            },
            label: {
                show: false,
                position: 'center'
            },
            emphasis: {
                label: {
                    show: true,
                    fontSize: '14',
                    fontWeight: 'bold',
                    color: '#eef4ff'
                }
            },
            labelLine: {
                show: false
            },
            data: [] as { name: string; value: number }[]
        }
    ]
});

let timer: number | null = null;

const fetchData = async () => {
    try {
        const res = await apiGetWarningLevels();
        if (res.code === 200) {
            chartOptions.value.series[0].data = res.data.map((item: any) => ({
                name: item.name,
                value: item.value
            }));
            chartOptions.value = { ...chartOptions.value };
        }
    } catch (error) {
        console.error('Failed to fetch warning levels data', error);
    }
};

watch(() => screenStore.refreshKey, fetchData);

onMounted(() => {
    fetchData();
    timer = window.setInterval(fetchData, 10000); // 10秒更新一次
});

onUnmounted(() => {
    if (timer) {
        clearInterval(timer);
    }
});
</script>

<style lang="scss" scoped>
@import '@/assets/scss/common/variables.scss';

.warning-stats {
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
