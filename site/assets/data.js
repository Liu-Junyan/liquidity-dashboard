import { locale, t } from './zh-CN.js';

export const DAY = 86400000;
export const timestamp = date => Date.parse(`${date}T00:00:00Z`);
export function latestObservation(observations) {
  return observations.findLast(point => point.value !== null) ?? null;
}
export function changeAt(observations, weeks, indicator) {
  const latest = latestObservation(observations);
  if (!latest) return null;
  const target = timestamp(latest.date) - weeks * 7 * DAY;
  const prior = observations.find(point => timestamp(point.date) === target);
  if (!prior || prior.value === null) return null;
  const difference = (latest.value - prior.value) * (indicator.unit.kind === 'rate' ? 100 : 1);
  return Math.abs(difference) < 1e-8 ? 0 : difference;
}
export function inRange(observations, range, anchor) {
  if (range === 'all') return observations;
  const start = new Date(timestamp(anchor));
  if (range === 'ytd') start.setUTCMonth(0, 1);
  else start.setUTCFullYear(start.getUTCFullYear() - (range === '1y' ? 1 : 5));
  return observations.filter(point => timestamp(point.date) >= start.getTime());
}
export function summaryStatistics(observations, history = observations) {
  const latest = latestObservation(observations);
  const empty = () => ({value: null, count: 0});
  if (!latest) return {average3m: empty(), average1y: empty(), percentile: empty()};
  const end = timestamp(latest.date);
  function average(months) {
    const start = new Date(end);
    const day = start.getUTCDate();
    start.setUTCDate(1);
    start.setUTCMonth(start.getUTCMonth() - months);
    const lastDay = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 0)).getUTCDate();
    start.setUTCDate(Math.min(day, lastDay));
    const points = observations.filter(point => point.value !== null && timestamp(point.date) >= start.getTime() && timestamp(point.date) <= end);
    return {value: points.length ? points.reduce((sum, point) => sum + point.value, 0) / points.length : null, count: points.length};
  }
  const validHistory = history.filter(point => point.value !== null && timestamp(point.date) <= end);
  return {
    average3m: average(3),
    average1y: average(12),
    percentile: {
      value: validHistory.length ? validHistory.filter(point => point.value <= latest.value).length / validHistory.length * 100 : null,
      count: validHistory.length,
    },
  };
}
export function formatNumber(value, precision = 2) {
  return value === null || value === undefined ? '—' : new Intl.NumberFormat(locale, {minimumFractionDigits: precision, maximumFractionDigits: precision}).format(value);
}
export function formatDate(date, options = {}) {
  if (!date) return '—';
  return new Intl.DateTimeFormat(locale, {year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'UTC', ...options}).format(new Date(date.length === 10 ? timestamp(date) : date));
}
export function formatChange(value, indicator) {
  if (value === null) return '—';
  const suffix = indicator.unit.kind === 'rate' ? 'bp' : indicator.unit.kind === 'ratio' ? t('percentagePoints') : indicator.unit.label;
  const digits = indicator.unit.kind === 'rate' ? 1 : indicator.unit.precision;
  return `${value > 0 ? '+' : ''}${formatNumber(value, digits)} ${suffix}`;
}
export function parseRoute(hash, categories, indicators) {
  const params = new URLSearchParams(hash.replace(/^#/, ''));
  const indicator = indicators.find(item => item.id === params.get('indicator'));
  const category = indicator?.categoryId ?? (categories.some(item => item.id === params.get('category')) ? params.get('category') : categories[0].id);
  const range = ['ytd', '1y', '5y', 'all'].includes(params.get('range')) ? params.get('range') : '5y';
  return { category, range, indicator: indicator?.id ?? null };
}
export const frequencyLabel = frequency => frequency === 'weekly' ? t('weeklyFrequency') : frequency;
