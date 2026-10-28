import {formatDate, formatNumber, timestamp} from './data.js';
import {t} from './zh-CN.js';

const instances = new Map();
const resizeObserver = new ResizeObserver(entries => entries.forEach(({target}) => instances.get(target)?.resize()));
export function disposeCharts(parent) {
  for (const [element, chart] of instances) {
    if (parent.contains(element)) { resizeObserver.unobserve(element); chart.dispose(); instances.delete(element); }
  }
}
export function drawChart(element, observations, indicator, {sparkline = false} = {}) {
  if (!window.echarts) { if (!sparkline) element.textContent = t('chartUnavailable'); return; }
  const chart = window.echarts.init(element, null, {renderer: 'svg'});
  instances.set(element, chart);
  resizeObserver.observe(element);
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  chart.setOption({
    animation: !reducedMotion, animationDuration: 350,
    textStyle: {fontFamily: 'Arial, "PingFang SC", "Microsoft YaHei", sans-serif'},
    grid: sparkline ? {top: 8, bottom: 5, left: 1, right: 1} : {top: 20, bottom: 35, left: 60, right: 20},
    tooltip: sparkline ? {show: false} : {
      trigger: 'axis', renderMode: 'richText', confine: true,
      backgroundColor: '#12374b', borderWidth: 0, textStyle: {color: '#fff', fontSize: 12},
      formatter: params => {
        const point = params[0];
        return `${formatDate(new Date(point.value[0]).toISOString().slice(0, 10))}\n${formatNumber(point.value[1], indicator.unit.precision)} ${indicator.unit.label}\n${t('syntheticSeries')}`;
      },
    },
    xAxis: {type: 'time', show: !sparkline, min: timestamp(observations[0].date), max: timestamp(observations.at(-1).date), splitNumber: 4,
      axisLine: {lineStyle: {color: '#d9dfe2'}}, axisTick: {show: false}, axisLabel: {color: '#75818a', fontSize: 11, hideOverlap: true, formatter: value => new Intl.DateTimeFormat('zh-CN', {year: 'numeric', month: '2-digit', timeZone: 'UTC'}).format(value)}, splitLine: {show: false}},
    yAxis: {type: 'value', show: !sparkline, scale: true, splitNumber: 4, axisLabel: {color: '#75818a', fontSize: 11, formatter: value => formatNumber(value, indicator.unit.precision)}, splitLine: {lineStyle: {color: '#e8ecee', type: 'dashed'}}},
    series: [{type: 'line', name: indicator.name, data: observations.map(point => [timestamp(point.date), point.value]), connectNulls: false, showSymbol: false, symbolSize: 4, lineStyle: {width: sparkline ? 1.8 : 2, color: '#2b7295'}, itemStyle: {color: '#2b7295'}, areaStyle: sparkline ? {color: '#2b7295', opacity: 0.055} : undefined, emphasis: {lineStyle: {width: 2.5}}}],
  });
}
