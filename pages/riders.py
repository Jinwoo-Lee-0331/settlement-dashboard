"""라이더 관리 페이지 - 실제 업로드된 정산 데이터에서 집계한 라이더 목록 + 검색/상태 필터."""

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, callback, dash_table, html

import db
from components import page_header, won

dash.register_page(__name__, path="/riders", name="라이더 관리")

COLUMNS = [
    {"name": "이름", "id": "name"},
    {"name": "플랫폼", "id": "platforms"},
    {"name": "상태", "id": "state"},
    {"name": "최초 활동일", "id": "first_date"},
    {"name": "최근 활동일", "id": "last_date"},
    {"name": "누적 오더수", "id": "orders"},
    {"name": "누적 정산액", "id": "gross"},
]


def _riders_with_state():
    """업로드된 모든 정산 배치를 통틀어 라이더별 누적 통계 + 활성/휴면 상태."""
    riders = db.load_all_rider_history()
    if not riders:
        return [], None
    latest_date = max(r["last_date"] for r in riders)
    for r in riders:
        r["state"] = "활성" if r["last_date"] == latest_date else "휴면"
    return riders, latest_date


def _display_records(riders):
    return [
        {
            "name": r["name"],
            "platforms": r["platforms"],
            "state": r["state"],
            "first_date": r["first_date"],
            "last_date": r["last_date"],
            "orders": f"{int(r['orders']):,}건",
            "gross": won(r["gross"]),
        }
        for r in riders
    ]


def _dormant_panel(riders, latest_date):
    dormant = sorted((r for r in riders if r["state"] == "휴면"),
                      key=lambda r: r["last_date"], reverse=True)[:15]

    def item(r):
        return dbc.ListGroupItem([
            html.Div([html.Span(r["name"], className="fw-bold"),
                      dbc.Badge(r["platforms"] or "-", color="info", className="ms-2")]),
            html.Small(f"최근 활동일: {r['last_date']}", className="text-muted"),
        ])

    items = [item(r) for r in dormant] or \
        [dbc.ListGroupItem("휴면 라이더가 없습니다.", className="text-muted")]

    return dbc.Card(dbc.CardBody([
        html.H6(f"😴 최근 활동 없는 라이더 (최근 정산일 {latest_date} 기준)", className="mb-2"),
        dbc.ListGroup(items, flush=True, style={"maxHeight": "320px", "overflowY": "auto"}),
    ]), className="panel mt-3")


def _empty_state():
    return dbc.Alert(
        "아직 업로드된 정산 데이터가 없습니다. '정산 결과' 페이지에서 "
        "쿠팡이츠·배민 엑셀을 업로드하면 라이더 목록이 자동으로 채워집니다.",
        color="info",
    )


def layout():
    riders, latest_date = _riders_with_state()
    if not riders:
        return html.Div([
            page_header("라이더 관리", "실제 정산 데이터에서 집계한 라이더 목록입니다."),
            _empty_state(),
        ])

    return html.Div([
        page_header("라이더 관리", "실제 정산 데이터에서 집계한 라이더 목록입니다."),
        html.Div([
            dbc.Input(id="rider-search", placeholder="라이더 검색...",
                      style={"maxWidth": "280px"}),
            dbc.Select(
                id="rider-state-filter",
                options=[
                    {"label": "전체 상태", "value": "전체"},
                    {"label": "활성", "value": "활성"},
                    {"label": "휴면", "value": "휴면"},
                ],
                value="전체",
                style={"maxWidth": "160px"},
            ),
        ], className="d-flex gap-2 mb-2"),
        html.Div(id="rider-count", className="text-muted mb-2"),
        dash_table.DataTable(
            id="rider-table",
            columns=COLUMNS,
            data=_display_records(riders),
            sort_action="native",
            page_size=12,
            style_cell={"padding": "10px", "fontSize": "13px",
                        "textAlign": "left", "fontFamily": "inherit"},
            style_header={"backgroundColor": "#f8f9fb", "fontWeight": "600"},
            style_table={"overflowX": "auto"},
        ),
        _dormant_panel(riders, latest_date),
    ])


@callback(
    Output("rider-table", "data"),
    Output("rider-count", "children"),
    Input("rider-search", "value"),
    Input("rider-state-filter", "value"),
)
def _filter(query, state):
    riders, _ = _riders_with_state()
    if state and state != "전체":
        riders = [r for r in riders if r["state"] == state]
    if query:
        q = query.strip()
        riders = [r for r in riders if q in r["name"]]
    return _display_records(riders), f"등록된 라이더수 : {len(riders)}명"
