"""쿠팡이츠 / 배민 정산 엑셀 파싱 모듈.

두 플랫폼 파트너센터에서 내려받은 (비밀번호로 보호된) 엑셀 파일을 읽어
라이더별 정산 데이터로 변환합니다.
"""

import io

import msoffcrypto
import pandas as pd


def decrypt_excel(file_bytes: bytes, password: str) -> io.BytesIO:
    """비밀번호로 보호된 xlsx 바이트를 복호화해 메모리 버퍼로 반환."""
    buf = io.BytesIO(file_bytes)
    office_file = msoffcrypto.OfficeFile(buf)
    office_file.load_key(password=password)
    out = io.BytesIO()
    office_file.decrypt(out)
    out.seek(0)
    return out


def _get(df: pd.DataFrame, level0: str, level1: str | None = None) -> pd.Series:
    """MultiIndex 컬럼에서 (상위헤더, 하위헤더)로 컬럼을 찾는다.

    쿠팡이츠 리포트는 병합 셀 헤더를 쓰기 때문에 하위헤더가 없는 컬럼은
    pandas가 'Unnamed: N_level_1'로 채운다. level1=None이면 그런 컬럼을 찾는다.
    """
    for col in df.columns:
        c0, c1 = col
        if c0 != level0:
            continue
        if level1 is None:
            if str(c1).startswith("Unnamed"):
                return df[col]
        elif c1 == level1:
            return df[col]
    raise KeyError(f"컬럼을 찾을 수 없습니다: {level0} / {level1}")


def extract_coupang_settlement_date(file_bytes: bytes, password: str) -> str:
    """쿠팡이츠 '종합' 시트 상단에 찍힌 정산 기준일(예: 2026-07-23)을 추출."""
    decrypted = decrypt_excel(file_bytes, password)
    head = pd.read_excel(decrypted, sheet_name="종합", header=None, nrows=5)
    raw = head.iloc[3, 1]
    return str(raw).split(" ")[0]


