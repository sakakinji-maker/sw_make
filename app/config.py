"""환경 변수 설정을 한곳에서 읽는다."""

import os

from dotenv import load_dotenv

load_dotenv()

AI_PROVIDER = os.getenv("AI_PROVIDER", "mock")
AI_API_KEY = os.getenv("AI_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app/db/app.db")
