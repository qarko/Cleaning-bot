# 청소봇 QA 테스트 보고서

**테스트 일시**: 2026-03-28
**테스트 방식**: 코드 기반 정적 분석 (로컬 서버 미실행)
**대상**: `/home/claude/cleaning-bot/`

---

## 1. 대시보드 API 엔드포인트 분석

### 1.1 엔드포인트 목록

| Method | Path | 파라미터 | 설명 | 인증 |
|--------|------|----------|------|------|
| GET | `/api/dashboard/summary` | 없음 | 오늘 예약 요약 (건수, 매출, 상태별 분류) | boss 권한 |
| GET | `/api/dashboard/calendar` | `year`, `month` (optional) | 월별 캘린더 데이터 | boss 권한 |
| GET | `/api/dashboard/revenue` | `period` (day/week/month) | 매출 통계 + 품목별/결제방법별 분류 | boss 권한 |
| GET | `/api/dashboard/history` | `page`, `status` (optional) | 완료 내역 (페이지네이션) | boss 권한 |
| GET | `/api/dashboard/customer` | `q` (검색어) | 고객 검색 (연락처/주소) + 예약 이력 | boss 권한 |
| GET | `/` | 없음 | 랜딩 페이지 (static HTML) | 없음 |
| GET | `/health` | 없음 | 헬스체크 | 없음 |

### 1.2 인증 구조

- 헤더: `X-Telegram-Init-Data` (텔레그램 미니앱 initData)
- 검증 함수: `verify_telegram_init_data()` → HMAC-SHA256 서명 검증
- 권한: `verify_boss()` → Employee 테이블에서 `role == "boss"` 확인
- 에러 응답:
  - 401: 인증 정보 없음 / 인증 실패
  - 403: boss 아닌 사용자 접근 시

**인증 흐름**:
```
Request → X-Telegram-Init-Data 헤더 → parse_qs 파싱
→ hash 제외 후 정렬 → HMAC(WebAppData + BOT_TOKEN) 검증
→ user JSON 파싱 → Employee 테이블 조회 → role == "boss" 확인
```

---

## 2. API 구조 검증

### 2.1 `/api/dashboard/summary` - PASS (구조 양호)

**응답 구조**:
```json
{
  "date": "2026-03-28",
  "total": 5,
  "pending": 2,
  "in_progress": 2,
  "completed": 1,
  "revenue": 200000,
  "reservations": [
    {
      "reservation_no": "CL-20260328-001",
      "customer_name": "주소 또는 연락처",
      "items": [...],
      "status": "pending",
      "scheduled_time": "morning",
      "price": 40000,
      "payment_method": "cash"
    }
  ]
}
```

**발견 사항**:
- [INFO] `customer_name` 필드가 실제로는 `pickup_address` 또는 `customer.phone`을 사용 (이름이 아님) → 필드명과 실제 값 불일치 (혼동 가능)
- [OK] cancelled 상태 제외 정상
- [OK] 상태별 분류 로직 정확

### 2.2 `/api/dashboard/calendar` - PASS (경미한 이슈)

**응답 구조**:
```json
{
  "year": 2026,
  "month": 3,
  "days": {
    "2026-03-28": [
      {
        "reservation_no": "...",
        "customer_name": "...",
        "status": "...",
        "scheduled_time": "morning",
        "price": 40000
      }
    ]
  }
}
```

**발견 사항**:
- [WARN] `year`, `month` 파라미터가 없으면 `date.today()` 사용 → OK
- [WARN] `month=13` 등 비정상 값 입력 시 `date(year, 13, 1)` → **ValueError 예외 발생** (에러 핸들링 없음)
- [OK] cancelled 제외, 날짜 + 시간 정렬 정상

### 2.3 `/api/dashboard/revenue` - PASS (구조 양호)

**응답 구조**:
```json
{
  "period": "month",
  "data": [{"date": "2026-03", "revenue": 500000, "count": 12}],
  "by_item": [{"item_type": "carseat", "revenue": 200000, "count": 5}],
  "by_method": [{"method": "cash", "revenue": 300000, "count": 8}]
}
```

**발견 사항**:
- [OK] day/week/month 3가지 기간 지원
- [OK] 품목별, 결제방법별 분류 제공
- [INFO] `by_item`과 `by_method`는 기간 필터 없이 전체 데이터 반환 → 의도적일 수 있으나, period와 무관한 누적 데이터

### 2.4 `/api/dashboard/history` - PASS

**응답 구조**:
```json
{
  "total": 50,
  "page": 1,
  "reservations": [...]
}
```

**발견 사항**:
- [OK] 페이지네이션 (20건/페이지)
- [OK] status 필터 지원
- [OK] 기본값은 delivered + settled만 조회
- [INFO] `actual_payment_method`에 `getattr` 사용 → 방어 코드이나 모델에 필드가 있으므로 불필요

