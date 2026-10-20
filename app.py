"""
네이버 클립 숏폼 올인원 스튜디오 (Streamlit Web App)
- 네이버 블로그 URL 본문/사진 자동 추출 및 AI 4컷 슬라이드 기획
- 9:16 (1080x1920) 슬라이드 4장 실시간 렌더링 & ZIP 패키징
- Gemini Flash TTS (TEST11 엔진 통합) 음성 합성 및 기존 WAV 파일 호환
- 슬라이드 + 음성 자동 싱크 9:16 MP4 동영상 원클릭 생성
"""

import os
import io
import json
import time
import subprocess
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv, set_key

# 로컬 및 기존 TEST11 폴더의 .env 로드
load_dotenv(".env")
if not os.getenv("GEMINI_API_KEY") and os.path.exists("../TEST11/.env"):
    load_dotenv("../TEST11/.env")

# Streamlit Community Cloud의 st.secrets 지원
try:
    if "GEMINI_API_KEY" in st.secrets and not os.getenv("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = str(st.secrets["GEMINI_API_KEY"]).strip()
    if "APP_PASSWORD" in st.secrets and not os.getenv("APP_PASSWORD"):
        os.environ["APP_PASSWORD"] = str(st.secrets["APP_PASSWORD"]).strip()
except Exception:
    pass

from make_clip_slides import render_slides_from_config, ensure_fonts, ensure_sample_images
from tts_engine import (
    AVAILABLE_VOICES,
    AVAILABLE_MODELS,
    generate_tts_audio,
    concat_wav_files,
    estimate_slide_durations_from_single_wav,
    get_wav_duration,
    TTSError,
)
from video_maker import create_shortform_mp4
from blog_scraper import fetch_naver_blog
from ai_generator import generate_clip_plan_from_blog, generate_ai_image, fetch_smart_stock_photo

st.set_page_config(
    page_title="네이버 클립 숏폼 올인원 스튜디오",
    page_icon="🎬",
    layout="wide",
)

def check_access_password() -> bool:
    app_pwd = os.getenv("APP_PASSWORD", "").strip()
    if not app_pwd:
        return True
    if st.session_state.get("authenticated", False):
        return True

    _, center_col, _ = st.columns([1, 1.6, 1])
    with center_col:
        st.markdown("### 🔒 네이버 클립 스튜디오 접속 인증")
        st.info("보안을 위해 지정된 접근 비밀번호를 입력해주세요.")
        entered = st.text_input("접속 비밀번호", type="password", key="login_pwd_input")
        if st.button("확인 및 입장", use_container_width=True, type="primary"):
            if entered == app_pwd:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ 비밀번호가 올바르지 않습니다.")
    return False

if not check_access_password():
    st.stop()



def load_initial_data() -> dict:
    if os.path.exists("data.json"):
        with open("data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {"project_name": "naver_clip", "font_bold": "font/bold.ttf", "font_regular": "font/regular.ttf", "slides": []}


def save_data_json(data: dict) -> None:
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clear_widget_cache() -> None:
    """새로운 기획 생성, JSON 반영 또는 데이터 동기화 시 data_version을 증가시켜 브라우저 DOM 위젯 캐시를 완전히 강제 교체"""
    st.session_state.data_version = st.session_state.get("data_version", 0) + 1
    st.session_state.audio_bytes = None
    st.session_state.audio_metadata = None
    st.session_state.slide_durations = [9.5, 11.0, 10.5, 11.0]
    st.session_state.mp4_path = None


def reload_from_data_json() -> None:
    """data.json 파일에서 최신 내용을 강제로 불러와 위젯과 슬라이드를 완전 동기화"""
    loaded = load_initial_data()
    st.session_state.clip_data = loaded
    st.session_state.current_project = loaded.get("project_name", "")
    clear_widget_cache()
    s_paths, z_path = render_slides_from_config(loaded, output_dir="output")
    st.session_state.slide_paths = s_paths
    st.session_state.zip_path = z_path


# --- 세션 상태 초기화 ---
if "data_version" not in st.session_state:
    st.session_state.data_version = 1
if "clip_data" not in st.session_state:
    st.session_state.clip_data = load_initial_data()
if "current_project" not in st.session_state:
    st.session_state.current_project = st.session_state.clip_data.get("project_name", "")

# 프로젝트가 변경되었을 때 위젯 캐시 자동 감지 및 초기화
curr_proj = st.session_state.clip_data.get("project_name", "")
if st.session_state.current_project != curr_proj:
    clear_widget_cache()
    st.session_state.current_project = curr_proj

ver = st.session_state.get("data_version", 1)

if "slide_paths" not in st.session_state or "zip_path" not in st.session_state:
    s_paths, z_path = render_slides_from_config(st.session_state.clip_data, output_dir="output")
    st.session_state.slide_paths = s_paths
    st.session_state.zip_path = z_path
if "blog_images" not in st.session_state:
    st.session_state.blog_images = []
if "blog_text" not in st.session_state:
    st.session_state.blog_text = ""
if "audio_bytes" not in st.session_state:
    st.session_state.audio_bytes = None
if "audio_metadata" not in st.session_state:
    st.session_state.audio_metadata = None
if "slide_durations" not in st.session_state:
    st.session_state.slide_durations = [9.5, 11.0, 10.5, 11.0]
if "mp4_path" not in st.session_state:
    st.session_state.mp4_path = None


# --- 사이드바 설정 영역 (TEST11 스타일 계승 + 확장) ---
with st.sidebar:
    st.header("⚙️ 환경 및 음성/영상 설정")

    env_api_key = os.getenv("GEMINI_API_KEY", "")
    api_key_input = st.text_input(
        "1. Gemini API Key",
        value=env_api_key,
        type="password",
        placeholder="AIzaSy...",
        help="한 번 입력 후 아래 저장 버튼을 누르면 .env 파일에 영구 저장됩니다."
    )
    if st.button("💾 API Key 로컬에 기억하기 (.env 저장)", use_container_width=True):
        if api_key_input.strip():
            with open(".env", "a", encoding="utf-8"):
                pass
            set_key(".env", "GEMINI_API_KEY", api_key_input.strip())
            os.environ["GEMINI_API_KEY"] = api_key_input.strip()
            st.success("✅ .env 파일에 API 키가 저장되었습니다! 다음부터 자동으로 불러옵니다.")
        else:
            st.warning("API Key를 먼저 입력해주세요.")

    st.markdown("---")

    st.subheader("🎙️ 모델 및 목소리 선택")
    model_keys = list(AVAILABLE_MODELS.keys())
    selected_model = st.selectbox(
        "사용 모델",
        options=model_keys,
        index=0,
        format_func=lambda k: AVAILABLE_MODELS[k]
    )

    voice_keys = list(AVAILABLE_VOICES.keys())
    selected_voice = st.selectbox(
        "목소리 (화자) 선택",
        options=voice_keys,
        index=0,
        format_func=lambda k: f"{k} - {AVAILABLE_VOICES[k]}"
    )

    style_prompt = st.text_input(
        "연기 지시문 (선택)",
        value="",
        placeholder="예: 차분하고 신뢰감 있는 전문가 톤으로",
        help="비워두면 기본 톤으로 발화하며, 입력 시 해당 톤을 반영합니다."
    )

    st.markdown("---")
    st.subheader("🎞️ 동영상 전환 및 BGM 옵션")
    use_fade = st.checkbox("슬라이드 전환 시 부드러운 페이드 효과 적용", value=True)
    uploaded_bgm = st.file_uploader("배경음악 (BGM MP3/WAV, 선택)", type=["mp3", "wav"])
    bgm_vol = st.slider("BGM 볼륨 비율", min_value=0.05, max_value=0.40, value=0.12, step=0.01)

    st.markdown("---")
    if st.button("📂 결과물(output) 폴더 열기", use_container_width=True):
        out_abs = os.path.abspath("output")
        os.makedirs(out_abs, exist_ok=True)
        subprocess.Popen(["explorer", out_abs])


# --- 메인 타이틀 ---
st.title("🎬 네이버 클립 숏폼 올인원 스튜디오")
st.markdown(
    "**블로그 URL 추출 → 9:16 슬라이드 4장(PNG/ZIP) → Gemini Flash TTS 나레이션 → MP4 완성 동영상**을 한 화면에서 제작합니다."
)

# ==============================================================================
# STEP 1. 데이터 입력 (블로그 URL 자동 기획 OR JSON 붙여넣기)
# ==============================================================================
with st.expander("1️⃣ [Step 1] 블로그 URL 자동 불러오기 또는 data.json 붙여넣기", expanded=False):
    tab_blog, tab_json = st.tabs(["🌐 네이버 블로그 URL로 자동 기획 (AI)", "📋 data.json 직접 붙여넣기 / 편집"])

    with tab_blog:
        col_u1, col_u2 = st.columns([3, 1])
        with col_u1:
            blog_url = st.text_input(
                "네이버 블로그 본문 URL 입력",
                placeholder="https://blog.naver.com/아이디/글번호"
            )
        with col_u2:
            st.write("")
            st.write("")
            btn_fetch_and_plan = st.button("🚀 블로그 추출 + AI 4컷 자동 기획", type="primary", use_container_width=True)

        col_b1, col_b2 = st.columns([1, 1])
        with col_b1:
            btn_only_fetch = st.button("📥 블로그 본문 & 사진만 먼저 추출하기", use_container_width=True)
        with col_b2:
            btn_only_ai = st.button("✨ 아래 본문 텍스트로 AI 4컷 슬라이드 & 대본 생성", use_container_width=True)

        if btn_only_fetch or btn_fetch_and_plan:
            if not blog_url.strip():
                st.warning("네이버 블로그 URL을 입력해주세요.")
            else:
                try:
                    with st.spinner("네이버 블로그 모바일 뷰에서 본문과 원본 사진들을 추출하는 중입니다..."):
                        res = fetch_naver_blog(blog_url.strip())
                        st.session_state.blog_text = f"[제목] {res['title']}\n\n{res['body_text']}"
                        st.session_state.blog_images = res["downloaded_images"]
                    st.success(
                        f"✅ 블로그 추출 성공! (본문 {len(res['body_text']):,}자 / 이미지 {len(res['downloaded_images'])}장 다운로드 완료)"
                    )
                except Exception as e:
                    st.error(f"블로그 추출 실패: {e}")

        st.session_state.blog_text = st.text_area(
            "추출된 블로그 본문 (또는 직접 본문 내용을 붙여넣으세요)",
            value=st.session_state.blog_text,
            height=150,
            placeholder="URL 없이 본문 텍스트만 여기에 직접 복사+붙여넣기 하셔도 AI 기획이 가능합니다."
        )

        if st.session_state.blog_images:
            st.caption(f"📸 블로그에서 추출된 이미지 ({len(st.session_state.blog_images)}장):")
            img_cols = st.columns(min(len(st.session_state.blog_images), 6))
            for idx, b_img in enumerate(st.session_state.blog_images[:6]):
                with img_cols[idx]:
                    st.image(b_img, caption=f"블로그 사진 #{idx+1}", use_container_width=True)

        if btn_only_ai or (btn_fetch_and_plan and st.session_state.blog_text.strip()):
            eff_key = api_key_input.strip() or os.getenv("GEMINI_API_KEY")
            if not eff_key:
                st.error("좌측 사이드바에 Gemini API Key를 먼저 입력해주세요.")
            elif not st.session_state.blog_text.strip():
                st.warning("기획할 블로그 본문 텍스트가 없습니다.")
            else:
                try:
                    with st.spinner("Gemini AI가 30초 대본과 4컷 슬라이드 구성안을 작성하고 이미지를 렌더링 중입니다..."):
                        new_data = generate_clip_plan_from_blog(
                            blog_text=st.session_state.blog_text,
                            api_key=eff_key,
                            downloaded_images=st.session_state.blog_images
                        )
                        st.session_state.clip_data = new_data
                        st.session_state.current_project = new_data.get("project_name", "")
                        save_data_json(new_data)
                        clear_widget_cache()
                        s_paths, z_path = render_slides_from_config(new_data, output_dir="output")
                        st.session_state.slide_paths = s_paths
                        st.session_state.zip_path = z_path
                    st.success("🎉 AI 4컷 슬라이드 기획 및 이미지 렌더링이 완료되었습니다!")
                    st.rerun()
                except Exception as e:
                    st.error(f"AI 기획 중 오류 발생: {e}")

    with tab_json:
        st.caption("제미나이 채팅창에서 받은 `data.json` 코드를 그대로 붙여넣고 적용할 수 있습니다.")
        raw_json_str = st.text_area(
            "data.json 내용 편집",
            value=json.dumps(st.session_state.clip_data, ensure_ascii=False, indent=2),
            height=320
        )
        if st.button("✅ JSON 적용 및 슬라이드 4장 즉시 렌더링", type="primary"):
            try:
                parsed_json = json.loads(raw_json_str)
                st.session_state.clip_data = parsed_json
                st.session_state.current_project = parsed_json.get("project_name", "")
                save_data_json(parsed_json)
                clear_widget_cache()
                s_paths, z_path = render_slides_from_config(parsed_json, output_dir="output")
                st.session_state.slide_paths = s_paths
                st.session_state.zip_path = z_path
                st.success("✅ JSON 설정이 반영되어 슬라이드 4장과 ZIP 파일이 새로 생성되었습니다!")
                st.rerun()
            except Exception as e:
                st.error(f"JSON 형식 오류: {e}")


# ==============================================================================
# STEP 2. 슬라이드 4장 미리보기 & 사진/문구 간편 편집 & ZIP 다운로드
# ==============================================================================
st.markdown("---")
col_h1, col_h2, col_h3, col_h4 = st.columns([1.8, 1.1, 1.1, 1.3])
with col_h1:
    st.subheader("2️⃣ [Step 2] 9:16 슬라이드 4장 미리보기 및 커스텀")
with col_h2:
    if st.button("🔄 data.json 동기화", help="이전 프로젝트 텍스트/대본이 남아있을 때 data.json 파일 내용으로 화면을 깨끗하게 동기화합니다.", use_container_width=True):
        reload_from_data_json()
        st.toast("data.json 내용으로 동기화 완료!", icon="✅")
        st.rerun()
with col_h3:
    if st.button("🖼️ 슬라이드 다시 렌더링", use_container_width=True):
        save_data_json(st.session_state.clip_data)
        s_paths, z_path = render_slides_from_config(st.session_state.clip_data, output_dir="output")
        st.session_state.slide_paths = s_paths
        st.session_state.zip_path = z_path
        st.toast("슬라이드 4장이 최신 상태로 렌더링되었습니다!", icon="✅")
with col_h4:
    if st.session_state.zip_path and os.path.exists(st.session_state.zip_path):
        with open(st.session_state.zip_path, "rb") as zf:
            st.download_button(
                label=f"📦 ZIP 다운로드",
                data=zf.read(),
                file_name=os.path.basename(st.session_state.zip_path),
                mime="application/zip",
                type="primary",
                use_container_width=True,
            )

# 4장 나란히 미리보기
slides_list = st.session_state.clip_data.get("slides", [])
preview_cols = st.columns(4)
for idx in range(min(4, len(st.session_state.slide_paths))):
    with preview_cols[idx]:
        sp = st.session_state.slide_paths[idx]
        if os.path.exists(sp):
            st.image(sp, caption=f"슬라이드 {idx + 1} (1080×1920)", use_container_width=True)

# 슬라이드별 문구 및 사진 개별 수정 아코디언
with st.expander("✏️ 슬라이드별 사진 교체 및 텍스트/대본 세부 수정 (클릭하여 열기)", expanded=False):
    edit_cols = st.columns(4)
    updated = False

    for idx in range(min(4, len(slides_list))):
        s_cfg = slides_list[idx]
        img_key = "bg_image" if s_cfg.get("type") == "vertical_bg" else "photo"

        with edit_cols[idx]:
            st.markdown(f"#### 📄 슬라이드 {idx + 1}")

            # 사진 업로드 교체
            up_img = st.file_uploader(f"슬라이드 {idx+1} 사진 변경", type=["png", "jpg", "jpeg", "webp"], key=f"up_img_{idx}_{ver}")
            if up_img is not None:
                os.makedirs("images", exist_ok=True)
                ext = os.path.splitext(up_img.name)[1] or ".png"
                custom_path = f"images/custom_slide_{idx+1}{ext}"
                with open(custom_path, "wb") as f:
                    f.write(up_img.getbuffer())
                if s_cfg.get(img_key) != custom_path:
                    s_cfg[img_key] = custom_path
                    updated = True

            # 블로그 추출 사진 중에서 선택하기
            if st.session_state.blog_images:
                sel_blog_img = st.selectbox(
                    f"블로그 사진에서 선택 (#{idx+1})",
                    options=["(현재 이미지 유지)"] + st.session_state.blog_images,
                    key=f"sel_blog_{idx}_{ver}"
                )
                if sel_blog_img != "(현재 이미지 유지)" and s_cfg.get(img_key) != sel_blog_img:
                    s_cfg[img_key] = sel_blog_img
                    updated = True

            # 대본 맞춤 초고화질 실사 스톡 사진 적용 (만화/인형 왜곡 방지)
            if st.button(f"📸 대본 맞춤 실사 사진 적용 (#{idx+1})", key=f"btn_stock_img_{idx}_{ver}", use_container_width=True):
                with st.spinner(f"슬라이드 {idx+1} 주제에 맞는 초고화질 실사 스톡 사진을 적용 중입니다..."):
                    try:
                        w = 1080 if s_cfg.get("type") == "vertical_bg" else 970
                        h = 1920 if s_cfg.get("type") == "vertical_bg" else 600
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        stock_path = f"images/stock_slide_{idx+1}_{ts}.jpg"
                        ctx = f"{s_cfg.get('title', '')} {s_cfg.get('subtitle', '')} {s_cfg.get('narration', '')}"
                        fetch_smart_stock_photo(ctx, stock_path, width=w, height=h, seed_idx=idx + int(time.time()) % 5)
                        if os.path.exists(stock_path):
                            s_cfg[img_key] = stock_path
                            save_data_json(st.session_state.clip_data)
                            s_paths, z_path = render_slides_from_config(st.session_state.clip_data, output_dir="output")
                            st.session_state.slide_paths = s_paths
                            st.session_state.zip_path = z_path
                            st.toast(f"슬라이드 {idx+1}에 고화질 실사 사진이 적용되었습니다!", icon="📸")
                            st.rerun()
                    except Exception as e:
                        st.error(f"실사 사진 적용 실패: {e}")

            s_cfg["badge"] = st.text_input("상단 배지", value=s_cfg.get("badge", ""), key=f"badge_{idx}_{ver}")
            s_cfg["title"] = st.text_area("메인 제목", value=s_cfg.get("title", ""), height=68, key=f"title_{idx}_{ver}")
            s_cfg["subtitle"] = st.text_input("서브 제목", value=s_cfg.get("subtitle", ""), key=f"sub_{idx}_{ver}")
            s_cfg["card_badge"] = st.text_input("카드 배지", value=s_cfg.get("card_badge", ""), key=f"cbadge_{idx}_{ver}")
            s_cfg["cta"] = st.text_input("하단 CTA 문구", value=s_cfg.get("cta", ""), key=f"cta_{idx}_{ver}")

    if st.button("💾 수정한 텍스트/사진 즉시 반영하기", type="primary", use_container_width=True):
        save_data_json(st.session_state.clip_data)
        s_paths, z_path = render_slides_from_config(st.session_state.clip_data, output_dir="output")
        st.session_state.slide_paths = s_paths
        st.session_state.zip_path = z_path
        st.success("✅ 슬라이드 수정 사항이 반영되었습니다!")
        st.rerun()


# ==============================================================================
# STEP 3. 나레이션 음성(Gemini Flash TTS) & MP4 숏폼 동영상 원클릭 제작
# ==============================================================================
st.markdown("---")
st.subheader("3️⃣ [Step 3] 나레이션 음성(TTS) & 9:16 MP4 동영상 원클릭 합성")

# 슬라이드별 대본 편집 및 전체 대본 통합
narration_cols = st.columns(4)
slide_scripts = []
for idx in range(4):
    s_cfg = slides_list[idx] if idx < len(slides_list) else {}
    cur_nar = s_cfg.get("narration", "")
    with narration_cols[idx]:
        edited_nar = st.text_area(
            f"🗣️ 슬라이드 {idx+1} 대본",
            value=cur_nar,
            height=115,
            key=f"nar_input_{idx}_{ver}"
        )
        if idx < len(slides_list):
            slides_list[idx]["narration"] = edited_nar
        slide_scripts.append(edited_nar.strip())

full_script_text = "\n".join(s for s in slide_scripts if s)
st.caption(f"전체 대본 글자 수: **{len(full_script_text):,}자** (슬라이드 1~4 합산)")

tab_tts_auto, tab_wav_upload = st.tabs([
    "🎙️ 방법 A: Gemini Flash TTS로 음성 생성 + MP4 영상 한 번에 만들기",
    "📂 방법 B: 이미 만들어 둔 WAV 음성 파일 올려서 1초 만에 MP4 영상 만들기"
])

with tab_tts_auto:
    sync_mode = st.radio(
        "음성 생성 및 슬라이드 싱크 방식 선택",
        options=[
            "⚡ 통합 1회 생성 + 무음 구간 자동 싱크 (TEST11과 동일하게 한 번에 읽고 숨 고르기 구간에 맞춰 화면 전환 - 추천)",
            "🎯 슬라이드별 4회 분할 생성 (각 슬라이드 대본을 개별로 생성하여 0.01초 단위로 정확히 일치)"
        ],
        index=0
    )

    col_act1, col_act2 = st.columns([1, 1])
    with col_act1:
        btn_tts_and_mp4 = st.button(
            "🎬 Gemini TTS 음성 생성 + MP4 동영상 한 번에 제작",
            type="primary",
            use_container_width=True
        )
    with col_act2:
        btn_tts_only = st.button(
            "🔊 Gemini TTS 음성(WAV)만 먼저 생성하기",
            use_container_width=True
        )

    if btn_tts_and_mp4 or btn_tts_only:
        eff_key = api_key_input.strip() or os.getenv("GEMINI_API_KEY")
        try:
            start_t = time.time()
            if "통합 1회 생성" in sync_mode:
                with st.spinner(f"Gemini TTS ({selected_voice})로 전체 나레이션 음성을 생성하는 중입니다..."):
                    wav_bytes, meta = generate_tts_audio(
                        text=full_script_text,
                        voice=selected_voice,
                        model=selected_model,
                        api_key=eff_key,
                        style_prompt=style_prompt,
                    )
                    durations = estimate_slide_durations_from_single_wav(wav_bytes, slide_scripts)
            else:
                wav_chunks = []
                for idx, sc in enumerate(slide_scripts, 1):
                    with st.spinner(f"슬라이드 {idx}/4 음성 생성 중... ({selected_voice})"):
                        wb, meta = generate_tts_audio(
                            text=sc,
                            voice=selected_voice,
                            model=selected_model,
                            api_key=eff_key,
                            style_prompt=style_prompt,
                        )
                        wav_chunks.append(wb)
                wav_bytes, durations = concat_wav_files(wav_chunks, pause_sec=0.3)
                meta["duration_seconds"] = round(sum(durations), 2)

            elapsed_tts = round(time.time() - start_t, 2)
            meta["elapsed_seconds"] = elapsed_tts
            st.session_state.audio_bytes = wav_bytes
            st.session_state.audio_metadata = meta
            st.session_state.slide_durations = durations

            # WAV 파일 output 폴더에 자동 저장
            proj_name = st.session_state.clip_data.get("project_name", "naver_clip")
            os.makedirs("output", exist_ok=True)
            wav_out_path = os.path.join("output", f"{proj_name}_voice_{selected_voice}.wav")
            with open(wav_out_path, "wb") as wf:
                wf.write(wav_bytes)

            # 대본 텍스트 파일 저장
            script_out_path = os.path.join("output", f"{proj_name}_script.txt")
            with open(script_out_path, "w", encoding="utf-8") as sf:
                sf.write(full_script_text)

            st.success(f"✅ 음성 생성 완료! (총 길이: {meta.get('duration_seconds')}초 / 소요 시간: {elapsed_tts}초)")

            if btn_tts_and_mp4:
                with st.spinner("슬라이드 4장과 음성을 싱크하여 1080×1920 MP4 동영상을 인코딩하는 중입니다..."):
                    bgm_temp_path = None
                    if uploaded_bgm is not None:
                        bgm_temp_path = os.path.join("output", f"_temp_bgm_{uploaded_bgm.name}")
                        with open(bgm_temp_path, "wb") as bf:
                            bf.write(uploaded_bgm.getbuffer())

                    mp4_out = os.path.join("output", f"{proj_name}_final_clip.mp4")
                    create_shortform_mp4(
                        slide_paths=st.session_state.slide_paths,
                        wav_path=wav_out_path,
                        durations=durations,
                        output_mp4_path=mp4_out,
                        use_fade=use_fade,
                        bgm_path=bgm_temp_path,
                        bgm_volume=bgm_vol,
                    )
                    st.session_state.mp4_path = mp4_out
                st.success(f"🎉 네이버 클립용 MP4 동영상 제작 완료! ({mp4_out})")

        except TTSError as e:
            st.error(f"⚠️ {str(e)}")
        except Exception as e:
            st.error(f"⚠️ 오류 발생: {str(e)}")

with tab_wav_upload:
    st.info(
        "💡 **이미 `TEST11 (Gemini Flash TTS)`에서 뽑아두신 WAV 파일이 있으신가요?**\n"
        "아래에 WAV 파일을 올리시면 API를 다시 호출하지 않고 **무음 구간과 대본 길이를 자동 분석해 2초 만에 MP4 영상**으로 만들어 드립니다!"
    )
    uploaded_wav = st.file_uploader("기존 WAV 오디오 파일 업로드", type=["wav"])
    if uploaded_wav is not None:
        raw_wav = uploaded_wav.getvalue()
        total_wav_sec = get_wav_duration(raw_wav)
        auto_durs = estimate_slide_durations_from_single_wav(raw_wav, slide_scripts)
        st.caption(f"업로드된 WAV 총 재생 시간: **{total_wav_sec}초** → 자동 감지된 슬라이드 전환 시간: `{auto_durs}` 초")

        if st.button("🎬 업로드한 WAV 파일로 즉시 MP4 동영상 합성하기", type="primary", use_container_width=True):
            try:
                proj_name = st.session_state.clip_data.get("project_name", "naver_clip")
                os.makedirs("output", exist_ok=True)
                wav_out_path = os.path.join("output", f"{proj_name}_uploaded_voice.wav")
                with open(wav_out_path, "wb") as wf:
                    wf.write(raw_wav)

                st.session_state.audio_bytes = raw_wav
                st.session_state.audio_metadata = {
                    "voice": "Uploaded WAV",
                    "model": "Local File",
                    "duration_seconds": total_wav_sec
                }
                st.session_state.slide_durations = auto_durs

                bgm_temp_path = None
                if uploaded_bgm is not None:
                    bgm_temp_path = os.path.join("output", f"_temp_bgm_{uploaded_bgm.name}")
                    with open(bgm_temp_path, "wb") as bf:
                        bf.write(uploaded_bgm.getbuffer())

                mp4_out = os.path.join("output", f"{proj_name}_final_clip.mp4")
                with st.spinner("1080×1920 MP4 동영상을 고속 합성하는 중입니다..."):
                    create_shortform_mp4(
                        slide_paths=st.session_state.slide_paths,
                        wav_path=wav_out_path,
                        durations=auto_durs,
                        output_mp4_path=mp4_out,
                        use_fade=use_fade,
                        bgm_path=bgm_temp_path,
                        bgm_volume=bgm_vol,
                    )
                    st.session_state.mp4_path = mp4_out
                st.success(f"🎉 업로드된 WAV로 MP4 동영상 제작 완료! ({mp4_out})")
            except Exception as e:
                st.error(f"MP4 합성 오류: {e}")


# ==============================================================================
# STEP 4. 생성된 오디오 & MP4 동영상 확인 및 구간 타이밍 미세조정
# ==============================================================================
if st.session_state.audio_bytes is not None or (st.session_state.mp4_path and os.path.exists(st.session_state.mp4_path)):
    st.markdown("---")
    st.subheader("🎧 최종 결과물 재생 및 다운로드")

    res_col1, res_col2 = st.columns([1.2, 1])

    with res_col1:
        if st.session_state.audio_bytes is not None:
            st.markdown("#### 🔊 나레이션 오디오 (WAV)")
            st.audio(st.session_state.audio_bytes, format="audio/wav")
            meta = st.session_state.audio_metadata or {}
            size_kb = round(len(st.session_state.audio_bytes) / 1024, 1)
            st.info(
                f"**화자**: `{meta.get('voice', 'Kore')}` | **모델**: `{meta.get('model', '')}` | "
                f"**총 길이**: `{meta.get('duration_seconds', 0)}초` | **크기**: {size_kb} KB"
            )
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                label="💾 WAV 음성 파일 다운로드",
                data=st.session_state.audio_bytes,
                file_name=f"{st.session_state.clip_data.get('project_name', 'clip')}_{timestamp}.wav",
                mime="audio/wav",
                use_container_width=True,
            )

            # 슬라이드별 재생 시간 미세 조정기
            st.markdown("#### ⏱️ 슬라이드별 화면 표시 시간 미세 조정 (초)")
            st.caption("음성 무음 구간을 기준으로 자동 계산된 시간입니다. 원하시면 숫자를 조절한 뒤 [MP4 다시 인코딩]을 누르세요.")
            d_cols = st.columns(4)
            new_durs = []
            for i in range(4):
                cur_d = st.session_state.slide_durations[i] if i < len(st.session_state.slide_durations) else 8.0
                with d_cols[i]:
                    nd = st.number_input(f"슬라이드 {i+1} (초)", min_value=1.0, max_value=60.0, value=float(cur_d), step=0.2, key=f"dur_adj_{i}_{ver}")
                    new_durs.append(nd)

            if st.button("🔄 조정한 시간으로 MP4 영상 다시 인코딩 (2초 소요)", use_container_width=True):
                proj_name = st.session_state.clip_data.get("project_name", "naver_clip")
                os.makedirs("output", exist_ok=True)
                wav_tmp = os.path.join("output", f"{proj_name}_temp_sync.wav")
                with open(wav_tmp, "wb") as wf:
                    wf.write(st.session_state.audio_bytes)
                mp4_out = os.path.join("output", f"{proj_name}_final_clip.mp4")
                with st.spinner("조정된 타이밍으로 MP4를 다시 인코딩 중입니다..."):
                    create_shortform_mp4(
                        slide_paths=st.session_state.slide_paths,
                        wav_path=wav_tmp,
                        durations=new_durs,
                        output_mp4_path=mp4_out,
                        use_fade=use_fade,
                    )
                    st.session_state.slide_durations = new_durs
                    st.session_state.mp4_path = mp4_out
                st.success("✅ 타이밍 재조정 완료!")
                st.rerun()

    with res_col2:
        if st.session_state.mp4_path and os.path.exists(st.session_state.mp4_path):
            st.markdown("#### 📱 완성된 네이버 클립 숏폼 영상 (9:16 MP4)")
            with open(st.session_state.mp4_path, "rb") as vf:
                mp4_bytes = vf.read()
            st.video(mp4_bytes)
            st.download_button(
                label=f"🎬 완성본 MP4 동영상 다운로드 ({os.path.basename(st.session_state.mp4_path)})",
                data=mp4_bytes,
                file_name=os.path.basename(st.session_state.mp4_path),
                mime="video/mp4",
                type="primary",
                use_container_width=True,
            )
