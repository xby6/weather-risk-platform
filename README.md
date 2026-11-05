# 辽宁电力气象智能网格预报预警信息系统

集成气象监测、杆塔故障风险预测、算法任务管理、运行记录、AI 分析报告与三维地图大屏的项目源码。

## 项目结构

| 目录 | 内容 |
| --- | --- |
| `02_RuoYi_Admin/ruoyi-fastapi-backend` | FastAPI 后台、权限、任务及报告接口 |
| `02_RuoYi_Admin/ruoyi-fastapi-frontend` | Vue 3 后台管理界面 |
| `03_AI_Algorithm_Platform` | 算法运行与模型服务 |
| `Big_Screen` | Vue 3 / Three.js / ECharts 可视化大屏 |

## 本地运行

1. 参照各子项目 README 安装 Python / Node.js 依赖并初始化 MySQL、Redis。
2. 将各目录 `.env.example` 复制为模板注释指定的配置文件，填写本机连接信息及新的随机密钥。
3. 后端入口与部署参数见 `02_RuoYi_Admin/README.md`；算法平台接口见 `03_AI_Algorithm_Platform/README.md`。
4. 管理前端和大屏分别执行 `npm ci`、`npm run dev`。
5. AI 报告需要单独配置模型 API，参见 `02_RuoYi_Admin/AI_REPORT_README.md`。

## 功能说明

- [任务运行记录](02_RuoYi_Admin/TASK_HISTORY_README.md)
- [AI 分析报告](02_RuoYi_Admin/AI_REPORT_README.md)
- [三维地图与地理监测](Big_Screen/CASE12_VISUALIZATION_README.md)

本仓库是当前源码的独立快照。环境密钥、数据库内容、上传数据、模型权重、依赖目录、录屏及个人文稿保留在本地。部署需自行准备配置、模型和业务数据。

保留各子项目原有许可证与第三方署名；地形数据来源见 `Big_Screen/src/assets/terrain/SOURCE_ATTRIBUTION.md`。
