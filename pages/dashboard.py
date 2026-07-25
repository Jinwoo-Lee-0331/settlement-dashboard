"""대시보드 페이지 - KPI 카드 + 주간 정산 요약 차트 + 라이더 현황 파이차트."""

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import dcc, html
from plotly.subplots import make_subplots

import data
from components import kpi_card, page_header, won

dash.register_page(__name__, path="/", name="대시보드")

# 색상 (정산플러스 톤: 보라/파랑 계열)
PURPLE = "#8b8bf0"
BLUE = "#4a7bf7"
PIE_COLORS = {"활성": "#22c55e", "휴직": "#f59e0b", "계약종료": "#ef4444"}


def _weekly_figure() -> go.Figure:
    df = data.WEEKLY
    labels = [d.strftime("%m.%d.") for d in df["week"]]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=labels, y=df["orders"], name="배달 건수",
                marker_color=PURPLE, offsetgroup=0)
    fig.add_bar(x=labels, y=df["amount"], name="정산금액",
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


def _pie_figure() -> go.Figure:
    df = data.rider_state_counts()
    colors = [PIE_COLORS.get(s, "#999") for s in df["state"]]
    fig = go.Figure(
        go.Pie(labels=df["state"], values=df["count"], hole=0.0,
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
    k = data.kpis()
    return html.Div(
        [
            page_header("대시보드", "라이더 정산 관리 시스템에 오신 것을 환영합니다."),
            dbc.Row(
                [
                    kpi_card("총 라이더 수", f"{k['total_riders']}명", "👥"),
                    kpi_card("이번 주 정산액", won(k["week_amount"]), "📈"),
                    kpi_card("이번주 선정산 건수", f"{k['prepaid_count']}건", "🔔"),
                    kpi_card("이번 달 배달 건수", f"{k['month_orders']:,}건", "📦"),
                ],
                className="g-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody([
                                html.H5("주간 정산 요약", className="card-title"),
                                html.P("최근 7개의 주간보고서 정산 현황입니다.",
                                       className="card-sub"),
                                dcc.Graph(figure=_weekly_figure(),
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
                                html.P("라이더 상태 요약입니다.",
                                       className="card-sub"),
                                dcc.Graph(figure=_pie_figure(),
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