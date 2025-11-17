# -*- coding:utf-8 -*-
"""
音频工具模块
提供录音和播放功能
"""
import time

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

    def record_with_vad(self,
                        max_duration=30,
                        output_file=None,
                        vad_threshold=0.5,
                        min_speech_duration_ms=250,
                        min_silence_duration_ms=800):
        """
        使用VAD自动检测的录音方法

        :param max_duration: 最大录音时长（秒），防止无限录音
        :param output_file: 保存文件路径（可选）
        :param vad_threshold: VAD阈值
        :param min_speech_duration_ms: 最小语音时长
        :param min_silence_duration_ms: 最小静音时长（说完多久算结束）
        :return: (录音数据, 实际录音时长)
        """
        from vad_detector import VADDetector

        print(f"🎤 开始VAD智能录音（最长{max_duration}秒）...")
        print(f"💡 提示：检测到静音{min_silence_duration_ms}ms后自动停止")

        # 创建VAD检测器
        vad = VADDetector(
            sample_rate=self.sample_rate,
            threshold=vad_threshold,
            min_speech_duration_ms=min_speech_duration_ms,
            min_silence_duration_ms=min_silence_duration_ms,
            window_size_samples=self.chunk
        )

        # 初始化 PyAudio
        audio = pyaudio.PyAudio()
        
        try:
            # 打开音频流
            stream = audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=self.chunk
            )

            print("🎙️ 麦克风已就绪，请开始说话...")

            frames = []
            start_time = time.time()
            frame_count = 0
            speech_detected = False

            try:
                while True:
                    # 读取音频帧
                    data = stream.read(self.chunk, exception_on_overflow=False)
                    frame_count += 1

                    # VAD检测
                    is_speech, should_stop = vad.process_frame(data)

                    # 状态显示
                    if is_speech and not speech_detected:
                        print("🗣️ 检测到语音，开始录音...")
                        speech_detected = True

                    # 保存音频帧
                    if speech_detected:
                        frames.append(data)

                    # 实时显示
                    if frame_count % 10 == 0:  # 每10帧更新一次
                        elapsed = time.time() - start_time
                        status = "🗣️ 语音" if is_speech else "🤫 静音"
                        print(f"\r⏱️ {elapsed:.1f}s | {status} | 帧数: {len(frames)}",
                              end='', flush=True)

                    # 检查是否应该停止
                    if should_stop:
                        print("\n✅ 检测到说话结束，停止录音")
                        break

                    # 检查是否超时
                    if time.time() - start_time > max_duration:
                        print(f"\n⏰ 达到最大时长 {max_duration}秒，停止录音")
                        break

            except KeyboardInterrupt:
                print("\n⚠️ 录音被中断")
            finally:
                stream.stop_stream()
                stream.close()

            # 计算实际录音时长
            actual_duration = len(frames) * self.chunk / self.sample_rate
            print(f"📊 实际录音时长: {actual_duration:.2f}秒")

            if not frames:
                print("❌ 未录制到任何音频")
                return None, 0

            # 合并音频数据
            audio_data = b''.join(frames)

            # 保存文件（可选）
            if output_file:
                self._save_wav(audio_data, output_file, audio)
                print(f"💾 音频已保存: {output_file}")

            return audio_data, actual_duration
        
        finally:
            audio.terminate()

    def record_with_vad_lite(self,
                             max_duration=30,
                             output_file=None,
                             aggressiveness=2,
                             min_silence_duration_ms=800):
        """
        使用轻量级 VAD 自动检测的录音方法（适合树莓派 Zero 2W）

        :param max_duration: 最大录音时长（秒）
        :param output_file: 保存文件路径（可选）
        :param aggressiveness: VAD 敏感度 0-3（推荐2）
        :param min_silence_duration_ms: 最小静音时长（说完多久算结束）
        :return: (录音数据, 实际录音时长)
        """
        from vad_detector_lite import VADDetectorLite

        print(f"🎤 开始轻量级VAD录音（最长{max_duration}秒）...")
        print(f"💡 提示：检测到静音{min_silence_duration_ms}ms后自动停止")

        # 创建轻量级 VAD 检测器
        vad = VADDetectorLite(
            sample_rate=self.sample_rate,
            aggressiveness=aggressiveness,
            frame_duration_ms=30,  # 固定30ms帧
            padding_duration_ms=300,
            min_silence_duration_ms=min_silence_duration_ms
        )

        # WebRTC VAD 需要特定的帧大小
        vad_chunk_size = vad.get_frame_size_bytes()
        vad_chunk_samples = vad_chunk_size // 2  # int16 = 2字节

        print(f"🔧 VAD帧大小: {vad_chunk_samples} 样本 ({vad_chunk_size} 字节)")

        # 初始化 PyAudio
        audio = pyaudio.PyAudio()
        
        try:
            # 打开音频流
            stream = audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=vad_chunk_samples  # 使用VAD要求的帧大小
            )

            print("🎙️  麦克风已就绪，请开始说话...")

            frames = []
            start_time = time.time()
            frame_count = 0
            speech_detected = False

            try:
                while True:
                    # 读取音频帧（大小匹配VAD要求）
                    data = stream.read(vad_chunk_samples, exception_on_overflow=False)
                    frame_count += 1

                    # VAD 检测
                    is_speech, should_stop, buffered_audio = vad.process_frame(data)

                    # 第一次检测到语音
                    if vad.is_speaking and not speech_detected:
                        speech_detected = True

                    # 实时显示
                    if frame_count % 10 == 0:
                        elapsed = time.time() - start_time
                        status = "🗣️  语音" if is_speech else "🤫 静音"
                        silence = vad.silence_counter if vad.triggered else 0
                        print(f"\r⏱️  {elapsed:.1f}s | {status} | 静音计数: {silence}/{vad.silence_frames}",
                              end='', flush=True)

                    # 检查是否应该停止
                    if should_stop:
                        print("\n✅ 检测到说话结束，停止录音")
                        if buffered_audio:
                            frames = [buffered_audio]
                        break

                    # 检查是否超时
                    if time.time() - start_time > max_duration:
                        print(f"\n⏰ 达到最大时长 {max_duration}秒，停止录音")
                        # 获取缓冲的音频
                        if vad.voiced_frames:
                            frames = [b''.join(vad.voiced_frames)]
                        break

            except KeyboardInterrupt:
                print("\n⚠️  录音被中断")
            finally:
                stream.stop_stream()
                stream.close()

            if not frames:
                print("❌ 未录制到任何音频")
                return None, 0

            # 合并音频数据
            audio_data = frames[0] if len(frames) == 1 else b''.join(frames)

            # 计算实际录音时长
            actual_duration = len(audio_data) / (self.sample_rate * 2)  # 2字节per样本
            print(f"📊 实际录音时长: {actual_duration:.2f}秒")

            # 保存文件（可选）
            if output_file:
                self._save_wav(audio_data, output_file, audio)
                print(f"💾 音频已保存: {output_file}")

            return audio_data, actual_duration
        
        finally:
            audio.terminate()
    
    def _save_wav(self, audio_data, output_file, audio):
        """
        保存音频数据为WAV文件
        
        :param audio_data: 音频数据（bytes）
        :param output_file: 输出文件路径
        :param audio: PyAudio实例
        """
        # 确保目录存在
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # 根据文件扩展名保存
        if output_file.endswith('.pcm'):
            # 保存为PCM格式
            with open(output_file, 'wb') as f:
                f.write(audio_data)
        elif output_file.endswith('.wav'):
            # 保存为WAV格式
            with wave.open(output_file, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(audio.get_sample_size(self.format))
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data)
        else:
            # 默认保存为WAV
            with wave.open(output_file + '.wav', 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(audio.get_sample_size(self.format))
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data)


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

