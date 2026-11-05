from fastapi import APIRouter

# 路由前缀 /api/demo，框架自动识别
router = APIRouter(prefix="/api/demo", tags=["演示数据接口"])


@router.get("/get-data")
async def get_demo_data():
    """获取测试数据"""
    # 这里后续替换成 查数据库真实数据
    return {
        "code": 200,
        "msg": "查询成功",
        "data": {
            "name": "测试数据",
            "value": 12345,
            "desc": "前后端连通测试"
        }
    }