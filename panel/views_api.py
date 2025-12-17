import os, re
from django.db import connections
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from sentence_transformers import SentenceTransformer

KURE_MODEL_PATH = os.getenv("KURE_MODEL_PATH", "nlpai-lab/KURE-v1")
KURE_NORMALIZE  = os.getenv("KURE_NORMALIZE", "false").lower() in ("1", "true", "yes")
DOCVEC_VEC_COL  = "embedding"  

# KURE 임베딩
_sentence_model = None
def _get_kure_model():
    global _sentence_model
    if _sentence_model is None:
        _sentence_model = SentenceTransformer(KURE_MODEL_PATH, device="cpu")
    return _sentence_model

def _kure_embed(text: str) -> list[float]:
    model = _get_kure_model()
    vec = model.encode([text], normalize_embeddings=KURE_NORMALIZE)[0]
    return [float(x) for x in vec.tolist()]

def _as_vector_param(vec):
    return "[" + ",".join(str(float(x)) for x in vec) + "]"

#DB 헬퍼

def _nullish(v) -> bool:
    return v is None or str(v).strip().lower() in ("","-", "null", "none")

# 문서 검색 (KURE + pgvector)
def _retrieve_docs_from_insight(query_text: str, k: int = 5):
    """
    insight_docvec.embedding 기반 코사인 유사도 검색 → LLM 참고용 문맥 반환
    """
    try:
        qv = _kure_embed(query_text)
        qv_param = _as_vector_param(qv)
    except Exception as e:
        return {"error": f"KURE 임베딩 실패: {e}", "retrieved_docs": [], "retrieved_block": ""}

    sql = f"""
        SELECT id, content, 1.0 - ({DOCVEC_VEC_COL} <=> %s::vector) AS score
        FROM insight_docvec
        WHERE content IS NOT NULL
        ORDER BY {DOCVEC_VEC_COL} <=> %s::vector ASC
        LIMIT %s;
    """

    try:
        with connections["vecdb"].cursor() as cur:
            cur.execute(sql, [qv_param, qv_param, int(k)])
            rows = cur.fetchall()
    except Exception as e:
        return {"error": f"insight_docvec 검색 실패: {e}", "retrieved_docs": [], "retrieved_block": ""}

    docs = []
    for rid, content, score in rows:
        text = (content or "").strip()
        if len(text) > 800:
            text = text[:800] + " ..."
        docs.append({"id": str(rid), "score": round(score or 0, 4), "content": text})

    block = "\n\n".join(f"[{i+1}] {d['content']}" for i, d in enumerate(docs))
    return {"retrieved_docs": docs, "retrieved_block": block}

# LLM 초기화
llm_consistent = ChatAnthropic(
    model="claude-opus-4-20250514", #claude-haiku-4-5
    anthropic_api_key="",
    temperature=0,
    max_tokens=1000,
)

# 정규식
SQL_REGEX     = re.compile(r'"?sql"?\s*:\s*"?(SELECT[^"\n]+)"?', re.IGNORECASE | re.DOTALL)
OPINION_REGEX = re.compile(r'"?opinion"?\s*:\s*"?(.*?)"?\s*(?:\n|$)', re.IGNORECASE | re.DOTALL)
MAIN_REGEX    = re.compile(r'"?main"?\s*:\s*"?(.*?)"?\s*(?:\n|$)', re.IGNORECASE | re.DOTALL)
SUB_REGEX     = re.compile(r'"?sub"?\s*:\s*"?(.*?)"?\s*(?:\n|$)', re.IGNORECASE | re.DOTALL)

