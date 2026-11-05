import request from '@/utils/request'

export function checkAlgorithmServer(serverUrl) {
  return request({ url: '/algorithm/server/health', method: 'get', params: { serverUrl } })
}

export function listAlgorithmServers() {
  return request({ url: '/algorithm/server/list', method: 'get' })
}

export function createAlgorithmServer(data) {
  return request({ url: '/algorithm/server/create', method: 'post', data })
}

export function deleteAlgorithmServer(id) {
  return request({ url: `/algorithm/server/${id}`, method: 'delete' })
}

export function listAlgorithmModels(params) {
  return request({ url: '/algorithm/model/list', method: 'get', params })
}

export function syncAlgorithmModels(serverUrl) {
  return request({ url: '/algorithm/model/sync', method: 'post', params: { serverUrl } })
}

export function createAlgorithmModel(data) {
  return request({ url: '/algorithm/model/create', method: 'post', data })
}

export function uploadAlgorithmModel(data) {
  return request({
    url: '/algorithm/model/upload',
    method: 'post',
    data,
    headers: { 'Content-Type': 'multipart/form-data', repeatSubmit: false },
    timeout: 120000
  })
}

export function updateAlgorithmModelStatus(id, status) {
  return request({ url: `/algorithm/model/${id}/status`, method: 'put', data: { status } })
}

export function deleteAlgorithmModel(id) {
  return request({ url: `/algorithm/model/${id}`, method: 'delete' })
}

export function listAlgorithmTasks() {
  return request({ url: '/algorithm/task/list', method: 'get' })
}

export function createAlgorithmTask(data) {
  return request({ url: '/algorithm/task/create', method: 'post', data })
}

export function runAlgorithmTask(taskCode) {
  return request({ url: `/algorithm/task/run/${taskCode}`, method: 'post' })
}

export function getAlgorithmTaskStatus(taskCode) {
  return request({ url: `/algorithm/task/status/${taskCode}`, method: 'get' })
}

export function getAlgorithmTaskHistory(taskCode, params) {
  return request({ url: `/algorithm/task/history/${encodeURIComponent(taskCode)}`, method: 'get', params })
}

export function getAlgorithmTaskResult(taskCode) {
  return request({ url: `/algorithm/task/result/${taskCode}`, method: 'get' })
}

export function downloadAlgorithmTaskResult(taskCode) {
  return request({
    url: `/algorithm/task/result-file/${taskCode}`,
    method: 'get',
    responseType: 'blob',
    timeout: 120000
  })
}

export function deleteAlgorithmTask(taskCode) {
  return request({ url: `/algorithm/task/${taskCode}`, method: 'delete' })
}
