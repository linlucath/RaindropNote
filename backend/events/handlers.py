import os
from app.utils.logger import get_logger
logger = get_logger(__name__)

def cleanup_temp_files(data):
    logger.info(f"starting cleanup temp files ：{data['file_path']}")
    # 获取名称
    path=data['file_path']
    name=path[:-4]
    # 删除以这个文件开头的
    for file in os.listdir(os.path.dirname(path)):
        if file.startswith(name):
            os.remove(os.path.join(os.path.dirname(path), file))
    os.remove(data['file_path'])
    # 检查是否删除文件
    if os.path.exists(data['file_path']):
        logger.info(f"cleanup temp files failed ：{data['file_path']}")
    else:
        logger.info(f"cleanup temp files success ：{data['file_path']}")


