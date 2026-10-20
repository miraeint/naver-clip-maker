---
title: Naver Clip Shortform Studio
emoji: 🎬
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: "1.66.0"
app_file: app.py
pinned: false
---

# 🎬 네이버 클립 숏폼 올인원 스튜디오 (Naver Clip Shortform Studio)

네이버 블로그 URL 하나로 9:16 고화질 숏폼 슬라이드 기획, AI 나레이션(TTS), 1080x1920 MP4 동영상을 원클릭으로 자동 생성하는 스튜디오입니다.

## 주요 기능
- **네이버 블로그 본문/이미지 자동 추출**
- **Gemini AI 기반 4컷 숏폼 기획 & 대본 생성**
- **1080x1920 세로형 슬라이드 4장 실시간 렌더링**
- **Gemini Flash TTS 자연스러운 고음질 한국어 음성 합성**
- **FFmpeg 기반 슬라이드 + 음성 싱크 MP4 비디오 자동 생성**

## 필수 환경변수 설정 (Secrets)
Hugging Face Space의 **Settings > Variables and secrets**에서 다음 Secret을 등록하세요:
- `GEMINI_API_KEY`: Google AI Studio에서 발급받은 Gemini API 키
- `APP_PASSWORD` (선택 사항): 접속 비밀번호를 지정하여 타인의 무단 사용 방지
