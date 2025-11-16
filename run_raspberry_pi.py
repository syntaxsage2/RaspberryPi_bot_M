#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
树莓派语音助手启动脚本
Python版本，避免shell换行符问题
"""

import os
import sys
import subprocess
import time

def run_command(cmd, description=""):
    """运行系统命令"""
    if description:
        print(f"{description}...")

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"错误: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"运行命令失败: {e}")
        return False

def check_python_dependencies():
    """检查Python依赖"""
    print("检查Python依赖...")

    try:
        import pyaudio
        print("✓ PyAudio 已安装")
        return True
    except ImportError:
        print("正在安装PyAudio...")
        if not run_command("sudo apt-get update", "更新软件包列表"):
            return False
        if not run_command("sudo apt-get install -y python3-pyaudio portaudio19-dev", "安装PyAudio"):
            return False
        return True

def setup_audio_devices():
    """配置音频设备"""
    print("配置音频设备...")

    # 设置环境变量
    os.environ['AUDIODEV'] = 'hw:1,0'
    os.environ['ALSA_CARD'] = 'USB'

    # 创建音频输出目录
    os.makedirs("./audio_files", exist_ok=True)
    print("✓ 音频输出目录已创建")

    return True

def run_audio_setup():
    """运行音频配置工具"""
    print("运行音频配置工具...")

    try:
        # 导入并运行音频配置
        sys.path.append('.')
        from setup_raspberry_pi_audio import main as audio_setup_main
        audio_setup_main()
        return True
    except Exception as e:
        print(f"运行音频配置工具失败: {e}")
        return False

def check_audio_devices():
    """检查音频设备状态"""
    print("检查音频设备...")

    try:
        # 检查录音设备
        result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ 录音设备检测正常")
            print(result.stdout)
        else:
            print("⚠ 录音设备检测失败")

        # 检查播放设备
        result = subprocess.run(['aplay', '-l'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ 播放设备检测正常")
        else:
            print("⚠ 播放设备检测失败")

        return True
    except Exception as e:
        print(f"检查音频设备失败: {e}")
        return False

def main():
    """主函数"""
    print("=== 树莓派语音助手启动器 ===")
    print("=" * 40)

    # 1. 检查Python环境
    print(f"Python版本: {sys.version}")
    if sys.version_info < (3, 6):
        print("错误: 需要Python 3.6或更高版本")
        return False

    # 2. 检查Python依赖
    if not check_python_dependencies():
        print("Python依赖检查失败")
        return False

    # 3. 配置音频设备
    if not setup_audio_devices():
        print("音频设备配置失败")
        return False

    # 4. 检查音频设备
    if not check_audio_devices():
        print("音频设备检查失败")
        return False

    # 5. 运行音频配置工具
    print("运行音频配置工具...")
    try:
        # 先运行修复工具
        from fix_alsa_config import main as fix_alsa_main
        print("运行ALSA配置修复工具...")
        fix_alsa_main()
    except Exception as e:
        print(f"ALSA修复工具运行失败: {e}")

    try:
        # 再运行音频配置
        from setup_raspberry_pi_audio import main as audio_setup_main
        audio_setup_main()
    except Exception as e:
        print(f"音频配置工具运行失败: {e}")
        print("继续启动主程序...")

    # 6. 启动语音助手
    print("\n" + "=" * 40)
    print("启动语音助手...")
    print("提示: 说话时请靠近麦克风")
    print("按 Ctrl+C 退出程序")
    print("=" * 40)
    print("")

    try:
        # 导入并运行主程序
        from voice_assistant import main as voice_main
        voice_main()
    except KeyboardInterrupt:
        print("\n\n程序已退出")
    except Exception as e:
        print(f"程序出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()