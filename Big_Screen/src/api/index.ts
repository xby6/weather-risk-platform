import request from '@/utils/request';
import { getScreenQueryParams, screenStore } from '@/store/screenData';

export { screenStore } from '@/store/screenData';

type ScreenAllData = Record<string, any>;

const cityCoords: Record<string, [number, number]> = {
  沈阳: [123.429096, 41.796767],
  大连: [121.618622, 38.91459],
  鞍山: [122.995632, 41.110626],
  抚顺: [123.957208, 41.880872],
  本溪: [123.766485, 41.294176],
  丹东: [124.383044, 40.124296],
  锦州: [121.135742, 41.119269],
  营口: [122.235151, 40.667432],
  阜新: [121.670052, 42.022028],
  辽阳: [123.18152, 41.269402],
  盘锦: [122.070714, 41.119997],
  铁岭: [123.844279, 42.290585],
  朝阳: [120.450372, 41.573734],
  葫芦岛: [120.856394, 40.755572]
};

const unwrap = (res: any) => {
  if (!res) return {};
  if (res.code === 200 || res.code === 0) return res.data ?? {};
  if (res.data && (res.data.code === 200 || res.data.code === 0)) return res.data.data ?? {};
  return res.data ?? res;
};

const cityKeyword = (name: string = '') => String(name || '').replace(/市/g, '').trim();

const matchSelectedCity = (item: any) => {
  const keyword = cityKeyword(screenStore.selectedCity);
  if (!keyword) return true;
  return [item?.region, item?.city, item?.area, item?.lineCode, item?.line_code, item?.taskName, item?.taskCode]
    .some(value => cityKeyword(String(value || '')).includes(keyword));
};

const normalizeLevelName = (level: string) => {
  if (!level) return '未知';
  const text = level.toUpperCase();
  if (text.includes('IV') || level.includes('蓝') || level.includes('低')) return '蓝色';
  if (text.includes('III') || level.includes('黄') || level.includes('中')) return '黄色';
  if (text.includes('II') || level.includes('橙') || level.includes('较高')) return '橙色';
  if (text.includes('I') || level.includes('红') || level.includes('高')) return '红色';
  return level;
};

const numberOrNull = (value: any) => value === undefined || value === null || value === '' ? null : Number(value);

const getScreenAllData = async (): Promise<ScreenAllData> => {
  return unwrap(await request.get('/monitor/screen-all-data', { params: getScreenQueryParams() })) as ScreenAllData;
};

const getTaskRows = (data: ScreenAllData): any[] => {
  const rows = data?.task_list || [];
  return Array.isArray(rows) ? rows.filter(matchSelectedCity) : [];
};

export const apiGetWeatherMonitor = async () => {
  const data = await getScreenAllData();
  return {
    code: 200,
    data: {
      temperature: data.temperature ?? null,
      humidity: data.humidity ?? null,
      windSpeed: data.wind_speed ?? null,
      windDirection: data.wind_direction ?? '',
      rainfall: data.precipitation ?? null,
      pressure: data.pressure ?? null
    }
  };
};

export const apiGetWeatherTrend = async () => {
  const data = await getScreenAllData();
  const trend = data.weather_trend || [];
  return {
    code: 200,
    data: {
      times: trend.map((i: any) => i.time || i.date),
      temperature: trend.map((i: any) => numberOrNull(i.temperature)),
      humidity: trend.map((i: any) => numberOrNull(i.humidity)),
      windSpeed: trend.map((i: any) => numberOrNull(i.wind_speed))
    }
  };
};

export const apiGetStationRanking = async (type: string = 'temp') => {
  const data = await getScreenAllData();
  const rows = data.station_ranking || [];
  const fieldMap: Record<string, string[]> = {
    temp: ['temperature', 'temp'],
    wind: ['wind_speed', 'wind'],
    rain: ['precipitation', 'rain']
  };
  const fields = fieldMap[type] || fieldMap.temp;
  const ranking = rows
    .map((item: any) => {
      const value = fields.map(field => item[field]).find(value => value !== undefined && value !== null && value !== '');
      return {
        name: item.name || item.station || item.region || '-',
        value: Number(value ?? 0),
        time: item.time || ''
      };
    })
    .sort((a: any, b: any) => b.value - a.value);
  return { code: 200, data: ranking };
};

export const apiGetWarningLevels = async () => {
  const data = await getScreenAllData();
  return { code: 200, data: data.risk_distribution || [] };
};

export const apiGetTopStats = async () => {
  const data = await getScreenAllData();
  const tasks = getTaskRows(data);
  return {
    code: 200,
    data: {
      totalStations: data.station_count || 0,
      totalLines: data.line_count || 0,
      onlineStations: data.online_station_count || 0,
      warningEvents: data.warning_count || 0,
      tasksToday: tasks.length || 0,
      runningDays: data.running_days || 0
    }
  };
};

export const apiGetCurrentWarnings = async () => {
  const data = await getScreenAllData();
  const list = data.warning_list || [];
  return {
    code: 200,
    data: list.map((item: any) => ({
      point: item.tower_code || item.name || item.line_code || '预测点位',
      level: item.level || item.warning_level || '未知',
      probability: Number(item.probability_percent ?? Number(item.probability || 0) * 100),
      area: item.area || item.region || item.city || '',
      time: item.time || item.forecast_time || item.warning_time || '--',
      forecastHour: Number(item.forecast_hour || 0)
    }))
  };
};

