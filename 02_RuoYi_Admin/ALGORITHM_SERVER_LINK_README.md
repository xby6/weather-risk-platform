# RuoYi-Vue3-FastAPI 与 algorithm-server 互连说明

本次改造已完成 RuoYi 后台与独立 algorithm-server 的基础互连闭环。

## 1. 已新增 / 修改内容

### algorithm-server
新增标准接口：

- `GET /api/health`：算法服务器健康检查
- `GET /api/algorithms`：获取算法列表
- `GET /api/models`：获取模型文件列表
- `POST /api/tasks/run`：提交 JSON 算法任务
- `GET /api/tasks/status/{task_id}`：查询任务状态
- `GET /api/tasks/result/{task_id}`：获取任务结果
- `GET /api/tasks`：查看 algorithm-server 内存任务列表

新增算法文件：

- `algo/icing_forecast.py`：输电线路覆冰预测模拟算法
- `algo/wind_risk_forecast.py`：大风风险预测模拟算法
- `algo/comprehensive_risk.py`：综合电力气象风险模拟算法

保留原有接口：

- `/create`
- `/delete`
- `/update`
- `/list`
- `/process`
- `/stop`
- `/running-tasks`
- `/logs`

因此，原来的 ZIP 图像检测接口没有删除，新加的是给 RuoYi 后台调用的 JSON 标准接口。

### RuoYi 后端
新增文件：

- `module_admin/service/algorithm_client.py`
- `module_admin/service/algorithm_task_store.py`
- `module_admin/controller/algorithm_link_controller.py`

新增后端接口：

- `GET /algorithm/server/health`
- `GET /algorithm/model/list`
- `GET /algorithm/task/list`
- `POST /algorithm/task/create`
- `POST /algorithm/task/run/{task_code}`
- `GET /algorithm/task/status/{task_code}`
- `GET /algorithm/task/result/{task_code}`
- `DELETE /algorithm/task/{task_code}`

默认算法服务器地址：

```text
http://127.0.0.1:8000
```

也可以通过环境变量覆盖：

```bash
ALGORITHM_SERVER_URL=http://你的算法服务器IP:8000
```

### RuoYi 前端
新增文件：

- `src/api/algorithm.js`

修改文件：

- `src/views/task/index.vue`

现在任务管理页面已经从 Mock 数据改为真实请求后端接口，支持：

- 测试 algorithm-server 连接
- 同步算法列表
- 新建算法任务
- 提交任务运行
- 查询任务状态
- 获取任务结果
- 删除本地任务记录

## 2. 启动顺序

### 第一步：启动 algorithm-server

进入 algorithm-server 根目录，例如：

```bash
cd 03_AI_Algorithm_Platform
python app/main.py
```

启动后访问：

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/api/health
```

### 第二步：启动 RuoYi 后端

进入 RuoYi 后端目录：

```bash
cd ruoyi-fastapi-backend
python app.py
```

后端默认端口为：

```text
http://127.0.0.1:9099
```

由于项目配置中 `app_root_path = /dev-api`，前端会通过 `/dev-api` 访问后端。

### 第三步：启动 RuoYi 前端

进入前端目录：

```bash
cd ruoyi-fastapi-frontend
npm install
npm run dev
```

进入“任务管理”页面，依次点击：

1. 测试连接
2. 同步算法
3. 新增任务
4. 保存并运行
5. 查状态
6. 看结果

## 3. 已验证链路

已验证以下链路可以跑通：

```text
RuoYi 后端 algorithm_client
    ↓ HTTP
algorithm-server /api/health
    ↓
返回 online

RuoYi 后端 algorithm_client
    ↓ HTTP
algorithm-server /api/algorithms
    ↓
返回算法列表

RuoYi 后端 algorithm_client
    ↓ HTTP
algorithm-server /api/tasks/run
    ↓
运行 icing_forecast 模拟算法
    ↓
/api/tasks/status 返回 success
    ↓
/api/tasks/result 返回预测结果
```

## 4. 后续建议

当前任务记录使用 JSON 文件轻量存储，路径为：

```text
ruoyi-fastapi-backend/vf_admin/algorithm_tasks.json
```

后续正式开发时，建议迁移到 MySQL 表：

```text
algorithm_task
algorithm_model
algorithm_server
warning_info
```

真实深度学习模型接入时，只需要替换：

```text
algorithm-server/algo/icing_forecast.py
```

中的 `run(input_data)` 函数即可，建议保持输入输出 JSON 格式不变。
