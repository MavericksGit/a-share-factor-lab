# -*- coding: utf-8 -*-
"""读取项目根目录的 config.yaml 配置文件。"""

# yaml 模块用来解析 YAML 格式的配置文件（比 JSON 更适合人工阅读和写注释）
import yaml
# pathlib.Path 用面向对象的方式处理文件路径
from pathlib import Path

# 默认配置文件路径 = 本项目根目录下的 config.yaml
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def load_config(path=None):
    """读取 YAML 配置并返回一个 Python 字典。

    参数：
        path：配置文件的路径，缺省时使用项目根目录的 config.yaml
    """
    # 如果调用者没传路径，就用默认路径
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    # 以 utf-8 打开文件，避免 Windows 或中文注释出现乱码
    with open(config_path, "r", encoding="utf-8") as f:
        # safe_load 只解析普通数据类型，不执行任意代码，比 load 更安全
        return yaml.safe_load(f)
