# -*- coding:utf-8 -*-
"""
树莓派语音助手主程序
整合录音、语音识别、语音合成和播放功能
"""

import os
import sys
import time
import pyaudio
from config import (
    XFYUN_APPID, XFYUN_API_KEY, XFYUN_API_SECRET,
    OUTPUT_DIR, RECORDED_AUDIO, TTS_AUDIO,
    AUDIO_CONFIG, TTS_CONFIG, VAD_CONFIG, WAKE_RESPONSE_CONFIG,
    PORCUPINE_ACCESS_KEY, PORCUPINE_USE_CUSTOM,
    PORCUPINE_CUSTOM_MODEL_PATH, PORCUPINE_CUSTOM_KEYWORD,
    PORCUPINE_LANGUAGE_MODEL_PATH, PORCUPINE_SENSITIVITY,
    PORCUPINE_BUILTIN_KEYWORDS
)
from xfyun_asr_manual import XFyunASRManual
from xfyun_asr_stream import XFyunASRStream  # 流式ASR
from xfyun_tts_manual import XFyunTTSManual
from xfyun_tts_stream import XFyunTTSStream  # 流式TTS
from audio_utils import AudioRecorder, AudioPlayer


def setup_alsa_environment():
    """
    设置ALSA环境
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
        self.asr_stream = XFyunASRStream(XFYUN_APPID, XFYUN_API_KEY, XFYUN_API_SECRET)  # 流式ASR
        self.tts = XFyunTTSManual(XFYUN_APPID, XFYUN_API_KEY, XFYUN_API_SECRET)
        self.tts_stream = XFyunTTSStream(XFYUN_APPID, XFYUN_API_KEY, XFYUN_API_SECRET)  # 流式TTS
        self.recorder = AudioRecorder(
            sample_rate=AUDIO_CONFIG["sample_rate"],
            channels=AUDIO_CONFIG["channels"],
            chunk=AUDIO_CONFIG["chunk"],
            input_device_index=AUDIO_CONFIG.get("input_device_index")  # 指定麦克风
        )
        self.player = AudioPlayer()
        
        # 默认使用流式模式（更低延迟）
        self.use_stream_asr = True  # 流式识别
        self.use_stream_tts = True  # 流式播放
        
        # 初始化唤醒词检测器
        self.wake_word_detector = None
        self._init_wake_word_detector()
        
        print(" 语音助手初始化完成！")
        print("=" * 60)
    
    def _init_wake_word_detector(self):
        """初始化唤醒词检测器"""
        if not PORCUPINE_ACCESS_KEY or PORCUPINE_ACCESS_KEY == "你的AccessKey":
            print("⚠️  未配置Porcupine Access Key，唤醒功能未启用")
            print("   请在 config.py 中配置 PORCUPINE_ACCESS_KEY")
            return False
        
        try:
            if PORCUPINE_USE_CUSTOM:
                # 使用自定义中文唤醒词
                from wake_word_detector_porcupine_custom import PorcupineCustomDetector
                
                if not os.path.exists(PORCUPINE_CUSTOM_MODEL_PATH):
                    print(f"⚠️  自定义模型文件不存在: {PORCUPINE_CUSTOM_MODEL_PATH}")
                    return False
                
                self.wake_word_detector = PorcupineCustomDetector(
                    access_key=PORCUPINE_ACCESS_KEY,
                    keyword_paths=[PORCUPINE_CUSTOM_MODEL_PATH],
                    keywords=[PORCUPINE_CUSTOM_KEYWORD],
                    sensitivities=[PORCUPINE_SENSITIVITY],
                    model_path=PORCUPINE_LANGUAGE_MODEL_PATH
                )
                print(f"🎯 使用自定义唤醒词: {PORCUPINE_CUSTOM_KEYWORD}")
            else:
                # 使用内置英文唤醒词
                from wake_word_detector_porcupine import PorcupineDetector
                
                self.wake_word_detector = PorcupineDetector(
                    access_key=PORCUPINE_ACCESS_KEY,
                    keywords=PORCUPINE_BUILTIN_KEYWORDS,
                    sensitivities=[PORCUPINE_SENSITIVITY] * len(PORCUPINE_BUILTIN_KEYWORDS)
                )
                print(f"🎯 使用内置唤醒词: {', '.join(PORCUPINE_BUILTIN_KEYWORDS)}")
            
            if self.wake_word_detector.initialize():
                print("✅ 唤醒词检测器已启用")
                return True
            else:
                print("❌ 唤醒词检测器初始化失败")
                self.wake_word_detector = None
                return False
                
        except Exception as e:
            print(f"❌ 唤醒词检测器加载失败: {e}")
            self.wake_word_detector = None
            return False
    
    def _check_config(self):
        """检查配置是否完整"""
        if (XFYUN_APPID == "your_appid_here" or 
            XFYUN_API_KEY == "your_api_key_here" or 
            XFYUN_API_SECRET == "your_api_secret_here"):
            return False
        return True

    def listen(self, duration=5, use_stream=None, use_vad=False):
        """
        监听用户语音输入
        :param duration: 录音时长（秒），VAD模式下作为最大时长
        :param use_stream: 是否使用流式识别（None则使用默认设置）
        :param use_vad: 是否使用VAD自动检测（推荐！）
        :return: 识别的文本
        """
        print("\n" + "=" * 60)
        print("👂 开始监听...")
        if use_vad:
            print("🧠 轻量级VAD模式：自动检测说话结束（适配Zero 2W）")
        print("=" * 60)

        # 确定使用流式还是非流式
        if use_stream is None:
            use_stream = self.use_stream_asr

        if use_vad:
            # VAD模式：使用轻量级录音
            print("⚡ 使用轻量级VAD录音（WebRTC）")

            audio_data, actual_duration = self.recorder.record_with_vad_lite(
                max_duration=duration,
                output_file=RECORDED_AUDIO if not use_stream else None,
                aggressiveness=2,  # 标准敏感度
                min_silence_duration_ms=800
            )

            if not audio_data:
                print("\n⚠️  未录制到音频")
                return ""

            if use_stream:
                # 流式识别：启动ASR
                self.asr_stream.start_recognition()

                # 分帧发送音频
                chunk_size = self.recorder.chunk * 2  # 字节数
                for i in range(0, len(audio_data), chunk_size):
                    frame = audio_data[i:i + chunk_size]
                    self.asr_stream.add_audio_frame(frame)

                # 结束识别
                self.asr_stream.finish_recording()
                text = self.asr_stream.wait_result(timeout=10)
            else:
                # 传统识别
                text = self.asr.recognize_file(RECORDED_AUDIO)

        else:
            # 非VAD模式（固定时长）
            if use_stream:
                print("⚡ 使用流式识别模式（零延迟）")
                self.asr_stream.start_recognition()

                self.recorder.record_stream(
                    duration=duration,
                    frame_callback=self.asr_stream.add_audio_frame,
                    output_file=None
                )

                self.asr_stream.finish_recording()
                text = self.asr_stream.wait_result(timeout=10)
            else:
                print("💾 使用传统识别模式")
                audio_file = self.recorder.record(duration, RECORDED_AUDIO)
                text = self.asr.recognize_file(audio_file)

        if text:
            print(f"\n✅ 识别结果：{text}")
            return text
        else:
            print("\n⚠️  未识别到有效内容")
            return ""
    
    def speak(self, text, use_stream=None):
        """
        语音播报
        :param text: 要播报的文本
        :param use_stream: 是否使用流式播放（None则使用默认设置）
        """
        print("\n" + "=" * 60)
        print(f"🔊 准备播报：{text}")
        print("=" * 60)

        # 确定使用流式还是非流式
        if use_stream is None:
            use_stream = self.use_stream_tts
        
        if use_stream:
            # 流式播放（推荐，延迟更低）
            print("⚡ 使用流式播放模式（低延迟）")
            self.tts_stream.synthesize_and_play(
                text=text,
                vcn=TTS_CONFIG["vcn"],
                speed=TTS_CONFIG["speed"],
                volume=TTS_CONFIG["volume"],
                pitch=TTS_CONFIG["pitch"],
                save_file=None  # 不保存文件，直接播放
            )
        else:
            # 传统方式（完整文件播放）
            print("💾 使用传统播放模式（保存文件）")
            audio_file = self.tts.synthesize(
                text=text,
                output_file=TTS_AUDIO,
                vcn=TTS_CONFIG["vcn"],
                speed=TTS_CONFIG["speed"],
                volume=TTS_CONFIG["volume"],
                pitch=TTS_CONFIG["pitch"]
            )

            # 播放音频
            if audio_file and os.path.exists(audio_file):
                print("\n" + "-" * 60)
                self.player.play(audio_file, wait=True)
                print("-" * 60)
            else:
                print("❌ 语音合成失败，无法播放")
    
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
        print("\n🎙️ 进入交互模式")
        print("=" * 60)
        print("提示：")
        print("  - 按回车键开始录音（VAD智能检测结束）")
        print("  - 输入 'quit' 或 'exit' 退出")
        print("  - 输入 'speak:文本' 直接播报文本")
        print("  - 输入 'vad' 切换VAD开关")
        print(f"  - VAD状态：{'✅ 开启（智能检测）' if self.use_vad else '❌ 关闭（固定5秒）'}")
        print("=" * 60)

        # 添加VAD开关
        self.use_vad = True  # 默认开启VAD

        while True:
            try:
                # 等待用户指令
                user_input = input("\n🎤 请输入指令（直接回车开始录音）：").strip()

                # 退出
                if user_input.lower() in ['quit', 'exit', '退出']:
                    print("👋 再见！")
                    break

                # 切换VAD
                elif user_input.lower() == 'vad':
                    self.use_vad = not self.use_vad
                    status = '✅ 开启（智能检测）' if self.use_vad else '❌ 关闭（固定5秒）'
                    print(f"💡 VAD已切换: {status}")
                    continue

                # 直接播报
                elif user_input.startswith('speak:') or user_input.startswith('说:'):
                    text = user_input.split(':', 1)[1].strip()
                    if text:
                        self.speak(text)
                    else:
                        print("⚠️ 请输入要播报的文本")

                # 录音识别（使用VAD）
                else:
                    user_text = self.listen(duration=30, use_vad=self.use_vad)

                    if user_text:
                        # 这里后续可以接入大模型
                        # 目前只做简单回复
                        response = f"收到，你说的是：{user_text}"
                        self.speak(response)

            except KeyboardInterrupt:
                print("\n\n⚠️ 收到中断信号，再见！")
                break
            except Exception as e:
                print(f"\n❌ 发生错误：{e}")
                continue
    
    def run_with_wake_word(self):
        """唤醒词模式：等待唤醒 → 播放回应 → VAD录音 → ASR识别 → 回复 → 循环"""
        if not self.wake_word_detector:
            print("❌ 唤醒词检测器未初始化，无法使用唤醒模式")
            print("   请检查 config.py 中的 PORCUPINE_ACCESS_KEY 配置")
            return
        
        print("\n" + "=" * 60)
        print("🎤 语音助手 - 唤醒词模式")
        print("=" * 60)
        
        if PORCUPINE_USE_CUSTOM:
            print(f"🎯 唤醒词: {PORCUPINE_CUSTOM_KEYWORD}")
        else:
            print(f"🎯 唤醒词: {', '.join(PORCUPINE_BUILTIN_KEYWORDS)}")
        
        print(f"🎚️  敏感度: {PORCUPINE_SENSITIVITY}")
        print(f"💬 回应语: 你好，明")
        print(f"⏱️  监听超时: {WAKE_RESPONSE_CONFIG['listen_timeout']}秒")
        print("=" * 60)
        print("💡 说出唤醒词来激活助手（按Ctrl+C退出）")
        print("=" * 60)
        
        # 初始化PyAudio
        audio = pyaudio.PyAudio()
        
        try:
            # 打开音频流
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.wake_word_detector.get_sample_rate(),
                input=True,
                input_device_index=AUDIO_CONFIG.get('input_device_index'),
                frames_per_buffer=self.wake_word_detector.get_frame_length()
            )
            
            print("🎙️  监听唤醒词中...\n")
            
            wake_count = 0
            
            while True:
                # 读取音频帧
                pcm_data = stream.read(self.wake_word_detector.get_frame_length(), exception_on_overflow=False)
                
                # 检测唤醒词
                detected, keyword_index = self.wake_word_detector.detect(pcm_data)
                
                if detected and keyword_index >= 0:
                    wake_count += 1
                    keyword = PORCUPINE_CUSTOM_KEYWORD if PORCUPINE_USE_CUSTOM else PORCUPINE_BUILTIN_KEYWORDS[keyword_index]
                    
                    print(f"\n✨ 检测到唤醒词: {keyword}")
                    print(f"🔔 这是第 {wake_count} 次唤醒\n")
                    
                    # 播放回应语音："你好，明"（本地音频文件）
                    response_audio = WAKE_RESPONSE_CONFIG.get('response_audio')
                    if response_audio and os.path.exists(response_audio):
                        print("🔊 播放回应: 你好，明")
                        try:
                            self.player.play(response_audio, wait=True)
                        except Exception as e:
                            print(f"⚠️  播放回应失败: {e}")
                    else:
                        print(f"⚠️  回应音频文件不存在: {response_audio}")
                        print("   请将 '你好明.wav' 放置到 ./audio_files/ 目录")
                    
                    # 暂停唤醒检测流（避免录制时检测到自己的声音）
                    stream.stop_stream()
                    
                    # 使用VAD录制用户语音
                    print("\n📝 请说话...")
                    try:
                        audio_data, duration = self.recorder.record_with_vad_lite(
                            max_duration=WAKE_RESPONSE_CONFIG['listen_timeout'],
                            aggressiveness=VAD_CONFIG['aggressiveness'],
                            min_silence_duration_ms=VAD_CONFIG['min_silence_duration_ms']
                        )
                        
                        if audio_data is None or len(audio_data) == 0:
                            print("⚠️  未检测到语音输入")
                            # 重新开始监听唤醒词
                            stream.start_stream()
                            print("\n🎙️  监听唤醒词中...\n")
                            continue
                        
                        print(f"✅ 录音完成（时长: {duration:.1f}秒）")
                        
                        # ASR识别
                        print("🔄 识别中...")
                        if self.use_stream_asr:
                            # 流式识别：启动ASR
                            self.asr_stream.start_recognition()
                            
                            # 分帧发送音频
                            chunk_size = self.recorder.chunk * 2  # 字节数
                            for i in range(0, len(audio_data), chunk_size):
                                frame = audio_data[i:i + chunk_size]
                                self.asr_stream.add_audio_frame(frame)
                            
                            # 结束识别
                            self.asr_stream.finish_recording()
                            user_text = self.asr_stream.wait_result(timeout=10)
                        else:
                            # 手动识别
                            user_text = self.asr.recognize(audio_data)
                        
                        if not user_text:
                            print("❌ 识别失败或未识别到内容")
                            # 重新开始监听唤醒词
                            stream.start_stream()
                            print("\n🎙️  监听唤醒词中...\n")
                            continue
                        
                        print(f"💬 用户: {user_text}")
                        
                        # 简单回复（后续可接LLM）
                        reply = self._generate_simple_reply(user_text)
                        print(f"🤖 助手: {reply}")
                        
                        # TTS播放回复
                        self.speak(reply)
                        
                        # 继续监听唤醒词
                        if WAKE_RESPONSE_CONFIG.get('return_to_wake_mode', True):
                            stream.start_stream()
                            print("\n🎙️  监听唤醒词中...\n")
                        else:
                            print("✅ 对话结束")
                            break
                    
                    except Exception as e:
                        print(f"❌ 处理用户语音时出错: {e}")
                        # 重新开始监听唤醒词
                        stream.start_stream()
                        print("\n🎙️  监听唤醒词中...\n")
                        continue
        
        except KeyboardInterrupt:
            print("\n\n⚠️  用户中断")
        
        except Exception as e:
            print(f"\n❌ 唤醒模式运行出错: {e}")
        
        finally:
            # 清理资源
            try:
                stream.stop_stream()
                stream.close()
            except:
                pass
            
            audio.terminate()
            
            if self.wake_word_detector:
                self.wake_word_detector.cleanup()
            
            print(f"\n✅ 唤醒模式结束（总共唤醒 {wake_count} 次）")
    
    def _generate_simple_reply(self, user_text):
        """
        生成简单回复（后续可接入LLM）
        :param user_text: 用户输入文本
        :return: 回复文本
        """
        user_text_lower = user_text.lower()
        
        # 简单的关键词匹配
        if "天气" in user_text:
            return "今天天气不错，适合出门散步"
        elif "时间" in user_text or "几点" in user_text:
            import datetime
            now = datetime.datetime.now()
            return f"现在是{now.hour}点{now.minute}分"
        elif "你好" in user_text or "hello" in user_text_lower:
            return "你好，有什么可以帮助你的吗？"
        elif "再见" in user_text or "拜拜" in user_text:
            return "再见，期待下次与你聊天"
        elif "谢谢" in user_text:
            return "不客气，很高兴能帮到你"
        else:
            return f"我听到你说：{user_text}。这是一个测试回复，后续可以接入大语言模型"
    
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
    print("\n🚀 请选择运行模式：")
    print("=" * 60)
    print("1. 测试模式（完整测试所有功能）")
    print("2. 交互模式（持续对话）")
    print("3. 简单测试（单独测试某个功能）")
    print("4. 唤醒词模式（🌟推荐：唤醒 → 对话 → 循环）")
    print("=" * 60)
    
    mode = input("请输入模式编号（1/2/3/4）：").strip()
    
    if mode == '1':
        assistant.test_mode()
    elif mode == '2':
        assistant.interactive_mode()
    elif mode == '3':
        assistant.simple_test()
    elif mode == '4':
        assistant.run_with_wake_word()
    else:
        print("❌ 无效的模式选择")
        print("💡 默认进入交互模式...")
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

