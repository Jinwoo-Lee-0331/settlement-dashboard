"""정산 결과 페이지 - 라이더별 주간 정산 상세 표 + 검색 + 실제 정산 엑셀 업로드(DB 영구 저장)."""

import base64

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dash_table, dcc, html

import data
import db
import parsers
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

RECORD_FIELDS = db.RECORD_FIELDS

UPLOAD_STYLE = {
    "width": "100%", "height": "56px", "lineHeight": "56px",
    "borderWidth": "1px", "borderStyle": "dashed", "borderRadius": "8px",
    "textAlign": "center", "cursor": "pointer", "fontSize": "13px",
    "color": "#6b7280",
}


def _sample_records():
    return data.SETTLEMENT[RECORD_FIELDS].to_dict("records")


def _initial_state():
    """DB에 저장된 마지막 업로드가 있으면 그걸, 없으면 샘플 데이터를 초기 표시."""
    latest = db.load_latest_batch()
    if latest is None:
        return _sample_records(), {"source": "sample"}
    records, meta = latest
    return records, {
        "source": "upload",
        "settlement_date": meta["settlement_date"],
        "uploaded_at": meta["uploaded_at"],
        "coupang_filename": meta["coupang_filename"],
        "baemin_filename": meta["baemin_filename"],
    }


def _settlement_display_records(records):
    recs = []
    for r in records:
        rec = {"name": r["name"], "orders": f"{int(r['orders']):,}건"}
        for field in MONEY_FIELDS:
            rec[field] = won(r[field])
        recs.append(rec)
    return recs


def _source_badge(meta):
    if not meta or meta.get("source") != "upload":
        return dbc.Badge("샘플 데이터 표시 중", color="secondary", className="mb-2")
    return dbc.Badge(
        f"실제 업로드 데이터 · 기준일 {meta['settlement_date']} "
        f"(업로드: {meta['uploaded_at']})",
        color="success", className="mb-2",
    )


def _upload_card():
    return dbc.Card(dbc.CardBody([
        html.H6("실제 정산 데이터 업로드", className="mb-1"),
        html.P("쿠팡이츠·배민 파트너센터에서 내려받은 정산 엑셀을 올리면 DB에 저장되어, "
               "다음에 다시 접속해도 최신 업로드 데이터를 볼 수 있습니다.",
               className="text-muted small mb-3"),
        dbc.Row([
            dbc.Col([
                html.Label("쿠팡이츠 정산 엑셀", className="small fw-bold mb-1 d-block"),
                dcc.Upload(
                    id="upload-coupang",
                    children=html.Div("파일을 선택하거나 끌어다 놓으세요", id="upload-coupang-label"),
                    className="upload-box",
                    style=UPLOAD_STYLE,
                ),
                dbc.Input(id="coupang-password", type="password",
                          placeholder="엑셀 비밀번호", className="mt-2"),
            ], md=6),
            dbc.Col([
                html.Label("배민 정산 엑셀", className="small fw-bold mb-1 d-block"),
                dcc.Upload(
                    id="upload-baemin",
                    children=html.Div("파일을 선택하거나 끌어다 놓으세요", id="upload-baemin-label"),
                    className="upload-box",
                    style=UPLOAD_STYLE,
                ),
                dbc.Input(id="baemin-password", type="password",
                          placeholder="엑셀 비밀번호", className="mt-2"),
            ], md=6),
        ], className="g-3"),
        dbc.Button("업로드 적용", id="apply-upload-btn", color="primary", className="mt-3"),
        html.Div(id="upload-status", className="mt-2"),
    ]), className="panel mb-3")


