<h2>🎬DB Bridge</h2>
자연어 질의를 통한 고품질의 패널 추출

▶️ [GitHub에서 시연 영상 바로 재생하기](https://github.com/shinurim/SW_BE/issues/1#issue-3734958059)
<hr>

<h2>👀Preview</h2>
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
python -m venv venv<br>
# 가상환경 활성화
source venv/Scripts/activate<br>
# 라이브러리 설치
pip install -r requirements.txt
</code></pre>

<hr>
<h3>Environment Variables</h3>
<p><code>.env</code> 파일을 생성하고 다음 변수를 설정하세요:</p>
<pre><code># Django
SECRET_KEY=your_django_secret_key
DEBUG=True<br>
# LLM API KEY
ANTHROPIC_API_KEY=your_claude_api_key
OPENAI_API_KEY=your_openai_api_key<br>
# Database (RDB)
DB_DEFAULT_PASSWORD=your_db_password<br>
# Database (Vector DB - pgvector)
DB_VEC_PASSWORD=your_vecdb_password<br>
# Logging
LOG_LEVEL=INFO
</code></pre>
