# 소상공인용 AI 마케팅·고객응대 통합 지원 시스템

> 융합SW모델설계 PBL 과제 1 · 2026학년도 2학기 · 팀 **신창섭** (한재형 · 전지호 · 정회성)

소상공인 점주가 **예약·문의·홍보** 업무를 한 화면에서 처리하고, 생성형 AI로 답변과 홍보 문구 작성 부담을 줄이는 웹 시스템입니다. AI는 초안만 만들고, 최종 확정은 항상 점주가 합니다. 시연용 매장은 가상의 카페 **브루밍 카페**입니다.

- **GitHub 저장소**: https://github.com/sakakinji-maker/sw_make
- **최종 제출 버전**: `main` 브랜치 (태그 `v1.0-final`)
- **수행 기간**: 10주차(10/27) ~ 14주차(12/7 제출), 12/8 최종 발표

## 목차

1. [팀원과 역할](#팀원과-역할)
2. [주요 기능](#주요-기능)
3. [기술 스택](#기술-스택)
4. [실행 방법](#실행-방법)
5. [환경 설정 (.env)](#환경-설정-env)
6. [가상 데이터](#가상-데이터)
7. [테스트](#테스트)
8. [설계와 디자인 패턴](#설계와-디자인-패턴)
9. [AI 활용과 검증 장치](#ai-활용과-검증-장치)
10. [폴더 구조](#폴더-구조)
11. [산출물 위치](#산출물-위치)
12. [알려진 한계](#알려진-한계)
13. [협업 규칙](#협업-규칙)

## 팀원과 역할

| 이름 | GitHub | 역할 | 담당 기능 | 디자인 패턴 |
| --- | --- | --- | --- | --- |
| 한재형 | `jhhan1404` | PM | F-01 매장·메뉴 관리, F-02 마무리·통합, 문자 알림, 화면 개편 | State |
| 전지호 | `jeonjiho5219` | 설계 | F-04 채널별 AI 홍보 문구, F-05 대시보드 | Strategy |
| 정회성 | `sakakinji-maker` | 개발·검증 | F-02 예약·고객 관리, F-03 문의 접수·AI 답변 초안, AI 검증 실험 | Adapter |

팀원별 세부 기여는 결과보고서의 "팀원별 기여"에 정리했습니다.

## 주요 기능

### 필수 기능 (MVP)

| ID | 기능 | 화면 |
| --- | --- | --- |
| F-01 | 매장 정보·메뉴(사진 포함)·FAQ 관리 | 점주 `/owner/store` |
| F-02 | 예약 신청·조회·변경·취소, 점주 확정·취소·방문완료·노쇼 처리, 상태 변경 이력 | 고객 `/reservations/new`, `/reservations/lookup` · 점주 `/owner/reservations` |
| F-03 | 문의 접수, AI 답변 초안, 매장 정보 대조(사실 검증), 점주 수정·발송 | 고객 `/inquiries/new`, `/inquiries/lookup` · 점주 `/owner/inquiries` |
| F-04 | 채널별(인스타그램·블로그·문자) AI 홍보 문구 생성, 규칙 검사, 이력 저장 | 점주 `/owner/marketing` |
| F-05 | 대시보드: 오늘 예약 타임라인, 확정 대기·미응답 문의, 앞으로 7일 예약 그래프 | 점주 `/owner` |

### 추가로 구현한 것

- **문자 알림 11종** (SOLAPI): 예약 신청·변경·확정·취소, 새 문의, 답변 등록·수정. 모두 단문(90바이트) 이내
- **노쇼 관리**: 예약 상세의 노쇼 경고, 고객 이력의 단골·노쇼 주의 필터, 이름·번호 뒤 4자리 검색
- **확정 한마디**: 점주가 확정하면서 손님에게 메모를 남기면 손님의 "내 예약" 화면에 표시
- **점주 취소 사유**: 사유를 고르면 손님 문자에 함께 안내
- **발송 전 확인**: 점주가 고친 답변을 보내기 전에 매장 정보와 다시 대조
- **외국어 자동 수정**: AI 결과에 한자·가나가 섞이면 다시 생성하고, 남으면 그 글자만 고치도록 요청
- **예약 날짜 검색**, 대시보드 그래프 막대를 누르면 그날 예약 보기

## 기술 스택

- **백엔드**: Python 3.11 이상, FastAPI, SQLAlchemy 2, SQLite
- **화면**: Jinja2 템플릿, Bootstrap 5, Pretendard 글꼴
- **생성형 AI**: Groq(`qwen/qwen3.8-27b`) 사용, Gemini·Claude·OpenAI도 설정만 바꾸면 사용 가능 (Adapter 패턴)
- **문자**: SOLAPI(쿨SMS) REST API
- **품질**: pytest, ruff, GitHub Actions(CI)

## 실행 방법

자세한 설치 순서(VS Code 기준)는 [Git 가이드](docs/git_guide.md)에 있습니다.

```bash
python -m venv .venv
.venv\Scripts\activate             # Mac: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env             # Mac: cp .env.example .env
python -m app.db.seed --reset      # 가상 데이터 적재 (처음 상태로 되돌릴 때도 사용)
uvicorn app.main:app --reload      # 서버 실행
```

- **고객 화면**: http://127.0.0.1:8000/
- **점주 화면**: http://127.0.0.1:8000/owner
- **API 문서**: http://127.0.0.1:8000/docs

서버를 처음 켤 때 DB가 비어 있으면 가상 데이터가 자동으로 들어갑니다. 이미 데이터가 있으면 그대로 두므로, 처음 상태로 돌리려면 `python -m app.db.seed --reset`을 실행합니다.

다른 PC(예: 발표장)에서 접속해야 하면 서버를 켠 상태에서 터널을 엽니다.

```bash
cloudflared tunnel --url http://localhost:8000
```

## 환경 설정 (.env)

`.env.example`을 복사해 `.env`를 만듭니다. **`.env`는 Git에 올리지 않으며, API 키는 단톡방·코드·문서에 절대 붙여 넣지 않습니다.**

| 항목 | 값 | 설명 |
| --- | --- | --- |
| `AI_PROVIDER` | `mock`(기본) \| `groq` \| `gemini` \| `claude` \| `openai` | `mock`이면 실제 AI를 호출하지 않음 |
| `AI_API_KEY`, `AI_MODEL` | 제공사 콘솔에서 발급 | 실제 AI를 쓸 때만 |
| `SMS_PROVIDER` | `mock`(기본) \| `solapi` | `mock`이면 실제로 보내지 않고 터미널에 `[SMS mock]`만 출력 |
| `SMS_API_KEY`, `SMS_API_SECRET` | SOLAPI 콘솔에서 발급 | 권한은 "메시지 발송 → 문자"만 |
| `SMS_SENDER` | SOLAPI에 등록·인증한 발신번호 | |
| `SMS_OWNER_PHONE` | 점주 알림을 받을 번호 | 새 예약·새 문의 알림 |

**실제 문자 발송 시 주의**: SOLAPI는 API 키에 등록한 **허용 IP**에서 온 요청만 보냅니다. 와이파이를 바꾸면 "내 IP 확인"으로 현재 IP를 확인해 SOLAPI 콘솔에 추가해야 합니다. 설정이 틀려도 예약·문의는 막히지 않고 mock으로 대신합니다.

## 가상 데이터

실제 개인정보는 쓰지 않고, 모두 가상 데이터입니다. 위치: [`app/db/seed_data/`](app/db/seed_data/README.md)

| 파일 | 내용 |
| --- | --- |
| `stores.json` | 브루밍 카페 1곳, 메뉴 12개(음료 8·디저트 4) |
| `faqs.json` | FAQ 20개 |
| `inquiries.json` | 문의 30건 (가격·영업시간·근거 없음 질문 각 10건, AI 검증 실험용 정답 포함) |
| `reservations.json` | 예약 75건. 발표일(12/8) 기준으로 지난 예약·오늘 예약·앞으로 7일 예약을 구성, 단골·노쇼 손님 포함 |

메뉴 사진 12장과 배경 이미지는 **Google Gemini로 생성한 이미지**입니다. 출처는 [`app/presentation/static/menu/README.md`](app/presentation/static/menu/README.md)에 기록했습니다.

## 테스트

```bash
pytest           # 전체 테스트 (313개)
ruff check .     # 린트
ruff format .    # 포맷
```

- 모든 Pull Request에서 GitHub Actions가 `ruff check`, `ruff format --check`, `pytest`를 자동으로 실행합니다.
- 테스트는 실제 AI·문자 API를 호출하지 않습니다(Mock 사용).
- 기능별 정상·예외 테스트 케이스와 결과는 [테스트 케이스 문서](docs/test_cases.md)와 테스트 결과표에 정리했습니다.

## 설계와 디자인 패턴

3계층 구조(프레젠테이션 → 서비스 → 저장소)이며, 서비스는 SQL과 외부 API를 직접 다루지 않습니다.

| 패턴 | 위치 | 무엇이 자주 바뀌는가 | 담당 |
| --- | --- | --- | --- |
| State | `app/services/reservation/states.py` | 예약 정책(상태별 가능한 처리, 새 상태 추가) | 한재형 |
| Strategy | `app/services/marketing/strategies.py` | 홍보 채널 추가, 채널별 길이·해시태그 규칙 | 전지호 |
| Adapter | `app/adapters/ai/`, `app/adapters/sms/` | AI 제공사·모델 변경, 문자 서비스 변경, 테스트용 Mock 전환 | 정회성 (문자: 한재형) |

- 새 홍보 채널은 `strategies.py`에 클래스 하나와 `@register`만 추가하면 됩니다.
- 서비스는 `Notifier`(문자 알림)를 주입받아, 테스트에서는 알림을 끄거나 가짜 발송기로 바꿉니다.
- 설계 문서: [시스템 설계](docs/design/system_design.md) · [클래스 다이어그램](docs/design/class_diagram.md) · [ERD](docs/design/erd.md)

## AI 활용과 검증 장치

| 기능 | AI가 하는 일 | 검증 장치 |
| --- | --- | --- |
| F-03 문의 답변 | 매장 정보·메뉴·FAQ만 근거로 답변 초안 작성 | `FactChecker`가 초안과 점주 수정본의 가격·시각·휴무일을 DB와 대조, 프롬프트 인젝션 방어, 마크다운 기호 제거 |
| F-04 홍보 문구 | 채널·대상·키워드에 맞는 문구 작성 | 채널별 길이·해시태그 규칙 검사, 메뉴 가격·영업시간 대조, 외국어 문자 검사 |

- AI 결과는 화면에 "AI 생성" 표시를 하고, 손님에게는 점주가 확정한 답변만 보입니다.
- 13주차 검증 실험 결과: [experiment_week13.md](docs/verification/experiment_week13.md) (실행: `python -m scripts.verify_ai --ai`)
- AI 활용 로그: [ai_usage_log.md](docs/ai_usage_log.md)

## 폴더 구조

```
app/
  presentation/            # 프레젠테이션 계층
    routers/               #   customer, reservation, inquiry, owner, marketing
    templates/             #   customer/(고객 화면), owner/(점주 화면)
    static/                #   메뉴 사진, 배경 이미지
  services/                # 비즈니스 로직 계층
    reservation/           #   예약 서비스 + 상태 클래스 (State)
    inquiry/               #   문의 서비스 + FactChecker (DB 대조)
    marketing/             #   홍보 서비스 + 채널 전략 (Strategy)
    notification/          #   문자 알림 11종
    dashboard/, store/     #   대시보드, 매장·메뉴·메뉴 사진
  adapters/
    ai/                    #   AIClient 인터페이스, Mock, 실제 API (Adapter)
    sms/                   #   SmsSender 인터페이스, Mock, SOLAPI (Adapter)
  repositories/            # DB 조회·저장
  models/                  # Store, MenuItem, FAQ, Customer, Reservation, ReservationHistory, Inquiry, MarketingContent
  db/                      # DB 연결, 가상 데이터 적재 (seed_data/)
tests/                     # 기능별 정상·예외 테스트
scripts/verify_ai.py       # AI 검증 실험
docs/                      # 기획·설계·검증 문서
CLAUDE.md                  # 팀 코딩 규칙
```

## 산출물 위치

| 산출물 | 위치 |
| --- | --- |
| 소스코드 | 이 저장소 `main` 브랜치 |
| 데이터베이스 스키마·샘플 데이터 | `app/models/models.py`, [ERD](docs/design/erd.md), `app/db/seed_data/` |
| 요구사항 정의서·설계서 | `docs/planning/`, `docs/design/` |
| 테스트 케이스·결과 | [docs/test_cases.md](docs/test_cases.md), 테스트 결과표 |
| AI 활용 내역·검증 | [docs/ai_usage_log.md](docs/ai_usage_log.md), `docs/verification/` |
| 코딩 규칙 | [CLAUDE.md](CLAUDE.md) |

결과보고서, 최종 요구사항 정의서·설계서, 테스트 결과표, AI 활용 내역 및 검증 보고서의 제출본(docx·pdf)은 과목 제출함에 따로 냈습니다.

## 알려진 한계

- **사실 검증 범위**: `FactChecker`는 가격·시각·휴무일 같은 숫자 정보만 대조합니다. "메뉴에 없는 와플을 판다"처럼 숫자가 없는 오류는 잡지 못하므로 점주 확인에 의존합니다.
- **AI 응답 품질**: 무료 모델은 가끔 외국어가 섞이거나 호출 한도(429)에 걸립니다. 자동 재생성과 수정 요청으로 줄였지만 완전히 막지는 못합니다.
- **메뉴 사진 저장 방식**: 사진은 DB가 아니라 `static/menu`에 메뉴 이름으로 저장합니다. 메뉴 이름을 바꾸면 사진을 다시 올려야 합니다.
- **문자 발송 IP 제한**: SOLAPI 허용 IP 때문에 클라우드 배포(Railway 등)에서는 실제 문자를 보내기 어렵습니다. 시연은 노트북 서버와 cloudflared 터널로 합니다.
- **단일 매장·로그인 없음**: 매장 1곳 기준이며, 점주 화면 로그인은 범위에서 제외했습니다.

## 협업 규칙

- 브랜치: `main`(제출용) ← `develop`(통합) ← 기능 브랜치(`feature/...`)
- `main`, `develop`에 직접 push하지 않고 Pull Request로 병합합니다.
- 커밋 메시지는 `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `style:`로 시작합니다.
- 코드 작성 규칙은 [CLAUDE.md](CLAUDE.md), Git 사용법은 [docs/git_guide.md](docs/git_guide.md)를 따릅니다.
