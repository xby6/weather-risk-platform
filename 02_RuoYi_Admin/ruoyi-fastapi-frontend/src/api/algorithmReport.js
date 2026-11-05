import request from '@/utils/request'

const root = '/algorithm/report'
export const getReportConfig = () => request({ url: `${root}/config`, method: 'get' })
export const saveReportConfig = data => request({ url: `${root}/config`, method: 'put', data })
export const listReportModels = () => request({ url: `${root}/models`, method: 'get' })
export const listTaskReports = code => request({ url: `${root}/task/${encodeURIComponent(code)}`, method: 'get' })
export const createTaskReport = (code, regenerate = false) => request({
  url: `${root}/task/${encodeURIComponent(code)}`, method: 'post', params: { regenerate }, timeout: 120000
})
export const getTaskReport = id => request({ url: `${root}/${encodeURIComponent(id)}`, method: 'get' })
export const retryTaskReport = id => request({ url: `${root}/${encodeURIComponent(id)}/retry`, method: 'post' })
export const downloadTaskReport = id => request({ url: `${root}/${encodeURIComponent(id)}/download`, method: 'get', responseType: 'blob' })
