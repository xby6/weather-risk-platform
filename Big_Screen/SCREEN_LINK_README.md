# 大屏与 RuoYi 后端互连说明

本版本已经将 Big_Screen 前端的数据请求改为对接已互连的 RuoYi-Vue3-FastAPI 后端。

## 1. 已对接的后端接口

大屏前端通过 `src/api/index.ts` 统一请求后端数据，目前主要对接：

```text
GET /monitor/screen-all-data
GET /algorithm/task/list
GET /algorithm/server/health
```

开发环境下，前端请求前缀为 `/api`，Vite 代理会把请求转发到 RuoYi 后端：

```text
/api/monitor/screen-all-data      -> http://127.0.0.1:9099/monitor/screen-all-data
/api/algorithm/task/list          -> http://127.0.0.1:9099/algorithm/task/list
/api/algorithm/server/health      -> http://127.0.0.1:9099/algorithm/server/health
```

## 2. 已修改内容

```text
src/api/index.ts                  统一封装大屏接口，接入 RuoYi 后端和任务接口
src/store/screenData.ts           修复响应结构解析问题
src/utils/request.ts              支持 VITE_APP_BASE_API 配置
src/pages/center/SystemOverview.vue 由占位页面改为算法服务状态面板
src/pages/screen-header/ScreenHeader.vue 顶部天气信息改为后端动态数据
.env.development                  新增开发环境接口前缀
.env.production                   新增生产环境接口前缀
```

## 3. 启动顺序

先启动 algorithm-server：

```bash
cd 03_AI_Algorithm_Platform
python app/main.py
```

再启动 RuoYi 后端：

```bash
cd 02_RuoYi_Admin/ruoyi-fastapi-backend
python app.py
```

最后启动大屏：

```bash
cd Big_Screen
npm install
npm run dev
```

默认访问：

```text
http://127.0.0.1:6688
```

## 4. 注意事项

如果你的 RuoYi 后端端口不是 `9099`，请修改 `vite.config.ts` 中的代理地址：

```ts
target: 'http://127.0.0.1:9099'
```

如果生产部署到 Nginx，建议配置：

```nginx
location /screen/ {
    proxy_pass http://screen-web/;
}

location /api/ {
    proxy_pass http://backend:9099/;
}
```

当前版本已经能展示 RuoYi 后端的大屏模拟数据、算法任务列表和 algorithm-server 健康状态。后续如果后端增加真实气象数据库和预警表，只需要在 RuoYi 后端替换 `/monitor/screen-all-data` 的数据来源即可。
