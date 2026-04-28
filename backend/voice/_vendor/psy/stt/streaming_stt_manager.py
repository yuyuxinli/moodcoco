"""
流式语音识别管理器
管理多个并发的讯飞 ASR WebSocket 连接，支持实时音频流传输
"""
import asyncio
import base64
import hashlib
import hmac
import json
import threading
import time
from datetime import datetime
from email.utils import formatdate
from typing import Dict, List, Optional, Callable
from urllib.parse import urlencode, urlparse
import uuid

import websocket

from config import settings
from utils.logger import log


class StreamingSTTSession:
    """单个流式识别会话"""

    def __init__(
        self,
        session_id: str,
        socket_sid: Optional[str] = None,
        on_result: Optional[Callable] = None,
        on_partial: Optional[Callable] = None,
        hotwords: Optional[List[str]] = None
    ):
        self.session_id = session_id
        self.socket_sid = socket_sid  # ✅ 记录归属的 WebSocket 连接
        self.ws: Optional[websocket.WebSocket] = None
        self.audio_buffer: List[bytes] = []  # 断线时缓存
        self.is_connected = False
        self.is_finished = False
        self.result_text = ""
        self.error: Optional[str] = None
        self.result_segments: Dict[int, str] = {}  # 按 sn 维护完整文本片段
        self.last_sent_partial = ""  # 记录上次发送的 partial（去重）
        self.frame_counter = 0
        self.on_result = on_result  # 回调函数：收到最终结果时调用
        self.on_partial = on_partial  # 回调函数：收到实时识别结果时调用
        self.created_at = time.time()  # ✅ 创建时间（用于超时检测）
        self.last_activity = time.time()  # ✅ 最后活动时间

        # 讯飞配置
        self.app_id = settings.XFYUN_APP_ID
        self.api_key = settings.XFYUN_API_KEY
        self.api_secret = settings.XFYUN_API_SECRET
        self.base_url = settings.XFYUN_ASR_URL

        # STT 热词（用于提高人名识别准确率）
        # 格式：讯飞要求 "utf-8;word1|word2|word3"，最大 1024 字符
        self.hotwords_str = ""
        if hotwords:
            hotwords_limited = hotwords[:50]  # 限制 50 个
            hotwords_joined = "|".join(hotwords_limited)
            if len(hotwords_joined) <= 1000:  # 预留一些空间给 "utf-8;" 前缀
                self.hotwords_str = f"utf-8;{hotwords_joined}"
                log.info(f"📝 STT 热词已设置: {len(hotwords_limited)} 个词, 长度={len(self.hotwords_str)}")
            else:
                log.warning(f"⚠️ STT 热词超长被丢弃: {len(hotwords_limited)} 个词, 长度={len(hotwords_joined)} > 1000")

        # 线程锁
        self.lock = threading.Lock()
        
    def _create_url(self) -> str:
        """生成带鉴权参数的 WebSocket URL（复用现有逻辑）"""
        parsed = urlparse(self.base_url)
        host = parsed.netloc
        path = parsed.path or "/v1"
        
        date = formatdate(timeval=None, localtime=False, usegmt=True)
        signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
        
        signature_sha = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        
        signature_sha_base64 = base64.b64encode(signature_sha).decode('utf-8')
        
        authorization_origin = (
            f'api_key="{self.api_key}", '
            f'algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature_sha_base64}"'
        )
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
        
        params = {
            "authorization": authorization,
            "date": date,
            "host": host
        }
        
        return f"{self.base_url}?{urlencode(params)}"
    
    def start(self):
        """建立讯飞 WebSocket 连接"""
        try:
            url = self._create_url()
            
            # 创建 WebSocket 连接
            self.ws = websocket.WebSocketApp(
                url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            
            # 在新线程中运行
            wst = threading.Thread(target=self.ws.run_forever, kwargs={"sslopt": {"cert_reqs": 0}})
            wst.daemon = True
            wst.start()
            
            # 等待连接建立（最多3秒）
            for _ in range(30):
                if self.is_connected:
                    log.info(f"🎤 流式识别会话已建立: {self.session_id}")
                    return True
                time.sleep(0.1)
            
            log.error(f"❌ 流式识别会话连接超时: {self.session_id}")
            return False
            
        except Exception as e:
            log.error(f"❌ 建立流式识别会话失败 ({self.session_id}): {e}")
            return False
    
    def _on_open(self, ws):
        """连接建立"""
        self.is_connected = True
        log.info(f"🔗 讯飞 WebSocket 已连接: {self.session_id}")
    
    def _on_message(self, ws, message):
        """接收讯飞返回的识别结果"""
        try:
            msg = json.loads(message)
            header = msg.get("header", {})
            code = header.get("code", -1)
            status = header.get("status", 0)
            
            # 打印原始消息（用于调试）
            log.info(f"📥 讯飞响应: code={code}, status={status}, msg_len={len(message)}")
            
            if code != 0:
                error_msg = header.get("message", "未知错误")
                log.error(f"❌ 讯飞 ASR 错误: code={code}, msg={error_msg}")
                self.is_finished = True
                return
            
            # 解析识别结果
            payload = msg.get("payload", {})
            result = payload.get("result", {})
            text_base64 = result.get("text", "")
            
            log.info(f"📝 text_base64: {'存在' if text_base64 else '不存在'}, 长度: {len(text_base64) if text_base64 else 0}")
            
            if text_base64:
                # Base64 解码
                text_decoded = base64.b64decode(text_base64).decode('utf-8')
                log.info(f"📝 解码后: {text_decoded[:100]}")
                
                # 讯飞实际返回的是 JSON 格式（即使设置了 format: "plain"）
                # 需要解析 JSON 提取文本
                try:
                    text_json = json.loads(text_decoded)
                    sn = int(text_json.get("sn", 0))  # 序号
                    pgs = text_json.get("pgs", "")  # 动态修正标识：apd=追加, rpl=替换
                    rg = text_json.get("rg", [])  # 替换范围
                    
                    # 提取文本：遍历 ws -> cw -> w
                    text_ws = text_json.get("ws", [])
                    segment_text = ""
                    for ws_item in text_ws:
                        for cw_item in ws_item.get("cw", []):
                            segment_text += cw_item.get("w", "")
                    
                    log.info(f"📝 sn={sn}, pgs={pgs}, rg={rg}, 文本='{segment_text}'")
                    
                    partial_to_send = None
                    with self.lock:
                        # 根据讯飞动态修正逻辑处理文本
                        if pgs == "rpl":
                            # 替换模式：根据 rg 替换指定范围的片段
                            if isinstance(rg, list) and len(rg) == 2:
                                start, end = int(rg[0]), int(rg[1])
                                for idx in range(start, end + 1):
                                    self.result_segments.pop(idx, None)
                                log.info(f"📝 替换范围: rg={rg}，清理片段 {start}-{end}")
                            else:
                                # 如果 rg 不存在，视为全量替换
                                self.result_segments.clear()
                                log.info("📝 替换模式: rg 缺失，清空所有片段")
                            self.result_segments[sn] = segment_text
                        elif pgs == "apd":
                            # 追加模式：本帧返回的是新增内容，追加到现有结果
                            self.result_segments[sn] = segment_text
                        else:
                            # 默认：如果没有pgs字段，直接使用（兼容旧格式）
                            self.result_segments.clear()
                            self.result_segments[sn] = segment_text

                        # 重新拼接完整文本（按 sn 顺序）
                        ordered_keys = sorted(self.result_segments.keys())
                        self.result_text = "".join(self.result_segments[k] for k in ordered_keys)
                        log.info(f"📝 拼接结果: '{self.result_text}' (segments={len(ordered_keys)})")

                        # 锁内只收集数据，锁外执行回调
                        if status in [0, 1] and self.on_partial and self.result_text:
                            if self.result_text != self.last_sent_partial:
                                partial_to_send = self.result_text
                                self.last_sent_partial = self.result_text

                    # 回调在锁外执行，避免延长临界区
                    if partial_to_send is not None:
                        log.info(f"📤 发送 partial: '{partial_to_send[:50]}'")
                        self.on_partial(self.session_id, partial_to_send)

                except json.JSONDecodeError as je:
                    log.info(f"📝 不是JSON，直接使用: {text_decoded[:50]}")
                    # 如果不是 JSON，直接使用（兼容 plain 格式）
                    with self.lock:
                        self.result_text = text_decoded
            else:
                log.info(f"⚠️ 本帧无文本 (status={status})")

            # 检查是否结束
            if status == 2:
                self.is_finished = True
                log.info(f"✅ 流式识别完成: '{self.result_text}'")
                
                # 调用回调
                if self.on_result:
                    self.on_result(self.session_id, self.result_text, None)
                    
        except Exception as e:
            log.error(f"❌ 解析讯飞响应失败: {e}", exc_info=True)
            self.error = str(e)
            self.is_finished = True
            if self.on_result:
                self.on_result(self.session_id, "", str(e))
    
    def _on_error(self, ws, error):
        """连接错误"""
        log.error(f"❌ 讯飞 WebSocket 错误 ({self.session_id}): {error}")
        self.error = str(error)
        self.is_connected = False
        self.is_finished = True
    
    def _on_close(self, ws, close_status_code, close_msg):
        """连接关闭"""
        self.is_connected = False
        log.info(f"🔌 讯飞 WebSocket 已关闭: {self.session_id}")
    
    def send_chunk(self, chunk: bytes) -> bool:
        """
        发送音频片段（无延迟，立即发送）
        按照官方 demo 格式：header + parameter + payload
        
        Args:
            chunk: 音频数据（原始 PCM 格式）
            
        Returns:
            bool: 是否发送成功
        """
        # ✅ 更新最后活动时间
        self.last_activity = time.time()
        
        if not self.is_connected or not self.ws:
            # 缓存等待重连
            with self.lock:
                self.audio_buffer.append(chunk)
            log.warning(f"⚠️ WebSocket 未连接，已缓存 {len(chunk)}B")
            return False
        
        try:
            # 讯飞要求每帧 1280 字节，前端可能发送更大的片段，需要拆分
            FRAME_SIZE = 1280
            offset = 0
            
            # 讯飞识别参数（所有帧都需要）
            iat_params = {
                "domain": "slm",
                "language": "zh_cn",
                "accent": "mandarin",
                "dwa": "wpgs",
                # 延长静音判定时间，避免按住说话时过早结束（与前端60s一致）
                "eos": 60000,
                "result": {
                    "encoding": "utf8",
                    "compress": "raw",
                    "format": "plain"
                }
            }

            # 添加热词参数（仅在有热词时）
            if self.hotwords_str:
                iat_params["dhw"] = self.hotwords_str

            while offset < len(chunk):
                frame = chunk[offset:offset + FRAME_SIZE]
                frame_base64 = base64.b64encode(frame).decode('utf-8')
                
                # 确定帧状态：0=首帧, 1=中间帧
                status = 0 if self.frame_counter == 0 else 1
                
                # 按照官方 demo 格式构造数据（所有帧格式一致）
                request_data = {
                    "header": {
                        "app_id": self.app_id,
                        "status": status
                    },
                    "parameter": {
                        "iat": iat_params  # 每一帧都包含！
                    },
                    "payload": {
                        "audio": {
                            "encoding": "raw",   # PCM 格式（无损、低延迟、识别准确）
                            "sample_rate": 16000,
                            "audio": frame_base64
                        }
                    }
                }
                
                # 第一帧：打印详细信息（调试用）
                if self.frame_counter == 0:
                    log.info(f"📤 发送第一帧: frame_size={len(frame)}B, status={status}")
                    log.info(f"📤 音频参数: encoding=raw (PCM), sample_rate=16000")
                
                self.ws.send(json.dumps(request_data))
                self.frame_counter += 1
                offset += FRAME_SIZE
            
            return True
            
        except Exception as e:
            log.error(f"❌ 发送音频失败: {e}")
            # 缓存失败的片段
            with self.lock:
                self.audio_buffer.append(chunk)
            return False
    
    def send_end_frame(self) -> bool:
        """发送结束帧（按照官方 demo 格式）"""
        if not self.is_connected or not self.ws:
            log.error(f"❌ WebSocket 未连接，无法发送结束帧")
            return False
        
        try:
            # 讯飞识别参数（最后一帧也需要）
            iat_params = {
                "domain": "slm",
                "language": "zh_cn",
                "accent": "mandarin",
                "dwa": "wpgs",
                # 保持与音频帧一致的静音判定配置（与前端60s一致）
                "eos": 60000,
                "result": {
                    "encoding": "utf8",
                    "compress": "raw",
                    "format": "plain"
                }
            }

            # 添加热词参数（仅在有热词时）
            if self.hotwords_str:
                iat_params["dhw"] = self.hotwords_str

            # 按照官方 demo 格式（最后一帧也是 header + parameter + payload）
            end_frame = {
                "header": {
                    "app_id": self.app_id,
                    "status": 2  # 最后一帧
                },
                "parameter": {
                    "iat": iat_params
                },
                "payload": {
                    "audio": {
                        "encoding": "raw",   # PCM 格式（与音频帧保持一致）
                        "sample_rate": 16000,
                        "audio": ""  # 空音频
                    }
                }
            }
            
            self.ws.send(json.dumps(end_frame))
            log.info(f"📤 已发送结束帧, 共 {self.frame_counter} 帧")
            return True
            
        except Exception as e:
            log.error(f"❌ 发送结束帧失败: {e}")
            return False
    
    def reconnect(self) -> bool:
        """断线重连，发送缓存的片段"""
        log.info(f"🔄 尝试重连 ({self.session_id})...")
        
        # 重新建立连接
        if not self.start():
            return False
        
        # 发送缓存的音频片段
        with self.lock:
            buffer_copy = self.audio_buffer.copy()
            self.audio_buffer.clear()
        
        if buffer_copy:
            log.info(f"📦 发送缓存的 {len(buffer_copy)} 个音频片段")
            for chunk in buffer_copy:
                if not self.send_chunk(chunk):
                    return False
        
        return True
    
    def close(self):
        """关闭会话，释放资源"""
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                log.warning(f"Failed to close WebSocket for session {self.session_id}: {e}")
        self.is_connected = False
        log.info(f"🔒 流式识别会话已关闭: {self.session_id}")


class StreamingSTTManager:
    """流式 STT 管理器，管理多个并发会话"""
    
    def __init__(self, max_sessions: int = 10, session_timeout: int = 120):
        self.max_sessions = max_sessions
        self.session_timeout = session_timeout  # ✅ 会话超时时间（秒）
        self.sessions: Dict[str, StreamingSTTSession] = {}
        self.lock = threading.Lock()
        self._start_cleanup_timer()  # ✅ 启动定时清理任务
    
    def _start_cleanup_timer(self):
        """启动定时清理任务（每30秒检查一次）"""
        def cleanup_task():
            while True:
                time.sleep(30)
                try:
                    self._cleanup_timeout_sessions()
                except Exception as e:
                    log.error(f"❌ 定时清理任务失败: {e}", exc_info=True)
        
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()
        log.info("✅ STT 会话定时清理任务已启动")
    
    def create_session(
        self,
        session_id: Optional[str] = None,
        socket_sid: Optional[str] = None,
        on_result: Optional[Callable] = None,
        on_partial: Optional[Callable] = None,
        hotwords: Optional[List[str]] = None
    ) -> str:
        """
        创建新的流式识别会话

        Args:
            session_id: 会话 ID（可选，默认自动生成）
            socket_sid: WebSocket 连接 ID（用于连接断开时清理）
            on_result: 回调函数，签名为 (session_id: str, text: str, error: Optional[str])
            on_partial: 回调函数，签名为 (session_id: str, text: str)，收到中间识别结果时调用
            hotwords: STT 热词列表（用于提高人名识别准确率）

        Returns:
            str: 会话 ID
        """
        with self.lock:
            # 检查并发限制
            if len(self.sessions) >= self.max_sessions:
                # ✅ 清理已完成的会话和超时会话
                self._cleanup_finished_sessions()
                self._cleanup_timeout_sessions()

                if len(self.sessions) >= self.max_sessions:
                    # ✅ 打印当前会话状态帮助调试
                    log.warning(f"⚠️ 当前活跃会话数: {len(self.sessions)}")
                    for sid, sess in list(self.sessions.items())[:5]:  # 只打印前5个
                        age = time.time() - sess.created_at
                        log.warning(f"  - {sid}: age={age:.1f}s, finished={sess.is_finished}, socket_sid={sess.socket_sid}")
                    raise Exception(f"达到最大并发会话数限制: {self.max_sessions}")

            # 生成会话 ID
            if not session_id:
                session_id = str(uuid.uuid4())

            # 创建会话（传递热词和 partial 回调）
            session = StreamingSTTSession(
                session_id, socket_sid, on_result,
                on_partial=on_partial, hotwords=hotwords
            )
            if session.start():
                self.sessions[session_id] = session
                log.info(f"✅ STT 会话已创建: {session_id}, socket_sid={socket_sid}, hotwords={len(hotwords or [])}")
                return session_id
            else:
                raise Exception(f"创建流式识别会话失败: {session_id}")
    
    def send_chunk(self, session_id: str, chunk: bytes) -> bool:
        """向指定会话发送音频片段"""
        session = self.sessions.get(session_id)
        if not session:
            # 会话可能已结束，这是正常情况（前端延迟的音频片段）
            # 静默忽略，不报错
            return False
        
        # 如果会话已完成，也忽略后续音频
        if session.is_finished:
            return False
        
        return session.send_chunk(chunk)
    
    def end_session(self, session_id: str) -> tuple[Optional[str], Optional[str]]:
        """
        结束会话，返回识别结果

        Returns:
            tuple[Optional[str], Optional[str]]: (识别文本, 错误信息)
        """
        session = self.sessions.get(session_id)
        if not session:
            log.warning(f"⚠️ 会话不存在（可能已自动完成）: {session_id}")
            return None, None

        # 检查会话是否已经完成（讯飞可能已自动完成 / 已出错）
        if session.is_finished:
            log.info(f"✅ 会话已自动完成，直接返回结果: {session_id}")
            result, error = session.result_text, session.error
            self._close_session(session_id)
            return result, error

        # 如果 WebSocket 已断开，跳过结束帧，直接返回已有结果
        if not session.is_connected or not session.ws:
            log.warning(f"⚠️ WebSocket 已关闭，跳过结束帧: {session_id}")
            result, error = session.result_text, session.error
            self._close_session(session_id)
            return result, error

        # 发送结束帧
        session.send_end_frame()

        # 等待识别完成（最多30秒）
        for _ in range(300):
            if session.is_finished:
                result, error = session.result_text, session.error
                self._close_session(session_id)
                return result, error
            time.sleep(0.1)

        log.error(f"❌ 等待识别结果超时: {session_id}")
        self._close_session(session_id)
        return None, "STT recognition timeout"
    
    def _close_session(self, session_id: str):
        """关闭并移除会话"""
        with self.lock:
            session = self.sessions.pop(session_id, None)
            if session:
                session.close()
    
    def _cleanup_finished_sessions(self):
        """清理已完成的会话（内部方法，需要在 lock 中调用）"""
        finished_ids = [sid for sid, sess in self.sessions.items() if sess.is_finished]
        for sid in finished_ids:
            session = self.sessions.pop(sid)
            session.close()
        
        if finished_ids:
            log.info(f"🧹 清理了 {len(finished_ids)} 个已完成的会话")
    
    def _cleanup_timeout_sessions(self):
        """清理超时的会话（独立锁，避免死锁）"""
        with self.lock:
            current_time = time.time()
            timeout_ids = []
            
            for sid, sess in self.sessions.items():
                # 超时条件：最后活动时间超过阈值，且未完成
                age = current_time - sess.last_activity
                if age > self.session_timeout and not sess.is_finished:
                    timeout_ids.append(sid)
            
            for sid in timeout_ids:
                session = self.sessions.pop(sid)
                session.close()
                log.warning(f"⏰ 清理超时 STT 会话: {sid} (超时 {age:.1f}s)")
            
            if timeout_ids:
                log.info(f"🧹 清理了 {len(timeout_ids)} 个超时会话")
    
    def cleanup_by_socket(self, socket_sid: str):
        """
        清理指定 WebSocket 连接的所有 STT 会话
        （在连接断开时调用）
        
        Args:
            socket_sid: WebSocket 连接 ID
        """
        with self.lock:
            session_ids_to_close = [
                sid for sid, sess in self.sessions.items() 
                if sess.socket_sid == socket_sid
            ]
            
            for sid in session_ids_to_close:
                session = self.sessions.pop(sid)
                session.close()
                log.info(f"🔌 断开连接清理 STT 会话: {sid}")
            
            if session_ids_to_close:
                log.info(f"🧹 连接 {socket_sid} 断开，清理了 {len(session_ids_to_close)} 个 STT 会话")
    
    def cancel_session(self, session_id: str):
        """
        强制取消会话（不等待结果）
        
        Args:
            session_id: 会话 ID
        """
        with self.lock:
            session = self.sessions.pop(session_id, None)
            if session:
                session.close()
                log.info(f"❌ 强制取消 STT 会话: {session_id}")
            else:
                log.warning(f"⚠️ 尝试取消不存在的 STT 会话: {session_id}")


# 全局单例
_streaming_stt_manager: Optional[StreamingSTTManager] = None


def get_streaming_stt_manager() -> StreamingSTTManager:
    """获取流式 STT 管理器单例"""
    global _streaming_stt_manager
    if _streaming_stt_manager is None:
        _streaming_stt_manager = StreamingSTTManager(max_sessions=10)
        log.info("✅ 流式 STT 管理器已初始化")
    return _streaming_stt_manager

