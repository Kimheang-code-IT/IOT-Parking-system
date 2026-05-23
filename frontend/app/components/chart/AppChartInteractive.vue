<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from "vue";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { LineChart, PieChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DatasetComponent,
} from "echarts/components";
import type { EChartsOption } from "echarts";
import { fetchInteractiveChart } from "~/data/dashboard";

use([
  CanvasRenderer,
  LineChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DatasetComponent,
]);

const vChartRef = ref<any>(null);
const chartReady = ref(false);
const vehicleTypes = ref<string[]>([]);
const selectedType = ref<string>('All');

const chartOption = ref<EChartsOption>({
  legend: {},
  tooltip: {
    trigger: 'axis',
    showContent: false
  },
  dataset: {
    source: [['Type / Hour', '08:00']]
  },
  xAxis: { type: 'category' },
  yAxis: { gridIndex: 0 },
  grid: { top: '55%', bottom: '10%' },
  series: [
    { type: 'line', smooth: true, seriesLayoutBy: 'row', emphasis: { focus: 'series' } },
    { type: 'line', smooth: true, seriesLayoutBy: 'row', emphasis: { focus: 'series' } },
    { type: 'line', smooth: true, seriesLayoutBy: 'row', emphasis: { focus: 'series' } },
    {
      type: 'pie',
      id: 'pie',
      radius: '30%',
      center: ['50%', '25%'],
      emphasis: { focus: 'self' },
      label: { formatter: '{b}: {@08:00} ({d}%)' },
      encode: {
        itemName: 'Type / Hour',
        value: '08:00',
        tooltip: '08:00'
      }
    }
  ]
});

async function loadChart(vehicleType?: string) {
  try {
    const data = await fetchInteractiveChart(vehicleType);
    const source = data.source || [];
    // Extract vehicle type names from dataset rows (skip header)
    vehicleTypes.value = source.slice(1).map((r: any) => String(r[0] || ''));
    const seriesRows = Math.max(source.length - 1, 0);
    // Create one line series per data row (after header), then add the pie series
    const lineSeries = Array.from({ length: seriesRows }, () => ({
      type: 'line' as const,
      smooth: true,
      seriesLayoutBy: 'row' as const,
      emphasis: { focus: 'series' as const },
    }));

    const firstBucket = source[0]?.[1] || '08:00';

    chartOption.value = {
      ...chartOption.value,
      dataset: { source },
      series: [
        ...lineSeries,
        {
          type: 'pie',
          id: 'pie',
          radius: '30%',
          center: ['50%', '25%'],
          emphasis: { focus: 'self' },
          label: { formatter: `{b}: {@${firstBucket}} ({d}%)` },
          encode: {
            itemName: 'Type / Hour',
            value: firstBucket,
            tooltip: firstBucket,
          },
        },
      ],
    };

    // Wait until the chart component mounts before showing it
    await nextTick();
    chartReady.value = true;
    // Update legend on existing chart instance (if mounted)
    const chartInstance = vChartRef.value?.chart;
    if (chartInstance) {
      const initialSelected: Record<string, boolean> = {};
      if (selectedType.value === 'All') {
        vehicleTypes.value.forEach((t) => (initialSelected[t] = true));
      } else {
        vehicleTypes.value.forEach((t) => (initialSelected[t] = t === selectedType.value));
      }
      chartInstance.setOption({ legend: { data: vehicleTypes.value, selected: initialSelected } });
    }
  } catch (err) {
    console.error('Interactive chart load failed:', err);
  }

  // Attach axis pointer handler after chart is rendered
  setTimeout(() => {
    const chartInstance = vChartRef.value?.chart;
    if (chartInstance) {
      // ensure legend shows available vehicle types and apply initial selection
      const initialSelected: Record<string, boolean> = {};
      if (selectedType.value === 'All') {
        vehicleTypes.value.forEach((t) => (initialSelected[t] = true));
      } else {
        vehicleTypes.value.forEach((t) => (initialSelected[t] = t === selectedType.value));
      }
      chartInstance.setOption({ legend: { data: vehicleTypes.value, selected: initialSelected } });
      chartInstance.on('updateAxisPointer', function (event: any) {
        const xAxisInfo = event.axesInfo?.[0];
        if (xAxisInfo) {
          const dimension = xAxisInfo.value + 1;
          chartInstance.setOption({
            series: {
              id: 'pie',
              label: {
                formatter: '{b}: {@[' + dimension + ']} ({d}%)',
              },
              encode: {
                value: dimension,
                tooltip: dimension,
              },
            },
          });
        }
      });
      chartInstance.resize();
    }
  }, 100);
}

// Refetch chart data from backend when selectedType changes (backend-side filtering)
watch(selectedType, (val) => {
  const vehicleType = val === 'All' ? undefined : val;
  loadChart(vehicleType);
});

// initial load when component mounts
onMounted(() => {
  loadChart(selectedType.value === 'All' ? undefined : selectedType.value);
});</script>

<template>
  <div class="w-full h-[600px] min-h-[600px] relative">
    <ClientOnly>
      <div class="absolute top-2 right-2 z-20">
        <label class="sr-only">Vehicle Type</label>
        <select v-model="selectedType" class="bg-white border rounded px-2 py-1 text-sm">
          <option value="All">All</option>
          <option v-for="t in vehicleTypes" :key="t" :value="t">{{ t }}</option>
        </select>
      </div>
      <VChart v-if="chartReady" ref="vChartRef" autoresize class="h-full w-full" :option="chartOption" />
      <div
        v-else
        class="h-full w-full flex items-center justify-center text-xs text-muted-foreground uppercase font-bold tracking-widest"
      >
        Loading chart from database...
      </div>
      <template #fallback>
        <div class="h-full w-full flex items-center justify-center text-xs text-muted-foreground uppercase font-bold tracking-widest">
          Initializing chart...
        </div>
      </template>
    </ClientOnly>
  </div>
</template>
