# -*- coding:utf-8 -*-
"""
唤醒词检测器抽象基类
使用此基类可以轻松切换不同的唤醒词引擎（Porcupine、讯飞、Snowboy等）
"""

from abc import ABC, abstractmethod


class WakeWordDetectorBase(ABC):
    """唤醒词检测器抽象基类"""
    
    def __init__(self, keywords):
        """
        初始化唤醒词检测器
        
        :param keywords: 唤醒词列表，如 ["小助手", "你好"]
        """
        self.keywords = keywords if isinstance(keywords, list) else [keywords]
        self.is_active = False
    
    @abstractmethod
    def initialize(self):
        """
        初始化检测器（子类实现）
        
        :return: 是否初始化成功
        """
        pass
    
    @abstractmethod
    def detect(self, audio_frame):
        """
        检测音频帧中是否包含唤醒词（子类实现）
        
        :param audio_frame: 音频数据（bytes）
        :return: (detected, keyword_index)
                 detected: 是否检测到唤醒词
                 keyword_index: 检测到的唤醒词索引（-1表示未检测到）
        """
        pass
    
    @abstractmethod
    def cleanup(self):
        """
        清理资源（子类实现）
        """
        pass
    
    def get_keyword(self, index):
        """
        根据索引获取唤醒词
        
        :param index: 唤醒词索引
        :return: 唤醒词字符串
        """
        if 0 <= index < len(self.keywords):
            return self.keywords[index]
        return None
    
    def __enter__(self):
        """支持上下文管理器"""
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器"""
        self.cleanup()

