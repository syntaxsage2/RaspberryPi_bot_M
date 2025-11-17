# -*- coding:utf-8 -*-
"""
讯飞语音合成（TTS）模块 - 流式播放版本
支持边接收边播放，大幅降低延迟
"""

import websocket
import datetime
import hashlib
import base64
import hmac
import json
from urllib.parse import urlencode
import ssl
from wsgiref.handlers import format_date_time
from time import mktime
import _thread as thread
import os
import queue
import pyaudio
import time

# TTS私有云配置
TTS_HOST = "cbm01.cn-huabei-1.xf-yun.com"
TTS_PATH = "/v1/private/mcd9m97e6"

# 超拟人发音人列表
SUPER_REALISTIC_VOICES = {
    "x5_lingxiaoxuan_flow": "凌小萱流式 - 超拟人温柔女声",
    "x5_lingxiaoyue_flow": "凌小月流式 - 超拟人清亮女声",
    "x5_lingxiaoqi_flow": "凌小琪流式 - 超拟人甜美女声",
    "x5_lingxiaofeng_flow": "凌小峰流式 - 超拟人沉稳男声",
    "x5_lingfeiyi_flow": "凌飞一流式 - 超拟人标准男声",
    "x5_lingyuyan_flow": "凌语言流式 - 超拟人自然女声"
}


