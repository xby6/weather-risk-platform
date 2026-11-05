import { reactive } from 'vue'
import request from '../utils/request'

export type MapView = 'blue' | 'terrain' | 'flat'
function initialMapView(): MapView {
  try {
    const saved = localStorage.getItem('weather-screen-map-view')
    if (saved === 'terrain' || saved === 'flat') return saved
  } catch { /* Storage may be disabled by the browser. */ }
  return 'blue'
}

export const screenStore = reactive({
  selectedCity: '',
  selectedCityLabel: '辽宁省',
  refreshKey: 0,
  city: '',
  weather: '',
  temperatureRange: '',
  stationCount: 0,
  warningCount: 0,
  riskCount: 0,
  temperature: null as number | null,
  humidity: null as number | null,
  windSpeed: null as number | null,
  pressure: null as number | null,
  warningList: [] as any[],
  riskDistribution: [] as any[],
  warningTrend: [] as any[],
  mapPointMenuOpen: false,
  mapView: initialMapView()
})

export function setMapView(view: MapView) {
  screenStore.mapView = view
  try { localStorage.setItem('weather-screen-map-view', view) } catch { /* Optional preference. */ }
}

const unwrap = (res: any) => {
  if (!res) return {}
  if (res.code === 200 || res.code === 0) return res.data || {}
  if (res.data && (res.data.code === 200 || res.data.code === 0)) return res.data.data || {}
  return res.data || res
}

export const getScreenQueryParams = () => {
  return screenStore.selectedCity ? { city: screenStore.selectedCity } : {}
}

export const fetchScreenAllData = async () => {
  try {
    const res = await request.get('/monitor/screen-all-data', { params: getScreenQueryParams() })
    const data = unwrap(res)
    screenStore.city = data.city || screenStore.selectedCity || ''
    screenStore.weather = data.weather || ''
    screenStore.temperatureRange = data.temperature_range || ''
    screenStore.stationCount = data.station_count || 0
    screenStore.warningCount = data.warning_count || 0
    screenStore.riskCount = data.risk_count || 0
    screenStore.temperature = data.temperature ?? null
    screenStore.humidity = data.humidity ?? null
    screenStore.windSpeed = data.wind_speed ?? null
    screenStore.pressure = data.pressure ?? null
    screenStore.warningList = data.warning_list || []
    screenStore.riskDistribution = data.risk_distribution || []
    screenStore.warningTrend = data.warning_trend || []
  } catch (error) {
    console.error('大屏数据请求失败：', error)
  }
}

export const setSelectedCity = async (city: string) => {
  screenStore.selectedCity = city
  screenStore.selectedCityLabel = city || '辽宁省'
  screenStore.refreshKey += 1
  await fetchScreenAllData()
}

export const clearSelectedCity = async () => {
  screenStore.selectedCity = ''
  screenStore.selectedCityLabel = '辽宁省'
  screenStore.refreshKey += 1
  await fetchScreenAllData()
}
