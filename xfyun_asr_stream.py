# -*- coding:utf-8 -*-
"""
讯飞语音识别（ASR）模块 - 真正的流式版本
支持边录音边识别，几乎零延迟
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
import time
import queue

# ASR私有云配置
ASR_HOST = "iat-api.xfyun.cn"
ASR_PATH = "/v2/iat"

# 帧状态
STATUS_FIRST_FRAME = 0      # 第一帧
STATUS_CONTINUE_FRAME = 1   # 中间帧
STATUS_LAST_FRAME = 2       # 最后一帧


class XFyunASRStream:
    """讯飞语音识别类 - 真正的流式版本"""

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
        self.result_text = ""
        self.is_finished = False
        self.audio_queue = queue.Queue()  # 音频帧队列
        self.ws = None
        self.frame_count = 0
        self.status = STATUS_FIRST_FRAME

    def create_url(self):
        """
        生成WebSocket认证URL（私有云ASR）
        :return: 认证后的URL
        """
        url = f"wss://{ASR_HOST}{ASR_PATH}"

        # 生成RFC1123格式的时间戳
        now = datetime.datetime.now(datetime.timezone.utc)
        date = format_date_time(mktime(now.timetuple()))

        # 拼接签名字符串
        signature_origin = f"host: {ASR_HOST}\n"
        signature_origin += f"date: {date}\n"
        signature_origin += f"GET {ASR_PATH} HTTP/1.1"

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
            "host": ASR_HOST
        }
        url = url + '?' + urlencode(v)
        return url

    def on_message(self, ws, message):
        """处理接收到的消息"""
        try:
            msg = json.loads(message)

            # 检查code
            code = msg.get("code", -1)
            if code != 0:
                err_msg = msg.get("message", "未知错误")
                print(f"\n? 识别错误，错误码：{code}")
                print(f"   错误信息：{err_msg}")
                self.is_finished = True
                ws.close()
                return

            # 解析识别结果
            if "data" in msg and msg["data"]:
                data = msg["data"]
                status = data.get("status", 0)

                if "result" in data:
                    result = data["result"]

                    # 解析识别文本
                    if "ws" in result:
                        text = ""
                        for ws_item in result["ws"]:
                            if "cw" in ws_item:
                                for cw in ws_item["cw"]:
                                    w = cw.get("w", "")
                                    if w:
                                        text += w

                        if text:
                            # 实时显示识别结果
                            if status == 2:
                                # 最后一帧，如果只是标点符号，保留累积结果
                                if text.strip() in ['。', '，', '！', '？', '；', '：', '、'] or len(text.strip()) <= 1:
                                    print(f"", end='', flush=True)  # 不更新
                                else:
                                    # 完整结果
                                    self.result_text = text
                                    print(f"\r? 识别中：{text}", end='', flush=True)
                            else:
                                # 中间帧，实时更新
                                if not self.result_text:
                                    self.result_text = text
                                elif text.startswith(self.result_text):
                                    self.result_text = text
                                elif len(text) > len(self.result_text):
                                    self.result_text = text
                                else:
                                    if text not in self.result_text:
                                        self.result_text += text
                                
                                print(f"\r? 识别中：{self.result_text}", end='', flush=True)

                # 检查是否完成
                if status == 2:
                    print(f"\n? 识别完成！")
                    self.is_finished = True
                    ws.close()

        except Exception as e:
            print(f"\n? 处理消息出错：{e}")
            self.is_finished = True
            if ws:
                ws.close()

    def on_error(self, ws, error):
        """处理错误"""
        if self.is_finished and 'timeout' in str(error).lower():
            return  # 忽略正常关闭的超时
        print(f"\n? WebSocket错误：{error}")

    def on_close(self, ws, close_status_code, close_msg):
        """处理连接关闭"""
        self.is_finished = True

    def on_open(self, ws):
        """处理连接建立 - 启动发送线程"""
        def send_audio():
            """发送音频数据线程"""
            try:
                while not self.is_finished:
                    try:
                        # 从队列获取音频帧（超时0.1秒）
                        audio_frame = self.audio_queue.get(timeout=0.1)
                        
                        if audio_frame is None:
                            # None表示结束信号
                            self._send_frame(ws, b'', STATUS_LAST_FRAME)
                            print(f"\n? 已发送最后一帧")
                            break
                        
                        # 发送音频帧
                        self._send_frame(ws, audio_frame, self.status)
                        
                        # 更新状态
                        if self.status == STATUS_FIRST_FRAME:
                            self.status = STATUS_CONTINUE_FRAME
                        
                        self.frame_count += 1
                        
                    except queue.Empty:
                        continue
                    
            except Exception as e:
                print(f"\n? 发送音频出错：{e}")
                self.is_finished = True

        thread.start_new_thread(send_audio, ())

    def _send_frame(self, ws, audio_data, frame_status):
        """
        发送音频帧
        :param ws: WebSocket连接
        :param audio_data: 音频数据（bytes）
        :param frame_status: 帧状态（0/1/2）
        """
        # Base64编码
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')

        # 构造消息
        if frame_status == STATUS_FIRST_FRAME:
            # 第一帧（完整配置）
            d = {
                "common": {
                    "app_id": self.appid
                },
                "business": {
                    "language": "zh_cn",
                    "domain": "iat",
                    "accent": "mandarin",
                    "vinfo": 1,
                    "dwa": "wpgs"
                },
                "data": {
                    "status": 0,
                    "format": "audio/L16;rate=16000",
                    "encoding": "raw",
                    "audio": audio_base64
                }
            }
        else:
            # 中间帧和最后一帧
            d = {
                "data": {
                    "status": frame_status,
                    "format": "audio/L16;rate=16000",
                    "encoding": "raw",
                    "audio": audio_base64
                }
            }

        ws.send(json.dumps(d))

    def add_audio_frame(self, audio_data):
        """
        添加音频帧（由录音模块调用）
        :param audio_data: 音频数据（bytes）
        """
        self.audio_queue.put(audio_data)

    def finish_recording(self):
        """
        结束录音（由录音模块调用）
        """
        self.audio_queue.put(None)  # 发送结束信号

    def start_recognition(self):
        """
        启动识别
        :return: 启动成功返回True
        """
        print("? 启动流式语音识别...")
        
        # 重置状态
        self.result_text = ""
        self.is_finished = False
        self.audio_queue = queue.Queue()
        self.frame_count = 0
        self.status = STATUS_FIRST_FRAME

        # 创建WebSocket连接
        websocket.enableTrace(False)
        ws_url = self.create_url()

        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        self.ws.on_open = lambda ws: self.on_open(ws)

        # 在后台线程运行WebSocket
        def run_ws():
            self.ws.run_forever(
                sslopt={"cert_reqs": ssl.CERT_NONE},
                ping_timeout=1,
                ping_interval=30
            )

        thread.start_new_thread(run_ws, ())
        
        # 等待连接建立
        time.sleep(0.5)
        return True

    def wait_result(self, timeout=10):
        """
        等待识别结果
        :param timeout: 超时时间（秒）
        :return: 识别结果文本
        """
        start_time = time.time()
        while not self.is_finished:
            if time.time() - start_time > timeout:
                print(f"\n?? 识别超时")
                self.is_finished = True
                if self.ws:
                    self.ws.close()
                break
            time.sleep(0.1)
        
        return self.result_text


# 测试代码
if __name__ == "__main__":
    from config import XFYUN_APPID, XFYUN_API_KEY, XFYUN_API_SECRET
    import pyaudio

    # 创建流式ASR实例
    asr = XFyunASRStream(
        appid=XFYUN_APPID,
        api_key=XFYUN_API_KEY,
        api_secret=XFYUN_API_SECRET
    )

    # 启动识别
    asr.start_recognition()

    # 模拟录音（实际使用时由AudioRecorder调用）
    print("?? 开始录音5秒...")
    
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=1280
    )

    try:
        duration = 5
        chunks = int(16000 / 1280 * duration)
        
        for i in range(chunks):
            data = stream.read(1280)
            asr.add_audio_frame(data)
        
        # 结束录音
        asr.finish_recording()
        
        # 等待结果
        result = asr.wait_result()
        print(f"\n\n? 最终识别结果：{result}")
        
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

