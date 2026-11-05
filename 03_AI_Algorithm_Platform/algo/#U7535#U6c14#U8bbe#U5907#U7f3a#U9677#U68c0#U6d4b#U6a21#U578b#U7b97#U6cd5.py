from ultralytics import YOLO
from PIL import Image
import io
from pathlib import Path
import zipfile
import os
import tempfile
import yaml
import traceback
import logging


def algorithm(zip_path: Path, model_name: str, input_conf: float = 0.5) -> bytes:
    """
    算法处理函数接口
    
    参数:
        zip_path: 包含输入数据的ZIP文件路径
        model_name: 模型名称
        input_conf: 置信度阈值, 默认值为 0.5
    
    返回:
        bytes: 包含处理结果的ZIP文件二进制数据
    """
    logging.info(f"Starting algorithm with model {model_name} on zip file {zip_path}")

    # 加载配置文件
    CONFIG_PATH = Path("model_config.yaml")
    config = yaml.safe_load(CONFIG_PATH.read_text()) or {"models": {}}
    
    # 检查模型是否存在
    if model_name not in config["models"]:
        raise ValueError(f"Model '{model_name}' not found in configuration")
    
    model = YOLO(config["models"][model_name]["file"])
    logging.info(f"Loaded model {model_name} from {config['models'][model_name]['file']}")

    result_files = {}

    with tempfile.TemporaryDirectory() as temp_dir:
        # 将 zip 文件解压到临时文件夹
        with zipfile.ZipFile(zip_path) as zip_archive:
            zip_archive.extractall(temp_dir)
    
        # 遍历临时文件夹中的所有文件
        for current_dir, subdirs, files in os.walk(temp_dir):
            for filename in files:
                logging.info(f"Processing file {filename} in {current_dir}")
                file_path = os.path.join(current_dir, filename)
                file_extension = filename.split('.')[-1].lower()
                
                # 只处理图像文件
                if file_extension not in ['jpg', 'jpeg', 'png', 'bmp', 'tiff']:
                    logging.info(f"Skipping non-image file {filename}")
                    continue
                    
                try:
                    with Image.open(file_path) as img:
                        results = model.predict(source=img, conf=input_conf)
                        logging.info(f"Model {model_name} processed {filename} with {len(results[0].boxes)} detections")

                        detections = []
                        for box in results[0].boxes:
                            cls_id = int(box.cls[0])          # 类别ID
                            conf = float(box.conf[0])         # 置信度
                            xyxy = [float(x) for x in box.xyxy[0]]  # 坐标 [x1, y1, x2, y2]
                            detections.append({
                                "class_id": cls_id,
                                "confidence": round(conf, 3),
                                "bbox": xyxy
                            })
                        result_img = results[0].plot()
                        result_img = result_img[:, :, ::-1]  # BGR转RGB
                        img_pil = Image.fromarray(result_img)

                        result_files[filename] = (img_pil, detections)
                    
                except Exception as e:
                    logging.error(f"Error processing file {file_path}: {e}")
                    traceback.print_exc()

    # 准备结果ZIP文件
    result_zip_buffer = io.BytesIO()
    with zipfile.ZipFile(result_zip_buffer, "w") as result_zip:
        for filename, (img_pil, detections) in result_files.items():
            # 实际应用中应根据具体处理逻辑生成结果
            base_filename = filename.split('.')[0]

            output_buffer = io.StringIO()
            output_buffer.write(f"类别ID,置信度,x1,y1,x2,y2\n")
            for detection in detections:
                output_buffer.write(f"{detection['class_id']},{detection['confidence']},{detection['bbox'][0]},{detection['bbox'][1]},{detection['bbox'][2]},{detection['bbox'][3]}\n")

            # 获取 buffer 中的数据
            output_buffer.seek(0)
            file_data = output_buffer.read()
            result_zip.writestr(f"{base_filename}.txt", file_data)

            buf = io.BytesIO()
            img_pil.save(buf, format="JPEG")
            buf.seek(0)
            result_zip.writestr(f"{base_filename}.jpg", buf.read())

    result_zip_buffer.seek(0)
    if not result_files:
        raise RuntimeError("No valid inference results generated.")
    return result_zip_buffer.read()

