# 시스템 아키텍처 설계서 (초안 · 저장소 코드 대조본)

> 기준 저장소: `sakakinji-maker/sw_make` / 기본 브랜치 `main`  
> 확인 기준: 현재 저장소에 올라온 코드와 README의 구현 계획. 구현 중 변경될 수 있다.

## 1. 목적 및 범위

소상공인 점주가 매장·메뉴·예약·문의·홍보 업무를 웹에서 처리하도록 지원한다. 이 문서는 전체 구조와 F-04 채널별 AI 홍보 문구, F-05 점주 대시보드의 설계 방향을 정리한다.

## 2. 아키텍처 선택 및 근거

**3계층 구조**를 기본으로 한다.

- 프레젠테이션 계층: FastAPI 라우터와 Jinja2 템플릿. 고객 화면과 점주 화면의 요청·응답을 담당한다.
- 비즈니스 로직 계층: 예약·문의·홍보 서비스와 디자인 패턴 클래스. 업무 규칙, AI 요청, 결과 검사를 담당한다.
- 데이터 계층: SQLAlchemy 모델과 SQLAlchemy 세션을 통해 데이터를 저장·조회한다. 기본 DB는 SQLite이며, `DATABASE_URL` 환경 변수로 연결 대상을 바꿀 수 있다.

선택 근거: 화면, 업무 규칙, 데이터 처리를 분리하면 기능별 수정 범위를 줄이고 테스트하기 쉽다. 현재 코드도 `app/presentation`, `app/services`, `app/models`, `app/db`로 나뉘어 있어 이 구조와 맞는다. 단, `app/repositories`는 현재 README 안내 파일만 있고 실제 Repository 구현은 확인되지 않았다. 데이터 접근은 일부 서비스에서 SQLAlchemy 세션을 직접 사용할 수 있으므로 최종 구조는 구현 진행에 따라 보완한다.

## 3. 현재 코드 기준 구성

| 영역 | 저장소에서 확인한 구성 | 책임 / 상태 |
|---|---|---|
| 화면 | `app/main.py`, `app/presentation/routers/customer.py`, `owner.py`, Jinja2 템플릿 | 고객·점주 라우팅. `owner.py`의 대시보드는 현재 빈 예약 목록·문의 수 0·빈 콘텐츠를 전달하는 초기 화면 |
| 홍보 | `app/services/marketing/service.py`, `strategies.py` | `MarketingService.generate()`가 채널 전략으로 프롬프트를 만들고 AI 결과의 채널 규칙을 검사함. 저장·목록·메뉴/가격 대조는 TODO |
| 문의 | `app/services/inquiry/service.py`, `fact_checker.py` | 문의 답변 초안 생성과 가격·영업시간 대조. 저장·최종 답변 처리는 TODO |
| 예약 | `app/services/reservation/service.py`, `states.py` | 예약 상태 전이와 이력 기록. 생성·영업시간·정원 검사는 TODO |
| AI 연동 | `app/adapters/ai/base.py`, `mock_adapter.py`, `external_adapter.py`, `factory.py` | `AIClient` 인터페이스를 통해 Mock 또는 외부 AI 구현을 선택 |
| 데이터 | `app/models/models.py`, `app/db/database.py`, `seed.py` | SQLAlchemy 모델 8종, SQLite 연결 및 초기 샘플 데이터 |

## 4. 주요 데이터 흐름

### F-04 홍보 문구 생성
1. 점주가 채널(인스타그램/블로그/문자), 홍보 대상, 키워드를 입력한다.
2. `MarketingService.generate()`가 `get_strategy(channel)`로 채널 전략을 선택한다.
3. 전략의 `build_prompt()`가 채널별 작성 지침을 만든다.
4. `AIClient.generate()`가 문구를 생성한다. 설정에 따라 Mock 또는 외부 AI가 사용된다.
5. 전략의 `check()`가 글자 수·해시태그 수를 검사하고 위반 목록을 반환한다.
6. **추가 구현 필요:** 메뉴명·가격 DB 대조, 결과 저장, 저장 목록 조회 및 화면 표시.

### F-05 점주 대시보드
1. 점주가 `/owner`에 접속한다.
2. 현재 `owner.dashboard()`는 빈 데이터로 템플릿을 표시한다.
3. **추가 구현 필요:** 오늘 예약(상태별), 미응답 문의 수, 최근 홍보 콘텐츠 5건을 DB에서 조회해 화면에 전달한다.

