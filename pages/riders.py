"""라이더 관리 페이지 - 라이더 목록 표 + 상태 필터/검색 + 렌탈·대여 현황."""

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, callback, dash_table, html

import data
from components import page_header

dash.register_page(__name__, path="/riders", name="라이더 관리")

STATE_BADGE = {"활성": "success", "휴직": "warning", "계약종료": "danger"}


def _rider_records(df):
    recs = []
    for _, r in df.iterrows():
        j = r["joined"]
        # %-m/%-d는 Windows 미지원 → 직접 포맷
        joined = f"{j.year}. {j.month}. {j.day}." if hasattr(j, "year") else str(j)
        recs.append({
            "name": r["name"],
            "phone": r["phone"],
            "state": r["state"],
            "joined": joined,
        })
    return recs


def _rental_lease_lists():
    riders = data.RIDERS
    rentals = riders[riders["rental"]]
    leases = riders[riders["lease"]]

    def item(name, phone, tag):
        return dbc.ListGroupItem([
            html.Div([html.Span(name, className="fw-bold"),
                      dbc.Badge(tag, color="info", className="ms-2")]),
            html.Small(phone, className="text-muted"),
        ])

    rental_items = [item(r["name"], r["phone"], "렌탈")
                    for _, r in rentals.iterrows()] or \
        [dbc.ListGroupItem("진행 중인 렌탈이 없습니다.", className="text-muted")]
    lease_items = [item(r["name"], r["phone"], "대여")
                   for _, r in leases.iterrows()] or \
        [dbc.ListGroupItem("진행 중인 대여가 없습니다.", className="text-muted")]

    return dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H6(f"🛵 렌탈 진행 ({len(rentals)}명)", className="mb-2"),
            dbc.ListGroup(rental_items, flush=True,
                          style={"maxHeight": "260px", "overflowY": "auto"}),
        ]), className="panel"), md=6),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H6(f"🏍 대여 진행 ({len(leases)}명)", className="mb-2"),
            dbc.ListGroup(lease_items, flush=True,
                          style={"maxHeight": "260px", "overflowY": "auto"}),
        ]), className="panel"), md=6),
    ], className="g-3 mt-1")


def layout():
    df = data.RIDERS
    return html.Div([
        page_header("라이더 관리", "라이더 정보를 관리하고 정산 내역을 확인할 수 있습니다."),
        html.Div([
            dbc.Input(id="rider-search", placeholder="라이더 검색...",
                      style={"maxWidth": "280px"}),
            dbc.Select(
                id="rider-state-filter",
                options=[{"label": "전체 상태", "value": "전체"}] +
                        [{"label": s, "value": s}
                         for s in ["활성", "휴직", "계약종료"]],
                value="전체",
                style={"maxWidth": "160px"},
            ),
        ], className="d-flex gap-2 mb-2"),
        html.Div(id="rider-count", className="text-muted mb-2"),
        dash_table.DataTable(
            id="rider-table",
            columns=[
                {"name": "이름", "id": "name"},
                {"name": "연락처", "id": "phone"},
                {"name": "상태", "id": "state"},
                {"name": "가입일", "id": "joined"},
            ],
            data=_rider_records(df),
            sort_action="native",
            page_size=12,
            style_cell={"padding": "10px", "fontSize": "13px",
                        "textAlign": "left", "fontFamily": "inherit"},
            style_header={"backgroundColor": "#f8f9fb", "fontWeight": "600"},
        ),
        _rental_lease_lists(),
    ])


@callback(
    Output("rider-table", "data"),
    Output("rider-count", "children"),
    Input("rider-search", "value"),
    Input("rider-state-filter", "value"),
)
def _filter(query, state):
    df = data.RIDERS
    if state and state != "전체":
        df = df[df["state"] == state]
    if query:
        q = query.strip()
        df = df[df["name"].str.contains(q, na=False) |
                df["phone"].str.contains(q, na=False)]
    return _rider_records(df), f"등록된 라이더수 : {len(df)}명"