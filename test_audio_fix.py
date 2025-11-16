#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频修复测试脚本
测试新的音频录制功能
"""

import os
import sys
from audio_utils import AudioRecorder

def test_audio_recording():
    """测试音频录制功能"""
    print("=== 音频修复测试 ===")
    print("=" * 40)

    try:
        # 创建输出目录
        os.makedirs("./audio_files", exist_ok=True)

        # 测试新的AudioRecorder
        print("\n【测试1】初始化AudioRecorder")
        recorder = AudioRecorder(
            sample_rate=16000,
            channels=1,
            chunk=1024,
            input_device_index=None  # 让系统自动选择
        )
        print(" ✓ AudioRecorder初始化成功")

        print("\n【测试2】录制3秒音频")
        output_file = "./audio_files/test_fix.wav"

        try:
            result_file = recorder.record(duration=3, output_file=output_file)
            print(f" ✓ 录音成功: {result_file}")

            # 检查文件
            if os.path.exists(result_file):
                file_size = os.path.getsize(result_file)
                print(f" 📊 文件大小: {file_size} 字节")

                if file_size > 0:
                    print(" ✓ 录音文件有效")
                else:
                    print(" ⚠ 录音文件为空")
            else:
                print(" ❌ 录音文件未生成")

        except Exception as e:
            print(f" ❌ 录音失败: {e}")
            print("\n【建议】")
            print("1. 检查麦克风是否连接")
            print("2. 检查系统音频设置")
            print("3. 尝试运行: python3 -m pip install --upgrade pyaudio")

    except Exception as e:
        print(f" ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 40)
    print("测试完成")

if __name__ == "__main__":
    test_audio_recording()