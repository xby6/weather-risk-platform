<template>
    <div class="screen-container" :data-map-style="screenStore.mapView">
        <div class="screen-content" ref="screenRef">
            <div v-if="loading" class="mask flex-c">
                <dv-loading>
                    <span class="loading-title">加载中...</span>
                </dv-loading>
            </div>
            
            <div class="header-section">
                <ScreenHeader></ScreenHeader>
            </div>
            
            <div class="main-content">
                <!-- Left Column -->
                <div class="left-col">
                    <section class="screen-panel panel-box realtime-panel">
                        <RealtimeMonitor />
                    </section>
                    <section class="screen-panel panel-box trend-panel">
                        <MeteorologicalTrend />
                    </section>
                    <section class="screen-panel panel-box ranking-panel">
                        <StationRanking />
                    </section>
                    <section v-if="screenStore.mapView !== 'terrain'" class="screen-panel panel-box warning-panel">
                        <WarningStats />
                    </section>
                </div>
                
                <!-- Center Column -->
                <div class="center-col">
                    <div class="top-stats">
                        <TopStats :compact="screenStore.mapView === 'terrain'" />
                    </div>
                    <div class="map-container">
                        <MapCenter />
                    </div>
                    <div class="bottom-row" :class="{ 'aux-collapsed': screenStore.mapView === 'terrain' && !terrainAuxOpen }">
                        <section class="screen-panel bottom-panel task-panel">
                            <TaskStatus />
                        </section>
                        <section class="screen-panel bottom-panel overview-panel">
                            <SystemOverview />
                        </section>
                        <section class="screen-panel bottom-panel logs-panel">
                            <LatestLogs />
                        </section>
                    </div>
                    <div v-if="screenStore.mapView === 'terrain'" class="geographic-footer">
                        <span>地形与气象空间监测</span>
                        <button type="button" :aria-expanded="terrainAuxOpen" @click="terrainAuxOpen = !terrainAuxOpen">{{ terrainAuxOpen ? '收起运行记录' : '运行记录与服务状态' }}</button>
                    </div>
                </div>
                
                <!-- Right Column -->
                <div class="right-col">
                    <section class="screen-panel panel-box current-warning-panel">
                        <CurrentWarnings />
                    </section>
                    <section class="screen-panel panel-box risk-panel">
                        <RiskDistribution />
                    </section>
                    <section class="screen-panel panel-box warning-trend-panel">
                        <WarningTrends />
                    </section>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import windowResize from '@/utils/resize';
import { onMounted, onUnmounted, ref } from 'vue';
import { fetchScreenAllData, screenStore } from '@/store/screenData'
import ScreenHeader from '@/pages/screen-header/ScreenHeader.vue';

// Left Components
import RealtimeMonitor from '@/pages/left/RealtimeMonitor.vue';
import MeteorologicalTrend from '@/pages/left/MeteorologicalTrend.vue';
import StationRanking from '@/pages/left/StationRanking.vue';
import WarningStats from '@/pages/left/WarningStats.vue';

// Center Components
import TopStats from '@/pages/center/TopStats.vue';
import MapCenter from '@/pages/center/MapCenter.vue';
import TaskStatus from '@/pages/center/TaskStatus.vue';
import SystemOverview from '@/pages/center/SystemOverview.vue';
import LatestLogs from '@/pages/center/LatestLogs.vue';

// Right Components
import CurrentWarnings from '@/pages/right/CurrentWarnings.vue';
import RiskDistribution from '@/pages/right/RiskDistribution.vue';
import WarningTrends from '@/pages/right/WarningTrends.vue';

const { screenRef, calcRate, windowDraw, unWindowDraw } = windowResize()
const loading = ref(true);
const terrainAuxOpen = ref(false);

onMounted(() => {
    fetchScreenAllData()
    windowDraw()
    calcRate()
    setTimeout(() => {
        loading.value = false;
    }, 1000);
})

onUnmounted(() => {
    unWindowDraw();
})
</script>

<style lang="scss" scoped>
@import '@/assets/scss/common/variables.scss';

