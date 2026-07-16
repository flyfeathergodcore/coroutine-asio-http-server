"""
数据库工具模块 - 提供统一的 MySQL 连接池和配置加载。

可复用功能：
  - load_config()    加载 YAML 配置文件
  - get_conn()       从连接池获取一个 MySQL 连接（用完 .close() 归还）
  - closing_conn()   自动获取和归还连接的上下文管理器

用法:
    from depend.db import load_config, get_conn, closing_conn

    # 方式1：手动管理（适合在单次调用中复用连接）
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(...)
    finally:
        if conn.is_connected():
            conn.close()    # 归还到连接池

    # 方式2：上下文管理器（推荐，自动归还）
    with closing_conn() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(...)
"""

import os
import yaml
import logging
import mysql.connector as connector
from mysql.connector.pooling import MySQLConnectionPool
from typing import Optional
from contextlib import contextmanager
from threading import Lock

logger = logging.getLogger(__name__)

_POOL = None
_POOL_LOCK = Lock()
_POOL_NAME = "agent_pool"
_POOL_SIZE = 5

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def load_config(path: Optional[str] = None) -> dict:
    """加载 YAML 配置文件（仅非环境配置，环境配置请使用 .env + os.getenv）

    Args:
        path: 配置文件路径，默认优先使用 CONFIG_PATH 环境变量，否则项目根目录下的 config.yaml

    Returns:
        dict: 解析后的配置字典
    """
    if path is None:
        cfg_path = os.getenv("CONFIG_PATH", os.path.join(_project_root, "config.yaml"))
    else:
        cfg_path = path
    with open(cfg_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def _ensure_pool(path: Optional[str] = None) -> MySQLConnectionPool:
    """懒初始化连接池（线程安全单例）"""
    global _POOL
    if _POOL is None:
        with _POOL_LOCK:
            # 双重检查
            if _POOL is None:
                _POOL = MySQLConnectionPool(
                    pool_name=_POOL_NAME,
                    pool_size=_POOL_SIZE,
                    pool_reset_session=True,
                    host=os.getenv("MYSQL_HOST", "localhost"),
                    port=int(os.getenv("MYSQL_PORT", "3306")),
                    user=os.getenv("MYSQL_USER", "webcpp"),
                    password=os.getenv("MYSQL_PASSWORD", "webcpp123"),
                    database=os.getenv("MYSQL_DATABASE", "webcpp"),
                )
    return _POOL


def get_conn(path: Optional[str] = None) -> connector.MySQLConnection:
    """
    从连接池获取一个健康的 MySQL 连接（使用后调用 .close() 归还）。

    自动检测连接健康状态，断开的连接会重新建立。

    Args:
        path: 配置文件路径，默认项目根目录下的 config.yaml

    Returns:
        MySQLConnection: 健康的池化连接

    Raises:
        mysql.connector.Error: 池中所有连接均不可用时抛出
    """
    pool = _ensure_pool(path)
    conn = pool.get_connection()
    try:
        # ping 检测健康状态，断连则自动重连
        conn.ping(reconnect=True, attempts=2)
    except connector.Error:
        # 这条连接已损坏，归还并换一条
        logger.warning("连接不健康，换一条重试")
        try:
            conn.close()
        except connector.Error:
            pass
        conn = pool.get_connection()
    return conn


@contextmanager
def closing_conn(path: Optional[str] = None):
    """
    自动获取和归还连接的上下文管理器。

    with closing_conn() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT ...")
    # 自动归还到池
    """
    conn = get_conn(path)
    try:
        yield conn
    finally:
        if conn and conn.is_connected():
            conn.close()