def layout():
    default_records, default_meta = _initial_state()
    return html.Div([
        page_header("정산 결과", "라이더별 정산 상세 내역입니다."),
        _upload_card(),
        html.Div(_source_badge(default_meta), id="settlement-source-badge"),
        html.Div(id="settlement-kpi-row"),
        dbc.Input(id="settlement-search", placeholder="라이더 검색...",
                  style={"maxWidth": "280px"}, className="mb-2"),
        html.Div(id="settlement-count", className="text-muted mb-2"),
        dash_table.DataTable(
            id="settlement-table",
            columns=COLUMNS,
            data=_settlement_display_records(default_records),
            sort_action="native",
            page_size=12,
            style_cell={"padding": "10px", "fontSize": "13px",
                        "textAlign": "left", "fontFamily": "inherit"},
            style_header={"backgroundColor": "#f8f9fb", "fontWeight": "600"},
            style_table={"overflowX": "auto"},
        ),
        dcc.Store(id="settlement-store", data=default_records),
        dcc.Store(id="settlement-meta-store", data=default_meta),
    ])


@callback(
    Output("upload-coupang-label", "children"),
    Input("upload-coupang", "filename"),
)
def _coupang_filename(filename):
    return filename or "파일을 선택하거나 끌어다 놓으세요"


@callback(
    Output("upload-baemin-label", "children"),
    Input("upload-baemin", "filename"),
)
def _baemin_filename(filename):
    return filename or "파일을 선택하거나 끌어다 놓으세요"


@callback(
    Output("settlement-store", "data"),
    Output("settlement-meta-store", "data"),
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
def _apply_upload(n_clicks, coupang_contents, coupang_filename, coupang_pw,
                   baemin_contents, baemin_filename, baemin_pw):
    if not coupang_contents or not baemin_contents:
        return dash.no_update, dash.no_update, dbc.Alert(
            "쿠팡이츠·배민 파일을 모두 선택해주세요.", color="warning", className="mb-0 py-2")
    if not coupang_pw or not baemin_pw:
        return dash.no_update, dash.no_update, dbc.Alert(
            "엑셀 비밀번호를 입력해주세요.", color="warning", className="mb-0 py-2")

    try:
        coupang_bytes = base64.b64decode(coupang_contents.split(",", 1)[1])
        baemin_bytes = base64.b64decode(baemin_contents.split(",", 1)[1])
        settlement_date = parsers.extract_coupang_settlement_date(coupang_bytes, coupang_pw)
        coupang_df = parsers.parse_coupang(coupang_bytes, coupang_pw)
        baemin_df = parsers.parse_baemin(baemin_bytes, baemin_pw)
        merged = parsers.merge_platform_settlements(coupang_df, baemin_df)
    except Exception as e:
        return dash.no_update, dash.no_update, dbc.Alert(
            f"파일 처리 중 오류가 발생했습니다: {e}", color="danger", className="mb-0 py-2")

    records = merged[RECORD_FIELDS].to_dict("records")
    db.save_batch(records, settlement_date, coupang_filename, baemin_filename)
    _, meta = db.load_latest_batch()
    meta["source"] = "upload"

    status = dbc.Alert(
        f"업로드 완료 및 저장됨 — {coupang_filename}, {baemin_filename} "
        f"(라이더 {len(records)}명, 기준일 {settlement_date})",
        color="success", className="mb-0 py-2")
    return records, meta, status


@callback(
    Output("settlement-source-badge", "children"),
    Input("settlement-meta-store", "data"),
)
def _render_badge(meta):
    return _source_badge(meta)


@callback(
    Output("settlement-table", "data"),
    Output("settlement-count", "children"),
    Output("settlement-kpi-row", "children"),
    Input("settlement-search", "value"),
    Input("settlement-store", "data"),
)
def _render(query, records):
    records = records or []
    total_gross = int(sum(r["gross"] for r in records))
    total_final = int(sum(r["final"] for r in records))
    kpis = dbc.Row(
        [
            kpi_card("정산 대상 라이더", f"{len(records)}명", "👥"),
            kpi_card("총 정산금액", won(total_gross), "💰"),
            kpi_card("최종 정산금액 합계", won(total_final), "📊"),
        ],
        className="g-3 mb-3",
    )

    filtered = records
    if query:
        q = query.strip()
        filtered = [r for r in records if q in r["name"]]

    return (_settlement_display_records(filtered),
            f"정산 대상 라이더수 : {len(filtered)}명",
            kpis)
