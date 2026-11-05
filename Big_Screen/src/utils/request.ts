import axios from 'axios';

// Create axios instance
const service = axios.create({
  baseURL: import.meta.env.VITE_APP_BASE_API || '/api',
  timeout: 8000
});

service.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
}, error => {
  return Promise.reject(error);
});

service.interceptors.response.use(
  (response) => {
    // 直接返回后端的 data（即 {code, msg, data}）
    return response.data;
  },
  (error) => {
    if (error.response?.status === 401) {
      console.error('登录已过期，请重新登录');
    }
    return Promise.reject(error);
  }
);
export default service;
