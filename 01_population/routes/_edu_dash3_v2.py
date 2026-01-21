# -*- coding: utf-8 -*-
"""
================================================================================
경북 인구·가구 진단 대시보드 (edu_dash3.py)
================================================================================

[구조 요약]
- edu_dash2.py와 동일한 "모듈형 대시보드" 패턴을 따릅니다.
  - main_app.py가 이 모듈을 import
  - 메뉴에서 edu_dash3 선택 시, main_app.py가 이 모듈의 render(request.args)를 호출
  - render()는
      * api_type 파라미터가 있으면: JSON API 응답
      * 없으면: HTML(문자열) 반환

[페이지 구성]
- view=sigungu   : 페이지 1) 경북 시군 진단(표 + 서브플롯 2x2 + 하단 카드)
- view=benchmark : 페이지 2) 경북 vs 시도 비교(막대 + 순위표)
- view=detail    : 드릴다운) 시군 → 읍면동 Top + 1세 인구 분포

[DB 전제(온톨로지 기준)]
- cache_sigungu_indicators : 시군 단위 지표
- fact_population_by_age + dim_admin_area : 읍면동/연령(1세) 상세

[주의]
- 실제 컬럼명이 다르면, 아래 SQL의 컬럼명만 맞춰주시면 됩니다.
================================================================================
"""

import json
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from flask import Response

# edu_dash2.py에서 사용 중인 DB 연결 유틸을 그대로 사용 (프로젝트에 이미 존재한다고 가정)
from module.db import get_db_engine


# =============================================================================
# 설정
# =============================================================================
DEFAULT_SIDO = "경상북도"
YMS = ["2022-12", "2023-12", "2024-12", "2025-12"]

# 지표 선택(드롭다운) -> (기준 컬럼명, 표시명)
METRICS = {
    "pop_total_yoy": ("total_pop", "총인구 변화율"),
    "youth_yoy": ("youth_pop", "유소년(0-14) 변화율"),
    "young_yoy": ("young_adult_pop", "청년(19-34) 변화율"),
    "aging_index_diff": ("aging_index", "고령화지수(65+/0-14) 변화"),
    "single_cnt_yoy": ("single_cnt", "1인가구(절대) 변화율"),
}

COMPARE_MODES = {
    "yoy": "전년 대비(2024→2025)",
    "3y": "3년 변화(2022→2025)",
    "trend": "연속 추세(4포인트)",
}


# =============================================================================
# 간단 TTL 캐시(프로세스 메모리)
# - 운영 환경에서 Redis/Flask-Caching으로 교체 가능
# =============================================================================
_TTL_CACHE: Dict[str, Tuple[datetime, Any]] = {}


def ttl_get(key: str) -> Optional[Any]:
    item = _TTL_CACHE.get(key)
    if not item:
        return None
    exp, val = item
    if datetime.utcnow() > exp:
        _TTL_CACHE.pop(key, None)
        return None
    return val


def ttl_set(key: str, val: Any, ttl_sec: int = 1800) -> None:
    _TTL_CACHE[key] = (datetime.utcnow() + timedelta(seconds=ttl_sec), val)


def json_response(payload: Any) -> Response:
    return Response(json.dumps(payload, ensure_ascii=False, default=str), mimetype="application/json")


# =============================================================================
# DB Access Layer
# =============================================================================
def _fetch_df(sql: str, params: Dict[str, Any]) -> pd.DataFrame:
    engine = get_db_engine()
    return pd.read_sql(sql, engine, params=params)


def _get_sigungu_base(ym: str, sido: str) -> pd.DataFrame:
    """
    cache_sigungu_indicators에서 "대표 시군"만 조회
    - 대표 시군 규칙: sigungu_code LIKE '____0'
    """
    cache_key = f"sigungu_base:{ym}:{sido}"
    cached = ttl_get(cache_key)
    if cached is not None:
        return cached.copy()

    sql = """
    SELECT
      base_ym,
      sido_nm,
      sigungu_code,
      sigungu_nm,
      total_pop,
      youth_pop,
      young_adult_pop,
      elderly_pop,
      aging_index,
      single_cnt,
      single_ratio
    FROM cache_sigungu_indicators
    WHERE base_ym = %(ym)s
      AND sido_nm = %(sido)s
      AND sigungu_code LIKE '____0'
    """
    df = _fetch_df(sql, {"ym": ym, "sido": sido})
    ttl_set(cache_key, df, ttl_sec=1800)
    return df.copy()


