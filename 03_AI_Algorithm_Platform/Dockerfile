FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources || true && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        build-essential \
        git \
        curl \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxrender1 \
        libxext6 \
        libgomp1 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
COPY wheels/ /wheels/

RUN pip install --no-cache-dir --upgrade pip wheel \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com && \
    pip install --no-cache-dir "setuptools<82" \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com

RUN pip install --no-cache-dir /wheels/torch-2.2.1+cpu-cp311-cp311-linux_x86_64.whl
RUN pip install --no-cache-dir /wheels/torchvision-0.17.1+cpu-cp311-cp311-linux_x86_64.whl

RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    mmengine==0.10.7 \
    addict \
    pyyaml \
    yapf \
    matplotlib \
    rich \
    termcolor

RUN pip install --no-cache-dir /wheels/mmcv-2.2.0-cp311-cp311-manylinux1_x86_64.whl

RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    fastapi>=0.116.1 \
    python-multipart>=0.0.20 \
    pyyaml>=6.0.2 \
    uvicorn>=0.35.0 \
    numpy==1.24.1 \
    pillow==10.2.0 \
    tqdm==4.65.2 \
    opencv-python-headless==4.10.0.82 \
    imageio==2.33.1 \
    tifffile==2023.4.12 \
    packaging==23.2 \
    requests==2.28.2 \
    typing_extensions==4.8.0 \
    filelock==3.9.0 \
    safetensors==0.4.2 \
    certifi==2024.2.2 \
    charset-normalizer==3.3.2 \
    idna==3.6 \
    urllib3==1.26.18 \
    dill==0.3.6 \
    einops==0.7.0

RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    scipy==1.10.1 \
    albumentations==1.3.1 \
    imgaug==0.4.0 \
    timm==0.9.8 \
    efficientnet_pytorch==0.7.1 \
    PyWavelets==1.4.1

RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    ultralytics==8.1.30

COPY . .

RUN if [ -d ops_dcnv3 ]; then \
      cd ops_dcnv3 && \
      pip install --no-cache-dir -v . --no-build-isolation ; \
    fi

RUN if [ -d ultralytics ]; then \
      SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])") && \
      ULTRA_PATH="$SITE_PACKAGES/ultralytics" && \
      rm -rf "$ULTRA_PATH" && \
      cp -r ./ultralytics "$ULTRA_PATH" ; \
    fi

EXPOSE 8000

CMD ["python", "/app/app/main.py"]