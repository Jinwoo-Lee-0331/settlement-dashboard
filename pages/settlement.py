"""정산 결과 페이지 - 라이더별 주간 정산 상세 표 + 검색."""

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, callback, dash_table, html

import data
from components import kpi_card, page_header, won

dash.register_page(__name__, path="/settlement", name="정산 결과")

COLUMNS = [
    {"name": "이름", "id": "name"},
    {"name": "총오더수", "id": "orders"},
    {"name": "총정산금액", "id": "gross"},
    {"name": "보험환급액", "id": "ins_refund"},
    {"name": "정산예정금액", "id": "expected"},
    {"name": "수수료", "id": "commission"},
    {"name": "원천세(3.3%)", "id": "withholding"},
    {"name": "선정산", "id": "prepaid"},
    {"name": "최종정산금액", "id": "final"},
]

MONEY_FIELDS = {"gross", "ins_refund", "expected", "commission",
                 "withholding", "prepaid", "final"}


def _settlement_records(df):
    recs = []
    for _, r in df.iterrows():
        rec = {"name": r["name"], "orders": f"{r['orders']:,}건"}
        for field in MONEY_FIELDS:
            rec[field] = won(r[field])
        recs.append(rec)
    return recs


def layout():
    df = data.SETTLEMENT
    total_gross = int(df["gross"].sum())
    total_final = int(df["final"].sum())
    return html.Div([
        page_header("정산 결과", "라이더별 이번 주 정산 상세 내역입니다."),
        dbc.Row(
            [
                kpi_card("정산 대상 라이더", f"{len(df)}명", "👥"),
                kpi_card("총 정산금액", won(total_gross), "💰"),
                kpi_card("최종 정산금액 합계", won(total_final), "📊"),
            ],
            className="g-3 mb-3",
        ),
        dbc.Input(id="settlement-search", placeholder="라이더 검색...",
                  style={"maxWidth": "280px"}, className="mb-2"),
        html.Div(id="settlement-count", className="text-muted mb-2"),
        dash_table.DataTable(
            id="settlement-table",
            columns=COLUMNS,
            data=_settlement_records(df),
            sort_action="native",
            page_size=12,
            style_cell={"padding": "10px", "fontSize": "13px",
                        "textAlign": "left", "fontFamily": "inherit"},
            style_header={"backgroundColor": "#f8f9fb", "fontWeight": "600"},
            style_table={"overflowX": "auto"},
        ),
    ])


@callback(
    Output("settlement-table", "data"),
    Output("settlement-count", "children"),
    Input("settlement-search", "value"),
)
def _filter(query):
    df = data.SETTLEMENT
    if query:
        q = query.strip()
        df = df[df["name"].str.contains(q, na=False)]
    return _settlement_records(df), f"정산 대상 라이더수 : {len(df)}명"
