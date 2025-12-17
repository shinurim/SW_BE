import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import connections

# 2025년 기준
BASE_YEAR = 2025

BIRTH_AGE_RANGE = {
    "10대": (10, 19),
    "20대": (20, 29),
    "30대": (30, 39),
    "40대": (40, 49),
    "50대": (50, 59),
    "60대+": (60, 120),
}

GENDER_MAP = {
    "남성": "M",  
    "여성": "F"
}

def _dictfetchall(cur):
    cols = [c[0] for c in cur.description] if cur.description else []
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _build_in_clause(column_name, values, params):
    if not values:
        return None
    placeholders = ", ".join(["%s"] * len(values))
    params.extend(values)
    return f"{column_name} IN ({placeholders})"


def _build_birth_clause(birth_labels, params):
    if not birth_labels:
        return None

    sub_clauses = []

    for label in birth_labels:
        age_range = BIRTH_AGE_RANGE.get(label)
        if not age_range:
            continue

        min_age, max_age = age_range 

        max_birth_year = BASE_YEAR - min_age 
        min_birth_year = BASE_YEAR - max_age 

        sub_clauses.append("(birth BETWEEN %s AND %s)")
        params.extend([min_birth_year, max_birth_year])

    if not sub_clauses:
        return None

    return "(" + " OR ".join(sub_clauses) + ")"


def direct_panel(filters: dict):

    gender_list = filters.get("gender", [])
    birth_list = filters.get("birth", [])
    region_list = filters.get("region", [])
    job_list = filters.get("job", [])

    gender_list = [GENDER_MAP[g] for g in gender_list if g in GENDER_MAP]

    where_clauses = []
    params = []

    clause = _build_in_clause("gender", gender_list, params)
    if clause:
        where_clauses.append(clause)

    clause = _build_in_clause("region", region_list, params)
    if clause:
        where_clauses.append(clause)

    clause = _build_in_clause("job", job_list, params)
    if clause:
        where_clauses.append(clause)

    clause = _build_birth_clause(birth_list, params)
    if clause:
        where_clauses.append(clause)

    sql = "SELECT * FROM panel_records"
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    print("[CHECKBOX][SQL]", sql, params)

    with connections["default"].cursor() as cur:
        cur.execute(sql, params)
        rows = _dictfetchall(cur)
    return rows


@csrf_exempt
@require_http_methods(["POST"])
def checkbox_search_view(request):
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    try:
        rows = direct_panel(body)
    except Exception as e:
        print("[CHECKBOX][ERROR]", repr(e))
        return JsonResponse(
            {
                "error": f"[CHECKBOX] {type(e).__name__}: {e}"
            },
            status=500,
        )

    return JsonResponse(rows, safe=False)
