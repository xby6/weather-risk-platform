from fastapi import APIRouter, UploadFile, File, Form, Response
import yaml
import json
from pathlib import Path

# 初始化路由
algorithm_routes = APIRouter()
# 配置文件路径
CONFIG_PATH = Path("./config.yaml")

# 创建算法的接口
@algorithm_routes.post("/create")
async def create_algorithm(
    file: UploadFile = File(...),
    algo_name: str = Form(""),
    args: str = Form(...),
    args_intro: str = Form(""),
    intro: str = Form(""),
):
    try:
        # 加载配置文件, 若文件不存在则创建空的算法配置
        config = yaml.safe_load(CONFIG_PATH.read_text()) or {"algorithms": {}}

        # 检查算法是否已存在
        if algo_name in config["algorithms"]:
            return Response(status_code=400, content="Algorithm already exists")

        # 确定算法文件保存路径
        algo_path = Path(f"./algo/{algo_name}.py")
        # 创建算法文件所在目录（若不存在）
        algo_path.parent.mkdir(parents=True, exist_ok=True)
        # 保存上传的算法文件
        algo_path.write_bytes(await file.read())

        # 更新配置文件中的算法信息
        config["algorithms"][algo_name] = {
            "args": args,
            "args_intro": args_intro,
            "intro": intro,
            "file": str(algo_path)
        }
        # 将更新后的配置写回文件
        CONFIG_PATH.write_text(yaml.safe_dump(config))
        return Response(content=f"Algorithm {algo_name} created", status_code=200)
    except Exception as e:
        # 发生异常时返回500错误
        return Response(status_code=500, content=str(e))

# 删除算法的接口
@algorithm_routes.post("/delete")
async def delete_algorithm(algo_name: str = Form(...)):
    try:
        # 加载配置文件, 若文件不存在则创建空的算法配置
        config = yaml.safe_load(CONFIG_PATH.read_text()) or {"algorithms": {}}
        
        # 检查算法是否存在
        if algo_name not in config["algorithms"]:
            return Response(status_code=404, content="Algorithm not found")

        # 获取算法文件路径
        algo_path = Path(config["algorithms"][algo_name]["file"])
        # 若算法文件存在则删除
        if algo_path.exists():
            algo_path.unlink()

        # 从配置中删除算法信息
        del config["algorithms"][algo_name]
        # 将更新后的配置写回文件
        CONFIG_PATH.write_text(yaml.safe_dump(config))
        return Response(content=f"Algorithm {algo_name} deleted", status_code=200)
    except Exception as e:
        # 发生异常时返回500错误
        return Response(status_code=500, content=str(e))

# 更新算法的接口
@algorithm_routes.post("/update")
async def update_algorithm(
    file: UploadFile = File(...),
    algo_name: str = Form(...),
    args: str = Form(...),
    args_intro: str = Form(...),
    intro: str = Form(...),
):
    try:
        # 加载配置文件, 若文件不存在则创建空的算法配置
        config = yaml.safe_load(CONFIG_PATH.read_text()) or {"algorithms": {}}
        
        # 检查算法是否存在
        if algo_name not in config["algorithms"]:
            return Response(status_code=404, content="Algorithm not found")

        # 确定算法文件保存路径
        algo_path = Path(f"./algo/{algo_name}.py")
        # 保存上传的算法文件
        algo_path.write_bytes(await file.read())

        # 更新配置文件中的算法信息
        config["algorithms"][algo_name] = {
            "args": args,
            "args_intro": args_intro,
            "intro": intro,
            "file": str(algo_path)
        }
        # 将更新后的配置写回文件
        CONFIG_PATH.write_text(yaml.safe_dump(config))
        return Response(content=f"Algorithm {algo_name} updated", status_code=200)
    except Exception as e:
        # 发生异常时返回500错误
        return Response(status_code=500, content=str(e))

# 列出所有算法的接口
@algorithm_routes.get("/list")
async def list_algorithms():
    try:
        # 加载配置文件
        config = yaml.safe_load(CONFIG_PATH.read_text())
        # 提取算法的基本信息
        algorithms = {
            name: {"intro": info["intro"], "args_intro": info["args_intro"], "args": info["args"]}
            for name, info in config["algorithms"].items()
        }
        return Response(content=json.dumps(algorithms), media_type="application/json")
    except Exception as e:
        # 发生异常时返回500错误
        return Response(status_code=500, content=str(e))