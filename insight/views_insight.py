from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from langchain_openai import ChatOpenAI
from django.db import connections
from collections import Counter
from django.http import JsonResponse
import json, re

# LLM 초기화
llm_consistent = None
try:
    llm_consistent = ChatOpenAI(
        model='gpt-4o',
        api_key="",
        temperature=0,
        max_tokens=1000,
        top_p=0.3,
        frequency_penalty=0.1,
    )
except Exception as e:
    print(f"ChatOpenAI 초기화 실패: {e}")


# 공통 유틸
REQUIRED_STAGE3_KEYS = ["sql", "opinion", "main", "sub", "count", "data"]

#qid_used 매핑
QID_QUESTION_MAP = {
    #생략
}

def _strip_md_fence(content: str) -> str:
    if not isinstance(content, str):
        return content

    text = content.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            first = lines[0]
            if first.startswith("```"):
                lines = lines[1:]
        text = "\n".join(lines).strip()

        if text.endswith("```"):
            text = text[:-3].strip()

    return text


def _validate_stage3(stage3: dict):
    for k in REQUIRED_STAGE3_KEYS:
        if k not in stage3:
            return JsonResponse({"error": f"stage3 missing '{k}'"}, status=400)
    return None


def _dictfetchall(cur):
    cols = [c[0] for c in cur.description] if cur.description else []
    return [dict(zip(cols, r)) for r in cur.fetchall()], cols

from collections import Counter

def build_chart_rows(rows, qids):
    result = []

    for qid in qids:
        counter = Counter()
        for row in rows:
            if not isinstance(row, dict):
                continue
            val = row.get(qid)
            if val is None:
                continue
            text = str(val).strip()
            if not text:
                continue
            counter[text] += 1

        for answer_group, count in counter.items():
            result.append({
                "qpoll": qid,
                "answer_group": answer_group,
                "count": count,
            })

    return result



