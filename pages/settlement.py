"""정산 결과 페이지 - 라이더별 일자별 정산 상세 + 검색 + 실제 정산 엑셀 업로드(다중 파일/DB 영구 저장) + 조회 모드."""

import base64
import os
from datetime import datetime, timedelta

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dash_table, dcc, html

import data
import db
import parsers
from components import kpi_card, page_header, won

DEFAULT_COUPANG_PASSWORD = os.environ.get("COUPANG_EXCEL_PASSWORD", "")
DEFAULT_BAEMIN_PASSWORD = os.environ.get("BAEMIN_EXCEL_PASSWORD", "")

dash.register_page(__name__, path="/settlement", name="정산 결과")

COLUMNS = [
    {"name": "일자", "id": "settlement_date"},
    {"name": "이름", "id": "name"},
    {"name": "플랫폼", "id": "platforms"},
    {"name": "총오더수", "id": "orders"},
    {"name": "오전점심피크", "id": "오전점심피크"},
    {"name": "오후논피크", "id": "오후논피크"},
    {"name": "저녁피크", "id": "저녁피크"},
    {"name": "심야", "id": "심야"},
    {"name": "총정산금액", "id": "gross"},
    {"name": "보험환급액", "id": "ins_refund"},
    {"name": "정산예정금액", "id": "expected"},
    {"name": "수수료", "id": "commission"},
    {"name": "원천세(3.3%)", "id": "withholding"},
    {"name": "선정산", "id": "prepaid"},
    {"name": "미션보너스", "id": "mission_bonus"},
    {"name": "최종정산금액", "id": "final"},
]

MONEY_FIELDS = {"gross", "ins_refund", "expected", "commission",
                 "withholding", "prepaid", "mission_bonus", "final"}

UPLOAD_STYLE = {
    "width": "100%", "height": "56px", "lineHeight": "56px",
    "borderWidth": "1px", "borderStyle": "dashed", "borderRadius": "8px",
    "textAlign": "center", "cursor": "pointer", "fontSize": "13px",
    "color": "#6b7280",
}


def _normalize_upload(contents, filenames):
    """dcc.Upload(multiple=True)의 contents/filename을 (내용, 파일명) 목록으로 정규화."""
    if not contents:
        return []
    if not isinstance(contents, list):
        contents = [contents]
        filenames = [filenames]
    return list(zip(contents, filenames))


def _normalize_names(filenames):
    if not filenames:
        return []
    return filenames if isinstance(filenames, list) else [filenames]


def _sample_records():
    recs = data.SETTLEMENT[db.RECORD_FIELDS].to_dict("records")
    for r in recs:
        r["platforms"] = "-"
        r["mission_bonus"] = 0
        r["settlement_date"] = "-"
        for b in parsers.MISSION_BUCKETS:
            r[b] = 0
    return recs


def _settlement_display_records(records):
    recs = []
    for r in records:
        rec = {
            "name": r["name"],
            "settlement_date": r.get("settlement_date", "-"),
            "orders": f"{int(r['orders']):,}건",
            "platforms": r.get("platforms") or "-",
        }
        for b in parsers.MISSION_BUCKETS:
            rec[b] = f"{int(r.get(b, 0)):,}건"
        for field in MONEY_FIELDS:
            rec[field] = won(r[field])
        recs.append(rec)
    return recs


