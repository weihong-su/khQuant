#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
miniQMT数据查看器启动脚本
"""

import sys
import os

# 添加当前目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from GUIDataViewer import main
    
    if __name__ == '__main__':
        main()
        
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保已安装所需的依赖包:")
    print("pip install PyQt5 pandas")
    input("按回车键退出...")
except Exception as e:
    print(f"运行出错: {e}")
    input("按回车键退出...") 