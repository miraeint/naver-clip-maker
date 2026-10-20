"""
Gemini TTS Service Engine (TEST11 호환 및 숏폼 싱크 확장판)
- Google GenAI SDK를 활용한 음성 합성 비즈니스 로직
- PCM / WAV 자동 감지 및 인메모리 컨테이너 변환
- 30종 공식 화자(Voice) 지원 및 슬라이드별 개별 합성 / 단일 파일 무음 구간 분석 지원
"""

import os
import io
import time
import wave
import struct
import base64
from typing import Optional, Dict, Tuple, List
from google import genai
from google.genai import errors

# Gemini 공식 지원 30종 화자 목록 및 특성 매핑 (TEST11 동일)
AVAILABLE_VOICES: Dict[str, str] = {
    "Kore": "차분하고 단호한 톤 (Firm)",
    "Puck": "경쾌하고 활기찬 톤 (Upbeat)",
    "Charon": "신뢰감 있고 정보 전달에 적합한 톤 (Informative)",
    "Fenrir": "열정적이고 흥분된 톤 (Excitable)",
    "Aoede": "산뜻하고 자연스러운 톤 (Breezy)",
    "Leda": "젊고 생동감 있는 톤 (Youthful)",
    "Zephyr": "밝고 맑은 톤 (Bright)",
    "Orus": "중후하고 또렷한 톤 (Firm)",
    "Achernar": "부드럽고 편안한 톤 (Soft)",
    "Sulafat": "따뜻하고 친근한 톤 (Warm)",
    "Alnilam": "안정적이고 묵직한 톤 (Firm)",
    "Sadachbia": "생기발랄한 톤 (Lively)",
    "Callirrhoe": "편안하고 여유로운 톤 (Easy-going)",
    "Autonoe": "밝고 통통 튀는 톤 (Bright)",
    "Enceladus": "숨소리가 섞인 감성적인 톤 (Breathy)",
    "Iapetus": "명료하고 선명한 톤 (Clear)",
    "Umbriel": "담담하고 편안한 톤 (Easy-going)",
    "Algieba": "부드럽고 매끄러운 톤 (Smooth)",
    "Despina": "차분하고 매끄러운 톤 (Smooth)",
    "Erinome": "깨끗하고 청명한 톤 (Clear)",
    "Algenib": "거칠고 개성 있는 허스키 톤 (Gravelly)",
    "Rasalgethi": "차분한 설명형 톤 (Informative)",
    "Laomedeia": "밝고 긍정적인 톤 (Upbeat)",
    "Schedar": "차분하고 일정한 톤 (Even)",
    "Gacrux": "성숙하고 깊이 있는 톤 (Mature)",
    "Pulcherrima": "직접적이고 당당한 톤 (Forward)",
    "Achird": "친절하고 다정한 톤 (Friendly)",
    "Zubenelgenubi": "편안하고 일상적인 톤 (Casual)",
    "Vindemiatrix": "부드럽고 온화한 톤 (Gentle)",
    "Sadaltager": "지적이고 학구적인 톤 (Knowledgeable)"
}

# 지원 모델 목록 (기존 TEST11의 3.1 모델 및 최신 3.8 TTS 모델 모두 지원)
AVAILABLE_MODELS = {
    "gemini-3.1-flash-tts-preview": "Gemini 3.1 Flash TTS (기존 공식 음성 합성 모델)",
    "gemini-3.8-flash-tts": "Gemini 3.8 Flash TTS (최신 고품질 음성 합성 전용 모델)",
    "gemini-3.8-flash-lite-tts": "Gemini 3.8 Flash-Lite TTS (고속 경량 음성 합성 모델)"
}


class TTSError(Exception):
    """TTS 처리 중 발생하는 도메인 예외"""
    def __init__(self, message: str, code: str = "TTS_ERROR"):
        super().__init__(message)
        self.code = code


def validate_text(text: str, max_length: int = 10000) -> str:
    if not text or not text.strip():
        raise TTSError("음성으로 변환할 텍스트를 1자 이상 입력해주세요.", code="EMPTY_INPUT")
    cleaned = text.strip()
    if len(cleaned) > max_length:
        raise TTSError(f"텍스트 길이가 최대 허용치({max_length:,}자)를 초과했습니다. (현재 {len(cleaned):,}자)", code="TEXT_TOO_LONG")
    return cleaned


def pcm_to_wav(pcm_bytes: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2) -> bytes:
    """
    Raw PCM 오디오 또는 이미 RIFF 헤더가 포함된 WAV 바이트를 표준 WAV 포맷으로 반환합니다.
    """
    if pcm_bytes[:4] == b"RIFF":
        return pcm_bytes
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm_bytes)
    return wav_io.getvalue()