class XFyunTTSStream:
    """讯飞语音合成类 - 流式播放版本"""

    def __init__(self, appid, api_key, api_secret):
        """
        初始化
        :param appid: 讯飞APPID
        :param api_key: 讯飞API Key
        :param api_secret: 讯飞API Secret
        """
        self.appid = appid
        self.api_key = api_key
        self.api_secret = api_secret
        self.audio_queue = queue.Queue()  # 音频数据队列
        self.is_finished = False  # 接收完成标志
        self.sample_rate = 16000  # 采样率
        self.channels = 1  # 声道数
        self.output_file = None  # 可选的文件保存
        self.save_to_file = False  # 是否保存文件
        self.file_data = []  # 用于保存的音频数据

    def create_url(self):
        """
        生成WebSocket认证URL（私有云TTS）
        :return: 认证后的URL
        """
        url = f"wss://{TTS_HOST}{TTS_PATH}"

        # 生成RFC1123格式的时间戳
        now = datetime.datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接签名字符串
        signature_origin = f"host: {TTS_HOST}\n"
        signature_origin += f"date: {date}\n"
        signature_origin += f"GET {TTS_PATH} HTTP/1.1"

        # 进行hmac-sha256加密
        signature_sha = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')

        # 生成authorization
        authorization_origin = f'api_key="{self.api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha}"'
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')

        # 拼接URL参数
        v = {
            "authorization": authorization,
            "date": date,
            "host": TTS_HOST
        }
        url = url + '?' + urlencode(v)
        return url

    def on_message(self, ws, message):
        """处理接收到的消息 - 流式播放版本"""
        try:
            msg = json.loads(message)

            # 检查错误
            if "header" in msg:
                header = msg["header"]
                code = header.get("code", -1)
                if code != 0:
                    err_msg = header.get("message", "未知错误")
                    print(f"❌ 合成错误，错误码：{code}")
                    print(f"   错误信息：{err_msg}")
                    self.is_finished = True
                    ws.close()
                    return

            # 处理音频数据
            audio_data = None
            status = 0
            seq = 0

            # 格式1: payload.audio.audio
            if "payload" in msg and "audio" in msg["payload"]:
                audio_info = msg["payload"]["audio"]
                if "audio" in audio_info:
                    audio_data = audio_info["audio"]
                    status = audio_info.get("status", 0)
                    seq = audio_info.get("seq", 0)

            # 格式2: 直接包含音频字段
            elif "audio" in msg:
                audio_data = msg["audio"]
                status = msg.get("status", 0)
                seq = msg.get("seq", 0)

            # 格式3: data.audio
            elif "data" in msg and msg["data"]:
                data = msg["data"]
                status = data.get("status", 0)
                seq = data.get("seq", 0)
                if "audio" in data and data["audio"]:
                    audio_data = data["audio"]

            # 如果有音频数据，放入队列
            if audio_data:
                try:
                    # Base64解码
                    audio = base64.b64decode(audio_data)
                    
                    # 放入播放队列（关键！）
                    self.audio_queue.put(audio)
                    print(f"🎵 [帧{seq}] 接收音频: {len(audio)} 字节")

                    # 如果需要保存文件
                    if self.save_to_file:
                        self.file_data.append(audio)

                except Exception as e:
                    print(f"❌ 处理音频帧失败: {e}")

            # 检查是否完成（状态2表示最后一帧）
            if status == 2:
                print(f"\n✅ 音频接收完成！（总帧数：{seq + 1}）")
                self.is_finished = True
                
                # 保存文件
                if self.save_to_file and self.output_file and self.file_data:
                    self._save_audio_file()
                
                ws.close()

        except Exception as e:
            print(f"❌ 解析消息出错：{e}")
            self.is_finished = True
            ws.close()

    def _save_audio_file(self):
        """保存音频文件"""
        try:
            audio_data = b''.join(self.file_data)
            
            # 确保目录存在
            output_dir = os.path.dirname(self.output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            with open(self.output_file, 'wb') as f:
                f.write(audio_data)
            
            file_size = os.path.getsize(self.output_file)
            print(f"💾 音频已保存: {self.output_file} ({file_size} 字节)")
        except Exception as e:
            print(f"⚠️ 保存文件失败: {e}")

    def on_error(self, ws, error):
        """处理错误"""
        print(f"❌ WebSocket错误：{error}")
        self.is_finished = True

    def on_close(self, ws, close_status_code, close_msg):
        """处理连接关闭"""
        print(f"🔌 WebSocket连接关闭")
        self.is_finished = True

    def on_open(self, ws, text, vcn, speed, volume, pitch):
        """处理连接建立"""
        def run(*args):
            # 构造请求（使用PCM格式以支持流式播放）
            request_data = {
                "header": {
                    "app_id": self.appid,
                    "status": 2
                },
                "parameter": {
                    "oral": {
                        "oral_level": "mid"
                    },
                    "tts": {
                        "vcn": vcn,
                        "speed": speed,
                        "volume": volume,
                        "pitch": pitch,
                        "bgs": 0,
                        "reg": 0,
                        "rdn": 0,
                        "rhy": 0,
                        "audio": {
                            "encoding": "raw",  # 使用PCM格式！
                            "sample_rate": self.sample_rate,
                            "channels": self.channels,
                            "bit_depth": 16,
                            "frame_size": 0
                        }
                    }
                },
                "payload": {
                    "text": {
                        "encoding": "utf8",
                        "compress": "raw",
                        "format": "plain",
                        "status": 2,
                        "seq": 0,
                        "text": base64.b64encode(text.encode('utf-8')).decode('utf-8')
                    }
                }
            }

            request_json = json.dumps(request_data, ensure_ascii=False)
            ws.send(request_json)
            print("📤 超拟人合成请求已发送")

        thread.start_new_thread(run, ())

    def play_stream(self):
        """
        流式播放线程
        从队列中取出音频数据并实时播放
        """
        print("🔊 启动流式播放线程...")
        
        # 初始化PyAudio
        p = pyaudio.PyAudio()
        
        try:
            # 打开音频流
            stream = p.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                output=True,
                frames_per_buffer=1024
            )
            
            print("✅ 播放流已就绪，开始播放...")
            first_frame = True
            
            while not self.is_finished or not self.audio_queue.empty():
                try:
                    # 从队列获取音频数据（超时1秒）
                    audio_chunk = self.audio_queue.get(timeout=1.0)
                    
                    if first_frame:
                        print("🎶 开始播放第一帧（几乎无延迟！）")
                        first_frame = False
                    
                    # 播放音频
                    stream.write(audio_chunk)
                    
                except queue.Empty:
                    # 队列为空，继续等待
                    if self.is_finished:
                        break
                    continue
            
            print("✅ 播放完成！")
            
            # 关闭流
            stream.stop_stream()
            stream.close()
            
        except Exception as e:
            print(f"❌ 播放出错：{e}")
        finally:
            p.terminate()

    def synthesize_and_play(self, text, vcn="x5_lingxiaoxuan_flow",
                           speed=50, volume=50, pitch=50, 
                           save_file=None):
        """
        合成语音并流式播放
        :param text: 要合成的文本
        :param vcn: 发音人
        :param speed: 语速 0-100
        :param volume: 音量 0-100
        :param pitch: 音高 0-100
        :param save_file: 可选，保存音频文件路径
        :return: 是否成功
        """
        print("=" * 60)
        print(f"🎤 开始流式语音合成：{text}")
        print(f"   发音人：{SUPER_REALISTIC_VOICES.get(vcn, vcn)}")
        print("=" * 60)

        # 重置状态
        self.is_finished = False
        self.audio_queue = queue.Queue()
        self.file_data = []
        
        # 配置文件保存
        if save_file:
            self.save_to_file = True
            self.output_file = save_file
        else:
            self.save_to_file = False

        # 启动播放线程
        play_thread = thread.start_new_thread(self.play_stream, ())

        # 创建WebSocket连接
        ws_url = self.create_url()
        
        now = datetime.datetime.now()
        date_header = format_date_time(mktime(now.timetuple()))
        
        headers = {
            "Host": TTS_HOST,
            "Date": date_header
        }

        ws = websocket.WebSocketApp(
            ws_url,
            header=headers,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        ws.on_open = lambda ws: self.on_open(ws, text, vcn, speed, volume, pitch)

        # 运行WebSocket
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

        # 等待播放完成
        print("⏳ 等待播放完成...")
        while not self.is_finished or not self.audio_queue.empty():
            time.sleep(0.1)
        
        time.sleep(0.5)  # 额外等待确保播放完成
        
        print("\n" + "=" * 60)
        print("✅ 流式语音合成和播放完成！")
        print("=" * 60)
        
        return True


# 测试代码
if __name__ == "__main__":
    from config import XFYUN_APPID, XFYUN_API_KEY, XFYUN_API_SECRET

    # 创建流式TTS实例
    tts_stream = XFyunTTSStream(
        appid=XFYUN_APPID,
        api_key=XFYUN_API_KEY,
        api_secret=XFYUN_API_SECRET
    )

    # 测试文本
    text = "你好，我是你的树莓派语音助手，很高兴为你服务。这是流式播放测试，延迟大大降低了！"

    # 准备保存路径（可选）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    audio_dir = os.path.join(script_dir, "audio_files")
    save_file = os.path.join(audio_dir, "test_stream.pcm")

    # 执行流式合成和播放
    print("\n" + "=" * 60)
    print("🚀 开始流式TTS测试")
    print("=" * 60)
    
    tts_stream.synthesize_and_play(
        text=text,
        vcn="x5_lingxiaoxuan_flow",
        speed=50,
        volume=50,
        pitch=50,
        save_file=save_file  # 可选保存
    )
    
    print("\n✅ 测试完成！")