def _get_sigungu_trend(sigungu_code: str, sido: str) -> pd.DataFrame:
    cache_key = f"sigungu_trend:{sigungu_code}:{sido}"
    cached = ttl_get(cache_key)
    if cached is not None:
        return cached.copy()

    sql = """
    SELECT
      base_ym,
      total_pop,
      youth_pop,
      young_adult_pop,
      elderly_pop,
      aging_index,
      single_cnt
    FROM cache_sigungu_indicators
    WHERE sido_nm = %(sido)s
      AND sigungu_code = %(sigungu_code)s
      AND base_ym IN ('2022-12','2023-12','2024-12','2025-12')
    ORDER BY base_ym
    """
    df = _fetch_df(sql, {"sido": sido, "sigungu_code": sigungu_code})
    ttl_set(cache_key, df, ttl_sec=3600)
    return df.copy()


def _get_sido_aggregate(ym: str, sido_list: List[str]) -> pd.DataFrame:
    """
    시도 비교용: cache_sigungu_indicators를 시도 단위로 집계
    """
    cache_key = f"sido_agg:{ym}:{'|'.join(sorted(sido_list))}"
    cached = ttl_get(cache_key)
    if cached is not None:
        return cached.copy()

    sql = """
    SELECT
      base_ym,
      sido_nm,
      SUM(total_pop) AS total_pop,
      SUM(youth_pop) AS youth_pop,
      SUM(young_adult_pop) AS young_adult_pop,
      SUM(elderly_pop) AS elderly_pop,
      ROUND(SUM(elderly_pop)::numeric / NULLIF(SUM(youth_pop),0), 6) AS aging_index,
      SUM(single_cnt) AS single_cnt
    FROM cache_sigungu_indicators
    WHERE base_ym = %(ym)s
      AND sigungu_code LIKE '____0'
      AND sido_nm = ANY(%(sido_list)s)
    GROUP BY base_ym, sido_nm
    ORDER BY sido_nm
    """
    df = _fetch_df(sql, {"ym": ym, "sido_list": sido_list})
    ttl_set(cache_key, df, ttl_sec=3600)
    return df.copy()


def _get_emd_totals(sigungu_code: str, ym: str, topn: int = 50) -> pd.DataFrame:
    """
    드릴다운: 시군 내 읍면동 총인구(연령 합계)
    fact_population_by_age + dim_admin_area JOIN
    """
    cache_key = f"emd_totals:{sigungu_code}:{ym}:{topn}"
    cached = ttl_get(cache_key)
    if cached is not None:
        return cached.copy()

    sql = """
    SELECT
      d.sigungu_code,
      d.sigungu_nm,
      d.eupmyeondong_nm AS emd_nm,
      SUM(p.pop_cnt) AS total_pop
    FROM fact_population_by_age p
    JOIN dim_admin_area d
      ON p.admin_code = d.admin_code
    WHERE p.base_ym = %(ym)s
      AND d.sigungu_code = %(sigungu_code)s
      AND d.eupmyeondong_nm IS NOT NULL
    GROUP BY d.sigungu_code, d.sigungu_nm, d.eupmyeondong_nm
    ORDER BY total_pop DESC NULLS LAST
    LIMIT %(topn)s
    """
    df = _fetch_df(sql, {"ym": ym, "sigungu_code": sigungu_code, "topn": topn})
    ttl_set(cache_key, df, ttl_sec=1800)
    return df.copy()


def _get_sigungu_age_dist(sigungu_code: str, ym: str) -> pd.DataFrame:
    """
    드릴다운: 시군 1세 단위 인구 분포(연령 합계)
    """
    cache_key = f"sigungu_age_dist:{sigungu_code}:{ym}"
    cached = ttl_get(cache_key)
    if cached is not None:
        return cached.copy()

    sql = """
    SELECT
      p.age AS age,
      SUM(p.pop_cnt) AS pop_cnt
    FROM fact_population_by_age p
    JOIN dim_admin_area d
      ON p.admin_code = d.admin_code
    WHERE p.base_ym = %(ym)s
      AND d.sigungu_code = %(sigungu_code)s
    GROUP BY p.age
    ORDER BY p.age
    """
    df = _fetch_df(sql, {"ym": ym, "sigungu_code": sigungu_code})
    ttl_set(cache_key, df, ttl_sec=1800)
    return df.copy()


# =============================================================================
# 계산 로직(변화율/위험플래그)
# =============================================================================
def _pct_change(curr: float, prev: float) -> Optional[float]:
    if prev is None or prev == 0 or curr is None:
        return None
    return (curr - prev) / prev


def _safe_float(x) -> Optional[float]:
    if x is None:
        return None
    try:
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return None
        return float(x)
    except Exception:
        return None


