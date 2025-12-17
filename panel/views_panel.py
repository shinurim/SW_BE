import os, re, json, time, ast
import numpy as np

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from sentence_transformers import SentenceTransformer
from django.db import connections

try:
    from panel.views_api import run_stage1_nl_to_meta
except Exception as e:
    run_stage1_nl_to_meta = None


# ===========================
# 공통 유틸
# ===========================

def _dictfetchall(cur):
    cols = [c[0] for c in cur.description] if cur.description else []
    return [dict(zip(cols, r)) for r in cur.fetchall()], cols

_WHERE_RE = re.compile(
    r"select\s+\*\s+from\s+panel_records\s*(where\s+.+?)?\s*;?\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)

def _extract_where(sql_text: str) -> str:
    s = (sql_text or "").strip()
    m = _WHERE_RE.search(s)
    if not m:
        return ""
    where = m.group(1) or ""
    where = re.split(r"\b(order\s+by|limit|offset)\b", where, flags=re.IGNORECASE)[0].strip()
    return where

_LIMIT_RE = re.compile(r"\blimit\s+(\d+)\b", flags=re.IGNORECASE)

def _extract_limit(sql_text: str):
    if not sql_text:
        return None
    m = _LIMIT_RE.search(sql_text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None

_ALLOWED_COLS = {
    #생략
}
_COL_RE = re.compile(
    r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b\s*"
    r"(?:=|<>|!=|>=|<=|>|<|in\s*\(|like\b|ilike\b|between\b|is\s+null|is\s+not\s+null)",
    flags=re.IGNORECASE
)

def _columns_from_where(where_sql: str):
    if not where_sql:
        return []
    cols = set()
    for m in _COL_RE.finditer(where_sql):
        c = m.group(1)
        if c.lower() in {"and","or","not","between","is","null"}:
            continue
        if c in _ALLOWED_COLS:
            cols.add(c)
    cols.add("id")
    return sorted(cols)

def _nullish(v) -> bool:
    return v is None or str(v).strip().lower() in ("", "null", "none", "-")

def _vendor_placeholder():
    vendor = connections["default"].vendor
    return ("?", "?") if vendor == "sqlite" else ("%s", "%s")

def _clean_tag(v: str) -> str:
    s = (v or "").strip()
    if not s:
        return s
    s = re.sub(r'^[\'"\s]+|[\'"\s,;]+$', '', s)
    s = re.sub(r"\s+", " ", s)
    return s

def _split_qids(qids_used: str):
    if not qids_used:
        return []
    parts = [p.strip() for p in str(qids_used).split("|") if p.strip()]
    seen, unique = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique

def _normalize_retrieved_block(retrieved_docs):
    if not retrieved_docs:
        return None
    if isinstance(retrieved_docs, dict):
        return retrieved_docs
    if isinstance(retrieved_docs, list):
        return retrieved_docs[0] if retrieved_docs else None
    return None


# KURE 임베딩
KURE_MODEL_PATH = os.getenv("KURE_MODEL_PATH", "nlpai-lab/KURE-v1")
KURE_NORMALIZE  = os.getenv("KURE_NORMALIZE", "false").lower() in ("1", "true", "yes")

KURE_TABLE     = os.getenv("KURE_TABLE", "kure_item_embeddings_v2")
KURE_UID_COL   = os.getenv("KURE_UID_COL", "uid")
KURE_VEC_COL   = os.getenv("KURE_VEC_COL", "vec")
KURE_MAIN_COL  = os.getenv("KURE_MAIN_COL", "main")
KURE_SUB_COL   = os.getenv("KURE_SUB_COL",  "sub")
KURE_QIDS_COL  = os.getenv("KURE_QIDS_COL", "qids_used")

RDB_BASE_COLS = ["id","gender","birth","region","subregion"]

_sentence_model = None
def _get_kure_model():
    global _sentence_model
    if _sentence_model is None:
        try:
            print(f"[INFO] Loading KURE model: {KURE_MODEL_PATH}")
            _sentence_model = SentenceTransformer(KURE_MODEL_PATH, device="cpu")
            print("[INFO] KURE model loaded successfully.")
        except Exception as e:
            raise RuntimeError(f"KURE 모델 로드 실패: {e}")
    return _sentence_model


def _kure_embed(text: str) -> list[float]:
    s = (text or "").strip()
    if not s:
        raise ValueError("빈 opinion 입니다.")
    model = _get_kure_model()
    vecs = model.encode([s], normalize_embeddings=KURE_NORMALIZE)
    if isinstance(vecs, np.ndarray):
        vec = vecs[0].tolist()
    else:
        vec = list(vecs[0])
    if not vec or len(vec) == 0:
        raise RuntimeError("KURE 임베딩 결과가 비었습니다.")
    return [float(x) for x in vec]


# RDB / vecdb 교집합 / 유사도 정렬 / 평균 이상 필터
def _run_insight_core(
    *,
    sql_text: str,
    opinion: str,
    main: str,
    sub: str,
    where_sql: str,
    limit: int,
    offset: int,          
    candidate_cap: int,   
):
    t0 = time.perf_counter()

    # 1️⃣ RDB 후보군 id 먼저 추출
    candidate_ids = None
    with connections["default"].cursor() as cur:
        if where_sql:
            ids_sql = f"""
                SELECT id
                FROM panel_records
                {where_sql}
                ORDER BY id DESC
            """
            params = []
        else:
            ids_sql = """
                SELECT id
                FROM panel_records
                ORDER BY id DESC
                LIMIT %s
            """
            params = [10000]

        cur.execute(ids_sql, params)
        candidate_ids = tuple(str(r[0]) for r in cur.fetchall())

    if not candidate_ids:
        elapsed = time.perf_counter() - t0
        return 0, [], f"{elapsed:.2f} sec"

    # 2️⃣ vecdb에서 main, sub에 해당하면서 qids_used가 NULL이 아닌 UID + vec 가져오기
    qids_sql = f"""
        SELECT {KURE_UID_COL} AS uid, {KURE_QIDS_COL} AS qids, {KURE_VEC_COL} AS vec
        FROM {KURE_TABLE}
        WHERE {KURE_MAIN_COL} = %s
          AND {KURE_SUB_COL}  = %s
          AND {KURE_QIDS_COL} IS NOT NULL
    """
    with connections["vecdb"].cursor() as cur:
        cur.execute(qids_sql, [main, sub])
        vec_rows = cur.fetchall() 

    if not vec_rows:
        elapsed = time.perf_counter() - t0
        return 0, [], f"{elapsed:.2f} sec"

    # 3️⃣ RDB 후보군과 uid 교집합
    candidate_set = set(candidate_ids)
    vec_filtered = [
        (str(uid), qids, vec) for uid, qids, vec in vec_rows
        if str(uid) in candidate_set
    ]
    if not vec_filtered:
        elapsed = time.perf_counter() - t0
        return 0, [], f"{elapsed:.2f} sec"

    uid_to_vec = {}
    uid_to_qids = {}
    qid_union = set()

    for uid, qids, vec in vec_filtered:
        uid_to_vec[uid] = vec
        q_list = _split_qids(qids)
        uid_to_qids[uid] = q_list
        qid_union.update(q_list)

    qid_cols = sorted([q for q in qid_union if re.fullmatch(r"q\d+", q)])

    # 4️⃣ RDB에서 이 uid들에 대한 패널 정보 + q답변 조회
    where_cols = _columns_from_where(where_sql)
    select_cols = (where_cols or RDB_BASE_COLS) + qid_cols
    seen, unique_cols = set(), []
    for c in select_cols:
        if c not in seen:
            seen.add(c)
            unique_cols.append(c)
    select_list = ", ".join(unique_cols) if unique_cols else "id"

    rdb_sql = f"""
        SELECT {select_list}
        FROM panel_records
        WHERE id = ANY(%s::text[])
    """
    with connections["default"].cursor() as cur:
        cur.execute(rdb_sql, [list(uid_to_vec.keys())])
        rdb_rows = cur.fetchall()
        rdb_cols = [c[0] for c in cur.description] if cur.description else []

    # 5️⃣ RDB 기준으로 "qids_used에 해당하는 답이 하나도 없는 uid" 제거
    col_idx = {c: i for i, c in enumerate(rdb_cols)}
    rows_raw = {}
    answers_map = {}
    valid_uids = []

    for r in rdb_rows:
        d = {c: r[i] for c, i in col_idx.items()}
        uid = str(d.get("id"))
        q_all = uid_to_qids.get(uid, [])

        answers = {}
        for q in q_all:
            if q in d and d[q] is not None:
                answers[q] = d[q]

        if not answers:
            continue

        rows_raw[uid] = d
        answers_map[uid] = answers
        valid_uids.append(uid)

    if not valid_uids:
        elapsed = time.perf_counter() - t0
        return 0, [], f"{elapsed:.2f} sec"

    # 6️⃣ opinion 임베딩
    qv = _kure_embed(opinion)
    qv_np = np.array(qv, dtype=np.float32)
    qnorm = np.linalg.norm(qv_np) + 1e-8

    # 7️⃣ "답이 있는 uid"만 대상으로 vec 유사도 계산
    sim_list = []
    for uid in valid_uids:
        vec = uid_to_vec[uid]
        if isinstance(vec, str):
            try:
                vec_list = ast.literal_eval(vec)
            except Exception:
                continue
        else:
            vec_list = vec

        vec_np = np.array(vec_list, dtype=np.float32)
        vnorm = np.linalg.norm(vec_np) + 1e-8
        sim = float(np.dot(qv_np, vec_np) / (vnorm * qnorm))
        sim_list.append((uid, sim))

    if not sim_list:
        elapsed = time.perf_counter() - t0
        return 0, [], f"{elapsed:.2f} sec"

    # 8️⃣ 유사도 평균 이상만 남기기
    mean_sim = sum(s for _, s in sim_list) / len(sim_list)
    sim_list_filtered = [(uid, s) for uid, s in sim_list if s >= mean_sim]
    if not sim_list_filtered:
        sim_list_filtered = sim_list

    sim_list_filtered.sort(key=lambda x: x[1], reverse=True)
    uid_ranked = [uid for uid, _ in sim_list_filtered]

    # limit이 0 이하 → 전체
    if limit and limit > 0:
        uid_page = uid_ranked[:limit]
    else:
        uid_page = uid_ranked

    total_count = len(uid_page)
    sim_map = {uid: sim for uid, sim in sim_list_filtered}

    rows_out = []
    for uid in uid_page:
        base = rows_raw[uid].copy()
        base["qids_used"] = list(answers_map[uid].keys())
        base["answers"] = answers_map[uid]
        base["sim"] = sim_map.get(uid)
        rows_out.append(base)

    elapsed = time.perf_counter() - t0
    return total_count, rows_out, f"{elapsed:.2f} sec"


# ===========================
# 메인 엔드포인트: 2단계 + 3단계 자동 분기
# ===========================
@csrf_exempt
@require_http_methods(["POST"])
def rdb_gateway(request):

    sql_text = ""
    opinion = None
    main = None
    sub = None

    try:
        body = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "JSON 파싱 실패"}, status=400)

    sql_text_in = (body.get("sql_text") or body.get("sql") or "").strip()
    query_in = (body.get("query") or "").strip()

    limit_param = body.get("limit")
    limit = int(limit_param) if limit_param is not None else 0 
    offset = int(body.get("offset") or 0) 
    candidate_cap = int(body.get("candidate_cap") or 1000)

    retrieved_docs  = body.get("retrieved_docs")
    retrieved_block = body.get("retrieved_block") or _normalize_retrieved_block(retrieved_docs)

    if sql_text_in:
        sql_text = sql_text_in
        opinion = body.get("opinion")
        main = body.get("main")
        sub = body.get("sub")
    elif query_in:
        if run_stage1_nl_to_meta is None:
            return JsonResponse(
                {"error": "메타 생성 함수(run_stage1_nl_to_meta)가 설정되어 있지 않습니다."},
                status=500,
            )
        try:
            meta = run_stage1_nl_to_meta(query_in)
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"메타 생성 호출 오류: {e}"}, status=500)

        sql_text = (meta.get("sql_text") or "").strip()
        opinion = meta.get("opinion")
        main = meta.get("main")
        sub = meta.get("sub")

        if not sql_text:
            return JsonResponse(
                {"error": "메타 생성 결과에 sql_text가 없습니다.", "meta": meta},
                status=500,
            )
    else:
        return JsonResponse({"error": "sql 또는 query 중 하나가 필요합니다."}, status=400)

    opinion_norm = None if _nullish(opinion) else opinion
    main_norm = None if _nullish(main) else _clean_tag(main)
    sub_norm = None if _nullish(sub) else _clean_tag(sub)

    where_sql = _extract_where(sql_text)
    sql_limit = _extract_limit(sql_text)  

    use_insight = bool(opinion_norm and main_norm and sub_norm)

    # ===========================
    # 3단계: opinion 기반 insight 필터
    # ===========================
    if use_insight:
        if limit and limit > 0 and sql_limit is not None:
            insight_limit = min(limit, sql_limit)
        elif limit and limit > 0:
            insight_limit = limit
        elif sql_limit is not None:
            insight_limit = sql_limit
        else:
            insight_limit = 0 

        try:
            total, data_rows, elapsed_str = _run_insight_core(
                sql_text=sql_text,
                opinion=opinion_norm,
                main=main_norm,
                sub=sub_norm,
                where_sql=where_sql,
                limit=insight_limit,
                offset=offset,
                candidate_cap=candidate_cap,
            )
        except Exception as e:
            return JsonResponse(
                {"error": f"Insight 처리 중 오류: {type(e).__name__}: {e}"},
                status=500,
            )

        return JsonResponse(
            {
                "sql": sql_text,
                "opinion": opinion_norm,
                "main": main_norm,
                "sub": sub_norm,
                "count": int(total),
                "sql_executed_time": elapsed_str,
                "data": data_rows,
                "retrieved_block": retrieved_block,
            },
            json_dumps_params={"ensure_ascii": False},
        )

    # ===========================
    # 2단계: RDB 검색
    # ===========================
    where_clause = f" {where_sql}" if where_sql else ""

    select_cols = _columns_from_where(where_sql) or ["id", "gender", "birth", "region", "subregion"]
    if "loyalty" not in select_cols:
        select_cols.append("loyalty")

    select_list = ", ".join(select_cols)
    lim_ph, _ = _vendor_placeholder()

    if sql_limit is not None:
        effective_limit = sql_limit
    elif not where_sql:
        effective_limit = 10000
    elif limit and limit > 0:
        effective_limit = limit
    else:
        effective_limit = None 

    order_by_clause = "ORDER BY loyalty DESC, id DESC"

    if effective_limit is not None:
        page_sql = f"""
            SELECT {select_list}
            FROM panel_records
            {where_clause}
            {order_by_clause}
            LIMIT {lim_ph}
        """.strip()
    else:
        page_sql = f"""
            SELECT {select_list}
            FROM panel_records
            {where_clause}
            {order_by_clause}
        """.strip()

    try:
        t0 = time.perf_counter()

        with connections["default"].cursor() as cur:
            if effective_limit is not None:
                cur.execute(page_sql, [int(effective_limit)])
            else:
                cur.execute(page_sql)
            rows, cols = _dictfetchall(cur)

        elapsed = time.perf_counter() - t0
        sql_executed_time = f"{elapsed:.2f} sec"
        total = len(rows)

        if sql_text_in and not query_in and opinion_norm is None:
            opinion_out = "N/A (User-provided SQL)"
            main_out = "N/A"
            sub_out = "N/A"
        else:
            opinion_out = opinion_norm
            main_out = main_norm
            sub_out = sub_norm

        if not rows or total == 0:
            return JsonResponse(
                {
                    "sql": sql_text,
                    "opinion": opinion_out,
                    "main": main_out,
                    "sub": sub_out,
                    "count": 0,
                    "sql_executed_time": sql_executed_time,
                    "data": [],
                },
                json_dumps_params={"ensure_ascii": False},
            )

        return JsonResponse(
            {
                "sql": sql_text,
                "opinion": opinion_out,
                "main": main_out,
                "sub": sub_out,
                "count": int(total),
                "sql_executed_time": sql_executed_time,
                "data": rows,
            },
            json_dumps_params={"ensure_ascii": False},
        )

    except Exception as e:
        if isinstance(e, IndexError):
            return JsonResponse(
                {
                    "sql": sql_text,
                    "opinion": opinion_norm,
                    "main": main_norm,
                    "sub": sub_norm,
                    "count": 0,
                    "sql_executed_time": "0.00 sec",
                    "data": [],
                    "message": "결과 없음 (IndexError)",
                },
                json_dumps_params={"ensure_ascii": False},
            )

        return JsonResponse(
            {
                "error": f"RDB 실행 오류: {type(e).__name__}: {e}",
                "sql": sql_text,
                "where": where_sql,
                "select_cols": select_cols,
                "db_vendor": connections["default"].vendor,
            },
            status=500,
        )