def parse_coupang(file_bytes: bytes, password: str) -> pd.DataFrame:
    """쿠팡이츠 '일별 정산 리포트' 엑셀 → 라이더별 정산 데이터.

    반환 컬럼: name, orders, gross, employ_ins, accident_ins, hourly_ins,
               promo, other_expense, expected, final
    """
    decrypted = decrypt_excel(file_bytes, password)
    df = pd.read_excel(decrypted, sheet_name="종합", header=[11, 12])
    df = df.dropna(subset=[df.columns[1]])  # 라이선스 ID가 없는 빈 행/각주 행 제거

    name_raw = _get(df, "성함")
    out = pd.DataFrame({
        "name_raw": name_raw,
        "orders": _get(df, "총 정산 오더수"),
        "gross": _get(df, "①과세 항목", "총 정산금액"),
        "employ_ins": _get(df, "비과세 항목", "③기사부담 고용보험").abs(),
        "accident_ins": _get(df, "비과세 항목", "⑤기사부담 산재보험").abs(),
        "hourly_ins": _get(df, "비과세 항목", "⑥시간제보험").abs(),
        "promo": _get(df, "총 지원금"),
        "other_expense": _get(df, "차감내역").abs(),
        "expected": _get(df, "정산 예정금액"),
        "final": _get(df, "라이더별 실지급액"),
    })
    # 성함 컬럼이 "배우람1752"처럼 이름+식별용 숫자로 되어 있어 뒤 숫자를 제거
    out["name"] = out["name_raw"].astype(str).str.replace(r"\d+$", "", regex=True).str.strip()
    out = out.drop(columns=["name_raw"]).dropna(subset=["name"])
    out = out[out["name"] != "nan"]
    numeric_cols = [c for c in out.columns if c != "name"]
    out[numeric_cols] = out[numeric_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    return out.groupby("name", as_index=False)[numeric_cols].sum()


def parse_baemin(file_bytes: bytes, password: str) -> pd.DataFrame:
    """배민 '배달처리비' 상세 엑셀(주문 단위) → 날짜·라이더별 집계.

    하나의 파일에 여러 운행일이 섞여 있을 수 있어 날짜별로 묶는다.
    반환 컬럼: date(YYYY-MM-DD), name, orders, gross (배달처리비 합계)
    """
    decrypted = decrypt_excel(file_bytes, password)
    df = pd.read_excel(decrypted, sheet_name=0, header=0)
    df = df.dropna(subset=["라이더명"])
    df["date"] = pd.to_datetime(df["운행일"].astype(str), format="%Y%m%d").dt.strftime("%Y-%m-%d")
    grouped = (
        df.groupby(["date", "라이더명"])
        .agg(orders=("배달번호", "count"), gross=("배달처리비", "sum"))
        .reset_index()
        .rename(columns={"라이더명": "name"})
    )
    return grouped


def merge_platform_settlements(coupang_df: pd.DataFrame, baemin_df: pd.DataFrame) -> pd.DataFrame:
    """두 플랫폼 라이더별 정산 데이터를 이름 기준으로 합쳐 data.SETTLEMENT 스키마로 변환."""
    c = coupang_df.copy()
    b = baemin_df.copy().rename(columns={"orders": "orders_baemin", "gross": "gross_baemin"})

    merged = pd.merge(c, b, on="name", how="outer").fillna(0).infer_objects(copy=False)

    result = pd.DataFrame({
        "name": merged["name"],
        "orders": merged["orders"] + merged["orders_baemin"],
        "gross": merged["gross"] + merged["gross_baemin"],
        "employ_ins": merged["employ_ins"],
        "accident_ins": merged["accident_ins"],
        "hourly_ins": merged["hourly_ins"],
        "ins_refund": 0,
        "expected": merged["expected"] + merged["gross_baemin"],
        "promo": merged["promo"],
        "other_income": 0,
        "commission": 0,
        "withholding": 0,
        "rental": 0,
        "lease": 0,
        "prepaid": 0,
        "other_expense": merged["other_expense"],
        "final": merged["final"] + merged["gross_baemin"],
    })
    result.insert(0, "rider_id", range(1, len(result) + 1))
    return result


_EMPTY_COUPANG_COLS = ["name", "orders", "gross", "employ_ins", "accident_ins",
                        "hourly_ins", "promo", "other_expense", "expected", "final"]
_EMPTY_BAEMIN_COLS = ["name", "orders", "gross"]


def parse_and_merge_multi(
    coupang_files: list[tuple[bytes, str]], coupang_password: str,
    baemin_files: list[tuple[bytes, str]], baemin_password: str,
) -> dict[str, pd.DataFrame]:
    """여러 쿠팡이츠/배민 파일을(각각 (파일바이트, 파일명) 목록) 정산일 기준으로 병합.

    쿠팡이츠는 파일 하나 = 하루치, 배민은 파일 하나에 여러 날짜가 섞여 있을 수
    있어 각각 날짜별로 나눈 뒤, 같은 날짜끼리 merge_platform_settlements로 합친다.
    반환: {settlement_date: 병합된 DataFrame(+platforms 컬럼)}
    """
    coupang_by_date: dict[str, pd.DataFrame] = {}
    for file_bytes, _filename in coupang_files:
        date = extract_coupang_settlement_date(file_bytes, coupang_password)
        df = parse_coupang(file_bytes, coupang_password)
        if date in coupang_by_date:
            df = pd.concat([coupang_by_date[date], df])
            numeric_cols = [c for c in df.columns if c != "name"]
            df = df.groupby("name", as_index=False)[numeric_cols].sum()
        coupang_by_date[date] = df

    baemin_by_date: dict[str, pd.DataFrame] = {}
    for file_bytes, _filename in baemin_files:
        df = parse_baemin(file_bytes, baemin_password)
        for date, sub in df.groupby("date"):
            sub = sub.drop(columns=["date"])
            if date in baemin_by_date:
                sub = pd.concat([baemin_by_date[date], sub])
                sub = sub.groupby("name", as_index=False)[["orders", "gross"]].sum()
            baemin_by_date[date] = sub

    result: dict[str, pd.DataFrame] = {}
    for date in sorted(set(coupang_by_date) | set(baemin_by_date)):
        c_df = coupang_by_date.get(date, pd.DataFrame(columns=_EMPTY_COUPANG_COLS))
        b_df = baemin_by_date.get(date, pd.DataFrame(columns=_EMPTY_BAEMIN_COLS))
        merged = merge_platform_settlements(c_df, b_df)

        has_coupang = set(c_df["name"])
        has_baemin = set(b_df["name"])

        def _platforms(name, has_coupang=has_coupang, has_baemin=has_baemin):
            tags = []
            if name in has_coupang:
                tags.append("coupang")
            if name in has_baemin:
                tags.append("baemin")
            return ",".join(tags)

        merged["platforms"] = merged["name"].map(_platforms)
        result[date] = merged

    return result