def compute_sigungu_kpis(ym: str, sido: str, compare_mode: str) -> pd.DataFrame:
    """
    시군 KPI 테이블 생성:
    - 현재 시점 수치 + 변화율/변화량(비교방식에 따라)
    """
    df_curr = _get_sigungu_base(ym, sido)

    # 비교 기준 시점 선택
    if compare_mode == "yoy":
        prev_ym = "2024-12" if ym == "2025-12" else None
    elif compare_mode == "3y":
        prev_ym = "2022-12" if ym == "2025-12" else None
    else:
        prev_ym = None

    if prev_ym:
        df_prev = _get_sigungu_base(prev_ym, sido)
        df = df_curr.merge(
            df_prev[["sigungu_code", "total_pop", "youth_pop", "young_adult_pop", "aging_index", "single_cnt"]],
            on="sigungu_code",
            suffixes=("", "_prev"),
            how="left",
        )
        df["total_pop_change"] = df.apply(lambda r: _pct_change(_safe_float(r["total_pop"]), _safe_float(r["total_pop_prev"])), axis=1)
        df["youth_change"] = df.apply(lambda r: _pct_change(_safe_float(r["youth_pop"]), _safe_float(r["youth_pop_prev"])), axis=1)
        df["young_change"] = df.apply(lambda r: _pct_change(_safe_float(r["young_adult_pop"]), _safe_float(r["young_adult_pop_prev"])), axis=1)
        df["aging_index_change"] = df.apply(
            lambda r: (_safe_float(r["aging_index"]) - _safe_float(r["aging_index_prev"]))
            if _safe_float(r["aging_index"]) is not None and _safe_float(r["aging_index_prev"]) is not None
            else None,
            axis=1,
        )
        df["single_cnt_change"] = df.apply(lambda r: _pct_change(_safe_float(r["single_cnt"]), _safe_float(r["single_cnt_prev"])), axis=1)
    else:
        df = df_curr.copy()
        df["total_pop_change"] = None
        df["youth_change"] = None
        df["young_change"] = None
        df["aging_index_change"] = None
        df["single_cnt_change"] = None

    # 위험 플래그(인구↓ + 유소년↓ + 고령화지수↑)
    df["risk_flag"] = df.apply(
        lambda r: bool(
            (r["total_pop_change"] is not None and r["total_pop_change"] < 0)
            and (r["youth_change"] is not None and r["youth_change"] < 0)
            and (r["aging_index_change"] is not None and r["aging_index_change"] > 0)
        ),
        axis=1,
    )
    return df


def metric_to_change_col(metric_key: str) -> str:
    if metric_key == "pop_total_yoy":
        return "total_pop_change"
    if metric_key == "youth_yoy":
        return "youth_change"
    if metric_key == "young_yoy":
        return "young_change"
    if metric_key == "aging_index_diff":
        return "aging_index_change"
    if metric_key == "single_cnt_yoy":
        return "single_cnt_change"
    return "total_pop_change"


# =============================================================================
# API 핸들러
# =============================================================================
def handle_api_request(api_type: str, args: Dict[str, Any]) -> Any:
    ym = args.get("ym", "2025-12")
    sido = args.get("sido", DEFAULT_SIDO)
    compare_mode = args.get("compare", "yoy")
    metric_key = args.get("metric", "pop_total_yoy")
    topn = int(args.get("topn", "20") or 20)

    # 페이지1: 시군 요약
    if api_type == "sigungu_kpis":
        df = compute_sigungu_kpis(ym, sido, compare_mode)
        selected = args.get("sigungu_codes")
        if selected:
            codes = [c.strip() for c in selected.split(",") if c.strip()]
            df = df[df["sigungu_code"].isin(codes)]

        order = args.get("order", "top")  # top/bottom
        change_col = metric_to_change_col(metric_key)
        df_sorted = df.sort_values(change_col, ascending=(order == "bottom"), na_position="last").head(topn)

        out_cols = [
            "sigungu_code", "sigungu_nm",
            "total_pop", "total_pop_change",
            "youth_pop", "youth_change",
            "young_adult_pop", "young_change",
            "aging_index", "aging_index_change",
            "single_cnt", "single_cnt_change",
            "risk_flag",
        ]
        return df_sorted[out_cols].to_dict(orient="records")

    if api_type == "sigungu_trend":
        sigungu_code = args.get("sigungu_code")
        if not sigungu_code:
            return {"error": "sigungu_code is required"}
        df = _get_sigungu_trend(sigungu_code, sido)
        return df.to_dict(orient="records")

    # 페이지2: 시도 비교
    if api_type == "sido_benchmark":
        sido_list_raw = args.get("sido_list")  # comma separated
        if sido_list_raw:
            sido_list = [x.strip() for x in sido_list_raw.split(",") if x.strip()]
        else:
            sido_list = [DEFAULT_SIDO, "서울특별시", "경기도", "부산광역시"]
        df = _get_sido_aggregate(ym, sido_list)
        return df.to_dict(orient="records")

    # 드릴다운
    if api_type == "emd_top":
        sigungu_code = args.get("sigungu_code")
        if not sigungu_code:
            return {"error": "sigungu_code is required"}
        topn = int(args.get("topn", "50") or 50)
        df = _get_emd_totals(sigungu_code, ym, topn=topn)
        return df.to_dict(orient="records")

    if api_type == "sigungu_age_dist":
        sigungu_code = args.get("sigungu_code")
        if not sigungu_code:
            return {"error": "sigungu_code is required"}
        df = _get_sigungu_age_dist(sigungu_code, ym)
        return df.to_dict(orient="records")

    return {"error": f"unknown api_type: {api_type}"}


