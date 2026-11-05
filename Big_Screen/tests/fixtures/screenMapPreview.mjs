// Synthetic interface fixture only. These values are not observations or model evaluation results.
const centers = [
  ['沈阳市', 123.429096, 41.796767], ['大连市', 121.618622, 38.91459],
  ['鞍山市', 122.995632, 41.110626], ['抚顺市', 123.957208, 41.880872],
  ['本溪市', 123.766485, 41.294176], ['丹东市', 124.383044, 40.124296],
  ['锦州市', 121.135742, 41.119269], ['营口市', 122.235151, 40.667432],
  ['阜新市', 121.670052, 42.022028], ['辽阳市', 123.18152, 41.269402],
  ['盘锦市', 122.070714, 41.119997], ['铁岭市', 123.844279, 42.290585],
  ['朝阳市', 120.450372, 41.573734], ['葫芦岛市', 120.856394, 40.755572]
];
export function screenMapPreview(city = '') {
  const rows = centers.filter(item => !city || item[0] === city).map(([name, lng, lat], index) => ({
    name: `${name.replace('市', '')}演示点位`, region: name,
    value: [lng, lat, 25 + index * 5], longitude: lng, latitude: lat,
    time: '2026-10-19 12:00:00', temperature: -3 + index * 0.6,
    humidity: 75 + index, wind_speed: index === 0 ? 0 : 3 + index * 0.4,
    precipitation: 0, wind_direction: 0, level: ['低', '一般', '较高', '高'][index % 4],
    probability_percent: 25 + index * 5
  }));
  const hours = Array.from({length: 12}, (_, i) => i + 1);
  return {
    city: city || '辽宁省', weather: '演示数据', temperature_range: '-3℃ ~ 5℃',
    station_count: rows.length, line_count: 1260, online_station_count: rows.length, warning_count: rows.length,
    risk_count: rows.length, running_days: 30, temperature: -3, humidity: 75, wind_speed: 0, pressure: 1016,
    map_points: rows, station_ranking: rows, warning_list: rows,
    risk_distribution: ['低', '一般', '较高', '高'].map((name, i) => ({name, value: rows.filter((_, j) => j % 4 === i).length})),
    weather_trend: hours.map((hour, i) => ({time: `${hour}:00`, temperature: -3 + Math.sin(i / 2) * 4, humidity: 75 + Math.sin(i) * 8, wind_speed: 3 + Math.cos(i / 2) * 2})),
    risk_distribution_by_region: {cities: rows.slice(0, 6).map(row => row.region), level1: [2, 1, 2, 1, 3, 2], level2: [3, 2, 1, 3, 1, 2], level3: [1, 2, 1, 2, 2, 1], level4: [2, 1, 1, 1, 2, 1]},
    prediction_hourly_trend: {hours, series: rows.slice(0, 3).map((row, i) => ({name: row.region, data: hours.map(hour => Math.round(15 + i * 13 + Math.sin(hour / 3 + i) * 10 + hour * 2))}))},
    task_list: [{taskCode: 'DEMO_ONLY', taskName: '演示预测任务', algorithmName: '示例结果', status: 'success', progress: 100, createTime: '2026-10-19 12:00:00'}]
  };
}
