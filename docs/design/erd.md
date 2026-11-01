# 데이터베이스 설계서 (ERD)

- 프로젝트: 소상공인용 AI 마케팅·고객응대 통합 지원 시스템
- 작성자: 전지호
- 작성 기간: 2026. 11. 3. ~ 11. 8.

## 1. 설계 범위 및 기준

현재 프로젝트의 SQLAlchemy 모델과 기획서의 주요 데이터 정의를 기준으로 ERD를 작성했다. 기존 엔티티를 임의로 늘리지 않고 매장·메뉴·FAQ·고객·예약·예약 이력·문의·홍보 콘텐츠를 사용한다.

F-04와 F-05에 직접 관련된 테이블은 `stores`, `marketing_contents`, `reservations`, `inquiries`이다. 대시보드 전용 테이블은 만들지 않고 기존 데이터를 조회해 화면에 표시한다.

## 2. ERD

```mermaid
erDiagram
    STORES ||--o{ MENU_ITEMS : has
    STORES ||--o{ FAQS : has
    STORES ||--o{ RESERVATIONS : receives
    STORES ||--o{ INQUIRIES : receives
    STORES ||--o{ MARKETING_CONTENTS : owns
    CUSTOMERS ||--o{ RESERVATIONS : makes
    CUSTOMERS ||--o{ INQUIRIES : submits
    RESERVATIONS ||--o{ RESERVATION_HISTORIES : records

    STORES {
        int id PK
        string name
        string category
        string address
        time open_time
        time close_time
        string closed_days
        string phone
        int capacity_per_hour
    }
    MENU_ITEMS {
        int id PK
        int store_id FK
        string name
        int price
        string description
        bool on_sale
    }
    FAQS {
        int id PK
        int store_id FK
        string question
        text answer
    }
    CUSTOMERS {
        int id PK
        string name
        string phone
    }
    RESERVATIONS {
        int id PK
        int store_id FK
        int customer_id FK
        datetime reserved_at
        int party_size
        string request
        string status
    }
    RESERVATION_HISTORIES {
        int id PK
        int reservation_id FK
        string from_status
        string to_status
        datetime changed_at
    }
    INQUIRIES {
        int id PK
        int store_id FK
        int customer_id FK
        text content
        datetime received_at
        string status
        text ai_draft
        text final_answer
        text check_result
    }
    MARKETING_CONTENTS {
        int id PK
        int store_id FK
        string channel
        string target
        string keywords
        text text
        text check_result
        datetime saved_at
    }
```

## 3. 테이블 정의

### 3.1 stores (매장)

| 컬럼 | 자료형 | 키 | 설명 |
|---|---|---|---|
| id | INTEGER | PK | 매장 식별자 |
| name | VARCHAR(100) | | 매장명 |
| category | VARCHAR(50) | | 업종 |
| address | VARCHAR(200) | | 주소 |
| open_time | TIME | | 영업 시작 시각 |
| close_time | TIME | | 영업 종료 시각 |
| closed_days | VARCHAR(50) | | 휴무일(예: 월,화) |
| phone | VARCHAR(30) | | 매장 연락처 |
| capacity_per_hour | INTEGER | | 시간당 예약 정원 |

### 3.2 menu_items (메뉴·상품)

| 컬럼 | 자료형 | 키 | 설명 |
|---|---|---|---|
| id | INTEGER | PK | 메뉴 식별자 |
| store_id | INTEGER | FK → stores.id | 소속 매장 |
| name | VARCHAR(100) | | 메뉴명 |
| price | INTEGER | | 가격(원) |
| description | VARCHAR(300) | | 설명 |
| on_sale | BOOLEAN | | 판매 여부 |

### 3.3 faqs (자주 묻는 질문)

| 컬럼 | 자료형 | 키 | 설명 |
|---|---|---|---|
| id | INTEGER | PK | FAQ 식별자 |
| store_id | INTEGER | FK → stores.id | 소속 매장 |
| question | VARCHAR(300) | | 질문 |
| answer | TEXT | | 답변 |

### 3.4 customers (고객)

| 컬럼 | 자료형 | 키 | 설명 |
|---|---|---|---|
| id | INTEGER | PK | 고객 식별자 |
| name | VARCHAR(50) | | 고객명 |
| phone | VARCHAR(30) | | 연락처 |

### 3.5 reservations (예약)

| 컬럼 | 자료형 | 키 | 설명 |
|---|---|---|---|
| id | INTEGER | PK | 예약 식별자 |
| store_id | INTEGER | FK → stores.id | 예약 대상 매장 |
| customer_id | INTEGER | FK → customers.id | 예약 고객 |
| reserved_at | DATETIME | | 예약 일시 |
| party_size | INTEGER | | 예약 인원 |
| request | VARCHAR(300) | | 요청사항 |
| status | VARCHAR(10) | | 요청·확정·방문완료·취소·노쇼 |

