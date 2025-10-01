#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时数据补充工具启动脚本
"""

import sys
import os
import multiprocessing

# 确保从正确的目录导入模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入主模块
from GUIScheduler import main

if __name__ == "__main__":
    # 支持多进程
    multiprocessing.freeze_support()
    main() 