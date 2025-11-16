# -*- coding:utf-8 -*-
"""
讯飞语音合成（TTS）模块 - 私有云版本
严格按最新WebSocket标准实现
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

# TTS私有云配置 - 超拟人发音人专用
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


class XFyunTTSManual:
    """讯飞语音合成类 - 手动实现私有云版本"""

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
        self.output_file = None

    def create_url(self):
        """
        生成WebSocket认证URL（私有云TTS）
        :return: 认证后的URL
        """
        url = f"wss://{TTS_HOST}{TTS_PATH}"

        # 生成RFC1123格式的时间戳（按照官网示例使用本地时间）
        now = datetime.datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 打印调试信息
        print(f"[DEBUG TTS] date: {date}")

        # 拼接签名字符串（严格按文档格式）
        signature_origin = f"host: {TTS_HOST}\n"
        signature_origin += f"date: {date}\n"
        signature_origin += f"GET {TTS_PATH} HTTP/1.1"

        print(f"[DEBUG TTS] signature_origin: {signature_origin}")

        # 进行hmac-sha256加密
        signature_sha = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')

        print(f"[DEBUG TTS] signature_sha: {signature_sha}")

        # 生成authorization（完全复制ASR的成功格式）
        authorization_origin = f'api_key="{self.api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha}"'
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')

        print(f"[DEBUG TTS] authorization: {authorization}")

        # 拼接URL参数（确保包含所有必要参数）
        v = {
            "authorization": authorization,
            "date": date,
            "host": TTS_HOST
        }
        url = url + '?' + urlencode(v)

        print(f"[DEBUG TTS] URL参数: {v}")
        print(f"[DEBUG TTS] 完整URL: {url}")
        return url

    def on_message(self, ws, message):
        """处理接收到的消息 - 超拟人私有云格式"""
        try:
            msg = json.loads(message)
            print(f"[DEBUG] 收到消息: {msg.keys()}")  # 调试用：显示消息键

            # 检查code（超拟人格式）
            if "header" in msg:
                header = msg["header"]
                code = header.get("code", -1)
                if code != 0:
                    err_msg = header.get("message", "未知错误")
                    print(f" 合成错误，错误码：{code}")
                    print(f"   错误信息：{err_msg}")
                    ws.close()
                    return
            else:
                # 兼容旧格式
                code = msg.get("code", -1)
                if code != 0:
                    err_msg = msg.get("message", "未知错误")
                    print(f" 合成错误，错误码：{code}")
                    print(f"   错误信息：{err_msg}")
                    ws.close()
                    return

            # 处理音频数据 - 支持多种响应格式（基于官方文档）
            audio_data = None
            status = 0
            seq = 0

            # 格式1: 官方标准格式 - payload.audio.audio
            if "payload" in msg and "audio" in msg["payload"]:
                audio_info = msg["payload"]["audio"]
                if "audio" in audio_info:
                    audio_data = audio_info["audio"]
                    status = audio_info.get("status", 0)
                    seq = audio_info.get("seq", 0)
                    print(f"[DEBUG] 检测到官方格式 payload.audio.audio - seq:{seq}, status:{status}")

            # 格式2: 直接包含音频字段的响应格式
            elif "audio" in msg:
                audio_data = msg["audio"]
                status = msg.get("status", 0)
                seq = msg.get("seq", 0)
                print(f"[DEBUG] 检测到直接音频格式 - seq:{seq}, status:{status}")

            # 格式3: data.audio 格式
            elif "data" in msg and msg["data"]:
                data = msg["data"]
                status = data.get("status", 0)
                seq = data.get("seq", 0)

                if "audio" in data and data["audio"]:
                    audio_data = data["audio"]
                    print(f"[DEBUG] 检测到data.audio格式 - seq:{seq}, status:{status}")

            # 如果有音频数据，进行处理
            if audio_data:
                try:
                    print(f"[DEBUG] 准备写入文件: {self.output_file}")
                    print(f"[DEBUG] 文件目录存在: {os.path.exists(os.path.dirname(self.output_file) or '.')}")

                    # Base64解码并写入文件
                    audio = base64.b64decode(audio_data)
                    print(f"[DEBUG] Base64解码成功，音频数据长度: {len(audio)} 字节")

                    # 检查文件是否可以写入
                    try:
                        with open(self.output_file, 'ab') as f:
                            f.write(audio)
                            f.flush()  # 确保数据写入磁盘
                            os.fsync(f.fileno())  # 强制同步到磁盘（Linux重要）
                        print(f"[帧{seq}] ✅ 写入成功！")
                        print(f"[DEBUG] 写入音频数据：{len(audio)} 字节")

                        # 验证文件是否真的写入了
                        if os.path.exists(self.output_file):
                            actual_size = os.path.getsize(self.output_file)
                            print(f"[DEBUG] 文件实际大小: {actual_size} 字节")
                        else:
                            print(f"[DEBUG] ❌ 文件不存在！")

                    except IOError as e:
                        print(f"[DEBUG] ❌ 文件写入错误: {e}")
                        print(f"[DEBUG] 文件路径: {self.output_file}")
                        print(f"[DEBUG] 目录权限: 可能需要sudo或chmod")

                except Exception as e:
                    print(f"[DEBUG] ❌ 处理失败: {e}")
                    print(f"[DEBUG] 音频数据长度：{len(audio_data) if audio_data else 0}")

            # 检查是否完成（状态2表示最后一帧）
            if status == 2:
                print(f"\n 超拟人语音合成完成！（总帧数：{seq}）")
                # 确保所有数据写入文件
                import time
                time.sleep(0.1)  # 短暂延迟确保文件写入完成
                if os.path.exists(self.output_file):
                    file_size = os.path.getsize(self.output_file)
                    print(f"[DEBUG] 最终文件大小：{file_size} 字节")
                    if file_size > 0:
                        print(f"✅ 音频文件生成成功！")
                    else:
                        print(f"⚠️ 警告：音频文件大小为0字节")
                else:
                    print(f"❌ 错误：音频文件未生成")
                ws.close()

        except Exception as e:
            print(f" 解析消息出错：{e}")
            print(f" 原始消息: {message[:200]}...")
            ws.close()

    def on_error(self, ws, error):
        """处理错误"""
        print(f"\n WebSocket错误：{error}")
        print(f" 错误类型：{type(error).__name__}")
        if 'timeout' in str(error).lower():
            print(" 连接超时，但音频数据可能已接收完成")
            # 检查文件是否已生成
            if self.output_file and os.path.exists(self.output_file):
                file_size = os.path.getsize(self.output_file)
                if file_size > 0:
                    print(f" 音频文件已部分生成：{self.output_file} (大小: {file_size} 字节)")
                    # 认为成功，主动关闭连接
                    ws.close()

    def on_close(self, ws, close_status_code, close_msg):
        """处理连接关闭"""
        print(f"\n WebSocket连接关闭：状态码={close_status_code}, 消息={close_msg}")
        # 检查文件是否生成成功
        if self.output_file and os.path.exists(self.output_file):
            file_size = os.path.getsize(self.output_file)
            print(f" 音频文件已生成：{self.output_file} (大小: {file_size} 字节)")
        else:
            print(" 警告：音频文件未生成或为空")

    def on_open(self, ws, text, vcn, speed, volume, pitch):
        """处理连接建立 - 超拟人私有云格式"""
        def run(*args):
            # 超拟人私有云格式 - 严格按照私有云文档
            request_data = {
                "header": {
                    "app_id": self.appid,
                    "status": 2  # 修正为2，官方文档要求status∈[0,1,2]
                },
                "parameter": {
                    "oral": {
                        "oral_level": "mid"  # 口语化程度：mid
                    },
                    "tts": {
                        "vcn": vcn,  # 超拟人发音人
                        "speed": speed,  # 语速
                        "volume": volume,  # 音量
                        "pitch": pitch,  # 音高
                        "bgs": 0,  # 背景音
                        "reg": 0,  # 注册人
                        "rdn": 0,  # 随机数
                        "rhy": 0,  # 韵律
                        "audio": {
                            "encoding": "lame",  # MP3格式
                            "sample_rate": 24000,  # 24kHz采样率（超拟人推荐）
                            "channels": 1,  # 单声道
                            "bit_depth": 16,  # 16位深度
                            "frame_size": 0  # 帧大小
                        }
                    }
                },
                "payload": {
                    "text": {
                        "encoding": "utf8",
                        "compress": "raw",
                        "format": "plain",
                        "status": 2,  # 完整文本
                        "seq": 0,  # 序列号
                        "text": base64.b64encode(text.encode('utf-8')).decode('utf-8')
                    }
                }
            }

            request_json = json.dumps(request_data, ensure_ascii=False)
            print(f"[DEBUG TTS] 发送超拟人请求: {request_json[:500]}..." if len(request_json) > 500 else f"[DEBUG TTS] 发送超拟人请求: {request_json}")
            ws.send(request_json)
            print(" 超拟人合成请求已发送")

        thread.start_new_thread(run, ())

    def synthesize(self, text, output_file, vcn="x4_lingxiaoxuan_oral",
                   speed=50, volume=50, pitch=50):
        """
        合成语音
        :param text: 要合成的文本
        :param output_file: 输出音频文件路径
        :param vcn: 发音人
        :param speed: 语速 0-100
        :param volume: 音量 0-100
        :param pitch: 音高 0-100
        :return: 输出文件路径
        """
        self.output_file = output_file

        # 确保目录存在 - 修复Windows路径问题
        output_dir = os.path.dirname(output_file)
        if output_dir and output_dir != ".":
            os.makedirs(output_dir, exist_ok=True)
            print(f"[DEBUG] 确保输出目录存在：{output_dir}")
        elif output_file.startswith("./"):
            # 处理相对路径 ./dir/file 的情况
            rel_path = output_file[2:]  # 移除 "./"
            output_dir = os.path.dirname(rel_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                print(f"[DEBUG] 确保输出目录存在：{output_dir}")
        else:
            print(f"[DEBUG] 使用当前目录，无需创建：{os.getcwd()}")

        # 删除旧文件
        if os.path.exists(output_file):
            os.remove(output_file)

        print(f" 开始合成语音：{text}")
        print(f"   输出文件：{output_file}")
        print(f"   合成中", end='', flush=True)

        # 创建WebSocket连接
        websocket.enableTrace(True)  # 启用详细调试
        ws_url = self.create_url()

        # 获取当前时间戳用于WebSocket头（按照官网示例使用本地时间）
        now = datetime.datetime.now()
        date_header = format_date_time(mktime(now.timetuple()))

        # 确保在握手时包含正确的头信息
        headers = {
            "Host": TTS_HOST,
            "Date": date_header  # 确保包含date头
        }

        print(f"[DEBUG TTS] WebSocket Headers: {headers}")
        print(f"[DEBUG TTS] WebSocket URL: {ws_url}")

        ws = websocket.WebSocketApp(
            ws_url,
            header=headers,  # 添加自定义头
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        ws.on_open = lambda ws: self.on_open(ws, text, vcn, speed, volume, pitch)

        # 运行WebSocket（使用默认超时设置）
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

        # 检查文件是否成功生成
        print(f"[DEBUG] 检查输出文件：{output_file}")
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            print(f"[DEBUG] 文件存在，大小：{file_size} 字节")
            if file_size > 0:
                print(f"\n✅ 超拟人语音合成成功！")
                print(f"📁 音频文件：{output_file}")
                print(f"📊 文件大小：{file_size} 字节")
                return output_file
            else:
                print(f"\n❌ 音频文件为空：{output_file}")
                return None
        else:
            print(f"\n❌ 音频文件未生成：{output_file}")
            print(f"[DEBUG] 当前工作目录：{os.getcwd()}")
            print(f"[DEBUG] 文件是否存在：{os.path.exists(output_file)}")
            return None


# 测试代码
if __name__ == "__main__":
    from config import XFYUN_APPID, XFYUN_API_KEY, XFYUN_API_SECRET

    # 创建TTS实例
    tts = XFyunTTSManual(
        appid=XFYUN_APPID,
        api_key=XFYUN_API_KEY,
        api_secret=XFYUN_API_SECRET
    )

    # 测试文本
    text = "你好，我是你的树莓派语音助手，很高兴为你服务。"

    # 使用绝对路径（适合树莓派Linux）
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    audio_dir = os.path.join(script_dir, "audio_files")
    output_file = os.path.join(audio_dir, "test_tts.mp3")

    print(f"[DEBUG] 脚本目录: {script_dir}")
    print(f"[DEBUG] 音频目录: {audio_dir}")
    print(f"[DEBUG] 输出文件: {output_file}")

    # 先测试文件写入功能
    print("\n=== 测试文件写入权限 ===")
    try:
        # 测试创建目录
        os.makedirs(audio_dir, exist_ok=True)
        print(f"✅ 目录创建成功: {audio_dir}")

        # 测试写入权限
        test_file = os.path.join(audio_dir, "test_write.mp3")
        with open(test_file, 'wb') as f:
            f.write(b"test audio data")
        os.remove(test_file)
        print("✅ 文件写入权限正常")

    except Exception as e:
        print(f"❌ 文件系统错误: {e}")
        print(f"请检查目录权限: sudo chmod -R 755 {audio_dir}")
        print(f"或者更改目录所有者: sudo chown -R pi:pi {audio_dir}")

    # 执行合成
    print("\n=== 开始语音合成 ===")
    result = tts.synthesize(text, output_file)
    print(f"\n 音频已保存到：{result}")