### 2.5 `/api/dashboard/customer` - PASS (경미한 이슈)

**발견 사항**:
- [OK] 빈 검색어 → `{"customer": null}` 반환
- [OK] 숫자면 연락처, 텍스트면 주소 검색
- [WARN] `formatted_patterns` 리스트 (line 329-331)가 생성되지만 사용되지 않음 → **데드 코드**
- [OK] 고객 예약 이력 최대 20건

---

## 3. 에러 핸들링 검증

### 3.1 API 레벨

| 시나리오 | 처리 | 평가 |
|----------|------|------|
| 인증 헤더 없음 | 401 HTTPException | OK |
| HMAC 검증 실패 | 401 HTTPException | OK |
| boss 아닌 사용자 | 403 HTTPException | OK |
| DB 연결 실패 | 미처리 (500 자동) | WARN |
| 잘못된 calendar 월 | 미처리 (ValueError) | BUG |
| items_json 파싱 실패 | try/except로 빈 리스트 | OK |

### 3.2 봇 핸들러 레벨

| 시나리오 | 처리 | 평가 |
|----------|------|------|
| 미등록 사용자 | "먼저 /start 로 등록해주세요" | OK |
| 잘못된 초대코드 | 재입력 요청 | OK |
| 예약 없음 | "예약이 없습니다" 응답 | OK |
| 봇 전역 에러 | error_handler (로깅 + 사용자 알림) | OK |
| OCR 실패 | 사용자에게 재시도 안내 | OK |
| 전화번호 형식 오류 | 재입력 요청 | OK |

### 3.3 글로벌 에러 핸들러

```python
# app/main.py:83-91
async def error_handler(update, context):
    logger.error(f"Bot error: {context.error}", exc_info=context.error)
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text("처리 중 오류가 발생했습니다.")
        except Exception:
            pass
```
- [OK] 로깅 + 사용자 메시지
- [OK] 메시지 전송 실패도 처리

---

## 4. 텔레그램 봇 핸들러 흐름 검증

### 4.1 사용자 등록 흐름

```
/start → 기존 사용자? → 메인 메뉴 표시
       → 신규 사용자 → 역할 선택 (boss/staff)
         → 초대코드 입력 → Employee 레코드 생성 → 메인 메뉴
```

**발견 사항**:
- [OK] ConversationHandler로 상태 관리
- [WARN] 초대코드가 환경변수 기본값으로 하드코딩 (`BOSS2026`, `STAFF2026`) → 보안상 반드시 변경 필요
- [OK] 중복 등록 시 기존 정보로 로그인

### 4.2 예약 등록 흐름 (수동)

```
/new → 연락처 입력 → 지역 선택 → 주소 입력 → 품목 선택
→ (서브타입/세척방식) → 수량 → 품목 요약 (추가/완료)
→ 날짜 선택 → 시간대 선택 → 결제 방법 → 특이사항
→ 확인 (등록/수정/취소) → 예약 생성 → 직원 알림
```

**발견 사항**:
- [OK] 14단계 ConversationHandler 상태 관리
- [OK] 복수 품목 추가 지원
- [OK] 자동 가격 계산
- [OK] 예약번호 자동 생성 (`CL-YYYYMMDD-NNN`)
- [OK] 등록 완료 시 staff에게 카드 알림

### 4.3 네이버 예약 OCR 흐름

```
사진 전송 (pending_action 없을 때) → boss 확인
→ Google Vision OCR → 텍스트 파싱 → 확인 메시지
→ (특이사항 입력) → 등록 확인 → 예약 생성
```

**발견 사항**:
- [OK] 핵심 필드 1개 이상 인식되면 진행
- [OK] 다양한 날짜 패턴 처리 (5가지)
- [OK] 특이사항 입력 옵션
- [WARN] 날짜 파싱 실패 시 `date.today()` 폴백 → 사용자에게 알림 없이 오늘 날짜로 등록될 수 있음

### 4.4 업무 처리 (상태 변경) 흐름

```
예약 카드에서 액션 버튼 클릭 → action_callback
→ 사진 필요 단계 → 사진 업로드 대기 → photo_handler / skip_photo_handler
→ 상태 업데이트 → 알림 발송 (카드 업데이트 + boss push 알림)
```

**발견 사항**:
- [OK] 역할별 버튼 분리 (staff: 업무 처리, boss: 정산/취소)
- [OK] 사진 첨부 스테이지 (`picked_up`, `cleaned`, `delivered`)
- [OK] 세척완료 시 배송 예정일 선택 분기
- [OK] task_update 기록 저장
- [OK] 알림 메시지 ID 추적 → 기존 메시지 edit (중복 메시지 방지)

