# -*- coding:utf-8 -*-
"""
轻量级 VAD (Voice Activity Detection) 模块
使用 WebRTC VAD - 专为树莓派 Zero 2W 优化
"""

import webrtcvad
import collections
import time


class VADDetectorLite:
    """基于 WebRTC VAD 的轻量级语音活动检测器"""
    
    def __init__(self, 
                 sample_rate=16000,
                 aggressiveness=2,
                 frame_duration_ms=30,
                 padding_duration_ms=300,
                 min_silence_duration_ms=1500):
        """
        初始化轻量级 VAD 检测器
        
        :param sample_rate: 采样率，WebRTC VAD 支持 8000/16000/32000/48000
        :param aggressiveness: 敏感度 0-3
                              0: 质量优先（不敏感）
                              1: 平衡
                              2: 检测优先（较敏感）- 推荐
                              3: 最敏感
        :param frame_duration_ms: 帧时长（毫秒），只能是 10/20/30
        :param padding_duration_ms: 语音前后缓冲时长（毫秒）
        :param min_silence_duration_ms: 最小静音时长（毫秒），超过此时长认为说话结束
        """
        # 参数验证
        if sample_rate not in [8000, 16000, 32000, 48000]:
            raise ValueError("采样率必须是 8000, 16000, 32000 或 48000")
        
        if frame_duration_ms not in [10, 20, 30]:
            raise ValueError("帧时长必须是 10, 20 或 30 毫秒")
        
        if aggressiveness not in [0, 1, 2, 3]:
            raise ValueError("敏感度必须是 0-3")
        
        self.sample_rate = sample_rate
        self.aggressiveness = aggressiveness
        self.frame_duration_ms = frame_duration_ms
        self.padding_duration_ms = padding_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms
        
        # 创建 VAD 实例
        self.vad = webrtcvad.Vad(aggressiveness)
        
        # 计算帧大小（字节数）
        # 公式：采样率 * 帧时长(秒) * 2字节(int16)
        self.frame_size_bytes = int(sample_rate * frame_duration_ms / 1000 * 2)
        
        # 计算缓冲帧数
        self.padding_frames = int(padding_duration_ms / frame_duration_ms)
        self.silence_frames = int(min_silence_duration_ms / frame_duration_ms)
        
        # 状态变量
        self.reset()
        
        print(f"✅ WebRTC VAD 初始化完成")
        print(f"   - 采样率: {sample_rate} Hz")
        print(f"   - 敏感度: {aggressiveness} (0=低 3=高)")
        print(f"   - 帧大小: {self.frame_size_bytes} 字节 ({frame_duration_ms}ms)")
    
    def reset(self):
        """重置检测器状态"""
        self.is_speaking = False
        self.triggered = False
        self.voiced_frames = []  # 缓冲区
        self.ring_buffer = collections.deque(maxlen=self.padding_frames)
        self.silence_counter = 0
        self.total_frames = 0
    
    def process_frame(self, audio_frame):
        """
        处理单个音频帧
        
        :param audio_frame: 音频数据（bytes），长度必须等于 frame_size_bytes
        :return: (is_speech, should_stop, buffered_audio)
                 is_speech: 当前帧是否为语音
                 should_stop: 是否应该停止录音
                 buffered_audio: 缓冲的音频数据（bytes），用于返回完整语音
        """
        # 验证帧大小
        if len(audio_frame) != self.frame_size_bytes:
            # 自动调整（填充或截断）
            if len(audio_frame) < self.frame_size_bytes:
                audio_frame = audio_frame + b'\x00' * (self.frame_size_bytes - len(audio_frame))
            else:
                audio_frame = audio_frame[:self.frame_size_bytes]
        
        # VAD 检测
        is_speech = self.vad.is_speech(audio_frame, self.sample_rate)
        
        self.total_frames += 1
        should_stop = False
        buffered_audio = None
        
        if not self.triggered:
            # 未触发状态：等待检测到语音
            self.ring_buffer.append((audio_frame, is_speech))
            num_voiced = len([f for f, speech in self.ring_buffer if speech])
            
            # 如果缓冲区中有足够多的语音帧，触发录音
            if num_voiced > 0.5 * self.ring_buffer.maxlen:
                self.triggered = True
                self.is_speaking = True
                # 将缓冲区的内容加入录音
                self.voiced_frames.extend([f for f, s in self.ring_buffer])
                self.ring_buffer.clear()
                print("🗣️  检测到语音，开始录音...")
        else:
            # 已触发状态：录音中
            self.voiced_frames.append(audio_frame)
            self.ring_buffer.append((audio_frame, is_speech))
            num_unvoiced = len([f for f, speech in self.ring_buffer if not speech])
            
            # 如果缓冲区中大部分是静音帧，增加静音计数
            if num_unvoiced > 0.9 * self.ring_buffer.maxlen:
                self.silence_counter += 1
            else:
                self.silence_counter = 0
            
            # 如果静音持续足够长，停止录音
            if self.silence_counter >= self.silence_frames:
                should_stop = True
                self.is_speaking = False
                # 返回完整的录音数据
                buffered_audio = b''.join(self.voiced_frames)
        
        return is_speech, should_stop, buffered_audio
    
    def get_frame_size_bytes(self):
        """获取帧大小（字节数）"""
        return self.frame_size_bytes


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("🎤 轻量级 VAD 检测器测试")
    print("=" * 60)
    
    # 创建 VAD 检测器
    vad = VADDetectorLite(
        sample_rate=16000,
        aggressiveness=2,
        frame_duration_ms=30,
        padding_duration_ms=300,
        min_silence_duration_ms=800
    )
    
    print(f"\n📊 帧大小: {vad.get_frame_size_bytes()} 字节")
    print("✅ VAD 检测器创建成功！")
    
    # 测试单帧处理
    print("\n🧪 测试单帧处理...")
    import numpy as np
    test_frame = np.zeros(vad.frame_size_bytes, dtype=np.uint8).tobytes()
    is_speech, should_stop, audio = vad.process_frame(test_frame)
    print(f"   静音帧测试: is_speech={is_speech}, should_stop={should_stop}")
    
    print("\n✅ VAD 模块测试完成！")

