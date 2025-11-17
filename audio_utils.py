# -*- coding:utf-8 -*-
"""
音频工具模块
提供录音和播放功能
"""

import pyaudio
import wave
import pygame
import os


class AudioRecorder:
    """音频录制类"""

    def __init__(self, sample_rate=16000, channels=1, chunk=1024, input_device_index=None):
        """
        初始化录音器
        :param sample_rate: 采样率
        :param channels: 声道数
        :param chunk: 音频块大小
        :param input_device_index: 输入设备ID
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk = chunk
        self.format = pyaudio.paInt16
        self.input_device_index = input_device_index
        self._tested_sample_rates = [16000, 44100, 48000, 22050]  # 常见采样率
        self.is_recording = False  # 录音状态标志
        
    def _find_supported_sample_rate(self, audio):
        """找到设备支持的采样率"""
        for rate in self._tested_sample_rates:
            try:
                # 尝试打开音频流测试采样率
                stream = audio.open(
                    format=self.format,
                    channels=self.channels,
                    rate=rate,
                    input=True,
                    input_device_index=self.input_device_index,
                    frames_per_buffer=self.chunk,
                    start=False  # 不启动流，只测试配置
                )
                stream.close()
                print(f"  ✓ 设备支持采样率: {rate}Hz")
                return rate
            except Exception:
                continue

        # 如果都不支持，尝试使用默认采样率
        print(f"  ⚠ 使用默认采样率: {self.sample_rate}Hz")
        return self.sample_rate

    def record(self, duration, output_file):
        """
        录制音频
        :param duration: 录制时长（秒）
        :param output_file: 输出文件路径（.pcm或.wav）
        :return: 录制的文件路径
        """
        print(f"  开始录音，时长 {duration} 秒...")

        # 初始化PyAudio
        audio = pyaudio.PyAudio()

        try:
            # 检测支持的采样率
            actual_sample_rate = self._find_supported_sample_rate(audio)

            # 打开音频流
            print(f"  使用采样率: {actual_sample_rate}Hz, 设备ID: {self.input_device_index}")

            stream = audio.open(
                format=self.format,
                channels=self.channels,
                rate=actual_sample_rate,
                input=True,
                input_device_index=self.input_device_index,  # 指定麦克风设备
                frames_per_buffer=self.chunk
            )

            frames = []

            # 录制音频
            for i in range(0, int(actual_sample_rate / self.chunk * duration)):
                data = stream.read(self.chunk)
                frames.append(data)

                # 显示进度
                progress = (i + 1) / (actual_sample_rate / self.chunk * duration) * 100
                print(f"\r录音中... {progress:.0f}%", end='', flush=True)

            print("\n 录音完成！")

            # 停止录音
            stream.stop_stream()
            stream.close()

            # 保存音频文件（使用实际采样率）
            if output_file.endswith('.pcm'):
                # 保存为PCM格式（用于讯飞ASR）
                with open(output_file, 'wb') as f:
                    f.write(b''.join(frames))
            elif output_file.endswith('.wav'):
                # 保存为WAV格式
                with wave.open(output_file, 'wb') as wf:
                    wf.setnchannels(self.channels)
                    wf.setsampwidth(audio.get_sample_size(self.format))
                    wf.setframerate(actual_sample_rate)  # 使用实际采样率
                    wf.writeframes(b''.join(frames))
            else:
                raise ValueError("不支持的文件格式，请使用.pcm或.wav")

            print(f" 音频已保存到：{output_file}")
            return output_file

        except Exception as e:
            print(f"\n ❌ 录音失败: {e}")
            raise
        finally:
            # 确保PyAudio被正确关闭
            audio.terminate()

    def record_stream(self, duration, frame_callback, output_file=None):
        """
        流式录音 - 边录边回调
        :param duration: 录制时长（秒）
        :param frame_callback: 回调函数，每录制一帧就调用 callback(audio_data)
        :param output_file: 可选，同时保存到文件
        :return: 录制的文件路径（如果提供了output_file）
        """
        print(f"🎙️ 开始流式录音，时长 {duration} 秒...")
        
        self.is_recording = True
        frames = []
        
        # 初始化PyAudio
        audio = pyaudio.PyAudio()
        
        try:
            # 使用16kHz采样率（讯飞ASR要求）
            actual_sample_rate = 16000
            
            # 使用1280字节块大小（讯飞ASR推荐）
            chunk_size = 1280
            
            print(f"  使用采样率: {actual_sample_rate}Hz, 块大小: {chunk_size}字节")
            
            # 打开音频流
            stream = audio.open(
                format=self.format,
                channels=self.channels,
                rate=actual_sample_rate,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=chunk_size
            )
            
            # 计算总帧数
            total_frames = int(actual_sample_rate / chunk_size * duration)
            
            # 录音循环
            for i in range(total_frames):
                if not self.is_recording:
                    break
                
                # 读取音频数据
                data = stream.read(chunk_size, exception_on_overflow=False)
                
                # 立即回调（关键！边录边发）
                if frame_callback:
                    frame_callback(data)
                
                # 如果需要保存文件
                if output_file:
                    frames.append(data)
                
                # 显示进度
                progress = (i + 1) / total_frames * 100
                print(f"\r🔴 录音中... {progress:.0f}%", end='', flush=True)
            
            print("\n✅ 录音完成！")
            
            # 停止录音
            stream.stop_stream()
            stream.close()
            
            # 保存文件（如果需要）
            if output_file and frames:
                output_dir = os.path.dirname(output_file)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)
                
                if output_file.endswith('.pcm'):
                    # 保存为PCM格式
                    with open(output_file, 'wb') as f:
                        f.write(b''.join(frames))
                elif output_file.endswith('.wav'):
                    # 保存为WAV格式
                    with wave.open(output_file, 'wb') as wf:
                        wf.setnchannels(self.channels)
                        wf.setsampwidth(audio.get_sample_size(self.format))
                        wf.setframerate(actual_sample_rate)
                        wf.writeframes(b''.join(frames))
                
                print(f"💾 音频已保存到：{output_file}")
                return output_file
            
            return None
            
        except Exception as e:
            print(f"\n❌ 录音失败: {e}")
            raise
        finally:
            self.is_recording = False
            audio.terminate()
    
    def stop_recording(self):
        """停止录音"""
        self.is_recording = False


class AudioPlayer:
    """音频播放类"""
    
    def __init__(self):
        """初始化播放器"""
        pygame.mixer.init()
        
    def play(self, audio_file, wait=True):
        """
        播放音频文件
        :param audio_file: 音频文件路径
        :param wait: 是否等待播放完成
        """
        if not os.path.exists(audio_file):
            print(f" 文件不存在：{audio_file}")
            return
        
        print(f" 播放音频：{audio_file}")
        
        try:
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            
            if wait:
                # 等待播放完成
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
                print(" 播放完成！")
        except Exception as e:
            print(f" 播放失败：{e}")
    
    def stop(self):
        """停止播放"""
        pygame.mixer.music.stop()


# 测试代码
if __name__ == "__main__":
    # 测试录音
    recorder = AudioRecorder()
    audio_file = "./audio_files/test_record.pcm"
    recorder.record(duration=3, output_file=audio_file)
    
    # 测试播放（需要先有mp3文件）
    # player = AudioPlayer()
    # player.play("./audio_files/test.mp3")

