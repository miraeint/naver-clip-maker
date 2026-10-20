@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Naver Clip All-in-One Studio
cls
echo ======================================================
echo    네이버 클립 숏폼 올인원 스튜디오 (슬라이드 + TTS + MP4)
echo ======================================================
echo.
echo [INFO] 웹 스튜디오 서버를 시작합니다...
echo [INFO] 잠시 후 브라우저에서 자동으로 화면이 열립니다.
echo [INFO] 종료하려면 이 창을 닫거나 Ctrl+C를 누르세요.
echo.

.\.venv\Scripts\streamlit.exe run app.py
pause
