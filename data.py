"""샘플 데이터 생성 모듈.

실제 서비스에서는 이 모듈이 DB 조회 / 엑셀 파싱 결과로 대체됩니다.
지금은 정산플러스 화면 구조에 맞춘 가짜 데이터를 메모리에서 생성합니다.
난수 시드를 고정해 실행할 때마다 동일한 데이터가 나오도록 했습니다.
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)

# 원천세율(정산플러스 화면의 3.3%)
WITHHOLDING_RATE = 0.033

KOREAN_SURNAMES = list("김이박최정강조윤장임한오서신권황안송류전홍")
KOREAN_GIVEN = ["두영", "제우", "주용", "성근", "태화", "근수", "큰복", "재호",
                "정윤", "광명", "재호", "현석", "민준", "서준", "도윤", "예준",
                "시우", "하준", "지호", "준우", "현우", "지훈", "우진", "선호"]

RIDER_STATES = ["활성", "활성", "활성", "활성", "휴직", "계약종료"]


def _make_name(i: int) -> str:
    s = KOREAN_SURNAMES[i % len(KOREAN_SURNAMES)]
    g = KOREAN_GIVEN[(i * 7) % len(KOREAN_GIVEN)]
    return f"{s}{g}"


def _make_phone(i: int) -> str:
    mid = 1000 + (i * 37) % 9000
    end = 1000 + (i * 53) % 9000
    return f"010-{mid}-{end}"


def make_riders(n: int = 120) -> pd.DataFrame:
    """라이더 마스터 데이터."""
    today = date(2026, 7, 22)
    rows = []
    for i in range(n):
        state = RIDER_STATES[i % len(RIDER_STATES)]
        joined = today - timedelta(days=int(RNG.integers(1, 400)))
        rows.append({
            "rider_id": i + 1,
            "name": _make_name(i),
            "phone": _make_phone(i),
            "state": state,
            "joined": joined,
            "rental": bool(RNG.random() < 0.09),   # 렌탈 진행 여부
            "lease": bool(RNG.random() < 0.12),     # 대여 진행 여부
        })
    return pd.DataFrame(rows)


def make_settlement(riders: pd.DataFrame) -> pd.DataFrame:
    """주간 정산 결과 데이터 (라이더별 상세).

    정산플러스 '정산 결과' 화면의 컬럼 구조를 따릅니다:
    총정산금액, 총오더수, 고용/산재/시간제보험, 보험환급액,
    정산예정금액, 프로모션, 기타수입, 수수료, 원천세(3.3%),
    렌탈료, 대여금, 선정산, 기타지출, 최종정산금액
    """
    active = riders[riders["state"] == "활성"].copy()
    rows = []
    for _, r in active.iterrows():
        orders = int(RNG.integers(80, 620))
        avg_fee = RNG.integers(3200, 4300)
        gross = int(orders * avg_fee)                        # 총 정산금액

        employ_ins = int(gross * 0.009)                       # 고용보험
        accident_ins = int(gross * 0.007)                     # 산재보험
        hourly_ins = int(gross * 0.004)                        # 시간제보험
        ins_refund = int(RNG.integers(0, 30000))               # 보험환급액

        promo = int(RNG.integers(0, 6)) * 10000                # 프로모션
        other_income = int(RNG.integers(0, 4)) * 5000          # 기타수입

        # 정산 예정금액 = 총정산금액 - 보험 + 보험환급 + 프로모션 + 기타수입
        expected = gross - employ_ins - accident_ins - hourly_ins \
            + ins_refund + promo + other_income

        commission = int(gross * 0.03)                         # 수수료
        withholding = int(expected * WITHHOLDING_RATE)         # 원천세 3.3%
        rental = int(RNG.integers(0, 2)) * int(RNG.integers(50000, 90000))
        lease = int(RNG.integers(0, 2)) * int(RNG.integers(80000, 130000))
        prepaid = int(RNG.integers(0, 3)) * 50000              # 선정산
        other_expense = int(RNG.integers(0, 3)) * 3000         # 기타지출

        final = expected - commission - withholding - rental \
            - lease - prepaid - other_expense                  # 최종 정산금액

        rows.append({
            "rider_id": r["rider_id"],
            "name": r["name"],
            "orders": orders,
            "gross": gross,
            "employ_ins": employ_ins,
            "accident_ins": accident_ins,
            "hourly_ins": hourly_ins,
            "ins_refund": ins_refund,
            "expected": expected,
            "promo": promo,
            "other_income": other_income,
            "commission": commission,
            "withholding": withholding,
            "rental": rental,
            "lease": lease,
            "prepaid": prepaid,
            "other_expense": other_expense,
            "final": final,
        })
    return pd.DataFrame(rows)


def make_weekly_trend(n_weeks: int = 7) -> pd.DataFrame:
    """대시보드 주간 정산 요약 차트용 데이터."""
    start = date(2026, 6, 1)
    rows = []
    for w in range(n_weeks):
        wk = start + timedelta(weeks=w)
        orders = int(RNG.integers(2000, 10000))
        amount = int(orders * RNG.integers(5500, 6500))
        rows.append({"week": wk, "orders": orders, "amount": amount})
    return pd.DataFrame(rows)


# 모듈 로드 시 1회 생성해 공유 (프로토타입이므로 전역 캐시)
RIDERS = make_riders()
SETTLEMENT = make_settlement(RIDERS)
WEEKLY = make_weekly_trend()


def kpis() -> dict:
    """대시보드 상단 KPI 카드 값."""
    total_riders = len(RIDERS)
    week_amount = int(SETTLEMENT["final"].sum())
    prepaid_count = int((SETTLEMENT["prepaid"] > 0).sum())
    month_orders = int(WEEKLY["orders"].tail(4).sum())
    return {
        "total_riders": total_riders,
        "week_amount": week_amount,
        "prepaid_count": prepaid_count,
        "month_orders": month_orders,
    }


def rider_state_counts() -> pd.DataFrame:
    """라이더 현황 파이차트용 상태별 집계."""
    counts = RIDERS["state"].value_counts().reset_index()
    counts.columns = ["state", "count"]
    return counts