def _compute_weekly_bonuses(start_date: str, end_date: str) -> dict[str, int]:
    """이름 -> 이 기간에 걸친 주(월~일)의 ALL CLEAR 6일 이상 달성 주간보너스 합계.

    주간 ALL CLEAR 횟수는 저장된 전체 이력을 기준으로 세되, 보너스는 그 주의
    시작일(월요일)이 선택한 기간 안에 있을 때만 이번 조회에 포함한다.
    """
    mission_days = db.load_mission_days()
    weeks: dict[tuple, int] = {}
    for r in mission_days:
        if not r["mission_all_clear"]:
            continue
        d = datetime.fromisoformat(r["settlement_date"]).date()
        week_start = d - timedelta(days=d.weekday())
        key = (r["name"], week_start)
        weeks[key] = weeks.get(key, 0) + 1

    range_start = datetime.fromisoformat(start_date).date()
    range_end = datetime.fromisoformat(end_date).date()

    bonuses: dict[str, int] = {}
    for (name, week_start), count in weeks.items():
        if count >= parsers.MISSION_WEEKLY_MIN_DAYS and range_start <= week_start <= range_end:
            bonuses[name] = bonuses.get(name, 0) + parsers.MISSION_WEEKLY_BONUS
    return bonuses


def _aggregate_by_day(rows: list[dict]) -> list[dict]:
    agg: dict[str, dict] = {}
    for r in rows:
        d = agg.setdefault(r["settlement_date"], {"date": r["settlement_date"], "gross": 0, "final": 0})
        d["gross"] += r.get("gross") or 0
        d["final"] += r.get("final") or 0
    return sorted(agg.values(), key=lambda x: x["date"])


def _build_kpis(rows: list[dict], weekly_total: int):
    names = {r["name"] for r in rows}
    total_gross = int(sum(r["gross"] for r in rows))
    total_final = int(sum(r["final"] for r in rows)) + weekly_total
    return dbc.Row(
        [
            kpi_card("정산 대상 라이더", f"{len(names)}명", "👥"),
            kpi_card("총 정산금액", won(total_gross), "💰"),
            kpi_card("주간보너스 합계", won(weekly_total), "🎁"),
            kpi_card("최종 정산금액 합계", won(total_final), "📊"),
        ],
        className="g-3 mb-3",
    )


def _table_rows(rows: list[dict], query: str | None):
    filtered = rows
    if query:
        q = query.strip()
        filtered = [r for r in rows if q in r["name"]]
    ordered = sorted(filtered, key=lambda r: (r.get("settlement_date", ""), -r["gross"]))
    return (_settlement_display_records(ordered),
            f"정산 대상 라이더수 : {len({r['name'] for r in filtered})}명")


def _source_badge_sample():
    return dbc.Badge("샘플 데이터 표시 중 (아직 업로드된 실제 데이터 없음)",
                      color="secondary", className="mb-2")


def _source_badge_upload(start_date, end_date):
    label = (f"실제 업로드 데이터 · {start_date}" if start_date == end_date
             else f"실제 업로드 데이터 · {start_date} ~ {end_date}")
    return dbc.Badge(label, color="success", className="mb-2")


def _trend_graph(per_day: list[dict]):
    dates = [d["date"] for d in per_day]
    fig = go.Figure()
    fig.add_bar(x=dates, y=[d["final"] for d in per_day], marker_color="#4f46e5")
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10), height=220,
        plot_bgcolor="white", showlegend=False,
    )
    fig.update_yaxes(showgrid=True, gridcolor="#eee")
    return dbc.Card(dbc.CardBody([
        html.H6("일자별 최종정산금액 추이", className="mb-2"),
        dcc.Graph(figure=fig, config={"displayModeBar": False}),
    ]), className="panel mb-3")


