"""
네이버 블로그 본문 텍스트 및 원본 이미지 자동 추출기
- 네이버 블로그 URL을 모바일 뷰(m.blog.naver.com)로 자동 우회 접속
- 본문 텍스트, 제목, 본문 내 고해상도 이미지 자동 다운로드 지원
"""

import os
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import Dict, List, Tuple, Optional
import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; SM-S918N) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Mobile Safari/537.36"
    ),
    "Referer": "https://m.blog.naver.com/",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def normalize_naver_blog_url(url: str) -> str:
    """
    일반 네이버 블로그 URL(blog.naver.com/...)을 크롤링이 용이한 m.blog.naver.com 주소로 변환합니다.
    """
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    if "blogId" in qs and "logNo" in qs:
        blog_id = qs["blogId"][0]
        log_no = qs["logNo"][0]
        return f"https://m.blog.naver.com/{blog_id}/{log_no}"

    if "blog.naver.com" in parsed.netloc and not parsed.netloc.startswith("m."):
        return url.replace("://blog.naver.com", "://m.blog.naver.com", 1)

    return url


def upgrade_naver_img_url(img_url: str) -> str:
    """
    네이버 블로그 썸네일 이미지 파라미터(?type=w80 등)를 고화질(w966)로 변환합니다.
    """
    if "pstatic.net" not in img_url and "naver.net" not in img_url:
        return img_url
    parsed = urlparse(img_url)
    qs = parse_qs(parsed.query)
    if "type" in qs:
        qs["type"] = ["w966"]
        new_query = urlencode(qs, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    return img_url


def fetch_naver_blog(url: str, save_img_dir: str = "images/blog") -> Dict:
    """
    네이버 블로그 URL에서 제목, 본문 텍스트, 고화질 이미지 파일들을 추출하고 다운로드합니다.
    """
    mobile_url = normalize_naver_blog_url(url)
    resp = requests.get(mobile_url, headers=HEADERS, timeout=12)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # 1. 제목 추출
    title_el = (
        soup.select_one(".se-title-text")
        or soup.select_one(".tit_h3")
        or soup.find("meta", property="og:title")
    )
    if title_el:
        if title_el.name == "meta":
            title = title_el.get("content", "").strip()
        else:
            title = title_el.get_text(" ", strip=True)
    else:
        title = "네이버 블로그 포스트"

    # 2. 본문 추출 (SmartEditor ONE 및 구버전 에디터 모두 대응)
    container = (
        soup.select_one(".se-main-container")
        or soup.select_one("#viewTypeSelector")
        or soup.select_one(".post_ct")
        or soup.body
    )

    paragraphs = []
    if container:
        text_nodes = container.select(".se-text-paragraph")
        if text_nodes:
            for p in text_nodes:
                t = p.get_text(" ", strip=True)
                if t:
                    paragraphs.append(t)
        else:
            raw_text = container.get_text("\n", strip=True)
            paragraphs = [line.strip() for line in raw_text.splitlines() if line.strip()]

    body_text = "\n".join(paragraphs)

    # 3. 본문 내 이미지 추출 및 다운로드
    os.makedirs(save_img_dir, exist_ok=True)
    img_urls = []
    if container:
        for img in container.select("img"):
            src = img.get("data-lazy-src") or img.get("src") or ""
            if not src:
                continue
            # 스티커, 아이콘, 프로필 등 제외
            if any(skip in src for skip in ["sticker", "profile", "icon", "spc.gif", "blank.gif", "storep"]):
                continue
            if "postfiles.pstatic.net" in src or "blogfiles.pstatic.net" in src or "mblogthumb" in src:
                hi_src = upgrade_naver_img_url(src)
                if hi_src not in img_urls:
                    img_urls.append(hi_src)

    downloaded_images = []
    for idx, i_url in enumerate(img_urls[:12], 1):
        try:
            img_resp = requests.get(i_url, headers=HEADERS, timeout=10)
            if img_resp.status_code == 200 and len(img_resp.content) > 5000:
                ext = ".png" if b"PNG" in img_resp.content[:16] else ".jpg"
                local_path = os.path.join(save_img_dir, f"blog_img_{idx}{ext}").replace("\\", "/")
                with open(local_path, "wb") as f:
                    f.write(img_resp.content)
                downloaded_images.append(local_path)
        except Exception:
            continue

    return {
        "url": mobile_url,
        "title": title,
        "body_text": body_text,
        "downloaded_images": downloaded_images,
    }
