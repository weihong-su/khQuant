#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
依赖检查脚本 - 在目标电脑上运行此脚本检查缺失的依赖
"""

import sys
import os
import platform
import subprocess

def check_python_modules():
    """检查Python模块依赖"""
    required_modules = [
        'PyQt5',
        'numpy', 
        'pandas',
        'requests',
        'psutil',
        'matplotlib',
        'PIL'
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
            print(f"✓ {module} - 已安装")
        except ImportError:
            print(f"✗ {module} - 缺失")
            missing_modules.append(module)
    
    return missing_modules

def check_system_dlls():
    """检查系统DLL"""
    import ctypes
    from ctypes import wintypes
    
    required_dlls = [
        'msvcp140.dll',
        'vcruntime140.dll', 
        'vcruntime140_1.dll',
        'msvcp140_1.dll',
        'concrt140.dll'
    ]
    
    missing_dlls = []
    for dll in required_dlls:
        try:
            ctypes.WinDLL(dll)
            print(f"✓ {dll} - 已安装")
        except OSError:
            print(f"✗ {dll} - 缺失")
            missing_dlls.append(dll)
    
    return missing_dlls

def check_vc_redist():
    """检查Visual C++ Redistributable"""
    import winreg
    
    vc_versions = [
        "Microsoft Visual C++ 2015-2022 Redistributable (x64)",
        "Microsoft Visual C++ 2015-2022 Redistributable (x86)", 
        "Microsoft Visual C++ 2019 Redistributable (x64)",
        "Microsoft Visual C++ 2019 Redistributable (x86)"
    ]
    
    installed_programs = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                           r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall") as key:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, subkey_name) as subkey:
                        try:
                            display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                            installed_programs.append(display_name)
                        except FileNotFoundError:
                            pass
                    i += 1
                except OSError:
                    break
    except Exception as e:
        print(f"检查已安装程序时出错: {e}")
        return False
    
    found_vc = False
    for vc_version in vc_versions:
        if any(vc_version in program for program in installed_programs):
            print(f"✓ {vc_version} - 已安装")
            found_vc = True
            break
    
    if not found_vc:
        print("✗ Visual C++ Redistributable - 缺失")
    
    return found_vc

def main():
    print("=" * 60)
    print("KHQuant 依赖检查工具")
    print("=" * 60)
    
    print(f"操作系统: {platform.system()} {platform.release()}")
    print(f"Python版本: {sys.version}")
    print(f"架构: {platform.architecture()[0]}")
    print()
    
    print("1. 检查Python模块依赖:")
    print("-" * 30)
    missing_modules = check_python_modules()
    print()
    
    if sys.platform == 'win32':
        print("2. 检查Visual C++ Redistributable:")
        print("-" * 30)
        has_vc = check_vc_redist()
        print()
        
        print("3. 检查系统DLL:")
        print("-" * 30)
        missing_dlls = check_system_dlls()
        print()
    
    print("=" * 60)
    print("检查结果汇总:")
    print("=" * 60)
    
    if missing_modules:
        print("缺失的Python模块:")
        for module in missing_modules:
            print(f"  - {module}")
        print("\n解决方案: pip install " + " ".join(missing_modules))
    
    if sys.platform == 'win32':
        if not has_vc:
            print("\n缺失Visual C++ Redistributable!")
            print("解决方案: 下载并安装 Microsoft Visual C++ 2015-2022 Redistributable")
            print("下载地址: https://aka.ms/vs/17/release/vc_redist.x64.exe")
        
        if missing_dlls:
            print(f"\n缺失系统DLL: {', '.join(missing_dlls)}")
            print("这些DLL通常包含在Visual C++ Redistributable中")
    
    if not missing_modules and (sys.platform != 'win32' or (has_vc and not missing_dlls)):
        print("✓ 所有依赖都已满足，程序应该能正常运行")
    
    print("\n按任意键退出...")
    input()

if __name__ == "__main__":
    main() 