def _upload_card():
    return dbc.Card(dbc.CardBody([
        html.H6("실제 정산 데이터 업로드", className="mb-1"),
        html.P("쿠팡이츠·배민 정산 엑셀을 여러 날짜분 한꺼번에 올릴 수 있습니다. "
               "파일마다 날짜를 자동으로 인식해 날짜별로 나눠 저장하며, "
               "이미 저장된 날짜를 다시 올리면 그 날짜만 덮어씁니다.",
               className="text-muted small mb-3"),
        dbc.Row([
            dbc.Col([
                html.Label("쿠팡이츠 정산 엑셀 (여러 개 선택 가능)", className="small fw-bold mb-1 d-block"),
                dcc.Upload(
                    id="upload-coupang",
                    children=html.Div("파일을 선택하거나 끌어다 놓으세요", id="upload-coupang-label"),
                    className="upload-box", style=UPLOAD_STYLE, multiple=True,
                ),
                dbc.Input(id="coupang-password", type="password",
                          value=DEFAULT_COUPANG_PASSWORD,
                          placeholder="엑셀 비밀번호 (모든 쿠팡이츠 파일 공통)", className="mt-2"),
            ], md=6),
            dbc.Col([
                html.Label("배민 정산 엑셀 (여러 개 선택 가능)", className="small fw-bold mb-1 d-block"),
                dcc.Upload(
                    id="upload-baemin",
                    children=html.Div("파일을 선택하거나 끌어다 놓으세요", id="upload-baemin-label"),
                    className="upload-box", style=UPLOAD_STYLE, multiple=True,
                ),
                dbc.Input(id="baemin-password", type="password",
                          value=DEFAULT_BAEMIN_PASSWORD,
                          placeholder="엑셀 비밀번호 (모든 배민 파일 공통)", className="mt-2"),
            ], md=6),
        ], className="g-3"),
        dbc.Button("업로드 적용", id="apply-upload-btn", color="primary", className="mt-3"),
        html.Div(id="upload-status", className="mt-2"),
    ]), className="panel mb-3")


def _period_controls(min_date, max_date):
    single_style = {"display": "none"}
    range_style = {"display": "none"}
    return dbc.Card(dbc.CardBody([
        dbc.Row(
            [
                dbc.Col(
                    dbc.ButtonGroup([
                        dbc.Button("최근정산일", id="btn-mode-latest", size="sm",
                                   outline=True, color="secondary", active=True),
                        dbc.Button("일별조회", id="btn-mode-daily", size="sm",
                                   outline=True, color="secondary"),
                        dbc.Button("기간조회", id="btn-mode-range", size="sm",
                                   outline=True, color="secondary"),
                    ]),
                    width="auto",
                ),
                dbc.Col(
                    dcc.DatePickerSingle(
                        id="settlement-date-single",
                        min_date_allowed=min_date, max_date_allowed=max_date,
                        date=max_date, display_format="YYYY-MM-DD",
                        style=single_style,
                    ),
                    width="auto",
                ),
                dbc.Col(
                    dcc.DatePickerRange(
                        id="settlement-date-range",
                        min_date_allowed=min_date, max_date_allowed=max_date,
                        start_date=min_date, end_date=max_date,
                        display_format="YYYY-MM-DD",
                        style=range_style,
                    ),
                    width="auto",
                ),
            ],
            className="g-2 align-items-center",
        ),
        dcc.Store(id="settlement-mode-store", data="latest"),
    ]), className="panel mb-3 py-1")


def _db_backend_badge():
    backend = db.engine.url.get_backend_name()
    if backend == "sqlite":
        return dbc.Alert(
            "⚠ DB: SQLite(임시 파일) 사용 중 — Render 등 배포 환경에서는 재시작/재배포 시 "
            "데이터가 초기화됩니다. 영구 저장하려면 DATABASE_URL 환경변수에 Postgres "
            "연결 문자열을 등록하세요.",
            color="warning", className="mb-2 py-2",
        )
    host = db.engine.url.host or "-"
    dbname = db.engine.url.database or "-"
    bounds = db.load_date_bounds()
    bounds_text = f"저장된 정산일: {bounds[0]} ~ {bounds[1]}" if bounds else "저장된 정산일 없음"
    return html.Div([
        dbc.Badge(f"DB: {backend}@{host}/{dbname} 연결됨 (영구 저장)",
                  color="success", className="mb-1 d-block"),
        html.Small(bounds_text, className="text-muted d-block mb-2"),
    ])


