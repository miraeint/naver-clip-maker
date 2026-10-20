@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Naver Clip 4-Slide Quick Renderer
echo ======================================================
echo    data.json 기반 1080x1920 슬라이드 4장 + ZIP 즉시 생성
echo ======================================================
echo.
.\.venv\Scripts\python.exe make_clip_slides.py
echo.
echo [완료] output 폴더를 엽니다...
explorer output
pause
