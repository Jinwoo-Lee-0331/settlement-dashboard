"""공용 UI 컴포넌트 (사이드바, KPI 카드 등)."""

import dash_bootstrap_components as dbc
from dash import html

BRAND = "정산플러스 - 배플"

NAV_ITEMS = [
    ("대시보드", "/"),
    ("정산 결과", "/settlement"),
    ("라이더 관리", "/riders"),
]


def won(value: int) -> str:
    """정수를 원화 문자열로 포맷."""
    return f"₩{value:,.0f}"


def sidebar(active_path: str = "/") -> html.Div:
    links = []
    for label, href in NAV_ITEMS:
        is_active = href == active_path
        links.append(
            dbc.NavLink(
                label,
                href=href,
                active=is_active,
                className="sidebar-link",
            )
        )
    return html.Div(
        [
            html.Div(
                [html.Span("🛵", className="brand-logo"),
                 html.Span(BRAND, className="brand-text")],
                className="brand",
            ),
            dbc.Nav(links, vertical=True, pills=True, className="mt-3"),
        ],
        className="sidebar",
    )


def kpi_card(title: str, value: str, icon: str = "📊") -> dbc.Col:
    return dbc.Col(
        dbc.Card(
            dbc.CardBody(
                [
                    html.Div(
                        [html.Span(title, className="kpi-title"),
                         html.Span(icon, className="kpi-icon")],
                        className="kpi-head",
                    ),
                    html.Div(value, className="kpi-value"),
                ]
            ),
            className="kpi-card",
        ),
        md=3, sm=6, xs=12,
    )


def page_header(title: str, subtitle: str = "") -> html.Div:
    children = [html.H2(title, className="page-title")]
    if subtitle:
        children.append(html.P(subtitle, className="page-subtitle"))
    return html.Div(children, className="page-header")