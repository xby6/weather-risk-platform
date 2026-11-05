<template>
    <div class="realtime-monitor">
        <div class="component-header flex-l">
            <div class="header-left flex-c">
                <i class="iconfont icon-monitoring" />
            </div>
            <div class="header-right flex-l">
                <span class="header-title">气象实时监控</span>
                <dv-decoration-3 class="dv-dec-3" />
            </div>
        </div>
        <div class="monitor-content">
            <div class="data-item flex-l" v-for="(item, index) in monitorData" :key="index">
                <div class="item-icon flex-c">
                    <i class="iconfont" :class="item.icon" :style="{ color: item.color }"></i>
                </div>
                <div class="item-info flex-c">
                    <div class="info-value">
                        <span class="value-text">{{ item.value }}</span>
                        <span class="unit-text">{{ item.unit }}</span>
                    </div>
                    <div class="info-label">{{ item.label }}</div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import { apiGetWeatherMonitor } from '@/api/index';
import { screenStore } from '@/store/screenData';

const monitorData = ref([
    { label: '温度', value: '-', unit: '℃', icon: 'icon-diagnose', color: '#d99051' },
    { label: '湿度', value: '-', unit: '%', icon: 'icon-clouddownload', color: '#7aa7ff' },
    { label: '风速', value: '-', unit: 'm/s', icon: 'icon-monitoring', color: '#8aa5c9' },
    { label: '风向', value: '-', unit: '', icon: 'icon-tongji4', color: '#7aa7ff' },
    { label: '降雨量', value: '-', unit: 'mm', icon: 'icon-cloudupload', color: '#6f9dff' },
    { label: '气压', value: '-', unit: 'hPa', icon: 'icon-diagnose', color: '#d8a74f' }
]);

let timer: number | null = null;

const fetchData = async () => {
    try {
        const res = await apiGetWeatherMonitor();
        if (res.code === 200) {
            const data = res.data;
            monitorData.value[0].value = data.temperature ?? '-';
            monitorData.value[1].value = data.humidity ?? '-';
            monitorData.value[2].value = data.windSpeed ?? '-';
            monitorData.value[3].value = data.windDirection || '-';
            monitorData.value[4].value = data.rainfall ?? '-';
            monitorData.value[5].value = data.pressure ?? '-';
        }
    } catch (error) {
        console.error('Failed to fetch weather monitor data', error);
    }
};

watch(() => screenStore.refreshKey, fetchData);

onMounted(() => {
    fetchData();
    timer = window.setInterval(fetchData, 5000); // 实时更新，每5秒刷新一次
});

onUnmounted(() => {
    if (timer) {
        clearInterval(timer);
    }
});
</script>

<style lang="scss" scoped>
@import '@/assets/scss/common/variables.scss';

.realtime-monitor {
    height: 100%;
    background-color: $theme-sub-color;
    border-radius: 10px;
    padding: 10px;
    box-sizing: border-box;

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

    .monitor-content {
        height: calc(100% - 44px);
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        grid-template-rows: repeat(3, minmax(0, 1fr));
        column-gap: 10px;
        row-gap: 6px;

        .data-item {
            min-width: 0;
            min-height: 0;
            
            .item-icon {
                width: 34px;
                height: 34px;
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 10px;
                margin-right: 9px;
                flex: 0 0 auto;
                i {
                    font-size: 18px;
                }
            }

            .item-info {
                align-items: flex-start;
                justify-content: center;
                flex-direction: column;

                .info-value {
                    .value-text {
                        color: #fff;
                        font-size: 18px;
                        font-weight: bold;
                        font-family: 'Electronic', sans-serif;
                        line-height: 1;
                    }
                    .unit-text {
                        color: rgba(220, 236, 255, 0.58);
                        font-size: 12px;
                        margin-left: 4px;
                    }
                }

                .info-label {
                    color: rgba(220, 236, 255, 0.66);
                    font-size: 12px;
                    margin-top: 3px;
                    line-height: 1.1;
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
