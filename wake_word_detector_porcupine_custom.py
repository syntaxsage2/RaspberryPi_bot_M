# -*- coding:utf-8 -*-
"""
Porcupine自定义唤醒词检测器实现
支持加载自定义训练的.ppn模型文件
"""

import numpy as np
import pvporcupine
from wake_word_detector_base import WakeWordDetectorBase


class PorcupineCustomDetector(WakeWordDetectorBase):
    """基于Porcupine的自定义唤醒词检测器"""
    
    def __init__(self, access_key, keyword_paths, keywords=None, sensitivities=None, model_path=None):
        """
        初始化Porcupine自定义检测器
        
        :param access_key: Picovoice Access Key（从官网获取）
        :param keyword_paths: 自定义唤醒词模型文件路径列表
                             如 ["./models/语音小智_zh_raspberry-pi_v3_0_0.ppn"]
        :param keywords: 唤醒词名称列表（用于显示），如 ["语音小智"]
        :param sensitivities: 敏感度列表（0.0-1.0），如 [0.5]
                             0.0: 不敏感（误唤醒少，但可能漏检）
                             0.5: 平衡（推荐）
                             1.0: 非常敏感（易误唤醒）
        :param model_path: 语言模型文件路径（.pv文件）
                          如 "./models/porcupine_params_zh.pv" 用于中文
                          如果为None，使用默认英文模型
        """
        # 如果没提供keywords名称，从文件名提取
        if keywords is None:
            import os
            keywords = [os.path.basename(path).replace('.ppn', '') for path in keyword_paths]
        
        super().__init__(keywords)
        
        self.access_key = access_key
        self.keyword_paths = keyword_paths if isinstance(keyword_paths, list) else [keyword_paths]
        self.sensitivities = sensitivities or [0.5] * len(self.keyword_paths)
        self.model_path = model_path  # 语言模型路径
        self.porcupine = None
        self.sample_rate = 16000  # Porcupine固定16kHz
        self.frame_length = 512   # Porcupine固定512样本
    
    def initialize(self):
        """
        初始化Porcupine引擎
        
        :return: 是否初始化成功
        """
        try:
            print("🔄 正在初始化Porcupine自定义唤醒引擎...")
            
            # 检查模型文件是否存在
            import os
            for path in self.keyword_paths:
                if not os.path.exists(path):
                    print(f"❌ 模型文件不存在: {path}")
                    return False
                print(f"   找到模型: {path}")
            
            # 创建Porcupine实例（使用keyword_paths而不是keywords）
            # 如果指定了语言模型，需要先检查文件是否存在
            if self.model_path:
                if not os.path.exists(self.model_path):
                    print(f"❌ 语言模型文件不存在: {self.model_path}")
                    print(f"💡 请从以下地址下载中文模型:")
                    print(f"   https://github.com/Picovoice/porcupine/raw/master/lib/common/porcupine_params_zh.pv")
                    return False
                print(f"   使用语言模型: {self.model_path}")
            
            self.porcupine = pvporcupine.create(
                access_key=self.access_key,
                keyword_paths=self.keyword_paths,  # 使用模型文件路径
                sensitivities=self.sensitivities,
                model_path=self.model_path  # 指定语言模型
            )
            
            self.is_active = True
            
            print("✅ Porcupine自定义模型初始化成功！")
            print(f"   - 采样率: {self.sample_rate} Hz")
            print(f"   - 帧长度: {self.frame_length} 样本")
            print(f"   - 唤醒词: {', '.join(self.keywords)}")
            print(f"   - 模型数: {len(self.keyword_paths)}")
            print(f"   - 敏感度: {self.sensitivities}")
            
            return True
            
        except Exception as e:
            print(f"❌ Porcupine初始化失败: {e}")
            import traceback
            traceback.print_exc()
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
    print("🎤 Porcupine自定义唤醒词检测器测试")
    print("=" * 60)
    
    # 从环境变量读取Access Key
    ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY", "你的AccessKey")
    
    if ACCESS_KEY == "你的AccessKey":
        print("\n❌ 请先设置 PORCUPINE_ACCESS_KEY 环境变量或修改代码中的 ACCESS_KEY")
        print("   获取Access Key: https://console.picovoice.ai/")
        exit(1)
    
    # 配置自定义模型路径
    MODEL_PATH = "./小智_zh_raspberry-pi_v3_0_0.ppn"
    
    if not os.path.exists(MODEL_PATH):
        print(f"\n❌ 模型文件不存在: {MODEL_PATH}")
        print("   请将模型文件放在项目根目录")
        exit(1)
    
    # 创建检测器
    detector = PorcupineCustomDetector(
        access_key=ACCESS_KEY,
        keyword_paths=[MODEL_PATH],
        keywords=["小智小智"],  # 显示名称
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

