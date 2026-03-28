# 올그린 청소봇 코드 리뷰 + 보안 감사

> **리뷰 날짜**: 2026-03-28
> **리뷰어**: Code Reviewer Agent (Opus 4.6)
> **대상**: cleaning-bot/ 전체 (23개 파일)
> **상태**: 운영 중 (DB 스키마 변경 금지)

---

## 목차
1. [전체 평가](#1-전체-평가)
2. [보안 감사](#2-보안-감사)
3. [에러 핸들링](#3-에러-핸들링)
4. [코드 품질](#4-코드-품질)
5. [비즈니스 로직](#5-비즈니스-로직)
6. [성능](#6-성능)
7. [발견 항목 요약표](#7-발견-항목-요약표)
8. [권장 조치](#8-권장-조치)

---

## 1. 전체 평가

### 아키텍처 (양호)
- FastAPI + python-telegram-bot 비동기 아키텍처가 잘 구성됨
- SQLAlchemy 2.0 async + asyncpg 적절히 사용
- 핸들러/서비스/모델/API 레이어 분리가 깔끔함
- ConversationHandler를 활용한 14단계 예약 플로우가 잘 설계됨
- notify_messages JSON으로 메시지 편집(스팸 방지) 패턴 우수

### 코드 규모
| 영역 | 파일 수 | 라인 수 |
|------|---------|---------|
| 핸들러 | 7 | ~1,627 |
| 모델 | 6 | ~127 |
| 서비스 | 1 | ~189 |
| API | 1 | ~389 |
| 기타 (main, config, db, keyboards, notifications) | 5 | ~836 |
| **합계** | **20** | **~3,168** |

---

## 2. 보안 감사

### 🔴 CRITICAL

#### SEC-01: 하드코딩된 초대 코드 (기본값)
- **파일**: `app/config.py:11-12`
- **내용**: `BOSS_INVITE_CODE = os.getenv("BOSS_INVITE_CODE", "BOSS2026")`, `STAFF_INVITE_CODE = os.getenv("STAFF_INVITE_CODE", "STAFF2026")`
- **위험**: .env에 값을 설정하지 않으면 추측 가능한 기본값으로 운영됨. 누구나 대표 권한 획득 가능.
- **대응**: 환경변수 미설정 시 시작 거부하거나, 랜덤 생성 후 로그 출력

#### SEC-02: 대시보드 API에 CORS 미설정
- **파일**: `app/main.py` (전체)
- **내용**: FastAPI에 CORSMiddleware가 없음
- **위험**: 기본적으로 모든 origin 허용. CSRF 공격에 노출될 수 있음
- **대응**: `CORSMiddleware` 추가, 허용 origin을 미니앱 도메인으로 제한

#### SEC-03: initData 시간 검증 누락
- **파일**: `app/api/routes/dashboard.py:19-47`
- **내용**: `verify_telegram_init_data()`에서 HMAC 서명은 검증하지만, `auth_date` 만료 검증이 없음
- **위험**: 탈취된 initData를 무기한 재사용 가능 (replay attack)
- **대응**: `auth_date`를 파싱하여 일정 시간(예: 1시간) 이후 거부

### 🟡 HIGH

#### SEC-04: SQL Injection 방어 확인 (양호)
- 모든 DB 접근이 SQLAlchemy ORM 쿼리를 사용 → SQL injection 위험 없음 ✅
- `dashboard.py:337`의 `Customer.phone.like(f"%{search}%")` — ORM이 파라미터 바인딩 처리하므로 안전
- `reservation_service.py`의 모든 쿼리 파라미터화 확인 ✅

#### SEC-05: 텔레그램 봇 인증 (양호, 일부 보완 필요)
- 봇 핸들러에서 `check_auth()` / `get_employee()`로 등록 여부 확인 ✅
- `reservation.py:40-42`: 예약 등록은 boss만 가능하도록 제한 ✅
- `naver_ocr.py:280`: OCR은 boss만 가능 ✅
- **⚠️ 미흡**: `task.py:action_callback` — employee 존재만 확인, role 체크 없음. staff가 cancel 액션 콜백 데이터를 수동 전송하면 예약 취소 가능. (단, 키보드에 cancel 버튼은 boss에게만 노출되므로 실질적 위험은 낮음)

#### SEC-06: 사진 URL 만료 문제
- **파일**: `app/bot/handlers/task.py:164`
- **내용**: `photo_url = file.file_path` — Telegram file_path는 1시간 후 만료
- **위험**: task_updates 테이블에 저장된 photo_url이 시간이 지나면 접근 불가
- **대응**: Cloudinary 업로드 구현 (TODO로 이미 표기됨)

#### SEC-07: Google Vision API 키 노출 가능성
- **파일**: `app/bot/handlers/naver_ocr.py:44`
- **내용**: API 키가 URL 쿼리스트링에 포함되어 전송
- **위험**: 로그에 API 키가 기록될 수 있음. HTTP가 아닌 HTTPS이므로 전송 중 노출은 없지만, 에러 로그 `resp.text` 출력 시 URL 포함 가능성
- **대응**: 에러 로그에서 URL 마스킹 처리, 또는 서비스 계정 인증으로 전환

### 🟢 LOW

#### SEC-08: Rate Limiting 없음
- 대시보드 API와 봇 핸들러에 rate limiting 없음
- 소규모 서비스이므로 현재 영향 낮음, 성장 시 추가 필요

#### SEC-09: 에러 응답에 내부 정보 미노출 (양호)
- `dashboard.py`의 HTTPException에 일반적인 한국어 메시지만 포함 ✅
- 글로벌 에러 핸들러에서 사용자에게는 일반 메시지만 전송 ✅

---

## 3. 에러 핸들링

### 🟡 HIGH

#### ERR-01: DB 세션 관리 — commit 후 예외 미처리
- **파일**: `app/services/reservation_service.py:69`, `app/bot/handlers/start.py:73`
- **내용**: `await db.commit()` 실패 시 예외가 상위로 전파됨. 글로벌 에러 핸들러에서 잡히지만, 사용자에게 상태가 모호해질 수 있음
- **영향**: 중복 예약번호 생성 시 (`reservation_no` UNIQUE 제약 위반) 적절한 에러 메시지 없이 일반 오류 표시

#### ERR-02: 예약번호 생성 경쟁 조건 (Race Condition)
- **파일**: `app/services/reservation_service.py:12-20`
- **내용**: `generate_reservation_no()`가 COUNT 기반 — 동시 요청 시 같은 번호 생성 가능
- **영향**: `reservation_no` UNIQUE 제약으로 두 번째 INSERT가 실패
- **대응**: retry 로직 추가 또는 DB 시퀀스 활용

#### ERR-03: notify_group_status_change 실패 시 상태 불일치
- **파일**: `app/bot/handlers/task.py:86-91`
- **내용**: `update_reservation_status()` 성공 후 `notify_group_status_change()` 실패하면, DB는 변경됐지만 알림은 미발송
- **영향**: 대표가 상태 변경을 인지하지 못할 수 있음
- **대응**: 치명적이지 않음 (카드 조회 시 최신 상태 표시). 로깅만으로 충분

### 🟢 LOW

#### ERR-04: JSON 파싱 방어 (양호)
- `items_json`, `notify_messages` 파싱 시 모든 곳에서 `try/except` 처리 ✅
- `notifications.py:149`, `dashboard.py:104-107` 등 일관성 있게 적용

#### ERR-05: Telegram API 호출 실패 처리 (양호)
- `notifications.py:196-211`: edit_message 실패 → send_message fallback ✅
- `notifications.py:258-259`: boss alert 실패 로깅 ✅
- `send_daily_schedule()`: 개별 직원 전송 실패 무시 (적절)

---

## 4. 코드 품질

### 🟡 MEDIUM

#### CQ-01: 견적 키보드 중복 코드
- **파일**: `app/bot/handlers/quote.py:10-51`
- **내용**: `q_item_type_keyboard()`, `q_subtype_keyboard()`, `q_quantity_keyboard()`가 원본 키보드를 복사 후 callback_data 접두사만 변경
- **개선**: 팩토리 함수로 리팩토링 가능 (예: `prefixed_keyboard(original_kb, prefix_map)`)
- **현재 영향**: 기능 동작에 문제 없음, 유지보수 시 양쪽 수정 필요

#### CQ-02: 매직 스트링 산재
- 상태값 (`"pending"`, `"confirmed"`, ...), 역할 (`"boss"`, `"staff"`), 결제방법 (`"cash"`, `"card"`, `"naver"`) 등이 문자열 리터럴로 여러 파일에 흩어져 있음
- `keyboards.py`에 LABELS 딕셔너리가 있지만 Enum 등의 공식 정의가 없음
- **영향**: 오타 시 런타임 버그, IDE 자동완성 불가
- **대응**: Python Enum 클래스 정의 권장 (단, DB 변경 없이 코드만)

#### CQ-03: add_current_item / add_current_item_msg 중복
- **파일**: `app/bot/handlers/reservation.py:155-201`
- **내용**: 두 함수가 거의 동일 (query.edit_message_text vs update.message.reply_text 차이만)
- **개선**: 공통 로직 추출 후 메시지 전송부만 분리

#### CQ-04: 미사용 import / 변수
- `dashboard.py:331`: `formatted_patterns` 리스트가 생성되지만 실제 쿼리에서 사용되지 않음
- `reservation.py:1`: `from datetime import datetime` — datetime은 사용되지만 date가 아닌 datetime.strptime으로만 사용

### 🟢 LOW

#### CQ-05: 타입 힌트 (양호)
- 모델: SQLAlchemy `Mapped[T]` 타입 힌트 완전 적용 ✅
- 서비스: 반환 타입 명시 ✅
- 핸들러: Telegram Update/Context 타입 일관 적용 ✅

#### CQ-06: 로깅 수준 적절
- `logging.basicConfig(level=logging.INFO)` 적절 ✅
- OCR, 에러 핸들러에서 로깅 수행 ✅
- **보완점**: 예약 생성/상태변경 시 INFO 로그 추가하면 운영에 도움

---

## 5. 비즈니스 로직

### 🟡 HIGH

#### BL-01: 상태 전환 유효성 검증 없음
- **파일**: `app/services/reservation_service.py:118-125`
- **내용**: `update_reservation_status()`가 아무 상태에서 아무 상태로 전환 가능
- **위험**: 이론적으로 `settled` → `pending` 역전환 가능 (UI에서는 버튼이 없어 실질적 위험 낮음)
- **대응**: 허용 전환 맵 추가 권장
```python
VALID_TRANSITIONS = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"picking_up", "cancelled"},
    "picking_up": {"picked_up"},
    # ...
}
```

#### BL-02: 정산 중복 실행 방어 없음
- **파일**: `app/services/reservation_service.py:141-159`
- **내용**: `settle_reservation()`이 현재 상태 확인 없이 Payment 생성 → 빠른 더블클릭으로 중복 정산 가능
- **위험**: 동일 예약에 Payment 레코드 2개 생성, customer.total_paid 이중 가산
- **대응**: `if reservation.status != "delivered": return None` 가드 추가

#### BL-03: 고객 visit_count 증가 시점
- **파일**: `app/services/reservation_service.py:30`
- **내용**: `get_or_create_customer()` 호출 시마다 `visit_count += 1` — 예약 등록 시점에 증가
- **문제**: 예약 취소해도 visit_count는 감소하지 않음
- **영향**: 고객 방문 횟수가 실제보다 높게 표시될 수 있음 (실질적 영향 낮음)

### 🟢 LOW

#### BL-04: 네이버 OCR 영역 매핑 (현재 적절)
- `naver_ocr.py:402-406`: 주소에서 "세종"/"논산" 키워드로 area 결정
- 대전이 기본값이므로 현재 서비스 영역에서는 충분

#### BL-05: final_price 미활용
- `reservation.py:29`: `final_price` 필드가 존재하지만 어디서도 설정되지 않음
- `reservation_service.py:146`: `amount = reservation.final_price or reservation.price` — 할인 시 사용 예정으로 보임
- **영향**: 현재 문제 없음, 할인 기능 추가 시 활용 가능

---

## 6. 성능

### 🟢 양호

#### PERF-01: N+1 쿼리 방지 (양호)
- `selectinload(Reservation.customer)` 일관 적용 ✅
- `reservation_service.py:77`, `dashboard.py:82`, `dashboard.py:148` 등

#### PERF-02: 대시보드 쿼리 효율
- `/summary`: 오늘 예약 1회 쿼리 + 매출 1회 = 2쿼리 ✅
- `/calendar`: 월별 1회 쿼리 ✅
- `/revenue`: period 쿼리 + 품목별 + 방법별 = 3쿼리 (적절)
- `/history`: 페이지네이션 적용 ✅

#### PERF-03: 개선 가능 사항
- `notifications.py:send_or_update_card()`: 직원마다 `save_notify_message()` 개별 호출 → DB 세션을 N번 열고 닫음. 배치 업데이트로 개선 가능하나 현재 직원 수가 적어 영향 미미.
- `dashboard.py:237-257`: 품목별/방법별 매출 쿼리에 기간 필터 없음 → 전체 기간 집계. 데이터 증가 시 느려질 수 있음.

---

## 7. 발견 항목 요약표

| ID | 심각도 | 분류 | 요약 | 자동수정 |
|----|--------|------|------|----------|
| SEC-01 | 🔴 CRITICAL | 보안 | 하드코딩된 초대 코드 기본값 | ❌ (환경설정) |
| SEC-02 | 🔴 CRITICAL | 보안 | CORS 미설정 | ✅ 가능 |
| SEC-03 | 🔴 CRITICAL | 보안 | initData auth_date 만료 미검증 | ✅ 가능 |
| SEC-04 | ✅ OK | 보안 | SQL Injection 방어 | - |
| SEC-05 | 🟡 HIGH | 보안 | action_callback role 미검증 | ❌ (로직변경) |
| SEC-06 | 🟡 HIGH | 보안 | 사진 URL 만료 (Cloudinary TODO) | ❌ (외부연동) |
| SEC-07 | 🟡 HIGH | 보안 | API 키 로그 노출 가능성 | ✅ 가능 |
| SEC-08 | 🟢 LOW | 보안 | Rate limiting 없음 | ❌ (설계필요) |
| ERR-01 | 🟡 HIGH | 에러 | DB commit 실패 처리 | ❌ (로직변경) |
| ERR-02 | 🟡 HIGH | 에러 | 예약번호 경쟁 조건 | ❌ (로직변경) |
| ERR-03 | 🟡 HIGH | 에러 | 알림 실패 시 상태 불일치 | ❌ (이미 적절) |
| CQ-01 | 🟡 MED | 코드 | 견적 키보드 중복 코드 | ❌ (리팩토링) |
| CQ-02 | 🟡 MED | 코드 | 매직 스트링 | ❌ (리팩토링) |
| CQ-03 | 🟡 MED | 코드 | add_current_item 중복 | ❌ (리팩토링) |
| CQ-04 | 🟢 LOW | 코드 | 미사용 변수 (formatted_patterns) | ✅ 수정 |
| BL-01 | 🟡 HIGH | 비즈니스 | 상태 전환 유효성 없음 | ❌ (로직변경) |
| BL-02 | 🟡 HIGH | 비즈니스 | 정산 중복 실행 방어 없음 | ❌ (로직변경) |
| BL-03 | 🟢 LOW | 비즈니스 | visit_count 취소 시 미감소 | ❌ (정책결정) |

---

## 8. 권장 조치

### 즉시 조치 (운영 안정성)

1. **SEC-01**: `.env`에 `BOSS_INVITE_CODE`, `STAFF_INVITE_CODE` 반드시 고유값 설정 확인
2. **SEC-02**: `CORSMiddleware` 추가 (아래 코드 참고)
3. **SEC-03**: `auth_date` 만료 검증 추가
4. **BL-02**: `settle_reservation()`에 상태 가드 추가

### 단기 개선 (1-2주)

5. **BL-01**: 상태 전환 유효성 검증 맵 추가
6. **SEC-06**: Cloudinary 사진 업로드 구현
7. **ERR-02**: 예약번호 생성 retry 로직

### 중기 개선 (1개월)

8. **CQ-02**: 상태/역할/결제방법 Enum 정의
9. **CQ-01/03**: 중복 코드 리팩토링
10. **SEC-08**: Rate limiting 추가

---

## 자동 수정 사항

아래 항목은 DB 변경 없이, 비즈니스 로직 변경 없이 안전하게 수정되었습니다:

### 수정 1: CQ-04 — 미사용 변수 `formatted_patterns` 제거
- **파일**: `app/api/routes/dashboard.py:329-331`
- **내용**: 생성만 되고 사용되지 않는 `formatted_patterns` 리스트 제거

### 수정 2: SEC-02 — CORS 미들웨어 추가
- **파일**: `app/main.py`
- **내용**: `CORSMiddleware` 추가, 미니앱 도메인 허용

### 수정 3: SEC-03 — initData auth_date 만료 검증
- **파일**: `app/api/routes/dashboard.py`
- **내용**: `auth_date`가 1시간 이상 지난 경우 거부

### 수정 4: SEC-07 — OCR 에러 로그 API 키 마스킹
- **파일**: `app/bot/handlers/naver_ocr.py`
- **내용**: 에러 로그에서 `resp.text` 대신 상태코드만 출력

---

*리뷰 완료. 위 자동 수정 사항은 코드에 반영되었습니다.*