.screen-container {
    width: 100vw;
    height: 100vh;
    position: relative;
    background:
        radial-gradient(circle at 50% 34%, rgba(47, 91, 168, 0.18), transparent 34%),
        radial-gradient(circle at 12% 18%, rgba(216, 167, 79, 0.08), transparent 22%),
        linear-gradient(180deg, #080f1d 0%, #050b14 48%, #02050b 100%);
    display: block;
    overflow: hidden;

    .mask {
        position: fixed;
        top: 0;
        left: 0;
        bottom: 0;
        right: 0;
        background-color: #050a13;
        z-index: 9999;
    }

    .screen-content {
        width: 1920px;
        height: 1080px;
        box-sizing: border-box;
        padding: 18px 22px 20px;
        position: absolute;
        left: 0;
        top: 0;
        background:
            linear-gradient(180deg, rgba(5, 12, 23, 0.84), rgba(3, 7, 14, 0.96)),
            url('@/assets/home_bg.png');
        background-size: cover;
        background-position: center;
        display: flex;
        flex-direction: column;
        overflow: hidden;

        &::before {
            content: "";
            position: absolute;
            inset: 0;
            pointer-events: none;
            background:
                linear-gradient(rgba(112, 150, 205, 0.026) 1px, transparent 1px),
                linear-gradient(90deg, rgba(112, 150, 205, 0.026) 1px, transparent 1px);
            background-size: 46px 46px;
            mask-image: radial-gradient(circle at center, #000 0%, transparent 75%);
        }

        &::after {
            content: "";
            position: absolute;
            inset: 0;
            pointer-events: none;
            background:
                radial-gradient(circle at 50% 45%, rgba(79, 134, 255, 0.13), transparent 38%),
                linear-gradient(90deg, rgba(0, 0, 0, 0.18), transparent 18%, transparent 82%, rgba(0, 0, 0, 0.18));
        }

        > * {
            position: relative;
            z-index: 1;
        }

        .loading-title {
            font-size: 20px;
            color: #fff;
            margin-top: 10px;
        }

        .header-section {
            height: 66px;
            width: 100%;
            margin-bottom: 16px;
        }

        .main-content {
            flex: 1;
            display: grid;
            grid-template-columns: 340px minmax(0, 1fr) 340px;
            gap: 18px;
            min-height: 0;
            
            .left-col {
                display: grid;
                grid-template-rows: 1.02fr 1.08fr 1.02fr 0.88fr;
                gap: 14px;
                min-height: 0;
                
                .panel-box {
                    min-height: 0;
                }
            }
            
            .center-col {
                display: flex;
                flex-direction: column;
                gap: 14px;
                min-width: 0;
                min-height: 0;
                
                .top-stats {
                    height: 82px;
                }
                
                .map-container {
                    flex: 1;
                    position: relative;
                    min-height: 0;
                }
                
                .bottom-row {
                    height: 180px;
                    display: grid;
                    grid-template-columns: 1.4fr 0.8fr 1fr;
                    gap: 14px;
                    
                    .bottom-panel {
                        min-width: 0;
                    }
                }
            }
            
            .right-col {
                display: grid;
                grid-template-rows: 1.1fr 1fr 1fr;
                gap: 14px;
                min-height: 0;
                
                .panel-box {
                    min-height: 0;
                }
            }
        }
    }
}

:deep(.screen-panel > *) {
    position: relative;
    z-index: 1;
}

:deep(.screen-panel .realtime-monitor),
:deep(.screen-panel .meteorological-trend),
:deep(.screen-panel .station-ranking),
:deep(.screen-panel .warning-stats),
:deep(.screen-panel .current-warnings),
:deep(.screen-panel .risk-distribution),
:deep(.screen-panel .warning-trends),
:deep(.screen-panel .task-status-container),
:deep(.screen-panel .system-overview-container),
:deep(.screen-panel .latest-logs-container) {
    background: transparent !important;
    border-radius: 0 !important;
    height: 100%;
    padding: 14px !important;
}

:deep(.screen-panel .component-header),
:deep(.screen-panel .panel-title),
:deep(.screen-panel .current-warnings .header) {
    height: 34px;
    margin-bottom: 10px !important;
    padding: 0 0 0 10px !important;
    border-left: 3px solid #6f9dff !important;
    border-bottom: 1px solid rgba(112, 150, 205, 0.15) !important;
    color: #eef4ff !important;
    font-size: 15px !important;
    font-weight: 700 !important;
    line-height: 32px;
}

:deep(.screen-panel .component-header .header-left) {
    width: 26px !important;
}

:deep(.screen-panel .risk-distribution .component-header .header-left),
:deep(.screen-panel .warning-trends .component-header .header-left) {
    width: auto !important;
    flex: 1;
    justify-content: flex-start !important;
}

:deep(.screen-panel .component-header .header-left i) {
    color: #6f9dff !important;
    font-size: 16px !important;
}

:deep(.screen-panel .component-header .header-title),
:deep(.screen-panel .current-warnings .title) {
    color: #eef4ff !important;
    font-size: 15px !important;
    font-weight: 700 !important;
}

:deep(.screen-panel .component-header .dv-dec-3) {
    opacity: 0.44;
    width: 78px !important;
    height: 16px !important;
}

:deep(.screen-panel .more-link),
:deep(.screen-panel .sub-title) {
    color: rgba(220, 236, 255, 0.58) !important;
}

:deep(.screen-panel .chart-container) {
    height: calc(100% - 44px) !important;
}

.screen-container[data-map-style="terrain"] {
    background: #0b100e;
    .screen-content { background: radial-gradient(ellipse at 50% 40%, #253a2e55, transparent 60%), linear-gradient(180deg, #151d18, #080d0b); }
    .screen-content::after { background: radial-gradient(ellipse at center, #6b856011, transparent 60%); }
    :deep(.screen-panel) { border-color: #91a78330; background: linear-gradient(135deg, #25332966, #101b1566); }
    :deep(.screen-panel .component-header), :deep(.screen-panel .panel-title), :deep(.screen-panel .current-warnings .header) { border-left-color: #a3ba91 !important; border-bottom-color: #91a78324 !important; }
    :deep(.title-text) { color: #e1e9dc !important; text-shadow: 0 0 20px #8dab7160 !important; }
}

.screen-container:not([data-map-style="flat"]) {
    .screen-content { background: radial-gradient(ellipse at 50% 58%, #14274350, transparent 64%), linear-gradient(180deg, #03070d, #040911); }
    .screen-content::before { opacity: .25; }
    :deep(.screen-panel) { border-radius: 2px; border: 1px solid #5b84ac3a; background: linear-gradient(110deg, #0b1522b3, #0b12207a); box-shadow: none; }
    :deep(.top-stats-container .stat-item) { background: transparent; border: 0; border-bottom: 1px solid #6493bd35; border-radius: 0; box-shadow: none; }
    :deep(.top-stats-container .stat-item::before) { width: 2px; opacity: .4; }
    :deep(.screen-panel .component-header), :deep(.screen-panel .panel-title), :deep(.screen-panel .current-warnings .header) { height: 30px; font-size: 14px !important; border-left-width: 2px !important; line-height: 28px; }
    :deep(.screen-panel .chart-container) { height: calc(100% - 40px) !important; }
    :deep(.screen-header) { background: transparent; border-radius: 0; border-color: #6481ac2b; box-shadow: none; }
}
.screen-container[data-map-style="terrain"] {
    .screen-content { background: radial-gradient(ellipse at 50% 50%, #29332b50, transparent 68%), linear-gradient(180deg, #0a0e0d, #0c120f); }
    :deep(.screen-panel) { border-color: #8ea98b32; background: linear-gradient(110deg, #1b241e80, #17221b33); }
}

/* Command view: fixed HUD panels frame a floating, low-angle map platform. */
.screen-container[data-map-style="blue"] {
    .screen-content .main-content { grid-template-columns: 350px minmax(0, 1fr) 350px; gap: 22px; }
    :deep(.screen-panel) { background: linear-gradient(120deg, #0c1729c9, #07101e80); border-color: #497abd65; border-top-color: #659bd3b3; clip-path: polygon(0 0, calc(100% - 16px) 0, 100% 16px, 100% 100%, 0 100%); }
    :deep(.screen-panel .panel-title), :deep(.screen-panel .component-header), :deep(.screen-panel .current-warnings .header) { color: #d5e9ff !important; border-left-color: #6d9df6 !important; }
}

/* Geographic view has a separate grid: trends on the left, regional comparison
   and point table on the right, full-height map and optional operational drawer. */
.screen-container[data-map-style="terrain"] {
    .screen-content { background: radial-gradient(ellipse at 50% 55%, #343c3470, transparent 60%), #151a18; }
    .screen-content::before, .screen-content::after { display: none; }
    .screen-content .header-section { height: 54px; margin-bottom: 8px; }
    .screen-content .main-content {
        position: relative; grid-template-columns: 290px minmax(0, 1fr) 290px;
        grid-template-rows: 58px repeat(3, minmax(0, 1fr)) 36px; gap: 14px 26px;
        grid-template-areas: ". metrics ." "trend map risk" "forecast map warnings" "monitor map ranking" ". footer .";
    }
    .screen-content .main-content .left-col,
    .screen-content .main-content .right-col,
    .screen-content .main-content .center-col { display: contents; }
    .top-stats { grid-area: metrics; height: auto !important; width: 520px; justify-self: center; z-index: 2; }
    .map-container { grid-area: map; height: 100%; min-height: 0; }
    .realtime-panel { grid-area: monitor; }
    .trend-panel { grid-area: trend; }
    .ranking-panel { grid-area: ranking; }
    .warning-panel { display: none; }
    .risk-panel { grid-area: risk; }
    .current-warning-panel { grid-area: warnings; }
    .warning-trend-panel { grid-area: forecast; }
    .screen-content .main-content .bottom-row {
        position: absolute; left: 318px; right: 318px; bottom: 48px; height: 220px;
        display: grid; z-index: 15; padding: 12px; background: #141c18f5;
        border: 1px solid #84988855; box-shadow: 0 -12px 50px #0008; box-sizing: border-box;
    }
    .screen-content .main-content .bottom-row.aux-collapsed { display: none; }
    :deep(.screen-panel) { position: relative; z-index: 2; border: 0; border-top: 1px solid #83988c38; background: linear-gradient(90deg, #1f29212b, transparent); box-shadow: none; }
    :deep(.screen-panel .component-header), :deep(.screen-panel .panel-title), :deep(.screen-panel .current-warnings .header) {
        border: 0 !important; padding-left: 0 !important; color: #edf0e8 !important; font-size: 14px !important;
    }
    :deep(.screen-panel .component-header .dv-dec-3),
    :deep(.screen-panel .component-header .header-left i), :deep(.screen-panel .more-link) { display: none; }
    :deep(.screen-panel .component-header .header-left:has(i)) { display: none; }
    :deep(.screen-panel .current-warnings .warning-table-header),
    :deep(.screen-panel .station-ranking .ranking-header) { background: #52625318; }
    :deep(.screen-panel .component-header .header-title) { color: #e5eadd !important; }
    :deep(.station-ranking .component-header) { height: 52px; flex-direction: column; align-items: stretch; gap: 3px; padding-top: 4px !important; }
    :deep(.station-ranking .title-wrap i) { display: none; }
    :deep(.station-ranking .ranking-tabs) { justify-content: flex-start; flex: none; }
    :deep(.station-ranking .ranking-tabs .tab-item) { height: 19px; padding: 0 7px; border-radius: 3px; font-size: 10px; }
    :deep(.station-ranking .ranking-header), :deep(.station-ranking .ranking-row) { grid-template-columns: 34px minmax(0, 1fr) 62px 38px; column-gap: 4px; padding-left: 4px; padding-right: 4px; font-size: 10px; }
    :deep(.station-ranking .rank-num) { color: #a0b99b; }
}
.geographic-footer { grid-area: footer; position: relative; z-index: 3; display: flex; gap: 28px; justify-content: center; align-items: center; color: #8d9b8e; font-size: 11px; letter-spacing: 1px; }
.geographic-footer button { cursor: pointer; background: transparent; border: 1px solid #89988c44; border-radius: 20px; padding: 6px 14px; color: #c5cfc0; font-size: 11px; }
</style>
