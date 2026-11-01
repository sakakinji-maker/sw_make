# SOLID 원칙 점검표 (초안 · 저장소 코드 대조본)

> 현재 `main` 브랜치에서 확인한 코드에 대한 1차 점검이다. 설계 원칙을 완전히 준수한다고 단정하지 않고, 확인된 근거와 보완할 일을 구분한다.

| 원칙 | 현재 코드에서 확인한 근거 | 1차 판단 | 보완·검증할 일 |
|---|---|---|---|
| SRP 단일 책임 | `ChannelStrategy`가 채널별 지침·규칙 검사, `AIClient`가 AI 호출 인터페이스, `FactChecker`가 문의 답변의 가격·시각 대조를 담당 | 대체로 역할 분리 방향이 보임 | `MarketingService`에 생성·규칙 검사 외 저장·목록 기능을 추가할 때 별도 저장소 클래스로 분리할지 검토. 대시보드 조회 책임도 `DashboardService`로 분리 |
| OCP 개방-폐쇄 | `@register`와 `_REGISTRY`로 채널 전략을 등록하고 `get_strategy()`로 선택 | 채널 확장 구조 확인 | 새 채널 전략을 추가하는 테스트를 작성해 기존 `MarketingService` 수정 없이 동작하는지 확인 |
| LSP 리스코프 치환 | Instagram/Blog/SMS 전략이 `ChannelStrategy`를 상속하고 공통 `build_prompt()`, `check()` 계약 사용 | 상속 구조 확인, 계약 검증은 미완료 | 세 전략을 같은 방식으로 호출하는 공통 테스트 작성. 글자 수·해시태그 경계값 검증 |
| ISP 인터페이스 분리 | `AIClient`는 `generate()` 중심의 작은 추상 인터페이스 | 단순한 인터페이스 확인 | 실제·Mock 구현체가 동일한 호출 계약과 예외 규칙을 지키는지 테스트 |
| DIP 의존 역전 | `MarketingService`는 구체 AI SDK가 아닌 `AIClient`에 의존하고 `factory`가 구현체를 선택 | 의존 역전 방향 확인 | 서비스 테스트에서 `MockAIClient`를 주입해 실제 외부 AI 없이 검증. 외부 AI 호출은 Adapter 내부에만 유지 |

## 저장소 코드에서 확인한 구체 사항

- 홍보 전략: `app/services/marketing/strategies.py`
- 홍보 서비스: `app/services/marketing/service.py`
- AI 추상화·Mock·외부 구현: `app/adapters/ai/`
- 문의 답변의 사실 대조: `app/services/inquiry/fact_checker.py`
- 실제 홍보 서비스에는 현재 `메뉴명·가격 DB 대조`, `저장·목록 조회`가 TODO로 남아 있다.
- 점주 대시보드 라우트는 있으나 현재 빈 데이터를 템플릿에 전달한다. 대시보드 조회 서비스는 추가 구현이 필요하다.
- `app/repositories`에는 현재 README 안내 파일만 확인되어 실제 Repository 구현 여부를 추후 확인해야 한다.

## 구현 완료 후 체크리스트

- [ ] 채널별 전략을 서로 바꿔 끼워도 `MarketingService`가 같은 방식으로 동작한다.
- [ ] 새 채널 추가 시 기존 채널 클래스와 서비스 코드를 불필요하게 수정하지 않는다.
- [ ] AI 호출은 `AIClient`를 통해서만 이뤄지고 Mock으로 대체 가능하다.
- [ ] 홍보 문구의 메뉴명·가격 대조와 저장·목록 조회가 별도 책임으로 관리된다.
- [ ] 대시보드 조회 로직이 라우터에 직접 섞이지 않고 별도 서비스에서 처리된다.
- [ ] 테스트에서 정상 상황뿐 아니라 잘못된 채널, 규칙 위반, AI 실패, 데이터 없음 상황을 확인한다.
