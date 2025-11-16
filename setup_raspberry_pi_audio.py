#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
树莓派音频配置工具
用于配置和测试音频设备
"""

import subprocess
import os
import sys
import time

def check_audio_devices():
    """检查音频设备"""
    print("=== 检查音频设备 ===")
    try:
        # 检查录音设备
        result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
        print("录音设备:")
        print(result.stdout)
        if result.stderr:
            print("错误:", result.stderr)
    except Exception as e:
        print(f"检查录音设备失败: {e}")

    try:
        # 检查播放设备
        result = subprocess.run(['aplay', '-l'], capture_output=True, text=True)
        print("\n播放设备:")
        print(result.stdout)
        if result.stderr:
            print("错误:", result.stderr)
    except Exception as e:
        print(f"检查播放设备失败: {e}")

def create_alsa_config():
    """创建ALSA配置文件"""
    print("\n=== 创建ALSA配置 ===")

    alsa_config = """# 树莓派USB音频设备配置
pcm.!default {
    type asym
    playback.pcm "plughw:0,0"
    capture.pcm "plughw:1,0"
}

pcm.default_capture {
    type hw
    card 1
    device 0
}

pcm.default_playback {
    type hw
    card 0
    device 0
}
"""

    config_path = os.path.expanduser("~/.asoundrc")
    try:
        with open(config_path, 'w') as f:
            f.write(alsa_config)
        print(f"ALSA配置文件已创建: {config_path}")
        print("配置内容:")
        print(alsa_config)
    except Exception as e:
        print(f"创建ALSA配置文件失败: {e}")

def test_microphone():
    """测试麦克风"""
    print("\n=== 测试麦克风 ===")
    print("正在测试麦克风录制...")

    test_file = "/tmp/test_recording.wav"
    try:
        # 录制5秒音频
        cmd = [
            'arecord',
            '-D', 'plughw:1,0',  # 使用USB音频设备
            '-f', 'cd',         # CD质量: 16bit 44.1kHz
            '-t', 'wav',        # WAV格式
            '-d', '5',          # 录制5秒
            test_file
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ 录制成功: {test_file}")

            # 播放录制的音频
            print("播放录制的音频...")
            play_cmd = ['aplay', test_file]
            subprocess.run(play_cmd)

            # 清理
            os.remove(test_file)
            print("✓ 测试完成")
        else:
            print(f"✗ 录制失败: {result.stderr}")

    except Exception as e:
        print(f"测试麦克风失败: {e}")

def install_audio_tools():
    """安装音频工具"""
    print("\n=== 安装音频工具 ===")
    try:
        # 检查是否已安装alsa-utils
        result = subprocess.run(['which', 'arecord'], capture_output=True)
        if result.returncode != 0:
            print("正在安装alsa-utils...")
            subprocess.run(['sudo', 'apt-get', 'update'], check=True)
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'alsa-utils'], check=True)
        else:
            print("alsa-utils已安装")

        # 检查是否已安装sox
        result = subprocess.run(['which', 'sox'], capture_output=True)
        if result.returncode != 0:
            print("正在安装sox...")
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'sox'], check=True)
        else:
            print("sox已安装")

    except Exception as e:
        print(f"安装音频工具失败: {e}")

def main():
    """主函数"""
    print("树莓派音频配置工具")
    print("=" * 30)

    # 检查音频设备
    check_audio_devices()

    # 创建ALSA配置
    create_alsa_config()

    # 安装音频工具
    install_audio_tools()

    # 测试麦克风
    test_microphone()

    print("\n" + "=" * 30)
    print("配置完成！")
    print("如果麦克风测试失败，请检查:")
    print("1. USB麦克风是否正确连接")
    print("2. 麦克风是否被其他程序占用")
    print("3. 用户是否有音频设备权限")

if __name__ == "__main__":
    main()