export const apiGetRiskDistribution = async () => {
  const data = await getScreenAllData();
  return {
    code: 200,
    data: data.risk_distribution_by_region || { cities: [], level1: [], level2: [], level3: [], level4: [], level5: [] }
  };
};

export const apiGetWarningTrends = async () => {
  const data = await getScreenAllData();
  const predictionTrend = data.prediction_hourly_trend;
  if (predictionTrend?.hours?.length) {
    return {
      code: 200,
      data: predictionTrend
    };
  }
  const trend = data.warning_trend || [];
  return {
    code: 200,
    data: {
      hours: trend.map((_: any, index: number) => index + 1),
      series: []
    }
  };
};

export const apiGetTaskStatus = async () => {
  const data = await getScreenAllData();
  const rows = getTaskRows(data);
  const statusMap: Record<string, string> = {
    created: '已创建',
    submitted: '已提交',
    queued: '排队中',
    running: '运行中',
    success: '已完成',
    failed: '失败',
    stopped: '已停止'
  };
  return {
    code: 200,
    data: rows.map((item: any) => ({
      id: item.taskCode || item.task_code || '',
      name: item.taskName || item.task_name || item.taskCode || '算法任务',
      model: item.algorithmName || item.algorithmId || '-',
      type: item.taskType || '-',
      status: statusMap[String(item.status || '').toLowerCase()] || item.status || '未知',
      time: item.startTime || item.createTime || '--',
      updateTime: item.updateTime || '--',
      progress: Number(item.progress ?? 0)
    }))
  };
};

export const apiGetSystemOverview = async () => {
  try {
    const data = unwrap(await request.get('/algorithm/server/health'));
    return {
      code: 200,
      data: {
        status: data.status || 'offline',
        service: data.service || 'algorithm-server',
        version: data.version || '-',
        cpuUsage: data.cpu_usage ?? data.cpuUsage ?? 0,
        gpuUsage: data.gpu_usage ?? data.gpuUsage ?? 0,
        memoryUsage: data.memory_usage ?? data.memoryUsage ?? 0
      }
    };
  } catch {
    return { code: 200, data: { status: 'offline', service: 'algorithm-server', version: '-', cpuUsage: 0, gpuUsage: 0, memoryUsage: 0 } };
  }
};

export const apiGetSystemNotices = async () => {
  const data = unwrap(await request.get('/monitor/notices', { params: { limit: 10 } }));
  const rows = data?.rows || data || [];
  return {
    code: 200,
    data: {
      rows: Array.isArray(rows) ? rows : [],
      total: Number(data?.total || 0),
      unreadCount: Number(data?.unreadCount || 0)
    }
  };
};

export const apiReadSystemNotice = async (noticeId: number) => {
  const response: any = await request.post(`/monitor/notices/${noticeId}/read`);
  if (response?.code !== undefined && ![0, 200].includes(Number(response.code))) {
    throw new Error(response.msg || '公告已读状态保存失败');
  }
  const data = unwrap(response);
  return { code: 200, data };
};

const weatherLogContent = (item: any) => {
  const parts = [
    item.temperature !== null && item.temperature !== undefined ? `温度${item.temperature}℃` : '',
    item.humidity !== null && item.humidity !== undefined ? `湿度${item.humidity}%` : '',
    item.wind_speed !== null && item.wind_speed !== undefined ? `风速${item.wind_speed}m/s` : '',
    item.precipitation !== null && item.precipitation !== undefined ? `降水${item.precipitation}mm` : ''
  ].filter(Boolean);
  const place = [item.region, item.station].filter(Boolean).join(' ');
  return `${place}${parts.length ? `：${parts.join('，')}` : ''}`;
};

export const apiGetLatestLogs = async () => {
  const data = await getScreenAllData();
  const weatherLogs = (data.weather_timeline || []).map((item: any) => ({
    type: '气象',
    content: weatherLogContent(item),
    time: item.time || ''
  }));
  const warnings = (data.warning_list || []).map((item: any) => ({
    type: '预警',
    content: `${item.region || item.city || ''}${item.name || item.warning_type || ''}，等级：${normalizeLevelName(item.level || '')}`,
    time: item.time || ''
  }));
  const tasks = (await apiGetTaskStatus()).data.slice(0, 5).map((item: any) => ({
    type: '任务',
    content: `${item.name}，${item.status}`,
    time: item.time
  }));
  return {
    code: 200,
    data: [...weatherLogs, ...warnings, ...tasks]
      .filter(item => item.content)
      .sort((a, b) => String(a.time || '').localeCompare(String(b.time || '')))
  };
};

export const apiGetMapData = async () => {
  const data = await getScreenAllData();
  if (Array.isArray(data.map_points) && data.map_points.length > 0) {
    return { code: 200, data: data.map_points };
  }

  const warnings = data.warning_list || [];
  const points = warnings.map((item: any) => {
    const cityName = Object.keys(cityCoords).find(city => String(item.area || item.region || item.city || '').includes(city));
    if (!cityName) return null;
    const coords = cityCoords[cityName];
    const level = normalizeLevelName(item.level || item.warning_level || '');
    const value = level === '红色' ? 95 : level === '橙色' ? 75 : level === '黄色' ? 55 : level === '蓝色' ? 35 : 0;
    return {
      name: `${cityName}-${item.name || item.warning_type || '预警'}`,
      region: cityName,
      value: [coords[0], coords[1], value]
    };
  }).filter(Boolean);
  return { code: 200, data: points };
};