## 5. 외부 AI 및 장애 대응

서비스는 `AIClient` 추상 클래스에 의존한다. `MockAIClient`는 개발·테스트에 사용하고, `ExternalAIClient`는 실제 API 연결에 사용한다. `factory.get_ai_client()`가 `AI_PROVIDER` 설정을 보고 구현체를 선택한다. 홍보 서비스는 `AIClientError`가 발생하면 `ContentResult.error`를 반환한다. 실제 API 키는 `.env`에 보관하고 저장소에 커밋하지 않는다.

## 6. 디자인 패턴

- **State:** `ReservationState`와 하위 상태 클래스가 예약 상태별 허용 동작을 관리한다.
- **Strategy:** `ChannelStrategy`와 `InstagramStrategy`, `BlogStrategy`, `SmsStrategy`가 채널별 작성 지침과 규칙 검사를 분리한다.
- **Adapter:** `AIClient`를 공통 인터페이스로 두고 Mock/외부 AI 클라이언트를 교체한다.

## 7. 4+1 아키텍처 관점

| 관점 | 이 프로젝트에서 표현할 내용 | 현재 확인 상태 |
|---|---|---|
| 시나리오(+1) | 점주가 홍보 문구를 생성·검사·저장하고 대시보드에서 최근 콘텐츠를 확인하는 흐름 | 생성·검사는 코드 존재, 저장·대시보드는 추가 구현 필요 |
| 논리 관점 | `MarketingService`, `ChannelStrategy` 구현체, `AIClient`, `MarketingContent` 등 주요 클래스와 관계 | 일부 클래스 코드 확인 |
| 개발 관점 | `presentation / services / adapters / models / db / repositories` 패키지 구성 | 대부분 폴더 확인, repositories 구현은 미완성 |
| 프로세스 관점 | 요청→전략 선택→AI 생성→규칙 검사→(추후 DB 대조·저장) | 생성·규칙 검사까지 구현 |
| 물리 관점 | 사용자 브라우저→FastAPI 서버→SQLite, 필요 시 외부 AI API | 실행 구성은 README에 기재, 배포 인프라는 별도 정의 없음 |

## 8. 품질 속성 목표 및 검증 계획

| 품질 속성 | 목표 | 현재 달성 근거 | 검증 방법 / 남은 일 |
|---|---|---|---|
| 변경 용이성 | 새 홍보 채널 추가 시 기존 서비스 변경 최소화 | Strategy 등록 구조와 채널별 클래스 존재 | 새 테스트 전략을 등록해 기존 서비스 코드 변경 없이 동작하는지 테스트 |
| 테스트 용이성 | 외부 AI 없이 서비스 테스트 가능 | `MockAIClient` 구현 존재 | Mock 고정 응답·실패 응답으로 정상/예외 테스트 수행 |
| 신뢰성 | AI가 만든 채널 형식 위반을 표시 | 글자 수·해시태그 검사 구현 | 채널별 경계값 및 위반 케이스 테스트. 메뉴명·가격 DB 대조는 추가 구현 |
| 유지보수성 | 화면·업무 규칙·데이터 처리를 분리 | 폴더와 모듈이 계층별로 구분 | 라우터에 SQL/업무 로직이 섞이지 않는지 리뷰. Repository 계층은 아직 보완 필요 |
| 사용성 | 점주가 예약·문의·최근 홍보를 한 화면에서 확인 | 대시보드 라우트·템플릿 골격 존재 | 실제 데이터 연결 후 오늘 예약·미응답 문의·최근 5개 콘텐츠 표시 확인 |

## 9. 미완료·팀 확인 사항

- F-04의 메뉴명·가격 대조를 기존 `FactChecker`에 확장할지, 별도 검증 클래스로 둘지 결정한다.
- F-04 콘텐츠 저장·목록 조회를 담당할 Repository 또는 서비스 메서드를 구현한다.
- F-05 대시보드 조회 로직과 날짜 기준(오늘의 시간대)을 확정한다.
- `app/repositories`의 실제 구현 여부와 서비스의 DB 접근 방식을 팀 코딩 규칙에 맞춰 정리한다.
- 최종 제출 전 코드 변경사항을 반영해 이 문서와 다이어그램을 최신화한다.
