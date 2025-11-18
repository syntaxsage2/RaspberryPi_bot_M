# -*- coding:utf-8 -*-
"""
Porcupine唤醒词检测器实现
适用于树莓派 Zero 2W，轻量高效
"""

import numpy as np
import pvporcupine
from wake_word_detector_base import WakeWordDetectorBase


class PorcupineDetector(WakeWordDetectorBase):
    """基于Porcupine的唤醒词检测器"""
    
    def __init__(self, access_key, keywords, sensitivities=None):
        """
        初始化Porcupine检测器
        
        :param access_key: Picovoice Access Key（从官网获取）
        :param keywords: 唤醒词列表，如 ["porcupine", "picovoice"]
        :param sensitivities: 敏感度列表（0.0-1.0），如 [0.5, 0.5]
                             0.0: 不敏感（误唤醒少，但可能漏检）
                             0.5: 平衡（推荐）
                             1.0: 非常敏感（易误唤醒）
        """
        super().__init__(keywords)
        self.access_key = access_key
        self.sensitivities = sensitivities or [0.5] * len(keywords)
        self.porcupine = None
        self.sample_rate = 16000  # Porcupine固定16kHz
        self.frame_length = 512   # Porcupine固定512样本
    
    def initialize(self):
        """
        初始化Porcupine引擎
        
        :return: 是否初始化成功
        """
        try:
            print("🔄 正在初始化Porcupine唤醒引擎...")
            
            self.porcupine = pvporcupine.create(
                access_key=self.access_key,
                keywords=self.keywords,
                sensitivities=self.sensitivities
            )
            
            self.is_active = True
            
            print("✅ Porcupine初始化成功！")
            print(f"   - 采样率: {self.sample_rate} Hz")
            print(f"   - 帧长度: {self.frame_length} 样本")
            print(f"   - 唤醒词: {', '.join(self.keywords)}")
            print(f"   - 敏感度: {self.sensitivities}")
            
            return True
            
        except Exception as e:
            print(f"❌ Porcupine初始化失败: {e}")
            self.is_active = False
            return False
    
    def detect(self, audio_frame):
        """
        检测音频帧中是否包含唤醒词
        
        :param audio_frame: 音频数据（bytes，int16格式）
        :return: (detected, keyword_index)
        """
        if not self.is_active or self.porcupine is None:
            return False, -1
        
        try:
            # 转换为numpy数组（int16）
            if isinstance(audio_frame, bytes):
                audio_np = np.frombuffer(audio_frame, dtype=np.int16)
            else:
                audio_np = audio_frame
            
            # 确保帧长度正确
            if len(audio_np) != self.frame_length:
                # 填充或截断
                if len(audio_np) < self.frame_length:
                    audio_np = np.pad(audio_np, (0, self.frame_length - len(audio_np)))
                else:
                    audio_np = audio_np[:self.frame_length]
            
            # Porcupine检测
            keyword_index = self.porcupine.process(audio_np)
            
            # keyword_index >= 0 表示检测到唤醒词
            if keyword_index >= 0:
                return True, keyword_index
            else:
                return False, -1
                
        except Exception as e:
            print(f"⚠️ Porcupine检测出错: {e}")
            return False, -1
    
    def cleanup(self):
        """清理资源"""
        if self.porcupine is not None:
            self.porcupine.delete()
            self.porcupine = None
            self.is_active = False
            print("🔌 Porcupine已清理")
    
    def get_frame_length(self):
        """获取要求的帧长度（样本数）"""
        return self.frame_length
    
    def get_sample_rate(self):
        """获取要求的采样率"""
        return self.sample_rate


# 测试代码
if __name__ == "__main__":
    import os
    
    print("=" * 60)
    print("🎤 Porcupine唤醒词检测器测试")
    print("=" * 60)
    
    # 从环境变量读取Access Key（或直接填写）
    ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY", "F+yqD3li4VHEtcnA1gtjQAHMmE1PNHXTL3q+pYR1z/95JlvC3CspSQ==")
    
    if ACCESS_KEY == "F+yqD3li4VHEtcnA1gtjQAHMmE1PNHXTL3q+pYR1z/95JlvC3CspSQ==":
        print("\n❌ 请先设置 PORCUPINE_ACCESS_KEY 环境变量或修改代码中的 ACCESS_KEY")
        print("   获取Access Key: https://console.picovoice.ai/")
        exit(1)
    
    # 创建检测器
    detector = PorcupineDetector(
        access_key=ACCESS_KEY,
        keywords=["porcupine"],  # 可以改为其他内置唤醒词
        sensitivities=[0.5]
    )
    
    # 初始化
    if detector.initialize():
        print("\n✅ 检测器创建成功！")
        print(f"📊 帧大小: {detector.get_frame_length()} 样本")
        print(f"📊 采样率: {detector.get_sample_rate()} Hz")
        
        # 测试静音帧
        print("\n🧪 测试静音帧...")
        test_frame = np.zeros(512, dtype=np.int16).tobytes()
        detected, index = detector.detect(test_frame)
        print(f"   结果: detected={detected}, index={index}")
        
        # 清理
        detector.cleanup()
        print("\n✅ 测试完成！")
    else:
        print("\n❌ 检测器初始化失败")