# API
def run_stage1_nl_to_meta(user_input: str) -> dict:

    user_input = (user_input or "").strip()
    if not user_input:
        raise ValueError("질문이 비어 있습니다.")

    # 2️⃣ 문서 참조 (KURE + pgvector)
    retr = _retrieve_docs_from_insight(user_input, k=2)
    retrieved_block = retr.get("retrieved_block", "")
    retrieved_docs_list = retr.get("retrieved_docs", [])

    print("🔍 Retrieved Block Preview:")
    print("──────────────────────────────")
    print(retrieved_block[:800])
    print("──────────────────────────────")

    # 프롬프트 구성
    message = f"""
    역할: 사용자 입력으로 SQL (WHERE절)과 오피니언/해시태그를 동시 생성.
    ---
    ## 1. SQL (meta query) 규칙
    **출력:** `SELECT * FROM panel_records WHERE ...;` (조건 없으면 WHERE 절 생략)
    **형식:** 필드 중 값이 있는 것만 AND 연결. 문자열 값은 반드시 작은따옴표(')로 묶음.
    **필드:** gender, birth, region, subregion, married, nchild, famsize, education_level, job, work, p_income, h_income, owned_products, phone_brand, phone_model, car_ownship, car_manufacturer, car_model, ever_smoked, brand_smoked, brand_smoked_ETC, ever_esmoked, ever_smoked_brand_ETC, ever_alcohol, ever_smoked_ETC, p_company.
    **특수 규칙:**
    1.  **gender/married/nchild/famsize:** '여/여자'→'F', '남/남자'→'M'. '결혼했다'→`married='기혼'`. 자녀있음→`nchild > 0`. `nchild`는 int. `famsize`는 `'1명'...'5명 이상'` 문자열.
    2.  **휴대폰:** `phone_model LIKE '%값%'` 사용. `car_model`은 동등비교(`=`)만.
        * **최신폰:** `phone_model LIKE '%아이폰16%' OR phone_model LIKE '%갤럭시 S25%'`
        * **샤오미 계열:** `phone_model LIKE '%레드미%' OR phone_model LIKE '%Redmi%' OR phone_model LIKE '%포코%' OR phone_model LIKE '%Poco%'`만 사용.
    3.  **보유제품(owned_products):** 제품군 언급 시 그룹 내 모든 세부 제품을 OR로 연결 (`owned_products LIKE '%X%' OR ...`).

    ## 2. 직군(Work/Job) 데이터 (우선순위: Work > Job)
    **[Rule A] 직무(Work) - 100% 일치 시 사용 (`=`)**
    > ['경영/인사/총무/사무', '재무/회계/경리', '금융/보험/증권', '마케팅/광고/홍보/조사', '무역/영업/판매/매장관리', '고객상담/TM', '전문직/법률/인문사회/임원', '의료/간호/보건/복지', '교육/교사/강사/교직원', '방송/언론', '문화/스포츠', '서비스/여행/숙박/음식/미용/보안', '유통/물류/운송/운전', '디자인', '인터넷/통신', 'IT', '모바일', '게임', '전자/기계/기술/화학/연구/개발', '건설/건축/토목/환경', '생산/정비/기능/노무', '비경제활동인구', '종교', '농업/어업/축산업', '단기근로']

    **[Rule B] 직업(Job) - 의미상 가장 가까운 값 선택 (`=`)**
    Rule A 실패 시, 아래 리스트 중 사용자의 직업이 포함되거나 가장 유사한 값을 선택.
    > ['전문직 (의사, 간호사, 변호사, 회계사, 예술가, 종교인, 엔지니어, 프로그래머, 기술사 등)', '교직 (교수, 교사, 강사 등)', '경영/관리직 (사장, 대기업 간부, 고위 공무원 등)', '사무직 (기업체 차장 이하 사무직 종사자, 공무원 등)', '판매직 (보험판매, 세일즈맨, 도/소매업 직원, 부동산 판매, 행상, 노점상 등)', '서비스직 (미용, 통신, 안내, 요식업 직원 등)', '생산/노무직 (차량운전자, 현장직, 생산직 등)', '기능직 (기술직, 제빵업, 목수, 전기공, 정비사, 배관공 등)', '자영업 (제조업, 건설업, 도소매업, 운수업, 무역업, 서비스업 경영)', '농업/임업/축산업/광업/수산업', '임대업', '중/고등학생', '대학생/대학원생', '전업주부', '군인', '공공안전', '문화콘텐츠', '보건복지', '무직/구직/시험준비/건강사유', '퇴직/연금생활자', '단기근로']

    ## 3. 오피니언 (opinion) 및 해시태그 규칙
    **판정:** 사용자의 선호/의견/감정/가치/취향/습관/루틴/빈도/행동 의도가 드러나면 **존재**. 단순 사실(거주지, 나이, 직업 등)만 있으면 **부재**.
    **존재 시:**
    1.  **opinion:** 사용자 입력 반영하여 군더더기 없이 한 문장으로 요약.
    2.  **main/sub:** 아래 목록에서 각각 1개 선택. 다른 단어 추가/변형/순서 변경 금지.
    **부재 시:** `opinion`, `main`, `sub` 모두 "-" 처리.
    **메타 데이터 없이 오피니언과 main,sub만 존재할때 sql은 "sql": "SELECT * FROM panel_records;"로 반환
    **해시태그 목록:**
    * `#main "여가와 문화"` / `- "여행 이외의 모든 오프라인 문화생활"`, `- "여행 기반 오프라인 문화생활"`
    * `#main "일상 요소"` / `- "경험 추억 등 과거와 관련된 행동"`, `- "환경과 관련된 행동"`, `- "일상적으로 반복하는 행동"`
    * `#main "스타일 외모"` / `- "패션 관련 뷰티"`, `- "패션 외적인 뷰티"`
    * `#main "기술 및 정보"` / `- "디지털 도구 활용"`
    * `#main "소비와 재정"` / `- "소비를 통해 이득을 취하는 경우"`, `- "소비를 통해 가치관을 표현"`
    * `#main "건강 웰빙"` / `- "신체적 건강"`, `- "신체적·심적인 건강"` 

    [특정 패널 수]
    **찾는 패널의 수가 특정되었을때 (100명, 50명, 30명) LIMIT을 걸어 수를 조절한다
    ** 패널 수가 특정되지 않았을때는 LIMIT을 걸지 않는다

    ## 4. 최종 출력 규칙 (절대 준수)
    **출력:** "sql","opinion","main","sub" 4가지 키만 JSON 형식이 아닌 그대로 출력.
    **부재:** "-"으로만 처리. 선정 이유 및 연산 과정 출력 금지.

    **[출력예시]**
    "sql": "SELECT * FROM panel_records WHERE region = '서울' AND job = '대학생/대학원생' AND ever_smoked = '담배를 피워본 적이 없다';",
    "opinion": "환경문제에 관심이 많다"
    "main" : "일상 요소"
    "sub" : "환경과 관련된 행동"

    user_input:
    {user_input}

    참고:
    {retrieved_block}
    """

    # 4️⃣ LLM 호출
    try:
        resp = llm_consistent.invoke([HumanMessage(content=message)])
        content = getattr(resp, "content", "").strip()
    except Exception as e:
        return {"error": f"LLM 오류: {str(e)}"}

    # 5️⃣ 파싱
    m_sql = SQL_REGEX.search(content)
    m_op  = OPINION_REGEX.search(content)
    m_ma  = MAIN_REGEX.search(content)
    m_su  = SUB_REGEX.search(content)

    if not m_sql:
        return {
            "error": 'LLM 응답에서 "sql" 항목을 찾지 못했습니다.',
            "llm_output": content[:800]
        }

    sql_text = m_sql.group(1).strip().rstrip(";")
    opinion  = (m_op.group(1).strip() if m_op else "")
    main     = (m_ma.group(1).strip() if m_ma else "")
    sub      = (m_su.group(1).strip() if m_su else "")

    # 6️⃣ 정규화: "-", "", "null" → None
    opinion_value = None if _nullish(opinion) else opinion
    main_value    = None if _nullish(main)    else main
    sub_value     = None if _nullish(sub)     else sub

    #  main/sub 중 하나라도 비면 opinion도 None으로 강제(= 2단계로)
    if opinion_value is not None and (main_value is None or sub_value is None):
        opinion_value = None

    # 7️⃣ 반환
    return {
        "sql_text": sql_text,
        "opinion": opinion_value,
        "main": main_value,
        "sub": sub_value,
        "retrieved_docs": retrieved_docs_list
    }
