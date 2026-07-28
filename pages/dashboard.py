"""대시보드 페이지 - 실제 업로드 데이터 기반 KPI + 주간 정산 추이 + 라이더 현황."""

from collections import defaultdict
from datetime import datetime, timedelta

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import dcc, html
from plotly.subplots import make_subplots

import db
from components import kpi_card, page_header, won

dash.register_page(__name__, path="/", name="대시보드")

# 색상 (정산플러스 톤: 보라/파랑 계열)
PURPLE = "#8b8bf0"
BLUE = "#4a7bf7"
PIE_COLORS = {"활성": "#22c55e", "휴면": "#9ca3af"}


def _empty_state():
    return dbc.Alert(
        "아직 업로드된 정산 데이터가 없습니다. '정산 결과' 페이지에서 "
        "쿠팡이츠·배민 엑셀을 업로드하면 대시보드가 자동으로 채워집니다.",
        color="info",
    )


def _week_start(d):
    return d - timedelta(days=d.weekday())


def _weekly_trend() -> list[dict]:
    """저장된 전체 이력을 월~일 기준 주 단위로 묶어 (최근) 주간 배달건수/정산액 집계."""
    bounds = db.load_date_bounds()
    if not bounds:
        return []
    rows = db.load_records_in_range(bounds[0], bounds[1])
    weekly = defaultdict(lambda: {"orders": 0.0, "final": 0.0})
    for r in rows:
        d = datetime.fromisoformat(r["settlement_date"]).date()
        wk = _week_start(d)
        weekly[wk]["orders"] += r.get("orders") or 0
        weekly[wk]["final"] += r.get("final") or 0
    weeks = sorted(weekly.keys())[-7:]
    return [{"week": w, **weekly[w]} for w in weeks]


def _weekly_figure(weekly: list[dict]) -> go.Figure:
    labels = [w["week"].strftime("%m.%d.") for w in weekly]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=labels, y=[w["orders"] for w in weekly], name="배달 건수",
                marker_color=PURPLE, offsetgroup=0)
    fig.add_bar(x=labels, y=[w["final"] for w in weekly], name="정산금액",
                marker_color=BLUE, offsetgroup=1, secondary_y=True)
    fig.update_layout(
        barmode="group",
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"),
        plot_bgcolor="white",
        height=340,
    )
    fig.update_yaxes(title_text="", showgrid=True, gridcolor="#eee")
    fig.update_yaxes(title_text="", secondary_y=True, showgrid=False)
    return fig


def _rider_state_counts(riders: list[dict], latest_date: str) -> dict:
    active = sum(1 for r in riders if r["last_date"] == latest_date)
    return {"활성": active, "휴면": len(riders) - active}


def _pie_figure(counts: dict) -> go.Figure:
    labels = list(counts.keys())
    values = list(counts.values())
    colors = [PIE_COLORS.get(s, "#999") for s in labels]
    fig = go.Figure(
        go.Pie(labels=labels, values=values, hole=0.0,
               marker_colors=colors, textinfo="label+percent")
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=True,
        legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"),
        height=340,
    )
    return fig


def layout():
    riders = db.load_all_rider_history()
    bounds = db.load_date_bounds()

    if not riders or not bounds:
        return html.Div([
            page_header("대시보드", "라이더 정산 관리 시스템에 오신 것을 환영합니다."),
            _empty_state(),
        ])

    latest_date = bounds[1]
    latest_d = datetime.fromisoformat(latest_date).date()

    # 최근 정산일이 속한 주(월~일) 정산액 · 미션 달성 라이더 수
    week_start = _week_start(latest_d)
    week_end = week_start + timedelta(days=6)
    week_rows = db.load_records_in_range(week_start.isoformat(), week_end.isoformat())
    week_amount = int(sum(r.get("final") or 0 for r in week_rows))
    week_mission_riders = len({r["name"] for r in week_rows if r.get("mission_all_clear")})

    # 최근 정산일이 속한 달 배달건수
    month_start = latest_d.replace(day=1)
    month_rows = db.load_records_in_range(month_start.isoformat(), latest_date)
    month_orders = int(sum(r.get("orders") or 0 for r in month_rows))

    weekly = _weekly_trend()
    state_counts = _rider_state_counts(riders, latest_date)

    return html.Div(
        [
            page_header("대시보드", "라이더 정산 관리 시스템에 오신 것을 환영합니다."),
            dbc.Row(
                [
                    kpi_card("총 라이더 수", f"{len(riders)}명", "👥"),
                    kpi_card("이번 주 정산액", won(week_amount), "📈"),
                    kpi_card("이번주 미션 달성 라이더", f"{week_mission_riders}명", "🔔"),
                    kpi_card("이번 달 배달 건수", f"{month_orders:,}건", "📦"),
                ],
                className="g-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody([
                                html.H5("주간 정산 요약", className="card-title"),
                                html.P("최근 7개 주간보고서 정산 현황입니다.",
                                       className="card-sub"),
                                dcc.Graph(figure=_weekly_figure(weekly),
                                          config={"displayModeBar": False}),
                            ]),
                            className="panel",
                        ),
                        lg=8, md=12,
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody([
                                html.H5("라이더 현황", className="card-title"),
                                html.P("최근 정산일 기준 활성/휴면 현황입니다.",
                                       className="card-sub"),
                                dcc.Graph(figure=_pie_figure(state_counts),
                                          config={"displayModeBar": False}),
                            ]),
                            className="panel",
                        ),
                        lg=4, md=12,
                    ),
                ],
                className="g-3 mt-1",
            ),
        ]
    )
