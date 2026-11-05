FROM python:3.11.10-slim-bookworm

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 创建工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt ./

# 安装系统依赖和 Python 包
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        g++ \
        build-essential && \
    # 升级 pip 并安装依赖
    pip install --no-cache-dir --upgrade pip && \
    # 安装 PyTorch
    pip install --no-cache-dir \
        torch==2.2.1 \
        torchvision==0.17.1 \
        --index-url https://download.pytorch.org/whl/cpu && \
    # 安装 MMCV
    pip install --no-cache-dir \
        mmcv==2.2.0 \
        -f https://download.openmmlab.com/mmcv/dist/cpu/torch2.2/index.html && \
    # 安装其他依赖
    pip install --no-cache-dir -r requirements.txt && \
    # 清理 apt 缓存（但保留包信息以便后续 purge）
    rm -rf /var/lib/apt/lists/*

# 复制应用代码
COPY . .

# 编译安装 DCNv3 并清理
RUN cd ops_dcnv3 && \
    pip install --no-cache-dir -v . --no-build-isolation && \
    cd .. && \
    # 用本地 ultralytics 覆盖已安装的库
    SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])") && \
    ULTRALYTICS_PATH="$SITE_PACKAGES/ultralytics" && \
    rm -rf "$ULTRALYTICS_PATH" && \
    cp -r ./ultralytics "$ULTRALYTICS_PATH" && \
    pip uninstall -y opencv-python-headless opencv-python && \
    pip install opencv-python-headless==4.10.0.82 && \
    # 删除不需要的文件
    rm -rf ./ultralytics \
           ./ops_dcnv3 \
           ./mmcv \
           ./.venv \
           ./.git \
           /root/.cache/pip \
           /tmp/* \
           ~/.cache && \
    # 卸载编译工具（需要先更新 apt）
    apt-get purge -y g++ build-essential && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "./app/main.py"]
