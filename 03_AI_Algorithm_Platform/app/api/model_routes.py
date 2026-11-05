from fastapi import APIRouter, UploadFile, File, Form, Response
import yaml
import json
from pathlib import Path

# 创建路由实例
model_routes = APIRouter()
# 配置文件路径
CONFIG_PATH = Path("./model_config.yaml")

# 定义创建模型的接口
@model_routes.post("/create_model")
async def create_model(
    file: UploadFile = File(...),  # 上传的模型文件
    model_name: str = Form(...),   # 模型名称
    intro: str = Form(""),        # 模型简介
):
    try:
        # 加载配置文件
        config = yaml.safe_load(CONFIG_PATH.read_text()) or {"models": {}}
        # 检查模型是否已存在
        if model_name in config["models"]:
            return Response(status_code=400, content="Model already exists")

        # 定义模型文件保存路径
        model_path = Path(f"./model/{file.filename}")
        # 保存上传的模型文件
        model_path.write_bytes(await file.read())

        # 更新配置文件中的模型信息
        config["models"][model_name] = {
            "intro": intro,
            "file": str(model_path)
        }
        # 将更新后的配置写回文件
        CONFIG_PATH.write_text(yaml.safe_dump(config))
        return Response(content=f"Model {model_name} created", status_code=200)
    except Exception as e:
        # 发生异常时返回 500 错误
        return Response(status_code=500, content=str(e))

# 定义删除模型的接口
@model_routes.post("/delete_model")
async def delete_model(model_name: str = Form(...)):
    try:
        # 加载配置文件
        config = yaml.safe_load(CONFIG_PATH.read_text())
        # 检查模型是否存在
        if model_name not in config["models"]:
            return Response(status_code=404, content="Model not found")

        # 获取模型文件路径
        model_path = Path(config["models"][model_name]["file"])
        # 如果模型文件存在, 则删除文件
        if model_path.exists():
            model_path.unlink()

        # 从配置中删除模型信息
        del config["models"][model_name]
        # 将更新后的配置写回文件
        CONFIG_PATH.write_text(yaml.safe_dump(config))
        return Response(content=f"Model {model_name} deleted", status_code=200)
    except Exception as e:
        # 发生异常时返回 500 错误
        return Response(status_code=500, content=str(e))

# 定义获取模型列表的接口
@model_routes.get("/model_list")
async def model_list():
    try:
        # 加载配置文件
        config = yaml.safe_load(CONFIG_PATH.read_text())
        # 提取模型名称和简介
        models = {
            name: {"intro": info["intro"], "file": info["file"]}
            for name, info in config["models"].items()
        }
        # 返回 JSON 格式的模型列表
        return Response(
            content=json.dumps(models),
            media_type="application/json"
        )
    except Exception as e:
        # 发生异常时返回 500 错误
        return Response(status_code=500, content=str(e))