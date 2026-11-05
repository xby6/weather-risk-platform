# 任务管理与运行记录

任务管理页面新增以下功能：

- 点击任务行的「运行记录」，分页查看状态、进度、运行信息和错误的变化，最新记录在前。
- 用创建日期、任务状态、算法、区域和关键词筛选任务；「运行中」包含已提交和排队中的任务。
- 点击「导出筛选记录」，导出全部匹配任务的 CSV，不受当前列表页码限制。
- 在运行记录弹窗中点击「导出当前页记录」，导出当前页日志。CSV 使用 UTF-8 BOM，支持中文、换行和引号。
- 执行中的任务禁止重复提交；提交前使用数据库行锁确认状态，并持久化「已提交」记录。

## 数据与部署

运行记录保存到 MySQL 的 `algorithm_task_history` 表，与任务状态更新在同一事务中提交。重复轮询且状态、进度、信息和错误均未变化时不新增记录；仅查询结果文件也不新增状态记录。

首次使用时，后端会在表不存在时创建该表。如果应用数据库账号没有建表权限，请由数据库管理员在部署前执行：

`ruoyi-fastapi-backend/sql/algorithm_task_history_20261006.sql`

已存在的任务从启用功能后的首次变化开始记录，旧的状态变化无法补录。记录时间为后端数据库时间，不代表算法服务内部每条日志的发生时间。删除任务会同时删除其运行记录。此功能保留状态变化，不归档每次运行的结果文件。

接口：`GET /algorithm/task/history/{task_code}?pageNum=1&pageSize=20`。页码至少为 1，每页 1–100 条。

## 验证

前端目录执行：

```powershell
npm run test:tasks
npm run build:prod
```

若完整构建触及 Node 默认堆内存上限，可在前端目录使用更高的本次进程内存额度：

```powershell
node --max-old-space-size=8192 node_modules/vite/bin/vite.js build
```

后端目录执行：

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_algorithm*.py' -v
```

后端测试使用内存 SQLite 验证实际读写和事务回滚，适配 MySQL 的 `NOW()` 和 `FOR UPDATE` 语法；并验证 FastAPI 分页接口。MySQL 的真实行锁并发行为需要部署环境联调确认。
