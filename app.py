"""정산 대시보드 MVP - 메인 앱.

정산플러스(배플) 화면 구조를 참고한 배달기사 정산 대시보드 프로토타입.
- 좌측 사이드바 네비게이션
- 대시보드 / 정산 결과 / 라이더 관리 3개 페이지
- 메모리내 샘플 데이터 사용

실행:
    pip install -r requirements.txt
    python app.py
    브라우저에서 http://127.0.0.1:8050 접속
"""

import os

import dash
import dash_bootstrap_components as dbc
from dash import Dash, dcc, html
from dash.dependencies import Input, Output

from components import sidebar

app = Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="정산 대시보드",
)
server = app.server  # 배포(gunicorn 등)용 WSGI 엔트리포인트

app.layout = html.Div(
    [
        dcc.Location(id="url"),
        html.Div(id="sidebar-container"),
        html.Div(dash.page_container, className="content"),
        html.Div(id="brand-home-reload-dummy", style={"display": "none"}),
    ],
    className="app-shell",
)


@app.callback(Output("sidebar-container", "children"), Input("url", "pathname"))
def _render_sidebar(pathname):
    """현재 경로에 맞춰 사이드바 활성 항목을 갱신."""
    return sidebar(pathname or "/")


app.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks) {
            window.location.href = "/";
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("brand-home-reload-dummy", "children"),
    Input("brand-home", "n_clicks"),
    prevent_initial_call=True,
)


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 8050)))