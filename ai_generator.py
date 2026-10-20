"""
Gemini AI 기반 네이버 클립 4컷 슬라이드 기획 & 30초 나레이션 대본 자동 생성기
- 블로그 본문 텍스트를 분석하여 data.json 규격의 4컷 슬라이드 데이터와 슬라이드별 나레이션 대본을 한 번에 생성
"""

import os
import time
import json
import urllib.request
import urllib.parse
from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from google import genai


def generate_ai_image(
    prompt: str,
    width: int = 970,
    height: int = 600,
    output_path: Optional[str] = None
) -> str:
    """
    슬라이드 나레이션/상황에 맞춘 인물 및 장면 이미지를 실제 제조 현장 사진 톤에 맞춰 선명하게 생성합니다.
    """
    os.makedirs("images", exist_ok=True)
    if not output_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        output_path = f"images/ai_gen_{ts}.jpg"

    # 기존 블로그 사진들과 톤앤매너(쿨화이트 형광등 조명, 선명한 초점, 한국 현장 유니폼) 일치
    style_anchor = "Sharp DSLR documentary photo, clean modern Korean manufacturing factory, bright cool-white fluorescent lighting, natural color balance, deep focus, sharp details, Korean engineers in uniform"
    refined_prompt = f"{style_anchor}, {prompt.strip()}"
    encoded_prompt = urllib.parse.quote(refined_prompt)
    seed = int(time.time() * 1000) % 100000
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&model=flux&nologo=true&seed={seed}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=40) as resp, open(output_path, "wb") as f:
        f.write(resp.read())
    return output_path


class Slide1Spec(BaseModel):
    badge: str = Field(description="상단 배지 텍스트 (예: [30초 스마트공장 지식])")
    title: str = Field(description="강렬한 후킹 메인 타이틀 (줄바꿈 \\n 포함 2줄 이내, 줄당 14자 이내)")
    subtitle: str = Field(description="서브 타이틀 (22자 이내)")
    card_badge: str = Field(description="하단 카드 배지 (예: [ 핵심 체크 ])")
    bullets: List[List[str]] = Field(
        description="4개의 불릿 리스트. 각 항목은 ['▶ ', '핵심 문장(22자 이내)'] 또는 ['• ', '핵심 문장'] 형식의 2원소 리스트"
    )
    cta: str = Field(description="하단 유도 문구 (예: ▼ 30초 만에 핵심 개념 완벽 정리 시작)")
    narration: str = Field(description="1번 슬라이드가 나오는 동안 읽을 나레이션 대본 (약 7~9초 분량, 60~80자 내외)")
    image_prompt: str = Field(
        default="Photorealistic vertical cinematic shot of modern smart factory with robotic arms, blue ambient lighting, 8k",
        description="1번 슬라이드 주제와 대본에 어울리는 9:16 세로 인물 또는 현장 장면 이미지 생성용 상세 영문 프롬프트"
    )


class StandardSlideSpec(BaseModel):
    badge: str = Field(description="상단 배지 (예: [핵심 개념], [현장 실무 사례], [실무 팁])")
    title: str = Field(description="슬라이드 핵심 제목 (18자 이내)")
    subtitle: str = Field(description="부제목 또는 영문/보조 설명 (26자 이내)")
    highlight_color: List[int] = Field(description="강조 RGB 색상 배열 3원소 (예: [56, 189, 248], [52, 211, 153], [251, 191, 36])")
    card_badge: str = Field(description="하단 카드 소제목 배지 (예: [ 핵심 정의와 역할 ])")
    bullets: List[List[str]] = Field(
        description="3개의 불릿 항목. 각 항목은 ['▶ ', '소제목(16자 이내)', '• 상세 설명(24자 이내)'] 형식의 3원소 문자열 리스트"
    )
    cta: str = Field(description="하단 요약 또는 블로그 링크 유도 문구 (25자 이내)")
    narration: str = Field(description="이 슬라이드가 나오는 동안 읽을 나레이션 대본 (약 7~10초 분량, 65~85자 내외)")
    image_prompt: str = Field(
        default="Photorealistic shot of Korean engineers working in smart manufacturing plant, cinematic lighting, 8k",
        description="이 슬라이드의 핵심 내용과 나레이션 대본에 어울리는 16:9 가로 인물 또는 현장 상황 장면 이미지 생성용 상세 영문 프롬프트"
    )


class ClipPlanResponse(BaseModel):
    project_name: str = Field(description="영문 소문자 및 언더스코어로 된 짧은 프로젝트 이름 (예: spc_clip, mes_guide)")
    slide_1: Slide1Spec
    slide_2: StandardSlideSpec
    slide_3: StandardSlideSpec
    slide_4: StandardSlideSpec


