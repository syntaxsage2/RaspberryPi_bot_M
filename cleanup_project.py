#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目清理工具
清理讯飞语音合成项目中的无关文件
"""

import os
import shutil
import sys

def cleanup_project():
    """清理项目中的无关文件"""

    base_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"开始清理项目: {base_dir}")

    # 清理目标列表
    cleanup_targets = [
        # HTML网页资源文件（占用大量空间）
        "超拟人语音合成API文档 _ 讯飞开放平台文档中心_files",
        "星火认知大模型websocket接口文档 _ 讯飞开放平台文档中心_files",
        "超拟人语音合成API文档 _ 讯飞开放平台文档中心.html",
        "星火认知大模型websocket接口文档 _ 讯飞开放平台文档中心.html",

        # 临时文件
        "nul",

        # Python缓存（如果存在）
        "__pycache__",

        # 压缩包（如果不需要）
        "rtasr_python3_demo.zip",

        # IDE配置（如果不用PyCharm）
        "rtasr_python3_demo/.idea",

        # 测试音频文件（可选）
        # "rtasr_python3_demo/python/test_1.pcm",
    ]

    removed_count = 0
    total_size = 0

    for target in cleanup_targets:
        target_path = os.path.join(base_dir, target)

        if os.path.exists(target_path):
            try:
                # 计算文件/目录大小
                if os.path.isfile(target_path):
                    size = os.path.getsize(target_path)
                    total_size += size
                    os.remove(target_path)
                    print(f"✅ 删除文件: {target} ({size:,} 字节)")
                    removed_count += 1
                elif os.path.isdir(target_path):
                    size = get_dir_size(target_path)
                    total_size += size
                    shutil.rmtree(target_path)
                    print(f"✅ 删除目录: {target} ({size:,} 字节)")
                    removed_count += 1
            except Exception as e:
                print(f"❌ 删除失败: {target} - {e}")
        else:
            print(f"⏭️  不存在: {target}")

    print(f"\n清理完成！")
    print(f"删除项目数: {removed_count}")
    print(f"释放空间: {total_size:,} 字节 ({total_size/1024/1024:.2f} MB)")

    # 显示剩余文件
    print(f"\n项目结构:")
    show_project_structure(base_dir)

def get_dir_size(path):
    """获取目录大小"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.exists(filepath):
                total_size += os.path.getsize(filepath)
    return total_size

def show_project_structure(base_dir, prefix=""):
    """显示项目结构"""
    items = sorted(os.listdir(base_dir))
    for i, item in enumerate(items):
        item_path = os.path.join(base_dir, item)
        is_last = i == len(items) - 1
        current_prefix = "└── " if is_last else "├── "

        if os.path.isdir(item_path):
            print(f"{prefix}{current_prefix}{item}/")
            # 递归显示子目录（限制深度）
            if prefix.count("│") < 2:  # 限制显示深度
                extension = "    " if is_last else "│   "
                show_project_structure(item_path, prefix + extension)
        else:
            print(f"{prefix}{current_prefix}{item}")

if __name__ == "__main__":
    print("=== 讯飞语音合成项目清理工具 ===")
    print("此工具将清理项目中的无关文件")
    print("包括：HTML网页资源、临时文件、缓存等")

    confirm = input("\n确认开始清理？(y/N): ").strip().lower()
    if confirm == 'y':
        cleanup_project()
    else:
        print("清理已取消")

    print("\n建议使用版本控制工具（如git）管理项目文件")