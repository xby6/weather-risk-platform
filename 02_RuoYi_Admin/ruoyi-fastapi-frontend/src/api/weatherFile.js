import request from '@/utils/request'

export function listWeatherFiles() {
  return request({ url: '/weather-file/list', method: 'get' })
}

export function createWeatherFile(data) {
  return request({ url: '/weather-file/create', method: 'post', data })
}

export function createWeatherFolder(data) {
  return request({ url: '/weather-file/folder/create', method: 'post', data })
}

export function uploadWeatherFile(file, parentId = 0) {
  const data = new FormData()
  data.append('file', file)
  data.append('parent_id', parentId)
  return request({
    url: '/weather-file/upload',
    method: 'post',
    data,
    headers: {
      'Content-Type': 'multipart/form-data',
      encrypt: false,
      encryptResponse: false,
      repeatSubmit: false
    },
    timeout: 60000
  })
}

export function moveWeatherFile(data) {
  return request({ url: '/weather-file/move', method: 'post', data })
}

export function copyWeatherFile(data) {
  return request({ url: '/weather-file/copy', method: 'post', data })
}

export function processWeatherFile(id) {
  return request({ url: `/weather-file/process/${id}`, method: 'post' })
}

export function deleteWeatherFile(id) {
  return request({ url: `/weather-file/${id}`, method: 'delete' })
}
