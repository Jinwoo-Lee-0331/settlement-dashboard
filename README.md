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
│  ├─ settlement.py  # 정산 결과 (항목별 합산 + 라이더별 상세표 + 검색)
│  └─ riders.py      # 라이더 관리 (목록 + 상태필터/검색 + 렌탈·대여 현황)
├─ assets/style.css  # 스타일 (Dash가 assets/ 자동 로드)
└─ requirements.txt
```

## 실행

```bash
pip install -r requirements.txt
python app.py
```

브라우저에서 http://127.0.0.1:8050 접속.

## 다음 단계 (실서비스로 확장 시)

1. **데이터 소스 교체** — `data.py`의 샘플 생성부를 DB(PostgreSQL 등) 조회 또는
   쿠팡 정산표 엑셀 파싱(`dcc.Upload` + pandas)으로 대체.
2. **멀티테넌트/인증** — Flask-Login 세션으로 협력업체별 로그인 분리
   (Dash는 Flask 위에서 동작하므로 `app.server`에 붙이면 됩니다).
3. **라이더 공유 URL** — 정산플러스의 rider-signup / rider-settlement 처럼
   토큰 기반 개별 조회 페이지 추가.
4. **엑셀 다운로드** — 정산 결과를 xlsx로 내보내기(`dcc.Download` + pandas).
5. **배포** — 개발 서버 대신 `gunicorn app:server` (Linux) 또는 waitress(Windows).