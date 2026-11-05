<template>
  <div class="map-center" :data-map-style="screenStore.mapView">
    <div class="map-toolbar">
      <div>
        <span class="map-kicker">{{ screenStore.mapView === 'terrain' ? 'GEOGRAPHIC MONITOR' : 'POWER RISK COMMAND' }}</span>
        <strong>{{ selectedCity ? `${selectedCity}气象态势` : screenStore.mapView === 'terrain' ? '辽宁省 · 气象地理分布' : '全域气象风险态势' }}</strong>
        <span class="map-tip">{{ hoverName || (screenStore.mapView === 'flat' ? '滚轮缩放，点击城市聚焦' : '拖动旋转 · 滚轮缩放 · 点击城市联动') }}</span>
      </div>
      <div class="toolbar-actions">
        <div class="view-switch" role="group" aria-label="地图场景">
          <button v-for="view in mapViews" :key="view.value" type="button" :aria-pressed="screenStore.mapView === view.value"
            :class="{ active: screenStore.mapView === view.value }" @click="setMapView(view.value)">{{ view.label }}</button>
        </div>
        <button v-if="selectedCity" class="back-btn" type="button" @click="handleBack">返回全省</button>
        <button class="map-count" type="button" @click="pointMenuOpen = !pointMenuOpen">点位 {{ points.length }}</button>
      </div>
    </div>
    <v-chart
      v-if="screenStore.mapView === 'flat'"
      ref="chartRef"
      class="chart"
      :option="option"
      autoresize
      @click="handleMapClick"
      @mouseover="handleMapHover"
      @mouseout="handleMapOut"
    />
    <TerrainMap v-else ref="terrainRef" :geo-json="activeCityMap?.data || liaoningMap" :points="points" :mode="screenStore.mapView"
      :terrain-view="terrainView" :selected-point="selectedPoint" @region-select="handleRegionSelect" @point-select="handleThreePointSelect" />
    <div v-if="screenStore.mapView === 'terrain'" class="geographic-map-tools" role="group" aria-label="地形视角">
      <button type="button" :aria-pressed="terrainView === 'overhead'" @click="terrainView = 'overhead'">正射俯视</button>
      <button type="button" :aria-pressed="terrainView === 'oblique'" @click="terrainView = 'oblique'">倾斜地形</button>
    </div>
    <div v-if="screenStore.mapView === 'terrain'" class="elevation-legend" aria-label="高程着色图例">
      <span>高程晕渲 / m</span><i></i><div><span>0</span><span>800</span><span>1600</span></div>
    </div>
    <div class="map-caption">
      <div><span class="map-live-dot"></span>{{ selectedCity || '辽宁省' }} · {{ screenStore.mapView === 'terrain' ? '地形纹理视图' : screenStore.mapView === 'blue' ? '立体风险视图' : '平面点位视图' }}</div>
      <span v-if="screenStore.mapView !== 'flat'">公开高程晕渲 · 地形高度经视觉夸张</span>
      <a v-if="screenStore.mapView !== 'flat'" href="https://registry.opendata.aws/terrain-tiles/" target="_blank" rel="noopener noreferrer">地形数据 © Mapzen / USGS / NOAA</a>
      <span v-if="points.length > 300 && screenStore.mapView !== 'flat'">地图最多显示 300 个点，完整数据见点位菜单</span>
      <button v-if="screenStore.mapView !== 'flat'" type="button" @click="terrainRef?.resetView()">复位视角</button>
    </div>
    <div v-if="dataError" class="data-error" role="alert">{{ dataError }} <button type="button" @click="fetchData">重试</button></div>
    <div v-else-if="!hasData" class="empty-map">{{ selectedCity ? `${selectedCity}暂无点位数据` : '暂无预警点位数据' }}</div>
    <aside v-if="pointMenuOpen" class="point-menu-panel">
      <div class="point-menu-header">
        <div>
          <span>点位菜单</span>
          <strong>{{ pointMenuItems.length }} / {{ points.length }}</strong>
        </div>
        <button type="button" class="point-menu-close" @click="pointMenuOpen = false">×</button>
      </div>
      <input
        aria-label="搜索点位或区域"
        v-model.trim="pointSearch"
        class="point-search"
        type="text"
        placeholder="搜索点位/区域"
      />
      <div class="point-menu-list">
        <button
          v-for="item in pointMenuItems"
          :key="`${item.index}-${item.name}`"
          type="button"
          class="point-menu-item"
          :class="{ active: selectedPointIndex === item.index }"
          @click="selectPoint(item.point, item.index)"
        >
          <span class="point-menu-name">{{ item.name }}</span>
          <span class="point-menu-meta">{{ item.region }} · {{ item.time }}</span>
          <span class="point-menu-data">温度 {{ item.temperature }} · 风速 {{ item.windSpeed }}</span>
        </button>
        <div v-if="!pointMenuItems.length" class="point-menu-empty">暂无匹配点位</div>
      </div>
    </aside>
    <div v-if="selectedPoint" class="point-detail-panel">
      <div class="point-detail-header">
        <div>
          <span>点位详情</span>
          <strong>{{ selectedPoint.name || '气象点位' }}</strong>
        </div>
        <button type="button" class="point-detail-close" @click="selectedPoint = null">×</button>
      </div>
      <div class="point-detail-form">
        <div v-for="row in pointDetailRows" :key="row.label" class="point-detail-row">
          <span class="point-detail-label">{{ row.label }}</span>
          <span class="point-detail-value">{{ row.value }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import TerrainMap from '@/components/map/TerrainMap.vue';
import VChart from 'vue-echarts';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { EffectScatterChart, MapChart, ScatterChart } from 'echarts/charts';
import { GeoComponent, TooltipComponent, VisualMapComponent } from 'echarts/components';
import * as echarts from 'echarts/core';
import type { EChartsOption } from 'echarts';
import liaoningMap from '@/common/echart/map/liaoning.json';
import shenyangMap from '@/common/echart/map/liaoning-cities/210100-shenyang.json';
import dalianMap from '@/common/echart/map/liaoning-cities/210200-dalian.json';
import anshanMap from '@/common/echart/map/liaoning-cities/210300-anshan.json';
import fushunMap from '@/common/echart/map/liaoning-cities/210400-fushun.json';
import benxiMap from '@/common/echart/map/liaoning-cities/210500-benxi.json';
import dandongMap from '@/common/echart/map/liaoning-cities/210600-dandong.json';
import jinzhouMap from '@/common/echart/map/liaoning-cities/210700-jinzhou.json';
import yingkouMap from '@/common/echart/map/liaoning-cities/210800-yingkou.json';
import fuxinMap from '@/common/echart/map/liaoning-cities/210900-fuxin.json';
import liaoyangMap from '@/common/echart/map/liaoning-cities/211000-liaoyang.json';
import panjinMap from '@/common/echart/map/liaoning-cities/211100-panjin.json';
import tielingMap from '@/common/echart/map/liaoning-cities/211200-tieling.json';
import chaoyangMap from '@/common/echart/map/liaoning-cities/211300-chaoyang.json';
import huludaoMap from '@/common/echart/map/liaoning-cities/211400-huludao.json';
import { apiGetMapData } from '@/api';
import { clearSelectedCity, screenStore, setSelectedCity, setMapView, type MapView } from '@/store/screenData';

use([CanvasRenderer, MapChart, ScatterChart, EffectScatterChart, GeoComponent, TooltipComponent, VisualMapComponent]);
echarts.registerMap('liaoning', liaoningMap as any);

const provinceCenter: [number, number] = [122.5, 41.0];
const provinceZoom = 1.15;

const cityMaps: Record<string, { mapName: string; center: [number, number]; data: any }> = {
  沈阳市: { mapName: 'liaoning-city-210100', center: [123.429096, 41.796767], data: shenyangMap },
  大连市: { mapName: 'liaoning-city-210200', center: [121.618622, 38.91459], data: dalianMap },
  鞍山市: { mapName: 'liaoning-city-210300', center: [122.995632, 41.110626], data: anshanMap },
  抚顺市: { mapName: 'liaoning-city-210400', center: [123.957208, 41.880872], data: fushunMap },
  本溪市: { mapName: 'liaoning-city-210500', center: [123.766485, 41.294176], data: benxiMap },
  丹东市: { mapName: 'liaoning-city-210600', center: [124.383044, 40.124296], data: dandongMap },
  锦州市: { mapName: 'liaoning-city-210700', center: [121.135742, 41.119269], data: jinzhouMap },
  营口市: { mapName: 'liaoning-city-210800', center: [122.235151, 40.667432], data: yingkouMap },
  阜新市: { mapName: 'liaoning-city-210900', center: [121.670052, 42.022028], data: fuxinMap },
  辽阳市: { mapName: 'liaoning-city-211000', center: [123.18152, 41.269402], data: liaoyangMap },
  盘锦市: { mapName: 'liaoning-city-211100', center: [122.070714, 41.119997], data: panjinMap },
  铁岭市: { mapName: 'liaoning-city-211200', center: [123.844279, 42.290585], data: tielingMap },
  朝阳市: { mapName: 'liaoning-city-211300', center: [120.450372, 41.573734], data: chaoyangMap },
  葫芦岛市: { mapName: 'liaoning-city-211400', center: [120.856394, 40.755572], data: huludaoMap }
};

Object.values(cityMaps).forEach(city => {
  echarts.registerMap(city.mapName, city.data);
});

const chartRef = ref<InstanceType<typeof VChart> | null>(null);
const terrainRef = ref<InstanceType<typeof TerrainMap> | null>(null);
const terrainView = ref<'oblique' | 'overhead'>('oblique');
const mapViews: { value: MapView; label: string }[] = [
  { value: 'blue', label: '立体态势' }, { value: 'terrain', label: '地理监测' }, { value: 'flat', label: '经典平面' }
];
const dataError = ref('');
let fetchId = 0;
const points = ref<any[]>([]);
const selectedPoint = ref<any | null>(null);
const selectedPointIndex = ref<number | null>(null);
const pointSearch = ref('');
const hoverName = ref('');
const mapCenter = ref<[number, number]>(provinceCenter);
const mapZoom = ref(provinceZoom);
const selectedCity = computed(() => screenStore.selectedCity);
const activeCityMap = computed(() => selectedCity.value ? cityMaps[selectedCity.value] : null);
const activeMapName = computed(() => activeCityMap.value?.mapName || 'liaoning');
const isCityView = computed(() => Boolean(activeCityMap.value));
const hasData = computed(() => points.value.length > 0);
const pointMenuOpen = computed({
  get: () => screenStore.mapPointMenuOpen,
  set: (value: boolean) => {
    screenStore.mapPointMenuOpen = value;
  }
});
const shouldShiftMap = computed(() => pointMenuOpen.value);
const geoLayout = computed(() => {
  if (isCityView.value) {
    return {
      zoom: shouldShiftMap.value ? 1.06 : 1.12,
      layoutCenter: [shouldShiftMap.value ? '62%' : '50%', '55%'],
      layoutSize: shouldShiftMap.value ? '94%' : '106%'
    };
  }

  return {
    center: mapCenter.value,
    zoom: shouldShiftMap.value ? mapZoom.value * 0.94 : mapZoom.value,
    layoutCenter: [shouldShiftMap.value ? '62%' : '50%', '54%'],
    layoutSize: shouldShiftMap.value ? '90%' : '100%'
  };
});

const formatPointValue = (value: any, unit = '') => {
  if (value === undefined || value === null || value === '') return '-';
  return `${value}${unit}`;
};

const getPointName = (point: any) => formatPointValue(point?.name || point?.station || point?.station_or_line || point?.line_code);
const getPointRegion = (point: any) => formatPointValue(point?.region || point?.city || point?.area);
const getPointTime = (point: any) => formatPointValue(point?.time || point?.create_time || point?.publish_time);

const pointMenuItems = computed(() => {
  const keyword = pointSearch.value.trim().toLowerCase();
  return points.value
    .map((point, index) => {
      const name = getPointName(point);
      const region = getPointRegion(point);
      const time = getPointTime(point);
      const temperature = formatPointValue(point?.temperature, '℃');
      const windSpeed = formatPointValue(point?.wind_speed ?? point?.windSpeed, 'm/s');
      return { point, index, name, region, time, temperature, windSpeed };
    })
    .filter(item => {
      if (!keyword) return true;
      return [item.name, item.region, item.time]
        .some(value => String(value || '').toLowerCase().includes(keyword));
    });
});

const pointDetailRows = computed(() => {
  const data = selectedPoint.value || {};
  const coords = Array.isArray(data.value) && data.value.length >= 2
    ? `${Number(data.value[0]).toFixed(4)}, ${Number(data.value[1]).toFixed(4)}`
    : '-';
  const riskScore = Array.isArray(data.value) && data.value.length >= 3 ? data.value[2] : data.risk_score;

  return [
    { label: '点位名称', value: formatPointValue(data.name || data.station || data.station_or_line) },
    { label: '所属区域', value: formatPointValue(data.region || data.city || data.area) },
    { label: '观测时间', value: formatPointValue(data.time || data.create_time || data.publish_time) },
    { label: '经纬度', value: coords },
    { label: '温度', value: formatPointValue(data.temperature, '℃') },
    { label: '湿度', value: formatPointValue(data.humidity, '%') },
    { label: '风速', value: formatPointValue(data.wind_speed ?? data.windSpeed, 'm/s') },
    { label: '风向', value: formatPointValue(data.wind_direction ?? data.windDirection) },
    { label: '降水量', value: formatPointValue(data.precipitation ?? data.rain, 'mm') },
    { label: '气压', value: formatPointValue(data.pressure, 'hPa') },
    { label: '风险等级', value: formatPointValue(data.risk_level || data.warning_level || data.level) },
    { label: '风险值', value: formatPointValue(riskScore) }
  ];
});

const showPointOnChart = async (index: number) => {
  if (index < 0) return;
  await nextTick();
  const chart = (chartRef.value as any)?.chart || (chartRef.value as any)?.getEchartsInstance?.();
  if (!chart) return;
  chart.dispatchAction({ type: 'downplay', seriesIndex: 0 });
  chart.dispatchAction({ type: 'highlight', seriesIndex: 0, dataIndex: index });
  chart.dispatchAction({ type: 'showTip', seriesIndex: 0, dataIndex: index });
};

const selectPoint = (point: any, index: number) => {
  if (!point) return;
  selectedPoint.value = point;
  selectedPointIndex.value = index;
  hoverName.value = getPointName(point);
  showPointOnChart(index);
};

const cityKeyword = (name: string) => String(name || '').replace(/市/g, '');
const resolveCityName = (name: string) => {
  const keyword = cityKeyword(name);
  if (!keyword) return '';
  return Object.keys(cityMaps).find(city => keyword.includes(cityKeyword(city)) || cityKeyword(city).includes(keyword)) || '';
};

const tooltipFormatter = (params: any) => {
  const data = params?.data || {};
  const cityName = resolveCityName(params?.name || data.region || '') || data.region || params?.name || '';
  if (params?.seriesType === 'effectScatter') {
    const lines = [
      `<b>${data.name || cityName || '气象点'}</b>`,
      data.region ? `区域：${data.region}` : '',
      data.time ? `时间：${data.time}` : '',
      data.temperature !== undefined && data.temperature !== null ? `温度：${data.temperature}℃` : '',
      data.humidity !== undefined && data.humidity !== null ? `湿度：${data.humidity}%` : '',
      data.wind_speed !== undefined && data.wind_speed !== null ? `风速：${data.wind_speed}m/s` : '',
      data.precipitation !== undefined && data.precipitation !== null ? `降水：${data.precipitation}mm` : ''
    ].filter(Boolean);
    return lines.join('<br/>');
  }
  if (isCityView.value && params?.name) {
    return `${selectedCity.value}<br/>${params.name}`;
  }
  return cityName || params?.name || '辽宁省';
};

const option = computed<EChartsOption>(() => ({
  animationDurationUpdate: 420,
  animationEasingUpdate: 'cubicOut',
  tooltip: {
    trigger: 'item',
    confine: true,
    backgroundColor: 'rgba(7, 18, 32, 0.92)',
    borderColor: 'rgba(111, 157, 255, 0.42)',
    textStyle: { color: '#e7f0ff' },
    formatter: tooltipFormatter
  },
  geo: {
    map: activeMapName.value,
    roam: true,
    ...geoLayout.value,
    scaleLimit: { min: 1, max: 8 },
    label: {
      show: true,
      color: 'rgba(238,244,255,.82)',
      fontSize: isCityView.value ? 10 : 12,
      hideOverlap: true,
      textBorderColor: 'rgba(3, 10, 18, 0.88)',
      textBorderWidth: isCityView.value ? 3 : 1
    },
    itemStyle: { areaColor: '#132b48', borderColor: '#6f9dff', borderWidth: 1 },
    emphasis: {
      itemStyle: { areaColor: '#2b5b8f' },
      label: {
        show: true,
        color: '#fff',
        fontSize: isCityView.value ? 15 : 13,
        fontWeight: 700,
        textBorderColor: 'rgba(3, 10, 18, 0.92)',
        textBorderWidth: 3
      }
    }
  },
  visualMap: {
    min: 0,
    max: 100,
    show: points.value.length > 0,
    seriesIndex: 0,
    left: 18,
    bottom: 20,
    textStyle: { color: '#e7f0ff' },
    inRange: { color: ['#6f9dff', '#d8a74f', '#e86c5b'] }
  },
  series: [
    {
      name: '预警点位',
      type: 'effectScatter',
      coordinateSystem: 'geo',
      data: points.value,
      symbolSize: (value: any) => Math.max(8, Number(value?.[2] || 0) / 6),
      rippleEffect: { brushType: 'stroke', scale: 3.2 },
      itemStyle: { color: '#e86c5b', shadowColor: 'rgba(232,108,91,.42)', shadowBlur: 12 }
    },
    ...(selectedPoint.value ? [
      {
        name: '选中点位',
        type: 'effectScatter' as const,
        coordinateSystem: 'geo' as const,
        data: [selectedPoint.value],
        symbolSize: 24,
        silent: true,
        tooltip: { show: false },
        rippleEffect: { brushType: 'stroke' as const, scale: 4.4 },
        itemStyle: {
          color: '#ffd36b',
          shadowColor: 'rgba(255, 211, 107, 0.58)',
          shadowBlur: 18
        },
        z: 20
      }
    ] : [])
  ]
}));

const focusCity = (city: string) => {
  const cityMap = cityMaps[city];
  if (!cityMap) return;
  mapCenter.value = cityMap.center;
  mapZoom.value = 2.65;
};

const fetchData = async () => {
  const id = ++fetchId;
  dataError.value = '';
  try {
    const res = await apiGetMapData();
    if (id !== fetchId) return;
    points.value = res.data || [];
    selectedPoint.value = null;
    selectedPointIndex.value = null;
  } catch {
    if (id !== fetchId) return;
    points.value = [];
    dataError.value = '点位接口暂不可用，行政区底图仍可浏览';
  }
};

const handleThreePointSelect = (point: any) => selectPoint(point, points.value.indexOf(point));
const handleRegionSelect = (name: string) => {
  if (!isCityView.value) handleMapClick({ name });
  else hoverName.value = name;
};

const handleMapClick = async (params: any) => {
  if (params?.seriesType === 'effectScatter') {
    selectPoint(params.data || null, params.dataIndex ?? -1);
    return;
  }
  if (isCityView.value) {
    return;
  }
  selectedPoint.value = null;
  selectedPointIndex.value = null;
  const city = resolveCityName(params?.name || params?.data?.region || params?.data?.name || '');
  if (!city) return;
  focusCity(city);
  await setSelectedCity(city);
};

const handleMapHover = (params: any) => {
  const city = resolveCityName(params?.name || params?.data?.region || params?.data?.name || '');
  hoverName.value = city || params?.data?.name || params?.name || '';
};

const handleMapOut = () => {
  hoverName.value = '';
};

const handleBack = async () => {
  mapCenter.value = provinceCenter;
  mapZoom.value = provinceZoom;
  hoverName.value = '';
  selectedPoint.value = null;
  selectedPointIndex.value = null;
  await clearSelectedCity();
};

watch(
  () => screenStore.refreshKey,
  () => {
    fetchData();
  }
);

onMounted(fetchData);
onBeforeUnmount(() => { fetchId++; });
</script>

<style scoped>
.map-center {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(112, 150, 205, 0.22);
  border-radius: 14px;
  background:
    radial-gradient(circle at 50% 48%, rgba(79, 134, 255, 0.15), transparent 38%),
    linear-gradient(180deg, rgba(8, 20, 36, 0.58), rgba(5, 10, 19, 0.76));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    0 24px 56px rgba(0, 0, 0, 0.30);
}

.map-center::before {
  content: "";
  position: absolute;
  inset: 36px 58px 28px;
  border-radius: 50%;
  border: 1px solid rgba(112, 150, 205, 0.18);
  box-shadow: 0 0 70px rgba(79, 134, 255, 0.12);
  pointer-events: none;
}

.map-toolbar {
  position: absolute;
  left: 22px;
  right: 22px;
  top: 18px;
  z-index: 5;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  color: #eef4ff;
  pointer-events: auto;
}

.map-toolbar strong {
  display: block;
  margin-top: 2px;
  font-size: 22px;
  letter-spacing: 1px;
}

.map-kicker {
  color: rgba(216, 167, 79, 0.88);
  font-size: 12px;
  letter-spacing: 2px;
}

.map-tip {
  display: block;
  margin-top: 5px;
  color: rgba(220, 236, 255, 0.62);
  font-size: 12px;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
  max-width: 60%;
}

.view-switch { display: flex; padding: 3px; border: 1px solid #7fbbdf40; border-radius: 8px; background: #081723e6; }
.view-switch button { border: 0; padding: 7px 10px; border-radius: 5px; background: transparent; color: #a8c3d8; cursor: pointer; white-space: nowrap; font-size: 12px; }
.view-switch button.active { background: #22517a; color: #e9f8ff; box-shadow: inset 0 0 0 1px #67bfff66; }
.view-switch button:focus-visible { outline: 2px solid #e4d4a5; outline-offset: 2px; }
.map-caption { position: absolute; bottom: 18px; left: 22px; z-index: 3; display: flex; flex-direction: column; align-items: flex-start; gap: 7px; color: #7897ab; font-size: 10px; pointer-events: none; }
.map-caption > div { color: #c1d9df; font-size: 12px; letter-spacing: 1px; }
.map-live-dot { width: 5px; height: 5px; border-radius: 50%; display: inline-block; margin-right: 7px; background: #65d6d0; box-shadow: 0 0 8px #65d6d0; }
.map-caption button, .data-error button { pointer-events: auto; cursor: pointer; border: 1px solid #8db3c044; border-radius: 4px; background: #0e2028; color: #bdd2d6; padding: 5px 10px; font-size: 11px; }
.data-error { position: absolute; left: 50%; top: 78%; transform: translateX(-50%); z-index: 3; padding: 9px 12px; width: max-content; max-width: 85%; border: 1px solid #c7ae7644; border-radius: 5px; color: #d9cba8; background: #111c22e0; font-size: 12px; }
.map-center[data-map-style="terrain"] { border-color: #9fae8d38; background: radial-gradient(ellipse at 50% 55%, #47564729, transparent 70%), linear-gradient(180deg, #17211c80, #080d0cba); }
.map-center[data-map-style="terrain"]::before { border-color: #9da98a16; box-shadow: none; }
.map-center[data-map-style="terrain"] .view-switch button.active { background: #425b49; box-shadow: inset 0 0 0 1px #acc6a066; }
.map-center:not([data-map-style="flat"]) { border: 0; border-radius: 0; box-shadow: none; background: radial-gradient(ellipse at 50% 50%, #17305124, transparent 68%); overflow: hidden; }
.map-center:not([data-map-style="flat"])::before { display: none; }
.map-center[data-map-style="terrain"] { background: radial-gradient(ellipse at 50% 50%, #38413124, transparent 68%); }
.map-caption a { pointer-events: auto; color: #829d9d; font-size: 9px; text-decoration: none; }
.map-caption a:hover { color: #d9e6cf; }
.map-center[data-map-style="blue"] .map-kicker { color: #7ca8e8; }
.map-center[data-map-style="terrain"] .map-kicker { color: #859889; font-size: 10px; letter-spacing: 2px; }
.map-center[data-map-style="terrain"] .map-toolbar { top: 0; left: 0; right: 0; }
.map-center[data-map-style="terrain"] .map-toolbar strong { font-size: 16px; font-weight: 500; color: #c6d0bf; }
.map-center[data-map-style="terrain"] .map-tip { font-size: 10px; color: #738276; }
.map-center[data-map-style="terrain"] { overflow: visible; }
.map-center[data-map-style="terrain"] :deep(.terrain-canvas) { position: absolute; inset: -58px -150px -36px; width: calc(100% + 300px); height: calc(100% + 94px); }
.map-center[data-map-style="terrain"] .view-switch { border: 0; background: #121a15b0; }
.map-center[data-map-style="terrain"] .map-caption { bottom: 10px; left: 0; }
.geographic-map-tools { position: absolute; left: 50%; bottom: 14px; transform: translateX(-50%); display: flex; gap: 10px; z-index: 4; }
.geographic-map-tools button { cursor: pointer; border: 1px solid #7e92795c; background: #121a15d9; border-radius: 20px; color: #a9b4a5; padding: 7px 18px; font-size: 11px; }
.geographic-map-tools button[aria-pressed="true"] { border-color: #b8c8a299; color: #e7efdb; background: #45533b66; }
.elevation-legend { position: absolute; right: 4px; bottom: 14px; width: 120px; color: #8d9c88; font-size: 10px; z-index: 3; }
.elevation-legend i { display: block; height: 4px; margin: 6px 0; background: linear-gradient(90deg, #334937, #67774b, #a99d85, #c2baa9); }
.elevation-legend div { display: flex; justify-content: space-between; }

.back-btn,
.map-count {
  appearance: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 32px;
  padding: 0 13px;
  box-sizing: border-box;
  border: 1px solid rgba(112, 150, 205, 0.34);
  border-radius: 999px;
  background: rgba(8, 18, 32, 0.76);
  color: rgba(220, 236, 255, 0.86);
  font-size: 13px;
  line-height: 1;
  white-space: nowrap;
}

.back-btn,
.map-count {
  cursor: pointer;
  transition: all 0.2s ease;
}

.back-btn:hover,
.map-count:hover {
  border-color: rgba(111, 157, 255, 0.7);
  color: #fff;
  background: rgba(79, 134, 255, 0.18);
}

.chart {
  width: 100%;
  height: 100%;
}

.empty-map {
  position: absolute;
  left: 50%;
  top: 56%;
  transform: translate(-50%, -50%);
  z-index: 2;
  color: rgba(220, 236, 255, .72);
  font-size: 16px;
  padding: 10px 18px;
  border: 1px solid rgba(112, 150, 205, 0.20);
  border-radius: 999px;
  background: rgba(3, 10, 18, 0.52);
}

.point-menu-panel {
  position: absolute;
  left: 24px;
  top: 104px;
  bottom: 24px;
  z-index: 4;
  width: 278px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(112, 150, 205, 0.30);
  border-radius: 12px;
  background:
    linear-gradient(180deg, rgba(14, 28, 50, 0.94), rgba(5, 12, 23, 0.90)),
    radial-gradient(circle at 20% 0%, rgba(79, 134, 255, 0.14), transparent 36%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.07),
    0 18px 42px rgba(0, 0, 0, 0.32);
  color: #eef4ff;
}

.point-menu-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 12px 8px;
  border-bottom: 1px solid rgba(112, 150, 205, 0.16);
}

.point-menu-header span {
  display: block;
  color: rgba(216, 167, 79, 0.92);
  font-size: 12px;
  letter-spacing: 1px;
}

.point-menu-header strong {
  display: block;
  margin-top: 4px;
  color: #fff;
  font-size: 14px;
}

.point-menu-close {
  flex: 0 0 auto;
  width: 24px;
  height: 24px;
  border: 1px solid rgba(112, 150, 205, 0.32);
  border-radius: 50%;
  background: rgba(8, 18, 32, 0.84);
  color: rgba(220, 236, 255, 0.74);
  cursor: pointer;
  line-height: 1;
}

.point-menu-close:hover {
  border-color: rgba(111, 157, 255, 0.72);
  color: #fff;
  background: rgba(79, 134, 255, 0.18);
}

.point-search {
  flex: 0 0 auto;
  height: 30px;
  margin: 10px 12px 8px;
  padding: 0 10px;
  border: 1px solid rgba(112, 150, 205, 0.25);
  border-radius: 8px;
  background: rgba(3, 10, 18, 0.46);
  color: #eef4ff;
  font-size: 12px;
}

.point-search::placeholder {
  color: rgba(220, 236, 255, 0.42);
}

.point-menu-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 10px 12px;
}

.point-menu-item {
  width: 100%;
  display: block;
  margin-bottom: 8px;
  padding: 9px 10px;
  border: 1px solid rgba(112, 150, 205, 0.16);
  border-radius: 9px;
  background: rgba(8, 18, 32, 0.54);
  color: inherit;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s ease;
}

.point-menu-item:hover,
.point-menu-item.active {
  border-color: rgba(111, 157, 255, 0.62);
  background: rgba(79, 134, 255, 0.18);
  box-shadow: inset 3px 0 0 rgba(111, 157, 255, 0.82);
}

.point-menu-name,
.point-menu-meta,
.point-menu-data {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.point-menu-name {
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}

.point-menu-meta {
  margin-top: 5px;
  color: rgba(220, 236, 255, 0.58);
  font-size: 12px;
}

.point-menu-data {
  margin-top: 4px;
  color: rgba(216, 167, 79, 0.90);
  font-size: 12px;
}

.point-menu-empty {
  margin-top: 16px;
  color: rgba(220, 236, 255, 0.56);
  font-size: 13px;
  text-align: center;
}

.point-detail-panel {
  position: absolute;
  right: 24px;
  bottom: 24px;
  z-index: 4;
  width: 310px;
  max-height: calc(100% - 108px);
  overflow: hidden;
  border: 1px solid rgba(112, 150, 205, 0.34);
  border-radius: 12px;
  background:
    linear-gradient(180deg, rgba(14, 28, 50, 0.96), rgba(5, 12, 23, 0.94)),
    radial-gradient(circle at 18% 0%, rgba(79, 134, 255, 0.16), transparent 36%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.07),
    0 18px 44px rgba(0, 0, 0, 0.36);
  color: #eef4ff;
}

.point-detail-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 14px 10px;
  border-bottom: 1px solid rgba(112, 150, 205, 0.18);
}

.point-detail-header span {
  display: block;
  color: rgba(216, 167, 79, 0.92);
  font-size: 12px;
  letter-spacing: 1px;
}

.point-detail-header strong {
  display: block;
  margin-top: 4px;
  max-width: 230px;
  overflow: hidden;
  color: #fff;
  font-size: 15px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.point-detail-close {
  flex: 0 0 auto;
  width: 26px;
  height: 26px;
  border: 1px solid rgba(112, 150, 205, 0.32);
  border-radius: 50%;
  background: rgba(8, 18, 32, 0.84);
  color: rgba(220, 236, 255, 0.74);
  cursor: pointer;
  line-height: 1;
}

.point-detail-close:hover {
  border-color: rgba(111, 157, 255, 0.72);
  color: #fff;
  background: rgba(79, 134, 255, 0.18);
}

.point-detail-form {
  max-height: 322px;
  overflow-y: auto;
  padding: 10px 14px 14px;
}

.point-detail-row {
  display: grid;
  grid-template-columns: 82px minmax(0, 1fr);
  gap: 10px;
  min-height: 30px;
  align-items: center;
  border-bottom: 1px dashed rgba(112, 150, 205, 0.16);
}

.point-detail-row:last-child {
  border-bottom: 0;
}

.point-detail-label {
  color: rgba(220, 236, 255, 0.58);
  font-size: 12px;
}

.point-detail-value {
  overflow: hidden;
  color: #eef4ff;
  font-size: 13px;
  font-weight: 600;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
