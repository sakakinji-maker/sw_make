"""환경 변수 설정을 한곳에서 읽는다."""

import os

from dotenv import load_dotenv

load_dotenv()

# mock(개발·테스트) | gemini(팀 결정, 11/10) | claude | openai
AI_PROVIDER = os.getenv("AI_PROVIDER", "mock")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "")
AI_TIMEOUT = float(os.getenv("AI_TIMEOUT", "30"))
AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "2"))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app/db/app.db")

# 문자 알림 (예약·문의). mock(기본값, 실제 발송 안 함) | solapi(쿨SMS)
SMS_PROVIDER = os.getenv("SMS_PROVIDER", "mock")
SMS_API_KEY = os.getenv("SMS_API_KEY", "")
SMS_API_SECRET = os.getenv("SMS_API_SECRET", "")
SMS_SENDER = os.getenv("SMS_SENDER", "")  # 쿨SMS에 등록·인증한 발신번호
SMS_OWNER_PHONE = os.getenv("SMS_OWNER_PHONE", "")  # 점주 알림을 받을 휴대폰 번호
