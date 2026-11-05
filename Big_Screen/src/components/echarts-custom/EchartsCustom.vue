<template>
    <div ref="chartRef" :id="id" :class="className" :style="{ 'height' : height, 'width' :width}">
    </div>
</template>

<script lang="ts">
export default {
    name: "mEcharts"
};
</script>

<script setup lang="ts">
import * as echarts from 'echarts';
import theme from '@/common/echart/style/theme';
import { onMounted, onBeforeUnmount, ref, shallowRef, watch } from 'vue';
import type { EChartsType } from 'echarts';
import fujianJson from '@/common/echart/map/fujian.json';
import liaoningJson from '@/common/echart/map/liaoning.json';

const props = defineProps({
    // 图表唯一 id
    id: String,
    // 图表类名
    className: {
        type: String,
        default: 'chart'
    },
    // 图表宽度
    width: {
        type: String,
        require: true
    },
    // 图表高度
    height: {
        type: String,
        require: true
    },
    // 图表数据项
    options: {
        type: Object,
        default: () => ({}),
    }
})
const { id, className, height, width } = props;
const chartRef = ref();
// const charts = reactive({
//     chart as EChartsType: null
// })
const chart = shallowRef<EChartsType>()
let resizeObserver: ResizeObserver | undefined;
let resizeFrame = 0;

onMounted(() => {
    echarts.registerTheme('myTheme', theme); // 覆盖默认主题
    chart.value = echarts.init(chartRef.value, 'myTheme');
    echarts.registerMap("fujian", fujianJson as any);
    echarts.registerMap("liaoning", liaoningJson as any);
    initChart()
    resizeObserver = new ResizeObserver(() => {
        cancelAnimationFrame(resizeFrame);
        resizeFrame = requestAnimationFrame(() => {
            if (chartRef.value?.clientWidth && chartRef.value?.clientHeight) chart.value?.resize();
        });
    });
    resizeObserver.observe(chartRef.value);
})

onBeforeUnmount(() => {
    cancelAnimationFrame(resizeFrame);
    resizeObserver?.disconnect();
    chart.value?.dispose();
    chart.value = undefined;
})

// 监听改变
watch(
    () => props.options,
    val => {
        val && initChart(val)
    },
    {
        deep: true
    }
)

const initChart = (data?: any, clearCaching = false) => {
    if (data || props.options) {
        chart.value?.setOption(data || props.options, clearCaching)
    }
}

defineExpose({
    initChart
})
</script>

<style scoped>

</style>
