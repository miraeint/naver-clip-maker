# Streamlit Cloud Entry Point
import os
import sys

# app.py 실행
app_path = os.path.join(os.path.dirname(__file__), "app.py")
with open(app_path, "r", encoding="utf-8") as f:
    code = f.read()
exec(compile(code, app_path, "exec"), globals())