def layout():
    bounds = db.load_date_bounds()
    min_date, max_date = bounds if bounds else (None, None)

    return html.Div([
        page_header("정산 결과", "라이더별 일자별 정산 상세 내역입니다."),
        _db_backend_badge(),
        _upload_card(),
        html.Div(id="settlement-source-badge"),
        _period_controls(min_date, max_date),
        html.Div(id="settlement-trend-graph-wrap"),
        html.Div(id="settlement-kpi-row"),
        dbc.Input(id="settlement-search", placeholder="라이더 검색...",
                  style={"maxWidth": "280px"}, className="mb-2"),
        html.Div(id="settlement-count", className="text-muted mb-2"),
        dash_table.DataTable(
            id="settlement-table",
            columns=COLUMNS,
            data=[],
            sort_action="native",
            page_size=15,
            style_cell={"padding": "10px", "fontSize": "13px",
                        "textAlign": "left", "fontFamily": "inherit"},
            style_header={"backgroundColor": "#f8f9fb", "fontWeight": "600"},
            style_table={"overflowX": "auto"},
        ),
    ])


@callback(
    Output("upload-coupang-label", "children"),
    Input("upload-coupang", "filename"),
)
def _coupang_filename(filenames):
    names = _normalize_names(filenames)
    return ", ".join(names) if names else "파일을 선택하거나 끌어다 놓으세요"


@callback(
    Output("upload-baemin-label", "children"),
    Input("upload-baemin", "filename"),
)
def _baemin_filename(filenames):
    names = _normalize_names(filenames)
    return ", ".join(names) if names else "파일을 선택하거나 끌어다 놓으세요"


@callback(
    Output("settlement-mode-store", "data", allow_duplicate=True),
    Output("settlement-date-range", "start_date", allow_duplicate=True),
    Output("settlement-date-range", "end_date", allow_duplicate=True),
    Output("settlement-date-range", "min_date_allowed", allow_duplicate=True),
    Output("settlement-date-range", "max_date_allowed", allow_duplicate=True),
    Output("settlement-date-single", "min_date_allowed", allow_duplicate=True),
    Output("settlement-date-single", "max_date_allowed", allow_duplicate=True),
    Output("settlement-date-single", "date", allow_duplicate=True),
    Output("upload-status", "children"),
    Input("apply-upload-btn", "n_clicks"),
    State("upload-coupang", "contents"),
    State("upload-coupang", "filename"),
    State("coupang-password", "value"),
    State("upload-baemin", "contents"),
    State("upload-baemin", "filename"),
    State("baemin-password", "value"),
    prevent_initial_call=True,
)
def _apply_upload(n_clicks, coupang_contents, coupang_filenames, coupang_pw,
                   baemin_contents, baemin_filenames, baemin_pw):
    no_change = (dash.no_update,) * 8

    coupang_list = _normalize_upload(coupang_contents, coupang_filenames)
    baemin_list = _normalize_upload(baemin_contents, baemin_filenames)

    if not coupang_list and not baemin_list:
        return *no_change, dbc.Alert(
            "쿠팡이츠·배민 파일을 최소 하나 이상 선택해주세요.", color="warning", className="mb-0 py-2")
    if coupang_list and not coupang_pw:
        return *no_change, dbc.Alert(
            "쿠팡이츠 엑셀 비밀번호를 입력해주세요.", color="warning", className="mb-0 py-2")
    if baemin_list and not baemin_pw:
        return *no_change, dbc.Alert(
            "배민 엑셀 비밀번호를 입력해주세요.", color="warning", className="mb-0 py-2")

    try:
        coupang_files = [(base64.b64decode(c.split(",", 1)[1]), fn) for c, fn in coupang_list]
        baemin_files = [(base64.b64decode(c.split(",", 1)[1]), fn) for c, fn in baemin_list]
        merged_by_date = parsers.parse_and_merge_multi(
            coupang_files, coupang_pw or "", baemin_files, baemin_pw or "")
    except Exception as e:
        return *no_change, dbc.Alert(
            f"파일 처리 중 오류가 발생했습니다: {e}", color="danger", className="mb-0 py-2")

    if not merged_by_date:
        return *no_change, dbc.Alert(
            "처리할 데이터를 찾지 못했습니다.", color="warning", className="mb-0 py-2")

    coupang_names = ", ".join(fn for _, fn in coupang_list) or "-"
    baemin_names = ", ".join(fn for _, fn in baemin_list) or "-"
    for date, df in merged_by_date.items():
        cols = (db.RECORD_FIELDS + ["platforms", "mission_bonus", "mission_all_clear"]
                + parsers.MISSION_BUCKETS)
        records = df[cols].to_dict("records")
        db.save_batch(records, date, coupang_names, baemin_names)

    dates = sorted(merged_by_date.keys())
    min_date, max_date = db.load_date_bounds()
    status = dbc.Alert(
        f"업로드 완료 및 저장됨 — {len(dates)}일치({dates[0]} ~ {dates[-1]}) 반영",
        color="success", className="mb-0 py-2")
    return ("range", dates[0], dates[-1], min_date, max_date,
            min_date, max_date, dates[-1], status)


