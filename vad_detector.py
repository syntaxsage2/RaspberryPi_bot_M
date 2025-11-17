# -*- coding:utf-8 -*-
"""
VAD (Voice Activity Detection) 语音活动检测模块
使用 Silero VAD 实现高精度语音检测
"""

import torch
import numpy as np
from silero_vad import load_silero_vad, get_speech_timestamps


class VADDetector:
    """基于Silero VAD的语音活动检测器"""

    def __init__(self,
                 sample_rate=16000,
                 threshold=0.5,
                 min_speech_duration_ms=250,
                 min_silence_duration_ms=500,
                 window_size_samples=512):
        """
        初始化VAD检测器

        参数说明：
        :param sample_rate: 采样率（Hz），必须是16000
        :param threshold: 语音判定阈值（0-1），越大越严格
                         - 0.3: 宽松，容易触发（噪音环境用）
                         - 0.5: 标准，平衡
                         - 0.7: 严格，只检测明确语音
        :param min_speech_duration_ms: 最小语音时长（毫秒）
                                       低于此时长的语音被忽略（防误触发）
        :param min_silence_duration_ms: 最小静音时长（毫秒）
                                        连续静音超过此时长才认为说话结束
        :param window_size_samples: 处理窗口大小（样本数）
                                   512 = 32ms (推荐)
        """
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms
        self.window_size_samples = window_size_samples

        # 加载Silero VAD模型
        print("🔄 正在加载VAD模型...")
        self.model = load_silero_vad()
        print("✅ VAD模型加载完成！")

        # 状态变量
        self.reset()

    def reset(self):
        """重置检测器状态"""
        self.is_speaking = False  # 当前是否在说话
        self.speech_frames = 0  # 连续语音帧计数
        self.silence_frames = 0  # 连续静音帧计数
        self.total_frames = 0  # 总帧数

        # 计算帧数阈值
        ms_per_frame = (self.window_size_samples / self.sample_rate) * 1000
        self.min_speech_frames = int(self.min_speech_duration_ms / ms_per_frame)
        self.min_silence_frames = int(self.min_silence_duration_ms / ms_per_frame)

    def process_frame(self, audio_frame):
        """
        处理单个音频帧

        :param audio_frame: 音频数据（bytes或numpy array）
        :return: (is_speech, should_stop)
                 is_speech: 当前帧是否为语音
                 should_stop: 是否应该停止录音
        """
        # 转换为numpy数组
        if isinstance(audio_frame, bytes):
            audio_np = np.frombuffer(audio_frame, dtype=np.int16)
        else:
            audio_np = audio_frame

        # 归一化到 [-1, 1]
        audio_float = audio_np.astype(np.float32) / 32768.0

        # 确保长度正确
        if len(audio_float) != self.window_size_samples:
            # 填充或截断
            if len(audio_float) < self.window_size_samples:
                audio_float = np.pad(audio_float,
                                     (0, self.window_size_samples - len(audio_float)))
            else:
                audio_float = audio_float[:self.window_size_samples]

        # 转换为Tensor
        audio_tensor = torch.from_numpy(audio_float)

        # VAD检测
        speech_prob = self.model(audio_tensor, self.sample_rate).item()

        # 判断是否为语音
        is_speech = speech_prob > self.threshold

        # 更新状态
        self.total_frames += 1

        if is_speech:
            self.speech_frames += 1
            self.silence_frames = 0

            # 检测到足够长的语音，标记为"正在说话"
            if self.speech_frames >= self.min_speech_frames:
                self.is_speaking = True
        else:
            self.silence_frames += 1
            if self.is_speaking:
                self.speech_frames = 0

        # 判断是否应该停止
        should_stop = (
                self.is_speaking and
                self.silence_frames >= self.min_silence_frames
        )

        return is_speech, should_stop

    def process_audio_batch(self, audio_data):
        """
        处理整段音频（批量模式）
        用于分析已录制的音频

        :param audio_data: 完整音频数据（bytes或numpy array）
        :return: 包含语音片段的时间戳列表 [(start_ms, end_ms), ...]
        """
        # 转换为numpy数组
        if isinstance(audio_data, bytes):
            audio_np = np.frombuffer(audio_data, dtype=np.int16)
        else:
            audio_np = audio_data

        # 归一化
        audio_float = audio_np.astype(np.float32) / 32768.0

        # 转换为Tensor
        audio_tensor = torch.from_numpy(audio_float)

        # 获取语音时间戳
        timestamps = get_speech_timestamps(
            audio_tensor,
            self.model,
            sampling_rate=self.sample_rate,
            threshold=self.threshold,
            min_speech_duration_ms=self.min_speech_duration_ms,
            min_silence_duration_ms=self.min_silence_duration_ms
        )

        # 转换为毫秒
        result = []
        for ts in timestamps:
            start_ms = int(ts['start'] / self.sample_rate * 1000)
            end_ms = int(ts['end'] / self.sample_rate * 1000)
            result.append((start_ms, end_ms))

        return result


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("🎤 VAD检测器测试")
    print("=" * 60)

    # 创建VAD检测器
    vad = VADDetector(
        threshold=0.5,
        min_speech_duration_ms=250,
        min_silence_duration_ms=500
    )

    print("\n✅ VAD检测器创建成功！")
    print(f"📊 配置参数：")
    print(f"   - 采样率: {vad.sample_rate} Hz")
    print(f"   - 阈值: {vad.threshold}")
    print(f"   - 最小语音时长: {vad.min_speech_duration_ms} ms")
    print(f"   - 最小静音时长: {vad.min_silence_duration_ms} ms")
    print(f"   - 窗口大小: {vad.window_size_samples} 样本")

    # 测试单帧处理
    print("\n🧪 测试单帧处理...")
    test_frame = np.zeros(512, dtype=np.int16)  # 静音帧
    is_speech, should_stop = vad.process_frame(test_frame)
    print(f"   静音帧测试: is_speech={is_speech}, should_stop={should_stop}")

    print("\n✅ VAD模块测试完成！")