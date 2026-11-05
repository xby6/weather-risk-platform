# 算法、模型文件书写开发统一规范

本文档用于约束本系统后续新增算法、模型文件的开发方式。目标是保证算法能够被后台管理页面上传、同步到 `algorithm-server`、创建任务、真实执行、生成结果文件，并把结果回写到 `algorithm_task.result_json` 后供后台和大屏读取。

## 1. 接入链路

```text
后台管理前端上传算法/模型
-> RuoYi 后端保存 algorithm_model 记录
-> 同步到独立 algorithm-server
-> 任务管理选择算力平台、算法模型、数据文件和参数
-> algorithm-server 调用 /api/tasks/run 或 /api/tasks/run-file
-> 算法入口函数执行
-> 返回标准 JSON，必要时生成 Excel/CSV/图片文件
-> RuoYi 后端写回 algorithm_task.result_json
-> 后台结果弹窗和大屏读取真实预测数据
```

## 2. 基本原则

1. 算法文件必须能被 `algorithm-server` 独立加载和执行。
2. 算法不得直接依赖前端页面、浏览器、`localStorage`。
3. 算法不得直接连接 MySQL 或 Redis，数据库读写由平台统一处理。
4. 算法不得写死本机绝对路径，例如 `D:\xxx\file.xlsx`。
5. 算法不得自行启动 FastAPI、Flask、Uvicorn 等服务。
6. 算法必须提供统一入口函数。
7. 算法必须返回标准结构化结果，不能只返回普通字符串。
8. 生成的结果文件必须写入本次任务的 `output_dir`。
9. 真实模型执行成功时，返回结果必须包含 `used_real_model: true`。
10. 所有新增算法都必须遵守本规范，不只针对 TabPFN。

## 3. 推荐算法包结构

推荐上传 `.zip` 算法包：

```text
algorithm.zip
├── algorithm.py
├── model.pkl
├── requirements.txt
└── README.md
```

也可以上传单个 `.py` 文件，但必须包含统一入口函数，并在上传时填写入口：

```text
algorithm.py:run
```

## 4. 算法元信息

算法文件应声明 `ALGORITHM_META`：

```python
ALGORITHM_META = {
    "algorithm_id": "tabpfn_fault_forecast",
    "algorithm_name": "TabPFN杆塔故障概率预测",
    "version": "v1.0.0",
    "algorithm_type": "tabular_forecast",
    "input_type": "file",
    "output_type": "excel_json",
    "entrypoint": "algorithm.py:run",
    "run_api": "/api/tasks/run-file",
    "description": "基于历史气象数据预测未来逐小时杆塔故障概率和风险等级",
}
```

字段说明：

```text
algorithm_id      算法唯一编号，不能重复
algorithm_name    算法显示名称
version           算法版本
algorithm_type    算法类型，例如 icing、tabular_cv、tabular_forecast
input_type        输入类型，例如 json、file、xlsx、csv
output_type       输出类型，例如 json、excel_json、file
entrypoint        算法入口，例如 algorithm.py:run
run_api           运行接口，文件任务使用 /api/tasks/run-file
description       算法说明
```

## 5. 统一入口函数

当前系统上传算法包的真实运行时调用方式为：

```python
def run(input_data: dict) -> dict:
    ...
```

因此新增算法必须提供单参数入口。算法可以在函数内部拆分出 `params` 和上下文：

```python
def run(input_data: dict) -> dict:
    task_id = input_data.get("task_id")
    algorithm_id = input_data.get("algorithm_id")
    model_id = input_data.get("model_id")
    input_file = input_data.get("input_file")
    training_file = input_data.get("training_file")
    output_dir = input_data.get("output_dir")
    params = input_data.get("params") or {}
```

常用 `input_data` 字段：

```text
task_id          任务编号
algorithm_id     算法编号
model_id         模型编号
input_file       待预测文件绝对路径
training_file    历史训练文件绝对路径，可选
output_dir       本次任务输出目录
params           前端任务参数
model_path       静态模型文件路径，可选
```

## 6. 输入文件规范

Excel/CSV 输入文件要求：

1. 第一行为字段名，或由算法参数明确指定表头行。
2. 不建议使用合并单元格。
3. 不建议使用复杂多级表头。
4. 时间字段建议统一为 `time`、`datetime` 或 `forecast_time`。
5. 城市字段建议统一为 `city`。
6. 点位、线路、杆塔字段建议使用 `station_name`、`point_name`、`line_name`、`tower_id`。
7. 数值字段必须能转换为数字。
8. 缺失值由算法自行处理，并应在结果说明中体现。