def get_wav_duration(wav_bytes: bytes) -> float:
    """WAV 바이트 데이터의 재생 길이(초)를 정확히 반환합니다."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return round(frames / float(rate), 3) if rate > 0 else 0.0


def concat_wav_files(wav_list: List[bytes], pause_sec: float = 0.3) -> Tuple[bytes, List[float]]:
    """
    여러 개의 슬라이드별 WAV 바이트를 하나로 합치고,
    각 슬라이드가 화면에 표시되어야 할 정확한 재생 시간(초) 리스트를 반환합니다.
    """
    if not wav_list:
        raise ValueError("합칠 WAV 데이터가 없습니다.")

    params = None
    pcm_chunks = []
    durations = []

    for idx, wb in enumerate(wav_list):
        with wave.open(io.BytesIO(wb), "rb") as wf:
            if params is None:
                params = wf.getparams()
            n_frames = wf.getnframes()
            rate = wf.getframerate()
            sampwidth = wf.getsampwidth()
            nchannels = wf.getnchannels()
            raw_frames = wf.readframes(n_frames)

            clip_dur = n_frames / float(rate) if rate > 0 else 0.0
            # 슬라이드 전환 여유 시간(무음 패딩) 추가
            pad_sec = pause_sec if idx < len(wav_list) - 1 else 0.25
            pad_frames = int(rate * pad_sec)
            silence_bytes = b"\x00" * (pad_frames * sampwidth * nchannels)

            pcm_chunks.append(raw_frames + silence_bytes)
            durations.append(round(clip_dur + pad_sec, 3))

    out_io = io.BytesIO()
    with wave.open(out_io, "wb") as out_wf:
        out_wf.setnchannels(params.nchannels)
        out_wf.setsampwidth(params.sampwidth)
        out_wf.setframerate(params.framerate)
        for chunk in pcm_chunks:
            out_wf.writeframes(chunk)

    return out_io.getvalue(), durations


def estimate_slide_durations_from_single_wav(wav_bytes: bytes, slide_scripts: List[str]) -> List[float]:
    """
    통짜 WAV 파일 1개(예: 기존에 뽑아둔 42초 WAV)와 4장의 슬라이드 대본 텍스트를 받아,
    음성의 무음(숨 쉬는 구간) 및 글자 수 비율을 결합 분석하여
    1~4번 슬라이드의 가장 자연스러운 전환 시간(초) 4개를 계산합니다.
    """
    total_dur = get_wav_duration(wav_bytes)
    n_slides = len(slide_scripts)
    if n_slides == 0:
        return [total_dur]
    if total_dur <= 0:
        return [7.5] * n_slides

    # 1. 각 슬라이드 대본 글자 수 비율 계산 (공백 제외 가중치)
    lengths = [max(len(s.replace(" ", "").strip()), 5) for s in slide_scripts]
    total_len = sum(lengths)
    raw_targets = []
    acc = 0.0
    for l in lengths[:-1]:
        acc += total_dur * (l / total_len)
        raw_targets.append(acc)

    # 2. WAV 파일에서 무음 구간(에너지가 낮은 지점) 탐색하여 가장 가까운 숨 고르기 지점으로 스냅
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            rate = wf.getframerate()
            sampwidth = wf.getsampwidth()
            nchannels = wf.getnchannels()
            nframes = wf.getnframes()
            raw = wf.readframes(nframes)

        if sampwidth == 2 and nframes > 0:
            # 0.05초(50ms) 단위 윈도우 RMS 계산
            win_frames = max(int(rate * 0.05), 1)
            step_bytes = win_frames * sampwidth * nchannels
            rms_list = []
            for offset in range(0, len(raw) - step_bytes, step_bytes):
                chunk = raw[offset:offset + step_bytes]
                count = len(chunk) // 2
                samples = struct.unpack(f"<{count}h", chunk[:count * 2])
                avg_abs = sum(abs(s) for s in samples) / max(count, 1)
                rms_list.append(avg_abs)

            snapped_splits = []
            prev_split = 0.5
            for target_sec in raw_targets:
                # 목표 지점 전후 ±1.8초 범위 내에서 가장 조용한(숨 쉬는) 윈도우 찾기
                center_idx = int(target_sec / 0.05)
                search_radius = int(1.8 / 0.05)
                start_i = max(int((prev_split + 1.5) / 0.05), center_idx - search_radius, 0)
                end_i = min(len(rms_list) - 10, center_idx + search_radius)

                if start_i < end_i:
                    best_i = min(
                        range(start_i, end_i + 1),
                        key=lambda i: rms_list[i] + abs(i - center_idx) * 8.0
                    )
                    split_sec = round(best_i * 0.05, 2)
                else:
                    split_sec = round(target_sec, 2)
                snapped_splits.append(split_sec)
                prev_split = split_sec

            durations = []
            last_t = 0.0
            for sp in snapped_splits:
                durations.append(round(sp - last_t, 2))
                last_t = sp
            durations.append(round(max(total_dur - last_t, 1.0), 2))
            return durations
    except Exception:
        pass

    # 폴백: 글자 수 비례 배분
    durations = [round(total_dur * (l / total_len), 2) for l in lengths]
    diff = round(total_dur - sum(durations), 2)
    durations[-1] = round(durations[-1] + diff, 2)
    return durations


def generate_tts_audio(
    text: str,
    voice: str = "Kore",
    model: str = "gemini-3.1-flash-tts-preview",
    api_key: Optional[str] = None,
    style_prompt: Optional[str] = None,
    max_length: int = 10000
) -> Tuple[bytes, Dict[str, any]]:
    """
    Gemini API를 호출하여 텍스트를 음성으로 변환하고 WAV 바이너리를 반환합니다.
    """
    sanitized_text = validate_text(text, max_length=max_length)

    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise TTSError(
            "Gemini API Key가 설정되지 않았습니다. 좌측 사이드바에 API 키를 입력해주세요.",
            code="API_KEY_MISSING"
        )

    try:
        client = genai.Client(api_key=key)
    except Exception as e:
        raise TTSError(f"Gemini 클라이언트 초기화 실패: {str(e)}", code="CLIENT_INIT_FAILED")

    if "3.8" in model and style_prompt and style_prompt.strip():
        input_payload = [{
            "type": "user_input",
            "content": [{
                "type": "text",
                "text": sanitized_text,
                "annotations": [{
                    "type": "speech_metadata",
                    "style": style_prompt.strip(),
                }],
            }],
        }]
    else:
        final_text = f"{style_prompt.strip()}: {sanitized_text}" if (style_prompt and style_prompt.strip()) else sanitized_text
        input_payload = final_text

    interaction = None
    for attempt in range(3):
        try:
            interaction = client.interactions.create(
                model=model,
                input=input_payload,
                response_format={"type": "audio"},
                generation_config={
                    "speech_config": [
                        {"voice": voice}
                    ]
                }
            )
            break
        except errors.APIError as e:
            status_code = getattr(e, "code", None)
            err_msg = str(e)
            if status_code == 503 or "high demand" in err_msg.lower() or "temporar" in err_msg.lower() or status_code == 429:
                if attempt < 2:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                raise TTSError("현재 구글 AI 서버 트래픽이 많아 일시적으로 지연되고 있습니다. 잠시 후 다시 시도해주세요.", code="SERVER_BUSY")
            elif status_code in (401, 403) or "API_KEY_INVALID" in err_msg:
                raise TTSError("API Key가 유효하지 않거나 권한이 없습니다. API 키를 다시 확인해주세요.", code="AUTH_FAILED")
            elif "SAFETY" in err_msg or "blocked" in err_msg.lower():
                raise TTSError("안전성 및 콘텐츠 정책에 의해 음성 생성이 차단되었습니다. 텍스트 내용을 수정해주세요.", code="SAFETY_BLOCKED")
            else:
                raise TTSError(f"Gemini API 오류 ({status_code}): {err_msg}", code="API_ERROR")
        except Exception as e:
            err_str = str(e)
            if "timeout" in err_str.lower() and attempt < 2:
                time.sleep(2.0)
                continue
            raise TTSError(f"음성 생성 중 오류가 발생했습니다: {err_str}", code="UNKNOWN_ERROR")

    output_audio = getattr(interaction, "output_audio", None)
    if not output_audio or not output_audio.data:
        raise TTSError("모델로부터 오디오 스트림을 수신하지 못했습니다. (빈 응답)", code="EMPTY_AUDIO_RESPONSE")

    raw_audio_bytes = base64.b64decode(output_audio.data)
    wav_bytes = pcm_to_wav(raw_audio_bytes, channels=1, rate=24000, sample_width=2)
    duration_sec = get_wav_duration(wav_bytes)

    metadata = {
        "model": model,
        "voice": voice,
        "input_length": len(sanitized_text),
        "pcm_bytes_size": len(raw_audio_bytes),
        "wav_bytes_size": len(wav_bytes),
        "duration_seconds": duration_sec,
    }

    return wav_bytes, metadata
