# 배달기사 정산 대시보드 (MVP)

정산플러스(배플) 화면 구조를 참고한 Python Dash 프로토타입입니다.

## 구성

```
settlement_dashboard/
├─ app.py            # 메인 앱 (사이드바 + 멀티페이지 셸)
├─ data.py           # 샘플 데이터 생성 (실제 서비스에선 DB/엑셀 파싱으로 대체)
├─ components.py     # 공용 UI (사이드바, KPI 카드, 원화 포맷)
├─ pages/
│  ├─ dashboard.py   # 대시보드 (KPI + 주간 정산 차트 + 라이더 현황 파이)
│  ├─ settlement.py  # 정산 결과 (항목별 합산 + 라이더별 상세표 + 검색 + 실제 엑셀 업로드)
│  └─ riders.py      # 라이더 관리 (목록 + 상태필터/검색 + 렌탈·대여 현황)
├─ parsers.py        # 쿠팡이츠/배민 정산 엑셀 파싱
├─ db.py             # 정산 데이터 영구 저장 (DATABASE_URL 있으면 Postgres, 없으면 SQLite)
├─ migrate_to_postgres.py  # 로컬 SQLite 데이터를 Postgres로 옮기는 일회성 스크립트
├─ assets/style.css  # 스타일 (Dash가 assets/ 자동 로드)
└─ requirements.txt
```

## 실행

```bash
pip install -r requirements.txt
python app.py
```

브라우저에서 http://127.0.0.1:8050 접속.

## 정산 데이터 저장소 (SQLite / Postgres)

`정산 결과` 페이지에서 쿠팡이츠·배민 정산 엑셀을 업로드하면 DB에 저장되어
재시작·재접속해도 마지막 업로드 데이터를 그대로 볼 수 있습니다.

- **로컬 개발**: 별도 설정 없이 프로젝트 폴더의 `settlement.db`(SQLite)를 자동 사용.
- **배포(Render 등)에서도 영구 보존하려면**: 환경변수 `DATABASE_URL`에 Postgres
  연결 문자열을 넣으면 자동으로 그쪽을 사용합니다 (무료 Postgres는 만료되지 않는
  [Neon](https://neon.tech) 추천).
  1. `.env.example`을 `.env`로 복사하고 `DATABASE_URL` 값을 채워 로컬에서 테스트.
  2. 기존 로컬 데이터를 옮기려면 `python migrate_to_postgres.py` 실행.
  3. Render 대시보드 → 서비스 → **Environment** 탭에 동일한 `DATABASE_URL`을 등록.

## 다음 단계 (실서비스로 확장 시)

1. **멀티테넌트/인증** — Flask-Login 세션으로 협력업체별 로그인 분리
   (Dash는 Flask 위에서 동작하므로 `app.server`에 붙이면 됩니다).
2. **라이더 공유 URL** — 정산플러스의 rider-signup / rider-settlement 처럼
   토큰 기반 개별 조회 페이지 추가.
3. **엑셀 다운로드** — 정산 결과를 xlsx로 내보내기(`dcc.Download` + pandas).
4. **배포** — 개발 서버 대신 `gunicorn app:server` (Linux) 또는 waitress(Windows).