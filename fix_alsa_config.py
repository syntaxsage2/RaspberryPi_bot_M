#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复ALSA配置文件
"""

import os
import subprocess
import shutil

def backup_existing_config():
    """备份现有的ALSA配置"""
    config_path = os.path.expanduser("~/.asoundrc")
    backup_path = os.path.expanduser("~/.asoundrc.backup")

    if os.path.exists(config_path):
        try:
            shutil.copy2(config_path, backup_path)
            print(f"已备份现有配置到: {backup_path}")
            return True
        except Exception as e:
            print(f"备份配置文件失败: {e}")
            return False
    return True

def remove_corrupted_config():
    """删除损坏的配置文件"""
    config_path = os.path.expanduser("~/.asoundrc")

    if os.path.exists(config_path):
        try:
            os.remove(config_path)
            print("已删除损坏的配置文件")
            return True
        except Exception as e:
            print(f"删除配置文件失败: {e}")
            return False
    return True

def create_simple_alsa_config():
    """创建简化的ALSA配置"""
    config_path = os.path.expanduser("~/.asoundrc")

    # 简化的ALSA配置
    alsa_config = """# 简化的树莓派音频配置
pcm.!default {
    type hw
    card 1
    device 0
}

ctl.!default {
    type hw
    card 1
}
"""

    try:
        with open(config_path, 'w') as f:
            f.write(alsa_config)
        print(f"已创建简化的ALSA配置: {config_path}")
        return True
    except Exception as e:
        print(f"创建ALSA配置文件失败: {e}")
        return False

def create_plughw_config():
    """创建使用plughw的配置"""
    config_path = os.path.expanduser("~/.asoundrc")

    # 使用plughw的配置
    alsa_config = """# 树莓派音频配置 - 使用plughw
pcm.!default {
    type plug
    slave {
        pcm "plughw:1,0"
    }
}

ctl.!default {
    type hw
    card 1
}
"""

    try:
        with open(config_path, 'w') as f:
            f.write(alsa_config)
        print(f"已创建plughw ALSA配置: {config_path}")
        return True
    except Exception as e:
        print(f"创建ALSA配置文件失败: {e}")
        return False

def test_audio_devices():
    """测试音频设备"""
    print("\n=== 测试音频设备 ===")

    # 测试录音设备
    print("测试录音设备...")
    try:
        result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ 录音设备检测正常")
            print(result.stdout)
        else:
            print("✗ 录音设备检测失败")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"录音设备测试失败: {e}")
        return False

    # 测试播放设备
    print("测试播放设备...")
    try:
        result = subprocess.run(['aplay', '-l'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ 播放设备检测正常")
        else:
            print("✗ 播放设备检测失败")
            return False
    except Exception as e:
        print(f"播放设备测试失败: {e}")
        return False

    return True

def test_microphone_simple():
    """简化测试麦克风"""
    print("\n=== 测试麦克风 ===")

    test_file = "/tmp/test_recording.wav"

    # 尝试不同的录音命令
    test_commands = [
        # 方法1: 使用plughw
        ['arecord', '-D', 'plughw:1,0', '-f', 'cd', '-t', 'wav', '-d', '3', test_file],
        # 方法2: 使用hw
        ['arecord', '-D', 'hw:1,0', '-f', 'cd', '-t', 'wav', '-d', '3', test_file],
        # 方法3: 默认设备
        ['arecord', '-f', 'cd', '-t', 'wav', '-d', '3', test_file],
    ]

    for i, cmd in enumerate(test_commands):
        print(f"尝试方法{i+1}: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"✓ 录制成功！")

                # 播放测试
                print("播放录制的音频...")
                play_result = subprocess.run(['aplay', test_file], capture_output=True, text=True)
                if play_result.returncode == 0:
                    print("✓ 播放成功！")
                else:
                    print("✗ 播放失败")

                # 清理
                os.remove(test_file)
                return True
            else:
                print(f"✗ 录制失败: {result.stderr}")
        except Exception as e:
            print(f"录制失败: {e}")

    return False

def show_current_config():
    """显示当前配置"""
    config_path = os.path.expanduser("~/.asoundrc")

    if os.path.exists(config_path):
        print(f"\n当前ALSA配置 ({config_path}):")
        try:
            with open(config_path, 'r') as f:
                print(f.read())
        except Exception as e:
            print(f"读取配置文件失败: {e}")
    else:
        print("没有ALSA配置文件")

def main():
    """主函数"""
    print("=== ALSA配置修复工具 ===")
    print("=" * 40)

    # 显示当前配置
    show_current_config()

    print("\n选择操作:")
    print("1. 修复损坏的配置文件")
    print("2. 创建简化配置")
    print("3. 创建plughw配置")
    print("4. 测试音频设备")
    print("5. 显示当前配置")
    print("6. 全部执行")

    choice = input("\n请选择 (1-6): ").strip()

    if choice == '1':
        backup_existing_config()
        remove_corrupted_config()

    elif choice == '2':
        backup_existing_config()
        create_simple_alsa_config()

    elif choice == '3':
        backup_existing_config()
        create_plughw_config()

    elif choice == '4':
        test_audio_devices()
        test_microphone_simple()

    elif choice == '5':
        show_current_config()

    elif choice == '6':
        print("执行全部修复步骤...")
        backup_existing_config()
        remove_corrupted_config()

        print("\n尝试创建plughw配置...")
        if create_plughw_config():
            if test_audio_devices() and test_microphone_simple():
                print("\n✓ 配置成功！")
            else:
                print("\nplughw配置无效，尝试简化配置...")
                create_simple_alsa_config()
                test_audio_devices()
                test_microphone_simple()

    else:
        print("无效选择")
        return

    print("\n" + "=" * 40)
    print("修复完成！")

if __name__ == "__main__":
    main()