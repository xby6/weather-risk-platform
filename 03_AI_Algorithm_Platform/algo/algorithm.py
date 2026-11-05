import io
from pathlib import Path
import zipfile
import os
import tempfile
import time


def algorithm(zip_path: Path) -> bytes:
    """
    算法处理函数接口
    
    参数:
        zip_path: 包含输入数据的ZIP文件路径
        可在此处添加其他浮点型参数, 参数名应与请求中的参数名一致
    
    返回:
        bytes: 包含处理结果的ZIP文件二进制数据
    """
    result_files = {}

    with tempfile.TemporaryDirectory() as temp_dir:
        # 将 zip 文件解压到临时文件夹
        with zipfile.ZipFile(zip_path) as zip_archive:
            zip_archive.extractall(temp_dir)
    
        # 遍历临时文件夹中的所有文件
        for current_dir, subdirs, files in os.walk(temp_dir):
            for filename in files:
                file_path = os.path.join(current_dir, filename)
                file_extension = filename.split('.')[-1].lower()
                try:
                    with open(file_path, 'rb') as file:

                        content = file.read()
                        # 这里添加文件处理逻辑
                        result_files[filename] = content
                    
                except Exception as e:
                    print(f"处理文件 {file_path} 时出错: {e}")

    # 准备结果ZIP文件
    result_zip_buffer = io.BytesIO()
    with zipfile.ZipFile(result_zip_buffer, "w") as result_zip:
        for filename,content in result_files.items():
            # 实际应用中应根据具体处理逻辑生成结果
            base_filename = filename.split('.')[0]
            output_buffer = io.StringIO()
            output_buffer.write(f"文件名,结果\n")
            output_buffer.write(f"{filename},ok\n")

            # 获取 buffer 中的数据
            output_buffer.seek(0)
            file_data = output_buffer.read()
            result_zip.writestr(f"{base_filename}.txt", file_data)

    time.sleep(10)

    result_zip_buffer.seek(0)
    return result_zip_buffer.read()
