# 可执行算法包上传规范

本文件保留为兼容旧入口。最新、完整的算法和模型开发规范见：

```text
ALGORITHM_MODEL_DEVELOPMENT_SPEC.md
```

核心要求如下：

1. 上传单个 Python 算法文件时，入口填写 `algorithm.py:run`。
2. 上传 ZIP 算法包时，包内必须包含入口文件，例如 `algorithm.py`。
3. 当前 algorithm-server 对上传算法的调用方式为：

```python
def run(input_data: dict) -> dict:
    ...
```

4. 文件任务输入通过 `input_data["input_file"]`、`input_data["training_file"]`、`input_data["output_dir"]` 和 `input_data["params"]` 获取。
5. 结果文件必须写入 `output_dir`。
6. 返回结果必须是标准字典，不能只返回字符串。
7. 真实调用上传模型成功时，必须返回 `used_real_model: true`。

标准模板文件：

```text
algorithm.py
```
