"""
네이버 클립 9:16 (1080x1920) MP4 숏폼 동영상 합성 엔진
- 별도 FFmpeg 설치 없이 imageio-ffmpeg 내장 바이너리로 즉시 인코딩
- 슬라이드 4장(PNG) + 나레이션 음성(WAV) 완벽 싱크 및 부드러운 페이드 전환 지원
"""

import os
import subprocess
from typing import List, Optional
import imageio_ffmpeg


def create_shortform_mp4(
    slide_paths: List[str],
    wav_path: str,
    durations: List[float],
    output_mp4_path: str,
    use_fade: bool = True,
    fade_dur: float = 0.35,
    bgm_path: Optional[str] = None,
    bgm_volume: float = 0.12
) -> str:
    """
    슬라이드 이미지 리스트와 WAV 음성 파일, 각 슬라이드 표시 시간(초)을 받아
    네이버 클립/유튜브 쇼츠/릴스 표준 규격(1080x1920, H.264, AAC, 30fps) MP4를 생성합니다.
    """
    if len(slide_paths) != len(durations):
        raise ValueError("슬라이드 개수와 재생 시간(durations) 개수가 일치해야 합니다.")

    os.makedirs(os.path.dirname(output_mp4_path) or "output", exist_ok=True)
    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        import shutil
        ffmpeg_exe = shutil.which("ffmpeg") or "ffmpeg"

    n = len(slide_paths)
    safe_durations = [max(float(d), 1.0) for d in durations]

    cmd = [ffmpeg_exe, "-y"]

    if use_fade and n >= 2:
        # xfade 필터 사용 시 각 클립은 전환 겹침(fade_dur)만큼 여유를 두어 총 길이가 정확히 맞도록 설정
        for i, (sp, dur) in enumerate(zip(slide_paths, safe_durations)):
            extra = fade_dur if i < n - 1 else 0.2
            cmd.extend(["-loop", "1", "-t", f"{dur + extra:.3f}", "-r", "30", "-i", os.path.abspath(sp)])

        cmd.extend(["-i", os.path.abspath(wav_path)])
        audio_input_idx = n

        if bgm_path and os.path.exists(bgm_path):
            cmd.extend(["-stream_loop", "-1", "-i", os.path.abspath(bgm_path)])
            bgm_input_idx = n + 1
        else:
            bgm_input_idx = None

        filter_parts = []
        for i in range(n):
            filter_parts.append(f"[{i}:v]scale=1080:1920,setsar=1,format=yuv420p[v{i}]")

        offset = 0.0
        prev_label = "v0"
        for i in range(1, n):
            offset += safe_durations[i - 1]
            out_label = f"vx{i}" if i < n - 1 else "vout"
            filter_parts.append(
                f"[{prev_label}][v{i}]xfade=transition=fade:duration={fade_dur:.3f}:offset={offset:.3f}[{out_label}]"
            )
            prev_label = out_label

        if bgm_input_idx is not None:
            total_dur = sum(safe_durations)
            filter_parts.append(
                f"[{bgm_input_idx}:a]atrim=0:{total_dur:.3f},volume={bgm_volume:.2f}[bgm];"
                f"[{audio_input_idx}:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
            audio_map = "[aout]"
        else:
            audio_map = f"{audio_input_idx}:a"

        filter_complex = ";".join(filter_parts)
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", audio_map,
        ])
    else:
        # 즉시 전환 모드
        for sp, dur in zip(slide_paths, safe_durations):
            cmd.extend(["-loop", "1", "-t", f"{dur:.3f}", "-r", "30", "-i", os.path.abspath(sp)])
        cmd.extend(["-i", os.path.abspath(wav_path)])
        audio_input_idx = n

        v_inputs = "".join(f"[{i}:v]" for i in range(n))
        filter_complex = f"{v_inputs}concat=n={n}:v=1:a=0,scale=1080:1920,setsar=1,format=yuv420p[vout]"
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", f"{audio_input_idx}:a",
        ])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        os.path.abspath(output_mp4_path)
    ])

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"MP4 동영상 인코딩 실패:\n{proc.stderr[-800:]}")

    return output_mp4_path