def generate_clip_plan_from_blog(
    blog_text: str,
    api_key: Optional[str] = None,
    downloaded_images: Optional[List[str]] = None
) -> Dict:
    """
    블로그 본문을 바탕으로 네이버 클립 4컷 슬라이드 설정(data.json 구조) 및 30초 대본을 생성합니다.
    """
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("Gemini API Key가 필요합니다. 좌측 사이드바에 API Key를 입력해주세요.")

    client = genai.Client(api_key=key)

    prompt = f"""
당신은 제조/스마트공장/비즈니스 분야의 네이버 클립(9:16 숏폼) 전문 콘텐츠 디렉터입니다.
아래 블로그 본문 내용을 바탕으로 30~40초 분량의 네이버 클립 4컷 슬라이드 구성안과 각 컷별 나레이션 대본을 작성하세요.

[작성 규칙]
1. 1컷(slide_1): 시청자의 스크롤을 멈추게 하는 문제 제기 및 공감 후킹 (type: vertical_bg)
   - bullets는 정확히 4개 항목이며, 각 항목은 ["▶ ", "내용"] 또는 ["• ", "내용"] 형태의 길이 2짜리 배열이어야 합니다.
2. 2컷(slide_2): 핵심 개념 및 원리 정의 (highlight_color: [56, 189, 248])
   - bullets는 정확히 3개 항목이며, 각 항목은 ["▶ ", "핵심 키워드", "• 부연 설명"] 형태의 길이 3짜리 배열이어야 합니다.
3. 3컷(slide_3): 실제 현장 사례 및 도입 효과 (highlight_color: [52, 211, 153])
   - bullets는 정확히 3개 항목이며, 각 항목은 ["1. ", "핵심 효과", "• 구체적 설명"] 형태의 길이 3짜리 배열이어야 합니다.
4. 4컷(slide_4): 실무 적용 팁 3가지 및 하단 블로그 링크 유도 (highlight_color: [251, 191, 36])
   - bullets는 정확히 3개 항목이며, 각 항목은 ["▶ ", "체크 포인트", "• 실무 가이드"] 형태의 길이 3짜리 배열이어야 합니다.
   - 마지막 4컷의 narration 끝에는 항상 하단 블로그 링크 클릭을 유도하는 멘트를 포함하세요.
5. 각 텍스트는 모바일 세로 화면(1080x1920) 카드 안에 깔끔하게 들어가도록 간결하고 임팩트 있게 작성하세요.
6. image_prompt 작성 규칙 (슬라이드별 주제 100% 동적 맞춤):
   - 고정된 장면이 아니라, 각 슬라이드의 메인 제목(title), 서브 제목(subtitle), 대본(narration)의 핵심 주제와 키워드를 1:1로 반영하여 매번 완전히 새로운 장면 프롬프트를 작성하세요.
   - 휑하고 의미 없는 빈 복도나 빈 창고(empty warehouse/corridor)를 절대 묘사하지 말고, 해당 슬라이드의 주제(예: ERP 전산 입력, 품질 검사, 장비 가공, 안전 점검, 실무 회의 등)에 맞는 구체적인 행동을 수행하는 단정한 한국인 전문가 또는 설비 가동 장면을 묘사하세요.
   - 시각적 결(톤앤매너): 밝고 선명한 쿨화이트 조명(bright cool-white industrial lighting), 깊고 선명한 초점(deep focus, sharp details), 단정한 복장의 한국인 전문가, 사실적인 다큐멘터리 사진 스타일 (노란색 빈티지 필터, 과도한 보케, 텍스트/도표 그래픽 금지).

[블로그 본문 내용]
{blog_text[:8000]}
"""

    models_to_try = [
        "gemini-3.8-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-4-argon",
    ]

    last_err = None
    plan = None

    for m in models_to_try:
        for attempt in range(2):
            try:
                interaction = client.interactions.create(
                    model=m,
                    input=prompt,
                    response_format={
                        "type": "text",
                        "mime_type": "application/json",
                        "schema": ClipPlanResponse.model_json_schema()
                    }
                )
                plan = ClipPlanResponse.model_validate_json(interaction.output_text)
                break
            except Exception as e:
                last_err = e
                err_str = str(e).lower()
                if "503" in err_str or "high demand" in err_str or "unavailable" in err_str or "429" in err_str:
                    time.sleep(1.5)
                    continue
                else:
                    break
        if plan is not None:
            break

    if plan is None:
        raise RuntimeError(f"모든 AI 모델 연결 시도 실패 (마지막 오류: {last_err})")

    imgs = downloaded_images or []

    # 슬라이드 1: 블로그 1번 사진 우선, 없으면 AI 세로 이미지 생성
    if len(imgs) > 0 and os.path.exists(imgs[0]):
        bg_img = imgs[0]
    else:
        try:
            p_p = plan.slide_1.image_prompt or "Photorealistic vertical shot of modern smart factory automation, 8k"
            bg_img = generate_ai_image(p_p, width=1080, height=1920, output_path="images/ai_slide_1_bg.jpg")
        except Exception:
            bg_img = "images/slide1_bg.jpg"

    # 슬라이드 2: 블로그 2번 사진 우선, 없으면 AI 맞춤 이미지 생성
    if len(imgs) > 1 and os.path.exists(imgs[1]):
        p1_img = imgs[1]
    else:
        try:
            p_p = plan.slide_2.image_prompt or "Photorealistic shot of Korean engineers working in smart manufacturing plant, 8k"
            p1_img = generate_ai_image(p_p, width=970, height=600, output_path="images/ai_slide_2.jpg")
        except Exception:
            p1_img = "images/photo_1.png"

    # 슬라이드 3: 블로그 3번 사진 우선, 없으면 AI 맞춤 이미지 생성
    if len(imgs) > 2 and os.path.exists(imgs[2]):
        p2_img = imgs[2]
    else:
        try:
            p_p = plan.slide_3.image_prompt or "Photorealistic shot of modern manufacturing equipment and automation line, 8k"
            p2_img = generate_ai_image(p_p, width=970, height=600, output_path="images/ai_slide_3.jpg")
        except Exception:
            p2_img = "images/photo_2.png"

    # 슬라이드 4: 블로그 4번 사진이 있으면 사용, 없으면 1번 사진을 재탕하지 않고 대본에 맞춰 AI로 새 인물/장면을 즉시 생성!
    if len(imgs) > 3 and os.path.exists(imgs[3]):
        p3_img = imgs[3]
    else:
        try:
            p_p = plan.slide_4.image_prompt or "Photorealistic shot of Korean factory team reviewing quality management checklist, 8k"
            p3_img = generate_ai_image(p_p, width=970, height=600, output_path="images/ai_slide_4.jpg")
        except Exception:
            p3_img = imgs[0] if len(imgs) > 0 else "images/photo_3.png"

    data_dict = {
        "project_name": plan.project_name or "clip_project",
        "font_bold": "font/bold.ttf",
        "font_regular": "font/regular.ttf",
        "slides": [
            {
                "type": "vertical_bg",
                "bg_image": bg_img,
                "badge": plan.slide_1.badge,
                "title": plan.slide_1.title,
                "subtitle": plan.slide_1.subtitle,
                "card_badge": plan.slide_1.card_badge,
                "bullets": plan.slide_1.bullets,
                "cta": plan.slide_1.cta,
                "narration": plan.slide_1.narration,
                "image_prompt": plan.slide_1.image_prompt,
            },
            {
                "type": "standard_card",
                "photo": p1_img,
                "badge": plan.slide_2.badge,
                "title": plan.slide_2.title,
                "subtitle": plan.slide_2.subtitle,
                "highlight_color": plan.slide_2.highlight_color,
                "card_badge": plan.slide_2.card_badge,
                "bullets": plan.slide_2.bullets,
                "cta": plan.slide_2.cta,
                "narration": plan.slide_2.narration,
                "image_prompt": plan.slide_2.image_prompt,
            },
            {
                "type": "standard_card",
                "photo": p2_img,
                "badge": plan.slide_3.badge,
                "title": plan.slide_3.title,
                "subtitle": plan.slide_3.subtitle,
                "highlight_color": plan.slide_3.highlight_color,
                "card_badge": plan.slide_3.card_badge,
                "bullets": plan.slide_3.bullets,
                "cta": plan.slide_3.cta,
                "narration": plan.slide_3.narration,
                "image_prompt": plan.slide_3.image_prompt,
            },
            {
                "type": "standard_card",
                "photo": p3_img,
                "badge": plan.slide_4.badge,
                "title": plan.slide_4.title,
                "subtitle": plan.slide_4.subtitle,
                "highlight_color": plan.slide_4.highlight_color,
                "card_badge": plan.slide_4.card_badge,
                "bullets": plan.slide_4.bullets,
                "cta": plan.slide_4.cta,
                "narration": plan.slide_4.narration,
                "image_prompt": plan.slide_4.image_prompt,
            },
        ]
    }
    return data_dict
