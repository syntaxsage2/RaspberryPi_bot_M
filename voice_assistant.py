# -*- coding:utf-8 -*-
"""
树莓派语音助手主程序
整合录音、语音识别、语音合成和播放功能
"""

import os
import sys
from config import (
    XFYUN_APPID, XFYUN_API_KEY, XFYUN_API_SECRET,
    OUTPUT_DIR, RECORDED_AUDIO, TTS_AUDIO,
    AUDIO_CONFIG, TTS_CONFIG
)
from xfyun_asr_manual import XFyunASRManual
from xfyun_tts_manual import XFyunTTSManual
from audio_utils import AudioRecorder, AudioPlayer


def setup_alsa_environment():
    """
    设置ALSA环境（模仿simple_raspberry_pi.py的设置）
    这是让音频正常工作的关键！
    """
    print(" 配置音频环境...")
    
    # 删除可能有问题的ALSA配置文件
    config_path = os.path.expanduser("~/.asoundrc")
    if os.path.exists(config_path):
        try:
            os.remove(config_path)
            print("   已删除旧的ALSA配置")
        except:
            pass
    
    # 设置环境变量（关键！）
    os.environ['AUDIODEV'] = 'plughw:1,0'
    os.environ['ALSA_CARD'] = '1'
    print("   已设置音频环境变量")


