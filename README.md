<h2>🎬DB Bridge</h2>
자연어 질의를 통한 고품질의 패널 추출

▶️ [GitHub에서 시연 영상 바로 재생하기](https://github.com/shinurim/SW_BE/issues/1#issue-3734958059)
<hr>

<h2>Preview</h2>
<p align="center">
  <img src="./assets/판넬.png" width="900" />
</p>
<hr>

<h2>👥 Members</h2>
<table align="center" cellpadding="14">
  <tr>
    <td align="center">
      <img src="./members/yurim.png"
           width="140" height="140"
           style="border:2px solid #ddd;border-radius:12px;object-fit:cover;" />
      <div style="margin-top:8px;font-weight:600;">
        <a href="https://github.com/shinurim">신유림</a>
      </div>
    </td>
    <td align="center">
      <img src="./members/mint02123.png"
           width="140" height="140"
           style="border:2px solid #ddd;border-radius:12px;object-fit:cover;" />
      <div style="margin-top:8px;font-weight:600;">
        <a href="https://github.com/mint02123">민재영</a>
      </div>
    </td>
    <td align="center">
      <img src="./members/jonghwa-8620.png"
           width="140" height="140"
           style="border:2px solid #ddd;border-radius:12px;object-fit:cover;" />
      <div style="margin-top:8px;font-weight:600;">
        <a href="https://github.com/jonghwa-8620">박종화</a>
      </div>
    </td>
    <td align="center">
      <img src="./members/suheon98.png"
           width="140" height="140"
           style="border:2px solid #ddd;border-radius:12px;object-fit:cover;" />
      <div style="margin-top:8px;font-weight:600;">
        <a href="https://github.com/suheon98">조수헌</a>
      </div>
    </td>
    <td align="center">
      <img src="./members/rokiosm.png"
           width="140" height="140"
           style="border:2px solid #ddd;border-radius:12px;object-fit:cover;" />
      <div style="margin-top:8px;font-weight:600;">
        <a href="https://github.com/rokiosm">문경록</a>
      </div>
    </td>
  </tr>
</table>
<hr>

<h2>🛠 Tech Stack</h2>
<ul>
  <li>
    <strong>Backend</strong>
    <ul>
      <li>Python</li>
      <li>Django 4.2.27</li>
      <li>Django REST Framework 3.16.1</li>
      <li>django-cors-headers 4.9.0</li>
    </ul>
  </li>
  <li>
    <strong>Database</strong>
    <ul>
      <li>PostgreSQL</li>
      <li>pgvector (Vector similarity search)</li>
      <li>psycopg2-binary (PostgreSQL adapter)</li>
    </ul>
  </li>
  <li>
    <strong>LLM / RAG</strong>
    <ul>
      <li>LangChain (langchain · langchain-core · langchain-community)</li>
      <li>OpenAI API (openai · langchain-openai)</li>
      <li>Anthropic Claude API (anthropic · langchain-anthropic)</li>
    </ul>
  </li>
  <li>
    <strong>Embeddings / NLP</strong>
    <ul>
      <li>Sentence-Transformers</li>
      <li>PyTorch</li>
      <li>Tokenizers</li>
    </ul>
  </li>
  <li>
    <strong>Data / Utilities</strong>
    <ul>
      <li>NumPy</li>
      <li>requests</li>
      <li>python-dotenv</li>
    </ul>
  </li>
  <li>
    <strong>Infrastructure</strong>
    <ul>
      <li>Docker (컨테이너)</li>
    </ul>
  </li>
</ul>

<h2>🚀Getting Started</h2>
<h3>Installation</h3>
<pre><code>git clone https://github.com/hansung-sw-capstone-2025-2/2025_8_B_BE.git
cd 2025_8_B_BE
</code></pre>
<h4>가상환경 설정 (bash)</h4>
<pre><code># 가상환경 생성
python -m venv venv
</code></pre>
<pre><code># 가상환경 활성화
source venv/Scripts/activate
</code></pre>
<pre><code># 라이브러리 설치
pip install -r requirements.txt
</code></pre>

<h3>Environment Variables</h3>
<p><code>.env</code> 파일을 생성하고 다음 변수를 설정하세요:</p>

<pre><code># Django
SECRET_KEY=your_django_secret_key
DEBUG=True

# LLM API KEY
ANTHROPIC_API_KEY=your_claude_api_key
OPENAI_API_KEY=your_openai_api_key

# Database (RDB)
DB_DEFAULT_PASSWORD=your_db_password

# Database (Vector DB - pgvector)
DB_VEC_PASSWORD=your_vecdb_password

# Logging
LOG_LEVEL=INFO
</code></pre>

<hr>
<h2>🧩Project Structure</h2>
<pre><code>
DJANGO_PROJ
├── apis/                         # 공통 API (유저/마이페이지 등)
│   ├── models.py                 # 사용자 관련 DB 모델
│   ├── urls.py                   # apis 라우팅
│   └── views_save.py             # 사용자 데이터 저장/조회 API 로직
│
├── insight/                      # Insight 생성
│   ├── db_routers.py             # DB 라우팅
│   ├── models.py                 # VecDB 모델 (RAG용)
│   ├── urls.py                   # insight 라우팅
│   └── views_insight.py          # Stage3 결과 기반 인사이트 생성
│
├── panel/                        # Panel 추출 파이프라인 (Stage1~3)
│   ├── models.py                 # 패널 메타/응답 RDB + 설문 응답 VecDB 모델(민감 데이터로 인한 제거)
│   ├── urls.py                   # panel 라우팅
│   ├── views_api.py              # Stage1: 자연어 → SQL / opinion / main / sub 변환
│   ├── views_panel.py            # Stage2/3: SQL DirectFilter + Vec 유사도 기반 추출
│   └── views_checkbox.py         # 체크박스 기반 DirectFilter 
│
├── swproject_backend/            # 프로젝트 설정 (Django core)
│   ├── settings.py               # 환경설정
│   ├── urls.py                   # 프로젝트 루트 라우팅
│   └── wsgi.py                   # WSGI 엔트리포인트
│
├── manage.py                     # Django 관리 커맨드 엔트리
└── requirements.txt              # Python 패키지 의존성 목록
</code></pre>

<hr>
<h2>📌API Endpoints</h2>
<h3>Auth API (<code>/api/v1/auth</code>)</h3>
<ul>
  <li><code>POST /api/v1/auth/login</code> - 로그인</li>
  <li><code>POST /api/v1/auth/signup</code> - 회원가입</li>
</ul>

<h3>MyPage API (<code>/api/v1/mypage</code>)</h3>
<ul>
  <li><code>GET /api/v1/mypage</code> - 마이페이지 조회</li>
  <li><code>PATCH /api/v1/mypage/password</code> - 프로필 비밀번호 변경</li>
</ul>

<h3>User API (<code>/api/v1/user</code>)</h3>
<ul>
  <li><code>PATCH /api/v1/user/profile</code> - 프로필 변경</li>
</ul>

<h3>Segments API (<code>/api/v1/segments</code>)</h3>
<ul>
  <li><code>GET /api/v1/segments</code> - 저장된 세그먼트 리스트</li>
  <li><code>DELETE /api/v1/segments/delete</code> - 세그먼트 삭제</li>
</ul>

<h3>Save API (<code>/api/v1/save</code>)</h3>
<ul>
  <li><code>POST /api/v1/save/save_segment</code> - 세그먼트 저장</li>
</ul>

<h3>Insights API (<code>/api/v1/insights</code>)</h3>
<ul>
  <li><code>GET /api/v1/insights/&lt;int:segment_id&gt;</code> - 저장된 세그먼트 인사이트 조회</li>
</ul>

<h3>Panel API (<code>/api/v1/panels</code>)</h3>
<ul>
  <li><code>POST /api/v1/panels/search</code> - 체크박스(DirectFilter) 기반 패널 검색</li>
</ul>

<h3>Insight Generation API (<code>/api/v1/insight</code>)</h3>
<ul>
  <li><code>POST /api/v1/insight/from-text</code> - 인사이트 생성</li>
</ul>

<h3>Search API (<code>/api/v1/search</code>)</h3>
<ul>
  <li><code>POST /api/v1/search/text</code> - 심플/복잡 질의 결과 반환</li>
  <li><code>POST /api/v1/search/sql</code> - 심플/복잡 질의 결과 반환</li>
</ul>
<hr>

<h2>🔑Key Features</h2>
<ul>
  <li>
    <strong>Stage1 변환 (NL → SQL/Opinion/Main/Sub)</strong>:<br>
    자연어 질의를 <code>sql</code>, <code>opinion</code>, <code>main</code>, <code>sub</code>로 변환하고,
    <code>opinion</code>이 <code>null</code>이면 Direct Filtering 방식으로 패널을 추출합니다.
  </li>

  <li>
    <strong>Opinion 기반 고정밀 패널 추출</strong>:<br>
    <code>opinion</code>이 존재하면 <code>sql</code>로 1차 후보군을 필터링한 뒤,
    <code>main/sub</code> 카테고리에 해당하는 응답을 가진 후보 중에서<br>
    opinion 유사도가 평균 이상인 후보군을 교집합하여 최종 적합 패널을 추출합니다.
  </li>
  <li>
    <strong>Checkbox 기반 Direct Filtering</strong>:<br>
    체크박스 필터 또한 Direct Filtering 방식을 채택하여
    5초 내 적합한 패널을 빠르게 추출합니다.
  </li>

  <li>
    <strong>Loyalty 기반 우선순위 제공 (Direct Filtering 전용)</strong>:<br>
    <code>sql</code>만으로 패널을 추출하는 경우 <code>loyalty</code> 값을 부여해
    충성도가 높은 고품질 패널을 우선 제공합니다.(Direct Filtering 방식에서만 적용)
  </li>
  
  <li>
    <strong>적합 패널 인사이트 생성</strong>:<br>
    주관이 포함된 자연어 질의의 경우 적합 그룹의 설문 응답을 바탕으로
    적절한 인사이트를 생성합니다.
  </li>

  <li>
    <strong>적합V전체 인사이트 생성</strong>:<br>
    적합 그룹의 설문 특징과 전체 그룹의 설문 특징을 비교 분석하여
    차별화된 인사이트를 제공합니다.
  </li>

  <li>
    <strong>질의 추천 (3개)</strong>:<br>
    <ul>
      <li>유사 질의 2개 추천</li>
      <li>
        비유사(반대 선상) 질의 1개 추천<br>
        적합 그룹의 특징을 더 명확히 파악할 수 있도록 지원합니다. - <span style="color:#666;">(예: 좋아하는 ↔ 싫어하는)</span>
      </li>
    </ul>
  </li>

  <li>
    <strong>세그먼트 저장</strong>:<br>
    생성된 인사이트를 세그먼트 형태로 저장하여 추후 재활용할 수 있습니다.
  </li>
</ul>

<hr>
<h2>LLM Models</h2>
<ul>
  <li>claude-haiku-4-5 : 사용자 자연어 질의 판별</li>
  <li>gpt-4o : 인사이트 생성</li>
</ul>

<hr>
<h2>License</h2>
<p>본 프로젝트는 한성대학교 기업연계 SW캡스톤디자인 수업에서 진행되었습니다.</p>
