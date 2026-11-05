import torch
import numpy as np
from PIL import Image
import io
from pathlib import Path
import zipfile
import os
import tempfile
import yaml
import traceback
import logging

def algorithm(zip_path: Path, model_name: str) -> bytes:
    """
    电气设备语义分割算法接入接口
    将所有逻辑整合在单函数内，完成：解压->加载模型->预处理->推理->后处理(着色/融合)->打包结果
    """
    logging.info(f"Starting segmentation algorithm with model {model_name} on zip file {zip_path}")

    # ================= 1. 配置与定义 =================
    # 类别与颜色定义
    NAME_CLASSES = ["background", "绝缘子", "杆塔", "导线", "杆塔脚钉", "销钉", "悬垂线夹", "防震锤"]
    COLORS = [
        [0, 0, 0],       # background
        [128, 0, 0],     # 绝缘子
        [0, 128, 0],     # 杆塔
        [128, 128, 0],   # 导线
        [0, 0, 128],     # 杆塔脚钉
        [128, 0, 128],   # 销钉
        [0, 128, 128],   # 悬垂线夹
        [128, 128, 128]  # 防震锤
    ]
    INPUT_SHAPE = (512, 512) # 模型输入尺寸
    
    # 结果容器
    result_zip_buffer = io.BytesIO()

    # ================= 2. 加载模型 =================
    try:
        # 读取配置文件
        CONFIG_PATH = Path("model_config.yaml")
        config = yaml.safe_load(CONFIG_PATH.read_text()) or {"models": {}}
        
        # 获取模型文件路径
        if model_name not in config["models"]:
            # 兼容模式：如果配置未找到，尝试直接使用 model_name 作为路径
            model_file = model_name
            logging.warning(f"Model {model_name} not found in config, using as filename.")
        else:
            model_file = config["models"][model_name]["file"]

        # 确定设备并加载
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # 注意：这里假设 .pt 文件包含完整模型结构（Full Model），而非仅权重
        model = torch.load(model_file, map_location=device)
        model.eval()
        logging.info(f"Model loaded successfully on {device}")

    except Exception as e:
        logging.error(f"Model initialization failed: {e}")
        raise RuntimeError(f"Failed to load model: {e}")

    # ================= 3. 处理流程 =================
    with tempfile.TemporaryDirectory() as temp_dir:
        # 解压输入 ZIP
        try:
            with zipfile.ZipFile(zip_path) as zip_in:
                zip_in.extractall(temp_dir)
        except Exception as e:
            logging.error(f"Failed to unzip input: {e}")
            return b""

        # 创建输出 ZIP 对象
        with zipfile.ZipFile(result_zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_out:
            
            # 遍历文件
            for root, _, files in os.walk(temp_dir):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    ext = filename.split('.')[-1].lower()
                    
                    if ext not in ['jpg', 'jpeg', 'png', 'bmp', 'tiff']:
                        continue

                    try:
                        logging.info(f"Processing {filename}...")
                        
                        # --- 图像加载与预处理 ---
                        with Image.open(file_path) as img:
                            img = img.convert("RGB")
                            w_ori, h_ori = img.size
                            
                            # Resize -> Numpy -> Normalize -> Tensor [1, C, H, W]
                            img_resized = img.resize(INPUT_SHAPE, Image.BILINEAR)
                            img_np = np.array(img_resized, dtype=np.float32) / 255.0
                            img_tensor = torch.from_numpy(np.transpose(img_np, (2, 0, 1))).unsqueeze(0).to(device)

                            # --- 模型推理 ---
                            with torch.no_grad():
                                output = model(img_tensor)
                                # Argmax 获取类别索引矩阵 [H, W]
                                pred = torch.argmax(output, dim=1).squeeze(0).cpu().numpy()

                            # --- 后处理：生成彩色掩码 ---
                            # 创建空白彩色图
                            seg_img = np.zeros((pred.shape[0], pred.shape[1], 3), dtype=np.uint8)
                            
                            # 统计识别到的类别信息
                            detected_info = []
                            unique_ids, counts = np.unique(pred, return_counts=True)
                            total_pixels = pred.size
                            
                            for cls_id in range(len(NAME_CLASSES)):
                                # 像素着色
                                seg_img[pred == cls_id] = COLORS[cls_id]
                                
                                # 统计文本信息 (跳过背景)
                                if cls_id in unique_ids and cls_id != 0:
                                    count = counts[np.where(unique_ids == cls_id)][0]
                                    ratio = (count / total_pixels) * 100
                                    detected_info.append(f"{NAME_CLASSES[cls_id]}: {ratio:.2f}%")

                            # 调整掩码尺寸回原图大小
                            seg_img_pil = Image.fromarray(seg_img).resize((w_ori, h_ori), Image.NEAREST)
                            
                            # 图像融合 (原图 50% + 掩码 50%)
                            fused_img = Image.blend(img, seg_img_pil, 0.5)

                            # --- 写入结果到 ZIP ---
                            base_name = os.path.splitext(filename)[0]
                            
                            # 1. 写入融合后的图片 (.jpg)
                            img_buffer = io.BytesIO()
                            fused_img.save(img_buffer, format="JPEG", quality=95)
                            zip_out.writestr(f"{base_name}.jpg", img_buffer.getvalue())
                            
                            # 2. 写入识别文本结果 (.txt)
                            # 由于语义分割没有坐标框，这里输出识别到的类别和画面占比
                            txt_content = "Detected Classes and Area Ratio:\n"
                            if detected_info:
                                txt_content += "\n".join(detected_info)
                            else:
                                txt_content += "No specific equipment detected."
                            zip_out.writestr(f"{base_name}.txt", txt_content)
                            
                            logging.info(f"Processed {filename}: Found {len(detected_info)} classes")

                    except Exception as e:
                        logging.error(f"Error processing {filename}: {e}")
                        traceback.print_exc()

    # 返回二进制数据
    result_zip_buffer.seek(0)
    return result_zip_buffer.read()