# 메인 엔드포인트: 인사이트 생성
@csrf_exempt
@require_http_methods(["POST"])
def generate_insight(request):
    import traceback
    print("⚡ [INSIGHT] generate_insight 진입")

    try:
        try:
            body = json.loads(request.body or "{}")
        except Exception:
            return JsonResponse({"error": "JSON 파싱 실패"}, status=400)

        user_input = (body.get("user_input") or "").strip()
        stage3 = body.get("stage3") or {}

        if not isinstance(stage3, dict):
            return JsonResponse({"error": "stage3는 dict여야 합니다."}, status=400)

        err = _validate_stage3(stage3)
        if err is not None:
            return err

        #구성요소
        sql_text        = (stage3.get("sql") or "").strip()
        opinion         = (stage3.get("opinion") or "").strip()
        main            = stage3.get("main")
        sub             = stage3.get("sub")
        sql_time        = stage3.get("sql_executed_time")
        rows_specific      = stage3.get("data") or []
        retrieved_block = stage3.get("retrieved_block")

        rows_all = rows_specific 
        q_counter = Counter()
        for row in rows_specific:
            if not isinstance(row, dict):
                continue
            qids = row.get("qids_used") or []
            if isinstance(qids, (list, tuple)):
                for q in qids:
                    if isinstance(q, str) and q.strip():
                        q_counter[q.strip()] += 1

        rep_qids = []
        rep_qids = [qid for qid, _ in q_counter.most_common()]  # 전체 사용
        rep_qids_pretty = "\n".join(
        f"- {qid}: {QID_QUESTION_MAP.get(qid, '')}" for qid in rep_qids
        )

        # 패널에 대한 차트 집계
        chart1_rows = build_chart_rows(rows_specific, rep_qids)
        chart1_json = json.dumps(chart1_rows, ensure_ascii=False)

        print("🐣 [DEBUG] chart1_rows 개수:", len(chart1_rows))
        print("🐣 [DEBUG] chart1_rows 상위 5개:", chart1_rows)

        # qid 기반 전체 패널 재조회
        _WHERE_RE = re.compile(
            r"select\s+\*\s+from\s+panel_records\s*(where\s+.+?)?\s*;?\s*$",
            flags=re.IGNORECASE | re.DOTALL,
        )

        def _extract_where(sql_text_local: str) -> str:
            s = (sql_text_local or "").strip()
            m = _WHERE_RE.search(s)
            if not m:
                return ""
            where = m.group(1) or ""
            where = re.split(
                r"\b(order\s+by|limit|offset)\b",
                where,
                flags=re.IGNORECASE
            )[0].strip()
            return where

        where_clause = _extract_where(sql_text)

        extra_cond = ""
        if rep_qids:
            col_conds = []
            for col in rep_qids:
                safe_col = col.strip()
                if not safe_col:
                    continue
                col_conds.append(
                    f'"{safe_col}" IS NOT NULL AND "{safe_col}" <> \'\''
                )

            if col_conds:
                extra_cond = "(" + " OR ".join(col_conds) + ")"
                if where_clause:
                    where_clause = f"{where_clause} AND {extra_cond}"
                else:
                    where_clause = f"WHERE {extra_cond}"

            page_sql = f"""
                SELECT *
                FROM panel_records
                {where_clause}
                ORDER BY id
            """

            with connections["default"].cursor() as cur:
                cur.execute(page_sql)
                rows_all, cols = _dictfetchall(cur)

        chart2_rows = build_chart_rows(rows_all, rep_qids)
        chart2_json = json.dumps(chart2_rows, ensure_ascii=False)

        print("🐣 [DEBUG] chart2_rows 개수:", len(chart2_rows))
        print("🐣 [DEBUG] chart2_rows 상위 5개:", chart2_rows)

        retrieved_json = (
            "없음" if retrieved_block is None
            else json.dumps(retrieved_block, ensure_ascii=False)
        )

        prompt1 = f"""
    [ROLE]
    당신은 패널 데이터 분석가입니다. 입력으로 주어진 질의 / 패널 / 의견 / 참고문헌(RAG)을 바탕으로
    "이미 매우 구체적인 WHERE 조건"을 더 포괄적인 인사이트로 승격하여 요약·시각화 제안을 합니다.

    [DATA INPUTS]
    - main = {main}
    - sub = {sub}
    - user_input: {user_input}
    - sql: {sql_text}
    - opinion: {opinion}
    - chart1_rows : {chart1_json}
    - chart2_rows : {chart2_json}
    - rep_qids_text: {rep_qids_pretty}

    [해시태그 목록]
    #main "여가와 문화"
    - "여행 이외의 모든 오프라인 문화생활"
    - "여행 기반 오프라인 문화생활"
    #main "일상 요소"
    - "경험 추억 등 과거와 관련된 행동"
    - "환경과 관련된 행동"
    - "일상적으로 반복하는 행동"
    #main "스타일 외모"
    - "패션 관련 뷰티"
    - "패션 외적인 뷰티"
    #main "기술 및 정보"
    - "디지털 도구 활용"
    #main "소비와 재정"
    - "소비를 통해 이득을 취하는 경우"
    - "소비를 통해 가치관을 표현"
    #main "건강 웰빙"
    - "신체적 건강"
    - "신체적·심적인 건강"

    [STRICT RULES]
    1) 절대 새로운 데이터 추측 금지. panel 및 [참고] 블록(retrieved_json)만 근거로 사용한다.
    2) 선정 이유, 체인 오브 소트, LLM 연산 과정은 어떤 형태로도 출력하지 않는다.
    (설명 문장, 마크다운, 주석, 메타 텍스트 모두 금지. 오직 지정된 JSON만 출력한다.)
    3) 아래 [출력 예시] JSON의 키 구조와 자료형을 엄격히 지킨다.
    - 문자열은 문자열, 배열은 배열, 객체는 객체로 유지한다.
    - 불필요한 필드 추가 금지.
    4) 패널 data에 있는 q@에 해당하는 정보(자연어값)는 rep_qids_text[q*]에서 가져온다.

    [per_question_analysis]
    3stagepanel에 존재하는 ***모든 q@***에 대해 분석한다.
    목적:
    - chart1_rows속에 포함된 q@에 대하여 rep_qids_text을 참고하여 각각의 문항의 응답 패턴이 현재 집단(3stagepanel)의 특성을 보여주는 근거를 1~2문장으로 설명한다.
    - chart1_rows의 응답 경향을 간결하게 요약하여, insight1에서 집단 전체 인사이트를 도출할 수 있는 기반을 만든다.
    
    규칙:
    - 근거는 chart1_rows의 응답만 사용한다.
    - chart1_rows와 rep_qids_text에 존재하지 않는 새로운 응답/정보/비율은 생성하지 않는다.
    - main·sub·opinion·[참고]는 보조적 연결로만 사용한다.
    - 모든 설명은 1~2문장의 간결하고 자연스러운 분석으로 작성한다.

    [insight1]
    [per_question_analysis]과 chart1_rows을 바탕으로 chart1_rows만 기준으로 하여 인사이트 보고서를 정리한다.
   
    - [insight1] 보고서는 아래 4요소를 반드시 포함한다:
    1) 현재 집단의 전반적 특징을 1문장으로 요약한다.
    2) 이 집단의 핵심 행동·태도 특징을 1~2문장으로 설명한다.
    3) chart1_rows들의 응답 패턴이 위 특징을 어떻게 뒷받침하는지 1~2문장으로 설명한다.
    4) 이러한 특징들이 왜 opinion과 어떻게 일치하는지 1문장의 결론으로 정리한다.
    - 전체 분량은 550자(단일 문단) 이내의 간결한 보고서로 작성한다.

    [title]
    - insight1을 바탕으로 집단을 대표하는 한 줄 문장을 생성한다.
    - 의미가 있고 정확해야 하며 user_input의 의도를 자연스럽게 반영해야 한다.
    - 과장 금지, 새 정보 금지.

    [mainQ]
    chart1_rows 여기에 해당하는 qpoll': @ 중 rep_qids_text를 참고하여 user_input를 결정짓는 가장 직접적인
    qpoll을 하나 뽑아낸다 모든 qpoll의 경우를 다 판단하여 하나로 예측한다

    [insight2]
    chart1_rows를 chart2_rows와 비교 분석한다. [chart1]과 [chart2]를 참고한다. 그러나 핵심은 chart1_rows이어야한다
    - 각 문항별 응답률(answer_ratio)을 계산하며 분모는 rows_full의 패널 수이고, 분자는 rows_all의 패널 수이다.
    - 응답률(answer_ratio) = (분자 / 분모) * 100(반올림하여 정수로 표기)
    - 응답률(answer_ratio)이 높은 순서대로 문항을 정렬하여 나열한다. (내림차순)
    - "이 패널들은 <설명 문구>와 관련된 설문문항들인 \"<문항1>\"(<ratio1>%),
        \"<문항2>\"(<ratio2>%), \"<문항3>\"(<ratio3>%)의 응답 결과를 통해 해당 집단의 특성을 설명할 수 있습니다." 
    - 위에 문장을 포함하여 user_input에 대해 적합한 패널(chart1_rows)과 전체 패널(chart2_rows)의 차이점을 중점으로
      500자로 보고서 형식으로 요약 및 정리한다

    [keywords]
    - [insight1]의 내용을 바탕으로 핵심 단어 키워드 3개 를 추출한다.
    - main, sub, sql 조건, opinion 텍스트에서 직접 가져오지 않는다.
    - 즉, main 이름, sub 이름, 성별/연령/지역 같은 sql 조건, 
        또는 user_input의 opinion 문장을 그대로 가져오는 것은 금지이다.

    [similar_queries]
    user_input과 유사한 질의를 추천해 사용자의 연속적인 사용을 이끌어내기 위한 용도이다.
    총 3개의 질의를 추천한다.

    1) 반대 집단 질의 (1개)
    - 현재 집단의 특성이 뚜렷하게 드러나는 경우,
    사람의 특징(sql 조건: 성별, 연령, 지역, loyalty 등)은 최대한 유지하면서 opinion만 "반대 의미"로 바꾼다.
    - 예시 개념: 좋아하는 ↔ 싫어하는, 잘하는 ↔ 못하는, 자주 한다 ↔ 거의 하지 않는다

    2) 유사한 특징이지만 다른 집단 질의 (2개)
    - (유사쿼리1) 같은 main 내에서, 다른 sub에 해당하는 쿼리를 제안한다.
    예: main "소비와 재정" 안에서, "소비를 통해 이득" → "소비를 통해 가치관 표현" 으로 전환
    - (유사쿼리2) main/sub는 유지하되 gender, age, marriage 등 정량적인 사람의 특징(sql 조건)만 변경하여
    비교해볼 수 있는 질의를 만든다.

    [출력 예시]
    user_input예시: 서울 사는 여자 중 환경문제에 관심이 많은 사람
    {{
        "per_question_analysis":{{
    "q8": "평소 일회용 비닐봉투 사용을 줄이기 위해 장바구니/에코백 활용과 근처로 뛰어가 비를 피함를 한다는 응답이 각각 @%, @%를 차지한다. 이는 일회용 비닐봉투의 사용을 줄이기에 환경 문제에 관심이 많다고 볼 수 있다",
    "q2": "",
    }},
    "insight1": "보고서",
    "insight2":"보고서",
    "similar_queries": [
    "<서울 사는 여자 중 환경문제에 관심이 없는 사람>",
    "<서울 사는 여자 중 경험과 추억이 많은 사람>",
    "<서울 사는 남자 중 환경문제에 관심이 많은 사람>"
    ],
    "keywords": [
    "<keyword1>",
    "<keyword2>",
    "<keyword3>"
    ],
    "title": "",
    "mainQ: "q8"
    }}
    [참고]
    {retrieved_json}
    """

        try:
            if llm_consistent is None:
                print("❌ [INSIGHT] llm_consistent 가 None 입니다. ChatOpenAI 초기화 실패")
                return JsonResponse(
                    {"error": "LLM이 초기화되지 않았습니다. (llm_consistent is None)"},
                    status=500,
                    json_dumps_params={"ensure_ascii": False},
                )

            print("✅ [INSIGHT] LLM 호출 직전입니다.")
            result = llm_consistent.invoke(prompt1)

            # content 추출
            content = getattr(result, "content", str(result))

            print("🔥 [LLM RAW CONTENT START]")
            print(content)
            print("🔥 [LLM RAW CONTENT END]")

        except Exception as e:
            import traceback
            print("❌ [INSIGHT] LLM 호출 실패:", repr(e))
            traceback.print_exc()
            return JsonResponse(
                {"error": f"LLM 호출 실패: {type(e).__name__}: {e}"},
                status=500,
                json_dumps_params={"ensure_ascii": False},
            )

        #JSON 파싱
        try:
            clean = _strip_md_fence(content)
            raw = json.loads(clean)
        except Exception:
            raw = {"raw": content}

        chart_specific = {
            "spec": ["answer_group", "count", "qpoll"],
            "rows": chart1_rows,
        }
        chart_full = {
            "spec": ["answer_group", "count", "qpoll"],
            "rows": chart2_rows,
        }

        mainQ = raw.get("mainQ")

        if mainQ:
            chart_specific_mainQ = {
                "spec": chart_specific["spec"],
                "rows": [r for r in chart1_rows if r.get("qpoll") == mainQ],
            }
            chart_full_mainQ = {
                "spec": chart_full["spec"],
                "rows": [r for r in chart2_rows if r.get("qpoll") == mainQ],
            }
        else:
            chart_specific_mainQ = {
                "spec": chart_specific["spec"],
                "rows": [],
            }
            chart_full_mainQ = {
                "spec": chart_full["spec"],
                "rows": [],
            }

        per_question_analysis = raw.get("per_question_analysis", {})

        insights = []
        insight1_text = raw.get("insight1") or ""
        if insight1_text:
            insights.append({"id": "insight1", "text": insight1_text})

        insight2_text = raw.get("insight2") or ""
        if insight2_text:
            insights.append({"id": "insight2", "text": insight2_text})

        similar_queries = raw.get("similar_queries", [])
        keywords        = raw.get("keywords", [])
        title           = raw.get("title", "")

        insight_payload = {
            "charts": {
                "chart_specific": chart_specific_mainQ,    
                "chart_full": chart_full_mainQ,              
            },
            "per_question_analysis": per_question_analysis,
            "insights": insights,
            "similar_queries": similar_queries,
            "keywords": keywords,
            "title": title,
        }


        return JsonResponse(
            {
                "stage3": {
                    "sql_executed_time": sql_time,
                },
                "insight": insight_payload,
            },
            json_dumps_params={"ensure_ascii": False},
        )
    
    except Exception as e:
        print(" [INSIGHT] generate_insight 전체에서 예외 발생:", repr(e))
        traceback.print_exc()
        return JsonResponse(
            {"error": f"INTERNAL ERROR ({type(e).__name__}): {e}"},
            status=500,
            json_dumps_params={"ensure_ascii": False},
        )