class VoiceAssistant:
    """语音助手主类"""
    
    def __init__(self):
        """初始化语音助手"""
        print("=" * 60)
        print(" 树莓派语音助手初始化中...")
        print("=" * 60)
        
        # 首先设置音频环境（关键步骤！）
        setup_alsa_environment()
        
        # 检查配置
        if not self._check_config():
            print(" 配置检查失败，请先在 config.py 中填写讯飞API凭证！")
            sys.exit(1)
        
        # 创建输出目录
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
            print(f" 创建输出目录：{OUTPUT_DIR}")
        
        # 初始化各个模块（修复：使用手动实现）
        self.asr = XFyunASRManual(XFYUN_APPID, XFYUN_API_KEY, XFYUN_API_SECRET)
        self.tts = XFyunTTSManual(XFYUN_APPID, XFYUN_API_KEY, XFYUN_API_SECRET)
        self.recorder = AudioRecorder(
            sample_rate=AUDIO_CONFIG["sample_rate"],
            channels=AUDIO_CONFIG["channels"],
            chunk=AUDIO_CONFIG["chunk"],
            input_device_index=AUDIO_CONFIG.get("input_device_index")  # 指定麦克风
        )
        self.player = AudioPlayer()
        
        print(" 语音助手初始化完成！")
        print("=" * 60)
    
    def _check_config(self):
        """检查配置是否完整"""
        if (XFYUN_APPID == "your_appid_here" or 
            XFYUN_API_KEY == "your_api_key_here" or 
            XFYUN_API_SECRET == "your_api_secret_here"):
            return False
        return True
    
    def listen(self, duration=5):
        """
        监听用户语音输入
        :param duration: 录音时长（秒）
        :return: 识别的文本
        """
        print("\n" + "=" * 60)
        print(" 开始监听...")
        print("=" * 60)

        # 录音
        audio_file = self.recorder.record(duration, RECORDED_AUDIO)

        # 语音识别（修复：使用 recognize_file 方法）
        print("\n" + "-" * 60)
        text = self.asr.recognize_file(audio_file)
        print("-" * 60)

        if text:
            print(f"\n 识别结果：{text}")
            return text
        else:
            print("\n  未识别到有效内容")
            return ""
    
    def speak(self, text):
        """
        语音播报
        :param text: 要播报的文本
        """
        print("\n" + "=" * 60)
        print(f" 准备播报：{text}")
        print("=" * 60)

        # 语音合成（修复：使用手动TTS）
        audio_file = self.tts.synthesize(
            text=text,
            output_file=TTS_AUDIO,
            vcn=TTS_CONFIG["vcn"],
            speed=TTS_CONFIG["speed"],
            volume=TTS_CONFIG["volume"],
            pitch=TTS_CONFIG["pitch"]
        )

        # 播放音频（修复：检查audio_file是否存在）
        if audio_file and os.path.exists(audio_file):
            print("\n" + "-" * 60)
            self.player.play(audio_file, wait=True)
            print("-" * 60)
        else:
            print(" 语音合成失败，无法播放")
    
    def test_mode(self):
        """测试模式：测试所有功能"""
        print("\n 进入测试模式")
        print("=" * 60)
        
        # 测试1：TTS语音播报
        print("\n【测试1】语音合成与播放")
        test_text = "你好，我是你的树莓派语音助手，很高兴为你服务。"
        self.speak(test_text)
        
        # 测试2：录音和语音识别
        print("\n【测试2】录音与语音识别")
        print(" 请在接下来的5秒内说话...")
        input("按回车键开始录音...")
        user_text = self.listen(duration=5)
        
        # 测试3：对话回复
        if user_text:
            print("\n【测试3】语音回复")
            response = f"我听到你说：{user_text}"
            self.speak(response)
        
        print("\n 测试完成！")
    
    def interactive_mode(self):
        """交互模式：持续对话"""
        print("\n 进入交互模式")
        print("=" * 60)
        print("提示：")
        print("  - 按回车键开始录音（5秒）")
        print("  - 输入 'quit' 或 'exit' 退出")
        print("  - 输入 'speak:文本' 直接播报文本")
        print("=" * 60)
        
        while True:
            try:
                # 等待用户指令
                user_input = input("\n 请输入指令（直接回车开始录音）：").strip()
                
                # 退出
                if user_input.lower() in ['quit', 'exit', '退出']:
                    print(" 再见！")
                    break
                
                # 直接播报
                elif user_input.startswith('speak:') or user_input.startswith('说:'):
                    text = user_input.split(':', 1)[1].strip()
                    if text:
                        self.speak(text)
                    else:
                        print("  请输入要播报的文本")
                
                # 录音识别
                else:
                    user_text = self.listen(duration=5)
                    
                    if user_text:
                        # 这里后续可以接入大模型
                        # 目前只做简单回复
                        response = f"收到，你说的是：{user_text}"
                        self.speak(response)
            
            except KeyboardInterrupt:
                print("\n\n 收到中断信号，再见！")
                break
            except Exception as e:
                print(f"\n 发生错误：{e}")
                continue
    
    def simple_test(self):
        """简单测试：单独测试TTS或ASR"""
        print("\n 简单测试模式")
        print("=" * 60)
        print("1. 测试语音合成（TTS）")
        print("2. 测试语音识别（ASR）")
        print("3. 测试完整流程")
        print("=" * 60)
        
        choice = input("请选择测试项目（1/2/3）：").strip()
        
        if choice == '1':
            text = input("请输入要合成的文本：").strip()
            if text:
                self.speak(text)
            else:
                print("  未输入文本")
        
        elif choice == '2':
            print(" 请准备，将在3秒后开始录音...")
            import time
            time.sleep(3)
            user_text = self.listen(duration=5)
            print(f"\n最终识别结果：{user_text}")
        
        elif choice == '3':
            self.test_mode()
        
        else:
            print("  无效选择")


def main():
    """主函数"""
    # 创建语音助手实例
    assistant = VoiceAssistant()
    
    # 显示菜单
    print("\n 请选择运行模式：")
    print("=" * 60)
    print("1. 测试模式（完整测试所有功能）")
    print("2. 交互模式（持续对话）")
    print("3. 简单测试（单独测试某个功能）")
    print("=" * 60)
    
    mode = input("请输入模式编号（1/2/3）：").strip()
    
    if mode == '1':
        assistant.test_mode()
    elif mode == '2':
        assistant.interactive_mode()
    elif mode == '3':
        assistant.simple_test()
    else:
        print("  无效的模式选择")
        print(" 默认进入交互模式...")
        assistant.interactive_mode()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n 程序已退出")
    except Exception as e:
        print(f"\n 程序出错：{e}")
        import traceback
        traceback.print_exc()

