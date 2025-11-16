# -*- coding:utf-8 -*-
"""
讯飞语音听写（ASR）模块 - 私有云版本
严格按最新WebSocket标准实现
"""

import _thread as thread
import time
import websocket
import base64
import datetime
import hashlib
import hmac
import json
import ssl
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time
from time import mktime, sleep
import os

# ASR私有云配置
ASR_HOST = "iat-api.xfyun.cn"
ASR_PATH = "/v2/iat"

# 帧状态
STATUS_FIRST_FRAME = 0      # 第一帧
STATUS_CONTINUE_FRAME = 1   # 中间帧
STATUS_LAST_FRAME = 2       # 最后一帧


class XFyunASRManual:
    """讯飞语音识别类 - 手动实现私有云版本"""

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

    def create_url(self):
        """
        生成WebSocket认证URL（私有云ASR）
        :return: 认证后的URL
        """
        url = f"wss://{ASR_HOST}{ASR_PATH}"

        # 生成RFC1123格式的时间戳（GMT/UTC+0）
        now = datetime.datetime.now(datetime.timezone.utc)
        date = format_date_time(mktime(now.timetuple()))

        # 拼接签名字符串（严格按文档格式）
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
        """处理接收到的消息
        私有云格式：不需要header，直接是 code + data
        """
        try:
            msg = json.loads(message)

            # 检查code
            code = msg.get("code", -1)
            if code != 0:
                err_msg = msg.get("message", "未知错误")
                print(f" 识别错误，错误码：{code}")
                print(f"   错误信息：{err_msg}")
                ws.close()
                return

            # 解析识别结果（私有云格式：data.result）
            if "data" in msg and msg["data"]:
                data = msg["data"]
                status = data.get("status", 0)

                # 调试：打印完整的data结构
                print(f"\n[DEBUG ASR] 状态: {status}, data键: {list(data.keys())}")
                if "result" in data:
                    result = data["result"]
                    print(f"[DEBUG ASR] result键: {list(result.keys())}")
                    # 显示当前累积结果
                    print(f"[DEBUG ASR] 当前累积结果: '{self.result_text}'")

                if status == 2:  # 只在最后打印完整数据
                    print(f"\n[DEBUG ASR] 完整数据: {json.dumps(data, ensure_ascii=False, indent=2)}")

                if "result" in data:
                    result = data["result"]

                    # 调试：打印result结构
                    if status == 2:
                        print(f"[DEBUG ASR] result结构: {json.dumps(result, ensure_ascii=False, indent=2)}")

                    # 私有云格式：直接有 ws 字段，不需要text字段
                    if "ws" in result:
                        text = ""
                        for ws in result["ws"]:
                            if "cw" in ws:
                                for cw in ws["cw"]:
                                    w = cw.get("w", "")
                                    if w:  # 只添加非空内容
                                        text += w

                        if text:  # 如果有识别到内容
                            print(f"识别中：{text}", end='', flush=True)

                            # 关键修复：正确处理分段识别结果
                            if status == 2:
                                # 状态2是最终结果，需要智能处理
                                if text.strip() in ['。', '，', '！', '？', '；', '：', '、'] or len(text.strip()) <= 1:
                                    # 如果状态2只返回标点符号，保留之前累积的结果
                                    print(f"\n[DEBUG ASR] 状态2返回标点，保留累积结果: '{self.result_text}'")
                                else:
                                    # 状态2返回有效内容，作为最终结果
                                    print(f"\n[DEBUG ASR] 状态2设置最终结果: '{text}'")
                                    # 重要：状态2的结果是完整的，直接替换
                                    self.result_text = text
                            else:
                                # 状态0和1：累积识别结果，智能处理分词
                                if not self.result_text:
                                    # 第一次识别，直接设置
                                    self.result_text = text
                                elif text.startswith(self.result_text):
                                    # 新结果是之前结果的延续，替换
                                    self.result_text = text
                                elif len(text) > len(self.result_text):
                                    # 新结果更长，可能是修正，替换
                                    self.result_text = text
                                else:
                                    # 完全不同的结果，累积添加（但避免重复）
                                    if text not in self.result_text:
                                        self.result_text += text
                                print(f"\n[DEBUG ASR] 累积结果: '{self.result_text}' (长度: {len(self.result_text)})")

                    # 检查是否有lg字段（language result）
                    elif "lg" in result:
                        lg = result.get("lg", [])
                        text = ""
                        for item in lg:
                            if "wk" in item:
                                for wk in item["wk"]:
                                    w = wk.get("w", "")
                                    if w:
                                        text += w

                        if text:
                            print(f"识别中：{text}", end='', flush=True)
                            self.result_text = text

                    # 检查是否有其他格式（如直接的text字段）
                    elif "text" in result:
                        text = result.get("text", "")
                        if text:
                            print(f"识别中：{text}", end='', flush=True)
                            self.result_text = text

                    # 调试：如果都没有，打印result的所有键
                    else:
                        if status == 2:
                            print(f"[DEBUG ASR] result中没有ws或text字段，包含: {list(result.keys())}")

                # 检查是否完成
                if status == 2:
                    print("\n 识别完成！")
                    if ws and hasattr(ws, 'close') and callable(getattr(ws, 'close', None)):
                        try:
                            ws.close()
                        except:
                            pass

        except Exception as e:
            print(f" 处理消息出错：{e}")
            import traceback
            traceback.print_exc()
            # 确保ws对象有效且有关闭方法
            if ws and hasattr(ws, 'close') and callable(getattr(ws, 'close', None)):
                try:
                    ws.close()
                except:
                    pass

    def on_error(self, ws, error):
        """处理错误"""
        print(f" WebSocket错误：{error}")
        if ws and hasattr(ws, 'close'):
            try:
                ws.close()
            except:
                pass

    def on_close(self, ws, close_status_code, close_msg):
        """处理连接关闭"""
        pass

    def on_open(self, ws, audio_file):
        """处理连接建立"""
        def run(*args):
            frame_size = 1280  # 每帧音频大小（1280字节 = 640采样点）
            interval = 0.04     # 40ms间隔（对应640采样点@16kHz）
            status = STATUS_FIRST_FRAME

            with open(audio_file, "rb") as fp:
                while True:
                    buf = fp.read(frame_size)

                    # 文件结束
                    if not buf:
                        status = STATUS_LAST_FRAME
                        print(f"[DEBUG ASR] 文件读取完成，发送最后一帧")

                    # Base64编码音频数据
                    audio_base64 = str(base64.b64encode(buf), 'utf-8')

                    # 构造消息
                    if status == STATUS_FIRST_FRAME:
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
                        ws.send(json.dumps(d))
                        status = STATUS_CONTINUE_FRAME
                        sleep(interval)  # 等待40ms，模拟实时音频流

                    elif status == STATUS_CONTINUE_FRAME:
                        # 中间帧
                        d = {
                            "data": {
                                "status": 1,
                                "format": "audio/L16;rate=16000",
                                "encoding": "raw",
                                "audio": audio_base64
                            }
                        }
                        ws.send(json.dumps(d))
                        sleep(interval)  # 等待40ms，模拟实时音频流

                    elif status == STATUS_LAST_FRAME:
                        # 最后一帧
                        d = {
                            "data": {
                                "status": 2,
                                "format": "audio/L16;rate=16000",
                                "encoding": "raw",
                                "audio": audio_base64
                            }
                        }
                        ws.send(json.dumps(d))
                        break

                    # 模拟音频流传输间隔（40ms）
                    time.sleep(interval)

        thread.start_new_thread(run, ())

    def recognize_file(self, audio_file):  # 修复方法名
        """
        识别音频文件（兼容旧调用）
        """
        return self.recognize(audio_file)

    def recognize(self, audio_file):
        """
        识别音频文件
        :param audio_file: 音频文件路径（PCM格式，16k采样率，16bit，单声道）
        :return: 识别的文本
        """
        self.result_text = ""  # 重置结果
        print(f"[DEBUG ASR] 重置识别结果为空")

        print(f" 开始识别音频：{audio_file}")

        # 创建WebSocket连接
        websocket.enableTrace(False)
        ws_url = self.create_url()

        ws = websocket.WebSocketApp(
            ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        ws.on_open = lambda ws: self.on_open(ws, audio_file)

        # 运行WebSocket
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

        print(f"[DEBUG ASR] recognize函数返回结果: '{self.result_text}'")
        return self.result_text


# 测试代码
if __name__ == "__main__":
    from config import XFYUN_APPID, XFYUN_API_KEY, XFYUN_API_SECRET

    # 创建ASR实例
    asr = XFyunASRManual(
        appid=XFYUN_APPID,
        api_key=XFYUN_API_KEY,
        api_secret=XFYUN_API_SECRET
    )

    # 测试音频文件
    audio_file = "./audio_files/test.pcm"

    if os.path.exists(audio_file):
        result = asr.recognize(audio_file)
        print(f"\n 最终识别结果：{result}")
    else:
        print(f" 测试文件不存在：{audio_file}")