### 3.6 reservation_histories (예약 상태 이력)

| 컬럼 | 자료형 | 키 | 설명 |
|---|---|---|---|
| id | INTEGER | PK | 이력 식별자 |
| reservation_id | INTEGER | FK → reservations.id | 대상 예약 |
| from_status | VARCHAR(10) | | 변경 전 상태 |
| to_status | VARCHAR(10) | | 변경 후 상태 |
| changed_at | DATETIME | | 변경 시각 |

### 3.7 inquiries (고객 문의)

| 컬럼 | 자료형 | 키 | 설명 |
|---|---|---|---|
| id | INTEGER | PK | 문의 식별자 |
| store_id | INTEGER | FK → stores.id | 문의 대상 매장 |
| customer_id | INTEGER | FK → customers.id | 문의 고객 |
| content | TEXT | | 문의 내용 |
| received_at | DATETIME | | 접수 시각 |
| status | VARCHAR(10) | | 미응답·답변완료 |
| ai_draft | TEXT, NULL 허용 | | AI 원본 초안 |
| final_answer | TEXT, NULL 허용 | | 점주가 확정한 최종 답변 |
| check_result | TEXT, NULL 허용 | | DB 대조 결과(JSON) |

### 3.8 marketing_contents (홍보 콘텐츠)

| 컬럼 | 자료형 | 키 | 설명 |
|---|---|---|---|
| id | INTEGER | PK | 콘텐츠 식별자 |
| store_id | INTEGER | FK → stores.id | 소속 매장 |
| channel | VARCHAR(20) | | instagram·blog·sms |
| target | VARCHAR(100) | | 홍보 대상 |
| keywords | VARCHAR(200) | | 생성에 사용한 키워드 |
| text | TEXT | | 저장된 홍보 문구 |
| check_result | TEXT, NULL 허용 | | 채널 규칙 검사 결과 |
| saved_at | DATETIME | | 저장 시각 |

## 4. 관계 및 카디널리티

| 부모 | 자식 | 관계 | 설명 |
|---|---|---|---|
| stores | menu_items | 1:N | 한 매장은 여러 메뉴를 가진다. |
| stores | faqs | 1:N | 한 매장은 여러 FAQ를 가진다. |
| stores | reservations | 1:N | 한 매장에 여러 예약이 접수된다. |
| stores | inquiries | 1:N | 한 매장에 여러 문의가 접수된다. |
| stores | marketing_contents | 1:N | 한 매장은 여러 홍보 콘텐츠를 저장한다. |
| customers | reservations | 1:N | 한 고객은 여러 예약을 신청할 수 있다. |
| customers | inquiries | 1:N | 한 고객은 여러 문의를 등록할 수 있다. |
| reservations | reservation_histories | 1:N | 예약 상태가 변경될 때마다 이력이 추가된다. |

## 5. F-04·F-05 데이터 처리 기준

### F-04 홍보 문구

1. 점주가 채널·홍보 대상·키워드를 선택한다.
2. AI가 만든 초안과 채널 규칙 검사 결과를 화면에 표시한다.
3. 점주가 내용을 확인·수정한 뒤 저장한다.
4. 최종 저장 내용은 `marketing_contents`에 기록한다.
5. 채널별 목록은 `store_id`와 `channel`을 기준으로 조회하고, 최근 콘텐츠는 `saved_at` 내림차순으로 최대 5건을 조회한다.

### F-05 대시보드

- 오늘 예약: `reservations.reserved_at`의 날짜와 `store_id`로 조회하고 상태를 함께 표시한다.
- 미응답 문의 수: `inquiries.store_id`와 `status = '미응답'` 조건으로 집계한다.
- 최근 콘텐츠: `marketing_contents.store_id` 조건으로 `saved_at` 내림차순 정렬 후 5건을 가져온다.
- 대시보드 표시용 별도 테이블은 생성하지 않는다.

## 6. 데이터 무결성 및 운영 기준

- 각 테이블의 기본키는 `id`로 식별한다.
- 자식 테이블의 외래키는 실제 부모 레코드를 참조해야 한다.
- 매장 데이터는 여러 업무 데이터의 기준이 되므로 `store_id`로 매장 범위를 구분한다.
- 예약 상태 변경 이력은 기존 이력을 덮어쓰지 않고 새 행으로 추가한다.
- AI 원본 초안과 점주 최종 답변을 분리해 저장한다.
- 실제 개인정보 대신 프로젝트에서 생성한 가상 데이터를 사용한다.
- DB는 프로젝트 기술 스택에 따라 SQLite를 사용한다.