@callback(
    Output("settlement-mode-store", "data", allow_duplicate=True),
    Input("btn-mode-latest", "n_clicks"),
    Input("btn-mode-daily", "n_clicks"),
    Input("btn-mode-range", "n_clicks"),
    prevent_initial_call=True,
)
def _set_mode(n_latest, n_daily, n_range):
    trigger = dash.ctx.triggered_id
    return {
        "btn-mode-latest": "latest",
        "btn-mode-daily": "daily",
        "btn-mode-range": "range",
    }.get(trigger, "latest")


@callback(
    Output("settlement-date-single", "style"),
    Output("settlement-date-range", "style"),
    Output("btn-mode-latest", "active"),
    Output("btn-mode-daily", "active"),
    Output("btn-mode-range", "active"),
    Input("settlement-mode-store", "data"),
)
def _toggle_pickers(mode):
    single_style = {"display": "inline-block"} if mode == "daily" else {"display": "none"}
    range_style = {"display": "inline-block"} if mode == "range" else {"display": "none"}
    return single_style, range_style, mode == "latest", mode == "daily", mode == "range"


@callback(
    Output("settlement-table", "data"),
    Output("settlement-count", "children"),
    Output("settlement-kpi-row", "children"),
    Output("settlement-source-badge", "children"),
    Output("settlement-trend-graph-wrap", "children"),
    Input("settlement-search", "value"),
    Input("settlement-mode-store", "data"),
    Input("settlement-date-single", "date"),
    Input("settlement-date-range", "start_date"),
    Input("settlement-date-range", "end_date"),
)
def _render(query, mode, single_date, range_start, range_end):
    bounds = db.load_date_bounds()
    if not bounds:
        table_data, count_text = _table_rows(_sample_records(), query)
        kpis = _build_kpis(_sample_records(), 0)
        return table_data, count_text, kpis, _source_badge_sample(), None

    min_date, max_date = bounds
    if mode == "daily":
        day = single_date or max_date
        start_date = end_date = day
    elif mode == "range":
        start_date = range_start or min_date
        end_date = range_end or max_date
    else:
        start_date = end_date = max_date

    raw_rows = db.load_records_in_range(start_date, end_date)
    if not raw_rows:
        empty_alert = dbc.Alert("선택한 기간에 업로드된 데이터가 없습니다.",
                                 color="warning", className="mb-0 py-2")
        return [], "정산 대상 라이더수 : 0명", dbc.Row(className="g-3 mb-3"), empty_alert, None

    weekly_bonuses = _compute_weekly_bonuses(start_date, end_date)
    weekly_total = sum(weekly_bonuses.values())

    per_day = _aggregate_by_day(raw_rows)
    table_data, count_text = _table_rows(raw_rows, query)
    kpis = _build_kpis(raw_rows, weekly_total)
    badge = _source_badge_upload(start_date, end_date)
    trend = _trend_graph(per_day) if len(per_day) > 1 else None
    return table_data, count_text, kpis, badge, trend
