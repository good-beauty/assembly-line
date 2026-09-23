# -*- coding: utf-8 -*-
"""项目统一日志模块。所有模块通过 get_logger() 获取 logger，替代 print。"""
import logging
import os
import sys

_LOGGER_NAME = "assembly_line"
_CONFIGURED = False


def configure(
    level: int = None,
    fmt: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=None,
):
    """一次性配置根 logger。在生产/CI 中可覆盖 level 调节日志量。"""
    global _CONFIGURED
    if _CONFIGURED:
        return logging.getLogger(_LOGGER_NAME)
    _CONFIGURED = True
    root = logging.getLogger(_LOGGER_NAME)
    if level is None:
        level = logging.INFO
    root.setLevel(level)
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))
    root.addHandler(handler)
    return root


def get_logger(name: str):
    """返回带命名空间的 logger。"""
    configure()
    return logging.getLogger(f"{_LOGGER_NAME}.{name}")


def set_level(level: int):
    """运行期调整日志级别。"""
    logging.getLogger(_LOGGER_NAME).setLevel(level)