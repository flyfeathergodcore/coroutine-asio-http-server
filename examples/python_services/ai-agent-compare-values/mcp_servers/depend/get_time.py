from datetime import datetime

def get_now_datetime_str() -> str:
    """生成数据库 DATETIME(3) 标准格式时间"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

# 示例输出：2026-07-15 16:40:25.123