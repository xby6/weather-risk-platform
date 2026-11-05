# TabPFN 接口联调模型

`tabpfn_interface_smoke_v1.pkl` 用于验证系统的模型上传、算法登记、任务执行和结果查询接口。

它是一个无第三方依赖的可执行 Pickle 模型，能够被当前 algorithm-server 加载。它不是训练后的 TabPFN 权重，也不能用于业务预测。真实 TabPFN 模型仍需要授权下载基础权重，并使用训练数据生成拟合模型文件。

## 上传字段

- `algorithmId`: `tabpfn_interface_smoke_v1`
- `algorithmName`: `TabPFN接口联调模型（非真实推理）`
- `algorithmType`: `tabular`
- `version`: `v1.0-smoke`
- `featureOrder`: `temperature,humidity,wind_speed,wind_direction,precipitation,history_icing_thickness`

## 直接上传到 algorithm-server

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/models/upload `
  -F "file=@tabpfn_interface_smoke_v1.pkl" `
  -F "algorithmId=tabpfn_interface_smoke_v1" `
  -F "algorithmName=TabPFN接口联调模型（非真实推理）" `
  -F "algorithmType=tabular" `
  -F "version=v1.0-smoke" `
  -F "featureOrder=temperature,humidity,wind_speed,wind_direction,precipitation,history_icing_thickness" `
  -F "remark=仅用于接口联调，不是真实TabPFN模型"
```

上传后可通过 `GET /api/models` 和 `GET /api/algorithms` 检查模型与算法记录。

也可以在后台依次完成：上传模型、上传气象 Excel/CSV、进入任务管理选择模型和气象文件、点击“保存并运行”。文件任务会逐行执行上传模型，并把批量结果写回任务结果。

如果后续上传按 Excel 全部数值列训练的模型，请在上传窗口把“输入特征”填写为 `__file_columns__`；algorithm-server 将按文件有效列的原始顺序传入特征向量。

## 任务测试

```json
{
  "task_id": "tabpfn-smoke-001",
  "algorithm_id": "tabpfn_interface_smoke_v1",
  "model_id": "tabpfn_interface_smoke_v1",
  "region": "沈阳市",
  "line_code": "TEST-LINE-001",
  "forecast_hours": 1,
  "params": {
    "temperature": -5,
    "humidity": 92,
    "wind_speed": 4.5,
    "wind_direction": 45,
    "precipitation": 1.2,
    "history_icing_thickness": 3
  }
}
```

任务结果中的 `used_real_model=true` 只表示 algorithm-server 确实加载并执行了本次上传的 `.pkl` 文件，不表示执行了真实 TabPFN 权重。