# =============================================================================
# HTML 생성 (edu_dash2 방식: 문자열 반환)
# =============================================================================
def generate_html() -> str:
    html = f"""
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>edu_dash3 | 경북 인구·가구 진단</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.datatables.net/1.13.8/css/jquery.dataTables.min.css" rel="stylesheet">
<style>
  body {{ background:#f7f7f9; }}
  .card {{ border-radius: 16px; }}
  .small-muted {{ color:#6c757d; font-size:0.9rem; }}
  .kpi-badge {{ font-size:0.75rem; }}
  #subplot {{ height: 560px; }}
</style>
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.datatables.net/1.13.8/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
</head>

<body class="container-fluid p-3 p-md-4">

<nav class="navbar navbar-expand-lg bg-white rounded-4 shadow-sm px-3 mb-3">
  <a class="navbar-brand fw-bold" href="?view=sigungu">edu_dash3</a>
  <div class="navbar-nav">
    <a class="nav-link" href="?view=sigungu">경북 시군 진단</a>
    <a class="nav-link" href="?view=benchmark">경북 vs 시도 비교</a>
  </div>
  <div class="ms-auto small-muted">Flask 기반 · 반응형 · 필터/선택 · 표/차트 연동</div>
</nav>

<div id="page-root"></div>

<script>
// ------------------------------------------------------------
// 공통: API 호출
// ------------------------------------------------------------
async function apiCall(params) {{
  const qs = new URLSearchParams(params);
  const res = await fetch("?" + qs.toString());
  if (!res.ok) throw new Error("API error");
  return await res.json();
}}

function pctFmt(x) {{
  if (x === null || x === undefined) return "-";
  const v = Number(x);
  if (Number.isNaN(v)) return "-";
  return (v*100).toFixed(2) + "%";
}}
function numFmt(x) {{
  if (x === null || x === undefined) return "-";
  const v = Number(x);
  if (Number.isNaN(v)) return "-";
  return v.toLocaleString();
}}
function diffFmt(x) {{
  if (x === null || x === undefined) return "-";
  const v = Number(x);
  if (Number.isNaN(v)) return "-";
  return v.toFixed(4);
}}

// ------------------------------------------------------------
// 페이지 1
// ------------------------------------------------------------
function renderPageSigungu() {{
  const root = document.getElementById("page-root");
  root.innerHTML = `
  <div class="card shadow-sm mb-3">
    <div class="card-body">
      <div class="row g-2 align-items-end">
        <div class="col-6 col-md-2">
          <label class="form-label">기준시점</label>
          <select id="ym" class="form-select">
            {''.join([f'<option value="{y}" {"selected" if y=="2025-12" else ""}>{y}</option>' for y in YMS])}
          </select>
        </div>
        <div class="col-6 col-md-2">
          <label class="form-label">비교 기준</label>
          <select id="compare" class="form-select">
            <option value="yoy" selected>{COMPARE_MODES["yoy"]}</option>
            <option value="3y">{COMPARE_MODES["3y"]}</option>
            <option value="trend">{COMPARE_MODES["trend"]}</option>
          </select>
        </div>
        <div class="col-12 col-md-3">
          <label class="form-label">지표 선택</label>
          <select id="metric" class="form-select">
            {''.join([f'<option value="{k}">{v[1]}</option>' for k,v in METRICS.items()])}
          </select>
        </div>
        <div class="col-6 col-md-2">
          <label class="form-label">정렬</label>
          <select id="order" class="form-select">
            <option value="top" selected>Top</option>
            <option value="bottom">Bottom</option>
          </select>
        </div>
        <div class="col-6 col-md-1">
          <label class="form-label">N</label>
          <input id="topn" type="number" class="form-control" value="20" min="5" max="200">
        </div>
        <div class="col-12 col-md-2">
          <label class="form-label">시도</label>
          <input id="sido" class="form-control" value="{DEFAULT_SIDO}">
        </div>
      </div>
      <div class="row g-2 mt-2">
        <div class="col-12 col-md-10">
          <div class="small-muted">
            표의 행을 클릭하면 선택 시군의 4포인트 추세가 서브플롯에 반영됩니다. (상세 버튼은 드릴다운)
          </div>
        </div>
        <div class="col-12 col-md-2 text-end">
          <button class="btn btn-primary w-100" onclick="loadSigungu()">조회</button>
        </div>
      </div>
    </div>
  </div>

  <div class="row g-3">
    <div class="col-12 col-lg-6">
      <div class="card shadow-sm">
        <div class="card-body">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <h5 class="mb-0">시군 요약 표</h5>
            <button class="btn btn-outline-secondary btn-sm" onclick="exportTableCSV()">CSV 다운로드</button>
          </div>
          <table id="tbl" class="display" style="width:100%">
            <thead>
              <tr>
                <th>시군코드</th>
                <th>시군명</th>
                <th>총인구</th>
                <th>총인구 변화</th>
                <th>0-14 변화</th>
                <th>19-34 변화</th>
                <th>고령화지수</th>
                <th>고령화 변화</th>
                <th>1인가구 변화</th>
                <th>위험</th>
                <th>상세</th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="col-12 col-lg-6">
      <div class="card shadow-sm">
        <div class="card-body">
          <h5 class="mb-0">서브플롯 (2x2)</h5>
          <div class="small-muted mb-2">Top/Bottom · 스파크라인(선택 시군) · 사분면 · 연령대 요약</div>
          <div id="subplot"></div>
        </div>
      </div>
    </div>
  </div>

  <div class="row g-3 mt-1">
    <div class="col-12 col-lg-4">
      <div class="card shadow-sm">
        <div class="card-body">
          <h6 class="mb-1">이번 시점 위험 신호 Top 5</h6>
          <div id="card_top5" class="small-muted">-</div>
        </div>
      </div>
    </div>
    <div class="col-12 col-lg-4">
      <div class="card shadow-sm">
        <div class="card-body">
          <h6 class="mb-1">경북 공통 변화 3가지(자동 요약)</h6>
          <div id="card_common" class="small-muted">-</div>
        </div>
      </div>
    </div>
    <div class="col-12 col-lg-4">
      <div class="card shadow-sm">
        <div class="card-body">
          <h6 class="mb-1">데이터 기반 의사결정 예시</h6>
          <div id="card_decision" class="small-muted">-</div>
        </div>
      </div>
    </div>
  </div>
  `;

  window._tbl = null;
  window._lastRows = [];
  loadSigungu();
}}

async function loadSigungu() {{
  const ym = document.getElementById("ym").value;
  const compare = document.getElementById("compare").value;
  const metric = document.getElementById("metric").value;
  const order = document.getElementById("order").value;
  const topn = document.getElementById("topn").value;
  const sido = document.getElementById("sido").value;

  const rows = await apiCall({{
    api_type: "sigungu_kpis",
    view: "sigungu",
    ym, compare, metric, order, topn, sido
  }});

  window._lastRows = rows;

  if (window._tbl) {{
    window._tbl.clear().rows.add(rows).draw();
  }} else {{
    window._tbl = $("#tbl").DataTable({{
      data: rows,
      pageLength: 10,
      columns: [
        {{data:"sigungu_code"}},
        {{data:"sigungu_nm"}},
        {{data:"total_pop", render:(d)=>numFmt(d)}},
        {{data:"total_pop_change", render:(d)=>pctFmt(d)}},
        {{data:"youth_change", render:(d)=>pctFmt(d)}},
        {{data:"young_change", render:(d)=>pctFmt(d)}},
        {{data:"aging_index", render:(d)=>diffFmt(d)}},
        {{data:"aging_index_change", render:(d)=>diffFmt(d)}},
        {{data:"single_cnt_change", render:(d)=>pctFmt(d)}},
        {{data:"risk_flag", render:(d)=> d ? '<span class="badge text-bg-danger kpi-badge">RISK</span>' : '<span class="badge text-bg-secondary kpi-badge">OK</span>'}},
        {{data:null, render:(d)=>`<a class="btn btn-sm btn-outline-primary" href="?view=detail&sigungu_code=${{d.sigungu_code}}&sigungu_nm=${{encodeURIComponent(d.sigungu_nm)}}&ym=${{ym}}">상세</a>`}}
      ]
    }});

    $("#tbl tbody").on("click", "tr", async function () {{
      const data = window._tbl.row(this).data();
      if (!data) return;
      await drawSubplot(rows, data.sigungu_code, data.sigungu_nm, sido);
    }});
  }}

  if (rows.length > 0) {{
    await drawSubplot(rows, rows[0].sigungu_code, rows[0].sigungu_nm, sido);
  }} else {{
    Plotly.purge("subplot");
  }}

  renderCards(rows);
}}

function renderCards(rows) {{
  const risk = rows.filter(r=>r.risk_flag && r.total_pop_change!==null).sort((a,b)=>a.total_pop_change-b.total_pop_change).slice(0,5);
  const top5 = risk.map(r=>`${{r.sigungu_nm}} (총인구 ${{pctFmt(r.total_pop_change)}}, 유소년 ${{pctFmt(r.youth_change)}}, 고령화 ${{diffFmt(r.aging_index_change)}})`).join("<br>");
  document.getElementById("card_top5").innerHTML = top5 || "해당 기준에서 위험 플래그가 포착되지 않았습니다.";

  const avg = (k)=>{{
    const v = rows.map(r=>r[k]).filter(x=>x!==null && x!==undefined);
    if (v.length===0) return null;
    return v.reduce((a,b)=>a+b,0)/v.length;
  }};
  const m1 = avg("total_pop_change");
  const m2 = avg("youth_change");
  const m3 = avg("young_change");
  const m4 = avg("aging_index_change");
  document.getElementById("card_common").innerHTML =
    `- 총인구 변화 평균: ${{pctFmt(m1)}}<br>` +
    `- 유소년 변화 평균: ${{pctFmt(m2)}}<br>` +
    `- 청년 변화 평균: ${{pctFmt(m3)}}<br>` +
    `- 고령화지수 변화 평균: ${{diffFmt(m4)}}`;

  document.getElementById("card_decision").innerHTML =
    `- (단기) 위험 플래그 지역을 우선관리 대상으로 지정하고, 읍면동 상세로 원인구간(연령) 확인<br>` +
    `- (중기) 청년/유소년 감소가 동시 진행되는 시군은 생활SOC·교육/돌봄 수요 재산정 필요<br>` +
    `- (장기) 고령화지수 증가가 빠른 권역은 서비스 전달체계(거점/분소) 재설계 검토`;
}}

async function drawSubplot(rows, selectedCode, selectedName, sido) {{
  const topBars = rows.slice().filter(r=>r.total_pop_change!==null).sort((a,b)=>b.total_pop_change-a.total_pop_change).slice(0,10);
  const bottomBars = rows.slice().filter(r=>r.total_pop_change!==null).sort((a,b)=>a.total_pop_change-b.total_pop_change).slice(0,10);

  const trend = await apiCall({{api_type:"sigungu_trend", view:"sigungu", sigungu_code:selectedCode, sido}});

  const sx = rows.map(r=>r.total_pop_change);
  const sy = rows.map(r=>r.single_cnt_change);
  const sn = rows.map(r=>r.sigungu_nm);

  const avg = (k)=>{{
    const v = rows.map(r=>r[k]).filter(x=>x!==null && x!==undefined);
    if (v.length===0) return null;
    return v.reduce((a,b)=>a+b,0)/v.length;
  }};
  const aYouth = avg("youth_change");
  const aYoung = avg("young_change");
  const aPop = avg("total_pop_change");

  const data = [];

  data.push({{
    type:"bar",
    x: topBars.map(r=>r.sigungu_nm),
    y: topBars.map(r=>r.total_pop_change*100),
    name:"Top(총인구 변화율)",
    xaxis:"x",
    yaxis:"y"
  }});
  data.push({{
    type:"bar",
    x: bottomBars.map(r=>r.sigungu_nm),
    y: bottomBars.map(r=>r.total_pop_change*100),
    name:"Bottom(총인구 변화율)",
    xaxis:"x",
    yaxis:"y"
  }});

  data.push({{
    type:"scatter",
    mode:"lines+markers",
    x: trend.map(t=>t.base_ym),
    y: trend.map(t=>t.total_pop),
    name:`${{selectedName}} 총인구`,
    xaxis:"x2",
    yaxis:"y2"
  }});

  data.push({{
    type:"scatter",
    mode:"markers",
    x: sx.map(v=>v===null?null:v*100),
    y: sy.map(v=>v===null?null:v*100),
    text: sn,
    name:"시군",
    xaxis:"x3",
    yaxis:"y3"
  }});

  const sel = rows.find(r=>r.sigungu_code===selectedCode);
  if (sel && sel.total_pop_change!==null && sel.single_cnt_change!==null) {{
    data.push({{
      type:"scatter",
      mode:"markers+text",
      x: [sel.total_pop_change*100],
      y: [sel.single_cnt_change*100],
      text: [selectedName],
      textposition: "top center",
      name:"선택",
      xaxis:"x3",
      yaxis:"y3"
    }});
  }}

  data.push({{
    type:"bar",
    x: ["0-14", "19-34", "전체"],
    y: [aYouth===null?null:aYouth*100, aYoung===null?null:aYoung*100, aPop===null?null:aPop*100],
    name:"평균 변화율(%)",
    xaxis:"x4",
    yaxis:"y4"
  }});

  const layout = {{
    grid: {{rows:2, columns:2, pattern:"independent"}},
    height: 560,
    title: "경북 시군 진단 서브플롯(2x2)",
    xaxis: {{tickangle: -45}},
    yaxis: {{title: "%"}},
    xaxis2: {{title: "기준년월"}},
    yaxis2: {{title: "총인구"}},
    xaxis3: {{title: "총인구 변화율(%)"}},
    yaxis3: {{title: "1인가구 변화율(%)"}},
    xaxis4: {{title: "연령대"}},
    yaxis4: {{title: "%"}}
  }};

  Plotly.newPlot("subplot", data, layout, {{displayModeBar: true}});
}}

function exportTableCSV() {{
  const rows = window._lastRows || [];
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const csv = [headers.join(",")].concat(rows.map(r=>headers.map(h=>JSON.stringify(r[h]??"")).join(","))).join("\\n");
  const blob = new Blob([csv], {{type:"text/csv;charset=utf-8;"}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "sigungu_summary.csv";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}}

// ------------------------------------------------------------
// 페이지 2
// ------------------------------------------------------------
function renderPageBenchmark() {{
  const root = document.getElementById("page-root");
  root.innerHTML = `
  <div class="card shadow-sm mb-3">
    <div class="card-body">
      <div class="row g-2 align-items-end">
        <div class="col-6 col-md-2">
          <label class="form-label">기준시점</label>
          <select id="b_ym" class="form-select">
            {''.join([f'<option value="{y}" {"selected" if y=="2025-12" else ""}>{y}</option>' for y in YMS])}
          </select>
        </div>
        <div class="col-12 col-md-6">
          <label class="form-label">비교 대상 시도(콤마로 입력)</label>
          <input id="b_sidos" class="form-control" value="{DEFAULT_SIDO},서울특별시,경기도,부산광역시">
        </div>
        <div class="col-6 col-md-2">
          <label class="form-label">지표</label>
          <select id="b_metric" class="form-select">
            <option value="total_pop">총인구</option>
            <option value="youth_pop">유소년(0-14)</option>
            <option value="young_adult_pop">청년(19-34)</option>
            <option value="aging_index">고령화지수</option>
            <option value="single_cnt">1인가구(절대)</option>
          </select>
        </div>
        <div class="col-6 col-md-2 text-end">
          <button class="btn btn-primary w-100" onclick="loadBenchmark()">조회</button>
        </div>
      </div>
    </div>
  </div>

  <div class="row g-3">
    <div class="col-12 col-lg-6">
      <div class="card shadow-sm">
        <div class="card-body">
          <h5 class="mb-1">시도별 막대그래프(경북 위치 확인)</h5>
          <div id="b_bar"></div>
        </div>
      </div>
    </div>
    <div class="col-12 col-lg-6">
      <div class="card shadow-sm">
        <div class="card-body">
          <h5 class="mb-1">시도 순위표</h5>
          <table class="table table-sm table-bordered" id="b_tbl">
            <thead><tr><th>순위</th><th>시도</th><th>값</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
  `;
  loadBenchmark();
}}

async function loadBenchmark() {{
  const ym = document.getElementById("b_ym").value;
  const sidos = document.getElementById("b_sidos").value.split(",").map(x=>x.trim()).filter(Boolean);
  const metric = document.getElementById("b_metric").value;

  const data = await apiCall({{
    api_type: "sido_benchmark",
    view: "benchmark",
    ym: ym,
    sido_list: sidos.join(",")
  }});

  const vals = data.map(d=>({{
    sido: d.sido_nm,
    val: Number(d[metric])
  }})).filter(x=>!Number.isNaN(x.val));

  vals.sort((a,b)=>b.val-a.val);
  Plotly.newPlot("b_bar", [{{
    type:"bar",
    x: vals.map(v=>v.sido),
    y: vals.map(v=>v.val)
  }}], {{
    height: 420,
    title: `${{ym}} 시도별 ${{metric}}`,
    xaxis: {{tickangle:-45}}
  }}, {{displayModeBar:true}});

  const tb = document.querySelector("#b_tbl tbody");
  tb.innerHTML = "";
  vals.forEach((v, i)=>{{
    const tr = document.createElement("tr");
    const isGB = (v.sido === "{DEFAULT_SIDO}");
    tr.innerHTML = `<td>${{i+1}}</td><td>${{isGB?'<b>'+v.sido+'</b>':v.sido}}</td><td>${{v.val.toLocaleString()}}</td>`;
    tb.appendChild(tr);
  }});
}}

// ------------------------------------------------------------
// 드릴다운
// ------------------------------------------------------------
async function renderPageDetail(sigungu_code, sigungu_nm, ym) {{
  const root = document.getElementById("page-root");
  root.innerHTML = `
  <div class="card shadow-sm mb-3">
    <div class="card-body">
      <div class="d-flex justify-content-between align-items-center">
        <div>
          <h5 class="mb-1">시군 상세: ${{sigungu_nm}} (${{sigungu_code}})</h5>
          <div class="small-muted">읍면동 Top 및 1세 인구 분포</div>
        </div>
        <div><a class="btn btn-outline-secondary" href="?view=sigungu">← 돌아가기</a></div>
      </div>

      <div class="row g-2 mt-2 align-items-end">
        <div class="col-6 col-md-3">
          <label class="form-label">기준시점</label>
          <select id="d_ym" class="form-select">
            {''.join([f'<option value="{y}" {"selected" if y=="2025-12" else ""}>{y}</option>' for y in YMS])}
          </select>
        </div>
        <div class="col-6 col-md-2">
          <label class="form-label">Top N</label>
          <input id="d_topn" class="form-control" type="number" min="10" max="300" value="50">
        </div>
        <div class="col-12 col-md-3">
          <button class="btn btn-primary w-100" onclick="loadDetail('${{sigungu_code}}','${{sigungu_nm}}')">조회</button>
        </div>
      </div>
    </div>
  </div>

  <div class="row g-3">
    <div class="col-12 col-lg-6">
      <div class="card shadow-sm">
        <div class="card-body">
          <h6 class="mb-2">읍면동 총인구 Top</h6>
          <table class="table table-sm table-bordered" id="d_tbl">
            <thead><tr><th>읍면동</th><th>총인구</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="col-12 col-lg-6">
      <div class="card shadow-sm">
        <div class="card-body">
          <h6 class="mb-2">1세 단위 인구 분포</h6>
          <div id="d_age"></div>
        </div>
      </div>
    </div>
  </div>
  `;

  document.getElementById("d_ym").value = ym || "2025-12";
  await loadDetail(sigungu_code, sigungu_nm);
}}

async function loadDetail(sigungu_code, sigungu_nm) {{
  const ym = document.getElementById("d_ym").value;
  const topn = document.getElementById("d_topn").value;

  const emd = await apiCall({{api_type:"emd_top", view:"detail", ym, sigungu_code, topn}});
  const age = await apiCall({{api_type:"sigungu_age_dist", view:"detail", ym, sigungu_code}});

  const tb = document.querySelector("#d_tbl tbody");
  tb.innerHTML = "";
  emd.forEach(r=>{{
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${{r.emd_nm}}</td><td>${{Number(r.total_pop).toLocaleString()}}</td>`;
    tb.appendChild(tr);
  }});

  Plotly.newPlot("d_age", [{{
    type:"scatter",
    mode:"lines",
    x: age.map(a=>a.age),
    y: age.map(a=>a.pop_cnt)
  }}], {{
    height: 420,
    title: `${{sigungu_nm}} (${{ym}}) 1세 단위 인구 분포`,
    xaxis: {{title:"age"}},
    yaxis: {{title:"pop"}}
  }}, {{displayModeBar:true}});
}}

// ------------------------------------------------------------
// Router
// ------------------------------------------------------------
function router() {{
  const url = new URL(window.location.href);
  const view = url.searchParams.get("view") || "sigungu";

  if (view === "benchmark") {{
    renderPageBenchmark();
    return;
  }}
  if (view === "detail") {{
    const sigungu_code = url.searchParams.get("sigungu_code") || "";
    const sigungu_nm = decodeURIComponent(url.searchParams.get("sigungu_nm") || sigungu_code);
    const ym = url.searchParams.get("ym") || "2025-12";
    if (!sigungu_code) {{
      renderPageSigungu();
      return;
    }}
    renderPageDetail(sigungu_code, sigungu_nm, ym);
    return;
  }}

  renderPageSigungu();
}}

router();
</script>

</body>
</html>
"""
    return html


# =============================================================================
# edu_dash2 패턴: 메인 렌더 함수
# =============================================================================
def render(request_args):
    """
    메인 렌더 함수(edu_dash2와 동일 패턴)
    - api_type이 있으면 API 요청 처리(JSON)
    - 없으면 HTML 페이지 반환
    """
    api_type = request_args.get("api_type")
    if api_type:
        result = handle_api_request(api_type, request_args)
        return json_response(result)

    return Response(generate_html(), mimetype="text/html")
