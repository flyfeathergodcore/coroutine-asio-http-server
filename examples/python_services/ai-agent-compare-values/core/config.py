"""
配置加载器 — 从 YAML 文件读取所有配置

使用方式:
    from core.config import load_config
    config = load_config()                    # 自动查找 config.yaml
    config = load_config("/path/to/cfg.yaml") # 指定路径
"""

import os
from pathlib import Path
from typing import Optional, Any

import yaml


def load_config(config_path: Optional[str] = None) -> dict[str, Any]:
    """
    加载 YAML 配置文件。

    查找顺序:
    1. 传入的 config_path
    2. 环境变量 CONFIG_PATH
    3. 当前工作目录下的 config.yaml
    4. 向上查找最近的 config.yaml
    """
    path = _find_config(config_path)
    if path is None:
        raise FileNotFoundError("未找到 config.yaml，请设置 CONFIG_PATH 环境变量或在项目根目录创建")

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config or {}


def _find_config(config_path: Optional[str] = None) -> Optional[Path]:
    """查找配置文件"""
    if config_path:
        p = Path(config_path)
        return p if p.exists() else None

    env_path = os.getenv("CONFIG_PATH", "")
    if env_path:
        p = Path(env_path)
        return p if p.exists() else None

    # 从 CWD 向上查找
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        cfg = parent / "config.yaml"
        if cfg.exists():
            return cfg

    return None
