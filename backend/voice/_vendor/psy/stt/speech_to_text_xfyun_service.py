"""
讯飞星火「中英识别大模型」语音识别服务
基于 WebSocket 流式接口
API 文档: https://www.xfyun.cn/doc/spark/spark_zh_iat.html
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import ssl
import time
from datetime import datetime, timezone
from email.utils import formatdate
from urllib.parse import urlencode

import websocket

# vendored into moodcoco: replaced psychologists config/logger with stdlib equivalents
log = logging.getLogger(__name__)


class _Settings:
    """Lazy env-var shim replacing psychologists' config.settings."""
    @property
    def XFYUN_APP_ID(self) -> str:
        return os.environ.get("XFYUN_APP_ID", "")
    @property
    def XFYUN_API_KEY(self) -> str:
        return os.environ.get("XFYUN_API_KEY", "")
    @property
    def XFYUN_API_SECRET(self) -> str:
        return os.environ.get("XFYUN_API_SECRET", "")
    @property
    def XFYUN_ASR_URL(self) -> str:
        return os.environ.get("XFYUN_ASR_URL", "wss://ws-api.xfyun.cn/v2/iat")


settings = _Settings()


class XfyunASR:
    """
    讯飞中英识别大模型 ASR 服务
    
    支持中文、英文及 202 种方言的短语音识别（≤60秒）
    """
    
    def __init__(self):
        self.app_id = settings.XFYUN_APP_ID
        self.api_key = settings.XFYUN_API_KEY
        self.api_secret = settings.XFYUN_API_SECRET
        self.base_url = settings.XFYUN_ASR_URL
        
        if not all([self.app_id, self.api_key, self.api_secret]):
            log.warning("⚠️ 讯飞 ASR 配置不完整，请检查 XFYUN_APP_ID, XFYUN_API_KEY, XFYUN_API_SECRET")
        else:
            log.info(f"✅ 讯飞 ASR 服务初始化成功, APPID: {self.app_id[:8]}...")
    
    def _create_url(self) -> str:
        """
        生成带鉴权参数的 WebSocket URL（中英识别大模型）
        
        鉴权方式：签名机制，基于 hmac-sha256
        """
        from urllib.parse import urlparse
        parsed = urlparse(self.base_url)
        host = parsed.netloc
        path = parsed.path or "/v1"
        
        # 生成 RFC1123 格式的时间戳（必须是 UTC/GMT 时间）
        # 格式示例: "Wed, 03 Dec 2025 03:15:30 GMT"
        date = formatdate(timeval=None, localtime=False, usegmt=True)
        
        # 构造签名原文
        signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
        
        # 使用 HMAC-SHA256 签名
        signature_sha = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        
        signature_sha_base64 = base64.b64encode(signature_sha).decode('utf-8')
        
        # 构造 authorization 参数
        authorization_origin = (
            f'api_key="{self.api_key}", '
            f'algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature_sha_base64}"'
        )
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
        
        # 拼接最终 URL
        params = {
            "authorization": authorization,
            "date": date,
            "host": host
        }
        
        url = f"{self.base_url}?{urlencode(params)}"
        log.debug(f"讯飞 ASR WebSocket URL: {url[:100]}...")
        
        return url
    
    def _get_audio_format(self, file_path: str) -> str:
        """根据文件扩展名判断音频格式"""
        ext = os.path.splitext(file_path)[1].lower()
        format_map = {
            '.pcm': 'raw',
            '.wav': 'raw',
            '.mp3': 'lame',
        }
        return format_map.get(ext, 'raw')
    
    def recognize(self, audio_file: str) -> str:
        """
        执行语音识别（中英识别大模型）
        
        Args:
            audio_file: 音频文件路径（支持 pcm, wav, mp3）
            
        Returns:
            str: 识别结果文本，失败返回空字符串
        """
        if not os.path.exists(audio_file):
            log.error(f"音频文件不存在: {audio_file}")
            return ""
        
        if not all([self.app_id, self.api_key, self.api_secret]):
            log.error("讯飞 ASR 配置不完整，无法执行识别")
            return ""
        
        # 读取音频文件
        try:
            with open(audio_file, 'rb') as f:
                audio_data = f.read()
            log.info(f"🎤 开始识别 ({len(audio_data)/1024:.1f}KB)")
        except Exception as e:
            log.error(f"读取音频文件失败: {e}")
            return ""
        
        # 如果是 WAV 文件，跳过 44 字节的头部
        if audio_file.lower().endswith('.wav') and len(audio_data) > 44:
            audio_data = audio_data[44:]
        
        # 存储识别结果
        final_result = [""]
        is_completed = [False]
        error_msg = [None]
        
        def on_message(ws, message):
            """处理服务端返回的消息（中英识别大模型格式）"""
            try:
                msg = json.loads(message)
                
                # 检查错误码
                header = msg.get("header", {})
                code = header.get("code", -1)
                
                if code != 0:
                    error_msg[0] = header.get("message", "未知错误")
                    log.error(f"讯飞 ASR 错误: code={code}, message={error_msg[0]}")
                    is_completed[0] = True
                    return
                
                # 解析 payload.result.text（Base64 编码的 JSON）
                payload = msg.get("payload", {})
                result = payload.get("result", {})
                text_base64 = result.get("text", "")
                
                if not text_base64:
                    # 没有识别结果，可能是中间帧
                    status = header.get("status", 0)
                    if status == 2:
                        is_completed[0] = True
                    return
                
                # Base64 解码
                text_json_str = base64.b64decode(text_base64).decode('utf-8')
                text_data = json.loads(text_json_str)
                
                # 提取识别文本: ws[].cw[].w (plain 格式直接返回完整结果)
                ws_list = text_data.get("ws", [])
                
                current_text = []
                for ws_item in ws_list:
                    cw_list = ws_item.get("cw", [])
                    for cw_item in cw_list:
                        word = cw_item.get("w", "")
                        if word:
                            current_text.append(word)
                
                if current_text:
                    new_text = "".join(current_text)
                    # plain 格式每次返回完整结果，直接覆盖
                    final_result[0] = new_text
                
                # 检查是否结束
                status = header.get("status", 0)
                if status == 2:
                    is_completed[0] = True
                    
            except Exception as e:
                log.error(f"解析讯飞 ASR 响应失败: {e}, 原始消息: {message[:300] if len(message) > 300 else message}")
                is_completed[0] = True
        
        def on_error(ws, error):
            log.error(f"讯飞 ASR WebSocket 错误: {error}")
            error_msg[0] = str(error)
            is_completed[0] = True
        
        def on_close(ws, close_status_code, close_msg):
            is_completed[0] = True
        
        def on_open(ws):
            """连接建立后发送音频数据（中英识别大模型格式）"""
            
            import threading
            
            def send_audio():
                try:
                    audio_format = self._get_audio_format(audio_file)
                    frame_size = 1280  # 每帧约 40ms (16kHz, 16bit, 单声道)
                    interval = 0.01   # 10ms 发送间隔（加速到实时的4倍，节省约3秒）
                    seq = 0  # 音频序号，从 0 开始
                    
                    total_frames = (len(audio_data) + frame_size - 1) // frame_size
                    
                    for i in range(0, len(audio_data), frame_size):
                        frame = audio_data[i:i + frame_size]
                        frame_b64 = base64.b64encode(frame).decode('utf-8')
                        seq += 1  # 每帧递增
                        
                        # 判断帧状态（注意：所有音频数据帧的 status 为 0 或 1，不包括 2）
                        if i == 0:
                            status = 0  # 首帧
                        else:
                            status = 1  # 中间帧
                        
                        # 构造请求数据（严格按照 API 文档格式）
                        if status == 0:
                            # 首帧包含完整的 header + parameter + payload
                            request_data = {
                                "header": {
                                    "app_id": self.app_id,
                                    "res_id": "",  # 热词资源 ID，不使用热词时为空字符串
                                    "status": status
                                },
                                "parameter": {
                                    "iat": {
                                        "domain": "slm",           # 中英识别大模型
                                        "language": "zh_cn",
                                        "accent": "mandarin",
                                        "dwa": "wpgs",             # 开启动态修正
                                        "result": {
                                            "encoding": "utf8",
                                            "compress": "raw",
                                            "format": "plain"      # 使用 plain 格式，减少解析开销
                                        }
                                    }
                                },
                                "payload": {
                                    "audio": {
                                        "encoding": audio_format,
                                        "sample_rate": 16000,
                                        "channels": 1,
                                        "bit_depth": 16,
                                        "seq": seq,
                                        "status": status,
                                        "audio": frame_b64
                                    }
                                }
                            }
                        else:
                            # 中间帧和尾帧只发 header + payload
                            request_data = {
                                "header": {
                                    "app_id": self.app_id,
                                    "res_id": "",  # 热词资源 ID
                                    "status": status
                                },
                                "payload": {
                                    "audio": {
                                        "encoding": audio_format,
                                        "sample_rate": 16000,
                                        "channels": 1,
                                        "bit_depth": 16,
                                        "seq": seq,
                                        "status": status,
                                        "audio": frame_b64
                                    }
                                }
                            }
                        
                        ws.send(json.dumps(request_data))
                        time.sleep(interval)
                    
                    # 发送最后一帧（空音频，标志结束）
                    seq += 1
                    final_frame = {
                        "header": {
                            "app_id": self.app_id,
                            "res_id": "",
                            "status": 2  # 最后一帧
                        },
                        "payload": {
                            "audio": {
                                "encoding": audio_format,
                                "sample_rate": 16000,
                                "channels": 1,
                                "bit_depth": 16,
                                "seq": seq,
                                "status": 2,
                                "audio": ""  # 最后一帧 audio 为空字符串
                            }
                        }
                    }
                    ws.send(json.dumps(final_frame))
                    
                except Exception as e:
                    log.error(f"发送音频数据失败: {e}")
                    is_completed[0] = True
            
            # 在新线程中发送音频
            threading.Thread(target=send_audio).start()
        
        # 创建 WebSocket 连接
        try:
            url = self._create_url()
            
            ws = websocket.WebSocketApp(
                url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            
            # 运行 WebSocket
            import threading
            ws_thread = threading.Thread(target=lambda: ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}))
            ws_thread.daemon = True
            ws_thread.start()
            
            # 等待识别完成（最长 60 秒）
            timeout = 60
            start_time = time.time()
            while not is_completed[0] and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if not is_completed[0]:
                log.warning("讯飞 ASR 识别超时")
                ws.close()
            
        except Exception as e:
            log.error(f"讯飞 ASR 识别异常: {e}")
            return ""
        
        # 返回最终结果
        result_text = final_result[0]
        if result_text:
            log.info(f"✅ 识别完成: {result_text[:50]}{'...' if len(result_text) > 50 else ''}")
        return result_text if result_text else ""


# 全局实例
xfyun_asr = XfyunASR()


def run_test(audio_file: str) -> str:
    """
    运行语音识别测试（兼容原有接口）
    
    Args:
        audio_file: 音频文件路径
        
    Returns:
        str: 识别结果文本
    """
    return xfyun_asr.recognize(audio_file)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
    else:
        audio_file = "test_audio.wav"
    
    if not os.path.exists(audio_file):
        print(f"错误: 音频文件 '{audio_file}' 不存在")
        sys.exit(1)
    
    result = run_test(audio_file)
    print(f"识别结果: {result}")