杆塔故障概率预测推荐字段：

```text
time
city
line_name
tower_id
temperature
humidity
wind_speed
wind_direction
precipitation
pressure
icing_thickness
history_fault
```

历史训练文件必须包含目标字段，例如：

```text
is_fault
```

或：

```text
是否为故障杆塔
```

待预测文件不要求包含目标字段。

## 7. 标准返回结果

执行成功时返回：

```python
return {
    "success": True,
    "status": "success",
    "task_id": task_id,
    "algorithm_id": algorithm_id,
    "algorithm_name": "算法名称",
    "model_id": model_id,
    "used_real_model": True,
    "message": "任务执行成功",
    "result_type": "file",
    "output_file": "结果文件绝对路径",
    "output_filename": "结果文件名.xlsx",
    "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "result": [],
    "charts": [],
    "summary": {
        "total_records": 240,
        "forecast_hours": 24,
        "max_fault_probability": 0.82,
        "high_risk_count": 12
    },
    "error": None
}
```

执行失败时返回：

```python
return {
    "success": False,
    "status": "failed",
    "used_real_model": False,
    "message": "任务执行失败",
    "result_type": "json",
    "output_file": "",
    "output_filename": "",
    "result": [],
    "charts": [],
    "summary": {},
    "error": "具体错误信息"
}
```

## 8. 结果文件规范

如果算法生成 Excel，推荐包含以下工作表：

```text
未来故障预测
概率等级统计
逐小时结果
总体统计
任务说明
可视化图表
```

如果算法生成 CSV，应至少包含：

```text
forecast_time
city
line_name
tower_id
fault_probability
risk_level
used_real_model
```

结果文件必须位于 `output_dir` 内，否则 algorithm-server 会拒绝下载。

## 9. 杆塔故障预测字段规范

逐小时预测类结果建议包含：

```text
forecast_time         预测时间
forecast_hour         预测小时序号
city                  城市
line_name             线路名称
tower_id              杆塔编号
fault_probability     故障概率，0 到 1
risk_level            风险等级
probability_level     概率等级
used_real_model       是否真实调用模型
```

统一风险等级建议：

```text
低      fault_probability < 0.25
一般    0.25 <= fault_probability < 0.50
较高    0.50 <= fault_probability < 0.75
高      fault_probability >= 0.75
```

如算法内部使用英文等级，也必须在 `summary` 或 Excel 说明中明确映射关系。

## 10. 模型文件规范

允许的模型文件类型：

```text
.pkl
.joblib
.pt
.pth
.onnx
.py
.zip
```

要求：

1. 模型加载逻辑由算法入口文件负责。
2. 模型路径必须来自 `input_data["model_path"]` 或 `params["model_path"]`。
3. 不得写死模型文件路径。
4. 模型加载失败时必须返回明确错误。
5. 如果没有真实加载模型，不得返回 `used_real_model: true`。

## 11. 禁止写法

算法文件中禁止出现：

```python
uvicorn.run(...)
app = FastAPI()
pymysql.connect(...)
redis.Redis(...)
open("D:\\xxx\\xxx.xlsx")
```

禁止只返回字符串：

```python
return "运行成功"
```

必须返回标准字典。

## 12. 接入验收标准

新增算法正式接入系统前，必须满足：

1. 能在算力平台管理页面上传成功。
2. 能写入 `algorithm_model` 表。
3. 能同步到 `algorithm-server`。
4. 能在任务管理页面被选择。
5. 能选择历史训练文件或待预测文件。
6. 能通过 `/api/tasks/run` 或 `/api/tasks/run-file` 执行。
7. 能返回标准 `result_json`。
8. 能生成可下载结果文件。
9. 项目重启后仍能查看历史结果。
10. 大屏能读取预测风险、风险等级分布和逐小时趋势。
11. 真实模型执行成功时，结果中必须有 `used_real_model: true`。

## 13. 标准模板文件

项目根目录已提供标准模板：

```text
03_AI_Algorithm_Platform/algorithm.py
```

后续新增算法可以复制该文件，修改：

```text
ALGORITHM_META
_load_model
_predict_probability
run
```

其余返回格式、结果文件写入和异常处理建议保持一致。
