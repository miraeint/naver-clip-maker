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
from io import BytesIO
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
import requests
from PIL import Image
from google import genai


INDUSTRIAL_STOCK_LIBRARY: Dict[str, List[str]] = {
    "digital_twin": [
        "https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1200&q=80",
    ],
    "automation_robot": [
        "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?auto=format&fit=crop&w=1200&q=80",
    ],
    "control_dashboard": [
        "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1504868584819-f8e8b4b6d7e3?auto=format&fit=crop&w=1200&q=80",
    ],
    "pcb_circuit": [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=1200&q=80",
    ],
    "factory_plant": [
        "https://images.unsplash.com/photo-1581092580497-e0d23cbdf1dc?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=1200&q=80",
    ],
    "engineering_team": [
        "https://images.unsplash.com/photo-1531482615713-2afd69097998?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=1200&q=80",
    ],
}


def detect_industrial_category(context_text: str) -> str:
    text = (context_text or "").lower()
    if any(k in text for k in ["트윈", "시뮬레이션", "가상", "디지털", "twin", "simulation"]):
        return "digital_twin"
    if any(k in text for k in ["로봇", "자동화", "컨베이어", "공정", "조립", "robot", "automation"]):
        return "automation_robot"
    if any(k in text for k in ["모니터", "데이터", "대시보드", "관제", "mes", "erp", "분석", "dashboard"]):
        return "control_dashboard"
    if any(k in text for k in ["회로", "기판", "반도체", "pcb", "센서", "전자", "circuit"]):
        return "pcb_circuit"
    if any(k in text for k in ["팀", "컨설팅", "지원사업", "선정", "회의", "전략", "정부", "도입", "상담"]):
        return "engineering_team"
    return "factory_plant"


def fetch_smart_stock_photo(
    context_text: str,
    output_path: str,
    width: int = 970,
    height: int = 600,
    seed_idx: int = 0
) -> str:
    """
    초고화질 실사 산업/제조 스톡 사진(Unsplash 정품)을 주제에 맞춰 매칭 및 리사이징하여 저장합니다.
    만화/인형/왜곡 없이 실제 100% 사실적인 산업 현장 사진을 보장합니다.
    """
    cat = detect_industrial_category(context_text)
    urls = INDUSTRIAL_STOCK_LIBRARY.get(cat, INDUSTRIAL_STOCK_LIBRARY["factory_plant"])
    chosen_url = urls[seed_idx % len(urls)]

    try:
        resp = requests.get(chosen_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if resp.status_code == 200 and len(resp.content) > 10000:
            img = Image.open(BytesIO(resp.content)).convert("RGB")
            # 비율에 맞게 센터 크롭 후 리사이징
            target_ratio = width / height
            orig_ratio = img.width / img.height
            if orig_ratio > target_ratio:
                new_w = int(img.height * target_ratio)
                off = (img.width - new_w) // 2
                img = img.crop((off, 0, off + new_w, img.height))
            else:
                new_h = int(img.width / target_ratio)
                off = (img.height - new_h) // 2
                img = img.crop((0, off, img.width, off + new_h))
            img = img.resize((width, height), Image.Resampling.LANCZOS)
            os.makedirs(os.path.dirname(output_path) or "images", exist_ok=True)
            img.save(output_path, "JPEG", quality=92)
            return output_path
    except Exception as e:
        print(f"Stock fetch error ({cat}): {e}")

    return output_path


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

    # 기존 블로그 사진들과 톤앤매너 일치 및 만화/애니메이션/피규어 철저 배제
    style_anchor = (
        "Professional industrial DSLR documentary photograph, authentic modern smart manufacturing plant, "
        "industrial automation line, control room with dual monitors displaying digital twin simulation and 3D modeling, "
        "bright cool-white fluorescent lighting, natural color balance, deep focus, ultra crisp 8k photorealistic. "
        "Strictly avoid: NO anime, NO cartoon, NO 3d doll, NO figure, NO comic, NO illustration, NO CGI drawing, NO fake characters"
    )
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
   - 만화(anime), 카툰, 피규어/인형, 3D 애니메이션 스타일은 절대로 나오지 않아야 합니다.
   - 인물 중심보다는 '실제 공장 자동화 라인, 산업용 로봇, 제어실 모니터 시뮬레이션 화면, 설비 배치 3D 디지털 트윈 화면, 정밀 설비 가동 모습' 등 전문적이고 신뢰감 있는 실제 산업 다큐멘터리 사진(Professional real-world DSLR photo)으로 프롬프트를 작성하세요.
   - 시각적 결(톤앤매너): 밝고 선명한 쿨화이트 산업용 조명, 깊고 선명한 초점, 실제 제조 설비 및 엔지니어링 환경.

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

    # 슬라이드 1: 블로그 1번 사진 우선, 없으면 대본 맞춤 실사 스톡 사진 매칭
    if len(imgs) > 0 and os.path.exists(imgs[0]):
        bg_img = imgs[0]
    else:
        ctx1 = f"{plan.slide_1.title} {plan.slide_1.subtitle} {plan.slide_1.narration}"
        stock_path_1 = "images/stock_slide_1_bg.jpg"
        fetch_smart_stock_photo(ctx1, stock_path_1, width=1080, height=1920, seed_idx=0)
        bg_img = stock_path_1 if os.path.exists(stock_path_1) else "images/slide1_bg.jpg"

    # 슬라이드 2: 블로그 2번 사진 우선, 없으면 대본 맞춤 실사 스톡 사진 매칭
    if len(imgs) > 1 and os.path.exists(imgs[1]):
        p1_img = imgs[1]
    else:
        ctx2 = f"{plan.slide_2.title} {plan.slide_2.subtitle} {plan.slide_2.narration}"
        stock_path_2 = "images/stock_slide_2.jpg"
        fetch_smart_stock_photo(ctx2, stock_path_2, width=970, height=600, seed_idx=1)
        p1_img = stock_path_2 if os.path.exists(stock_path_2) else "images/photo_1.png"

    # 슬라이드 3: 블로그 3번 사진 우선, 없으면 대본 맞춤 실사 스톡 사진 매칭
    if len(imgs) > 2 and os.path.exists(imgs[2]):
        p2_img = imgs[2]
    else:
        ctx3 = f"{plan.slide_3.title} {plan.slide_3.subtitle} {plan.slide_3.narration}"
        stock_path_3 = "images/stock_slide_3.jpg"
        fetch_smart_stock_photo(ctx3, stock_path_3, width=970, height=600, seed_idx=2)
        p2_img = stock_path_3 if os.path.exists(stock_path_3) else "images/photo_2.png"

    # 슬라이드 4: 블로그 4번 사진 우선, 없으면 대본 맞춤 실사 스톡 사진 매칭
    if len(imgs) > 3 and os.path.exists(imgs[3]):
        p3_img = imgs[3]
    else:
        ctx4 = f"{plan.slide_4.title} {plan.slide_4.subtitle} {plan.slide_4.narration}"
        stock_path_4 = "images/stock_slide_4.jpg"
        fetch_smart_stock_photo(ctx4, stock_path_4, width=970, height=600, seed_idx=3)
        p3_img = stock_path_4 if os.path.exists(stock_path_4) else (imgs[0] if len(imgs) > 0 else "images/photo_3.png")

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