---

## 5. 상태 전환 흐름 검증

### 5.1 정의된 상태 값

```
pending → confirmed → picking_up → picked_up → cleaning
→ cleaned → delivering → delivered → settled

별도: cancelled (어느 단계에서든 가능, boss만)
```

### 5.2 상태 전환 매트릭스

| 현재 상태 | staff 가능 액션 | boss 가능 액션 | 다음 상태 |
|-----------|----------------|---------------|-----------|
| pending | 확정 | 취소 | confirmed / cancelled |
| confirmed | 수거 출발 | 취소 | picking_up / cancelled |
| picking_up | 수거 완료 (사진) | 취소 | picked_up / cancelled |
| picked_up | 세척 시작 | 취소 | cleaning / cancelled |
| cleaning | 세척 완료 (사진+배송일) | 취소 | cleaned / cancelled |
| cleaned | 배송 출발 | 취소 | delivering / cancelled |
| delivering | 배송 완료 (사진) | 취소 | delivered / cancelled |
| delivered | 정산 | 정산 | settled |
| settled | - | - | (최종) |
| cancelled | - | - | (최종) |

### 5.3 검증 결과

- [OK] 키보드 버튼이 현재 상태에 맞는 다음 단계만 표시
- [OK] boss는 settled/cancelled/delivered 상태에서 취소 불가
- [OK] 정산 시 결제 방법 확인 + 변경 가능
- [OK] 정산 완료 시 `customer.total_paid` 자동 업데이트
- [BUG-LOW] **상태 역전환 방지 없음**: `update_reservation_status()`는 현재 상태를 검증하지 않고 무조건 업데이트. UI에서는 순차 버튼만 제공하지만, API 레벨에서 직접 콜백을 조작하면 역전환 가능 (예: settled → pending). 텔레그램 봇 특성상 실질적 위험은 낮음.
- [OK] 사진 스테이지 매핑: `picked_up→pickup`, `cleaned→clean`, `delivered→delivery`

---

## 6. 발견 이슈 요약

### Critical (없음)

### High

| # | 위치 | 설명 |
|---|------|------|
| H-1 | `config.py:11` | 초대코드 기본값 `BOSS2026`/`STAFF2026` 하드코딩 — 프로덕션에서 환경변수 미설정 시 누구나 boss 등록 가능 |

### Medium

| # | 위치 | 설명 |
|---|------|------|
| M-1 | `dashboard.py:130` | `/calendar` 잘못된 month 값 (0, 13 등) → `ValueError` 예외 미처리, 500 에러 |
| M-2 | `reservation_service.py:118` | `update_reservation_status()` 상태 순서 검증 없음 — 역전환 방지 로직 부재 |
| M-3 | `dashboard.py:237-246` | `/revenue` by_item/by_method가 period 필터 없이 전체 누적 — 기간별 분석과 불일치 |

### Low

| # | 위치 | 설명 |
|---|------|------|
| L-1 | `dashboard.py:110` | `customer_name` 필드가 실제로는 주소/연락처 — 프론트엔드 혼동 유발 |
| L-2 | `dashboard.py:329-331` | `formatted_patterns` 변수 생성 후 미사용 — 데드 코드 |
| L-3 | `naver_ocr.py:370-372` | OCR 날짜 파싱 실패 시 `date.today()` 폴백 — 사용자에게 경고 없음 |
| L-4 | `dashboard.py:309` | `getattr(r, 'actual_payment_method', None)` — 모델에 필드 존재하므로 불필요 |

---

## 7. 전체 아키텍처 평가

### 잘된 점
- 역할 기반 접근 제어 (boss/staff) 일관 적용
- 텔레그램 initData HMAC 검증으로 미니앱 인증 구현
- ConversationHandler를 활용한 복잡한 예약 플로우 관리
- 알림 메시지 ID 추적 → edit_message로 카드 업데이트 (UX 우수)
- 글로벌 에러 핸들러 + 로깅
- 매일 아침 9시 자동 일정 알림 스케줄러
- 복수 품목 지원 + 자동 가격 계산

### 개선 권장
- Calendar API 입력값 검증 (year/month 범위 체크)
- 상태 전환 서비스에서 허용된 전환만 수행하도록 validation 추가
- 매출 통계 by_item/by_method에도 기간 필터 적용
- `customer_name` 필드명을 `display_name` 등으로 변경 검토

---

**테스트 결과**: Critical 0 / High 1 / Medium 3 / Low 4
**판정**: 기능적으로 안정적. H-1 초대코드는 환경변수 설정으로 해결 가능. M-1 calendar 입력값 검증 추가 권장.
