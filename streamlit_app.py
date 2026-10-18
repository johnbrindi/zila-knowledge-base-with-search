import json
import time
from urllib.parse import quote

import httpx
import streamlit as st


st.set_page_config(
    page_title="Zila API Studio",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');

    :root {
        --ink: #eaf0ff;
        --muted: #9ba8c5;
        --panel: #111a2d;
        --line: rgba(148, 163, 184, .16);
        --accent: #8b7cff;
        --teal: #58e0c1;
    }
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .stApp {
        color: var(--ink);
        background:
            radial-gradient(ellipse at 80% 0%, rgba(91, 74, 190, .20), transparent 35%),
            radial-gradient(ellipse at 0% 20%, rgba(34, 170, 151, .08), transparent 28%),
            #080d19;
    }
    [data-testid="stHeader"] { background: rgba(8, 13, 25, .75); }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #10182a 0%, #0c1322 100%);
        border-right: 1px solid var(--line);
    }
    [data-testid="stSidebar"] > div:first-child { padding-top: 1.4rem; }
    .block-container { max-width: 1440px; padding-top: 2rem; padding-bottom: 4rem; }
    h1, h2, h3 { font-family: 'Manrope', sans-serif !important; letter-spacing: -.035em; }
    h1 { font-size: clamp(2rem, 4vw, 3.15rem) !important; font-weight: 800 !important; }
    h2 { font-weight: 700 !important; }
    p, .stCaption { color: var(--muted); }
    .brand {
        display: flex; align-items: center; gap: .7rem; margin: 0 0 2rem;
        font: 800 1.2rem 'Manrope', sans-serif; letter-spacing: -.04em;
    }
    .brand-mark {
        display: grid; place-items: center; width: 2.3rem; height: 2.3rem;
        color: #090e1a; border-radius: .75rem;
        background: linear-gradient(135deg, var(--teal), #a2f6df);
        box-shadow: 0 0 24px rgba(88, 224, 193, .2);
    }
    .eyebrow {
        color: var(--teal); font-size: .74rem; font-weight: 700;
        letter-spacing: .13em; text-transform: uppercase;
    }
    .hero {
        padding: 1.8rem 2rem; margin: .2rem 0 1.4rem;
        border: 1px solid var(--line); border-radius: 1.25rem;
        background: linear-gradient(120deg, rgba(28, 39, 64, .92), rgba(17, 26, 45, .76));
        box-shadow: 0 18px 70px rgba(0, 0, 0, .16);
    }
    .hero p { max-width: 720px; font-size: 1.02rem; line-height: 1.65; margin-bottom: 0; }
    .panel {
        padding: 1.2rem 1.3rem; border-radius: 1rem; border: 1px solid var(--line);
        background: linear-gradient(145deg, rgba(20, 30, 50, .88), rgba(13, 21, 37, .88));
        min-height: 116px;
    }
    .panel-label { color: var(--muted); font-size: .85rem; }
    .panel-value { color: var(--ink); font: 700 1.3rem 'Manrope', sans-serif; margin-top: .55rem; }
    div[data-testid="stTabs"] button {
        border-radius: .75rem; font-weight: 600; padding: .65rem 1rem;
    }
    div[data-testid="stTabs"] button[aria-selected="true"] {
        color: #d9d5ff; background: rgba(139, 124, 255, .13);
    }
    .stButton > button, .stFormSubmitButton > button {
        border: 1px solid rgba(139, 124, 255, .42);
        border-radius: .75rem; font-weight: 700;
        color: #fff; background: linear-gradient(135deg, #7666ed, #5d55c8);
        transition: transform .16s ease, box-shadow .16s ease;
        min-height: 2.7rem;
    }
    .stButton > button:hover, .stFormSubmitButton > button:hover {
        color: #fff; border-color: #a69bff; transform: translateY(-1px);
        box-shadow: 0 8px 24px rgba(107, 92, 231, .24);
    }
    [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
    [data-testid="stTextArea"] textarea, [data-testid="stSelectbox"] div[role="combobox"] {
        border-radius: .7rem;
    }
    [data-testid="stExpander"] {
        border: 1px solid var(--line); border-radius: .8rem; background: rgba(17, 26, 45, .55);
    }
    [data-testid="stMetric"] {
        padding: .9rem 1rem; border: 1px solid var(--line); border-radius: .85rem;
        background: rgba(17, 26, 45, .72);
    }
    hr { border-color: var(--line); }
    code { color: #b9b1ff !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


def show_response(response: httpx.Response, elapsed_ms: float) -> None:
    try:
        body = response.json()
        is_json = True
    except ValueError:
        body = response.text
        is_json = False

    st.session_state["last_result"] = {
        "status": response.status_code,
        "elapsed_ms": round(elapsed_ms, 1),
        "body": body,
    }
    status_col, time_col = st.columns(2)
    status_col.metric("HTTP status", response.status_code)
    time_col.metric("Response time", f"{elapsed_ms:.0f} ms")

    if response.is_success:
        st.success("Request completed.")
    else:
        st.error(f"Request failed with HTTP {response.status_code}.")

    with st.expander("Response body", expanded=True):
        if is_json:
            st.json(body)
        else:
            st.code(body or "(empty response)", language="text")


def send_request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json_body: dict | list | None = None,
    files: dict | None = None,
    data: dict | None = None,
    needs_key: bool = True,
) -> None:
    base_url = st.session_state.get("api_url", "").strip().rstrip("/")
    api_key = st.session_state.get("api_key", "")
    if not base_url:
        st.error("Enter the API base URL in the sidebar.")
        return
    if needs_key and not api_key:
        st.error("Enter your API key in the sidebar. Protected endpoints require `x-api-key`.")
        return

    headers = {"x-api-key": api_key} if needs_key else {}
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=180.0) as client:
            response = client.request(
                method,
                f"{base_url}{path}",
                headers=headers,
                params=params,
                json=json_body,
                files=files,
                data=data,
            )
    except httpx.RequestError as exc:
        st.error(f"Could not reach the API: {exc}")
        return
    show_response(response, (time.perf_counter() - started) * 1000)


def csv_values(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


st.sidebar.markdown(
    '<div class="brand"><span class="brand-mark">Z</span><span>Zila API Studio</span></div>',
    unsafe_allow_html=True,
)
st.sidebar.markdown('<div class="eyebrow">Connection</div>', unsafe_allow_html=True)
st.sidebar.text_input("API base URL", value="http://localhost:8000", key="api_url")
st.sidebar.text_input("API key", type="password", key="api_key", help="Sent as the x-api-key header.")
st.sidebar.caption("Health checks are public. All /v1 endpoints use your API key.")
st.sidebar.divider()
st.sidebar.markdown("**Quick connection check**")
if st.sidebar.button("Check API health", use_container_width=True):
    send_request("GET", "/health", needs_key=False)
st.sidebar.caption("The API must be running before you send a request.")

st.markdown(
    """
    <div class="hero">
        <div class="eyebrow">Developer workspace · API testing</div>
        <h1>Test your endpoints.<br>Keep the flow moving.</h1>
        <p>Upload course material, query indexed content, and exercise the weekly opportunity digest API—all from one clean workspace.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

overview_cols = st.columns(3)
for col, label, value in zip(
    overview_cols,
    ("Document pipeline", "Knowledge search", "Opportunity digests"),
    ("Upload · status · delete", "Scoped semantic search", "Preview · run · publish"),
):
    col.markdown(
        f'<div class="panel"><div class="panel-label">{label}</div>'
        f'<div class="panel-value">{value}</div></div>',
        unsafe_allow_html=True,
    )

st.write("")
documents_tab, search_tab, digests_tab = st.tabs(
    ["Documents", "Search", "Opportunity digests"]
)

with documents_tab:
    st.subheader("Document endpoints")
    st.caption("Upload files for asynchronous ingestion, inspect their progress, or remove a document.")
    document_action = st.radio(
        "Document action",
        ["Upload", "Check status", "Delete"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if document_action == "Upload":
        with st.form("upload_document", clear_on_submit=False):
            uploaded_file = st.file_uploader(
                "Choose a document",
                type=["pdf", "docx", "pptx", "md", "markdown", "txt"],
                help="Supported formats: PDF, DOCX, PPTX, Markdown, and plain text.",
            )
            col1, col2 = st.columns(2)
            department = col1.selectbox(
                "Department",
                [
                    "ml", "web-frontend", "mobile", "cyber-security",
                    "embedded-system", "design", "web-backend", "gen-ai",
                ],
            )
            cohort_id = col2.text_input("Cohort ID", placeholder="e.g. cohort-2026")
            col3, col4 = st.columns(2)
            title = col3.text_input("Title (optional)", placeholder="Defaults to filename")
            document_id = col4.text_input(
                "Document ID (optional)",
                help="Pass an existing ID to replace a document.",
            )
            with st.expander("Chunking options"):
                col5, col6 = st.columns(2)
                chunk_size = col5.number_input(
                    "Chunk size", min_value=100, max_value=1500, value=700
                )
                chunk_overlap = col6.number_input(
                    "Chunk overlap", min_value=0, max_value=300, value=100
                )
            upload_clicked = st.form_submit_button("Upload and queue ingestion")

        if upload_clicked:
            if uploaded_file is None:
                st.error("Choose a file before uploading.")
            elif not cohort_id.strip():
                st.error("Enter a cohort ID.")
            elif chunk_overlap >= chunk_size:
                st.error("Chunk overlap must be smaller than chunk size.")
            else:
                form_data = {
                    "department": department,
                    "cohort_id": cohort_id.strip(),
                    "chunk_size": str(chunk_size),
                    "chunk_overlap": str(chunk_overlap),
                }
                if title.strip():
                    form_data["title"] = title.strip()
                if document_id.strip():
                    form_data["document_id"] = document_id.strip()
                upload_file = (
                    "file",
                    (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type),
                )
                send_request(
                    "POST",
                    "/v1/documents",
                    files={"file": upload_file[1]},
                    data=form_data,
                )

    elif document_action == "Check status":
        with st.form("document_status"):
            document_id = st.text_input("Document ID", placeholder="Paste the ID returned by upload")
            status_clicked = st.form_submit_button("Fetch document status")
        if status_clicked:
            if document_id.strip():
                send_request("GET", f"/v1/documents/{quote(document_id.strip(), safe='')}")
            else:
                st.error("Enter a document ID.")

    else:
        st.warning("Deleting removes the document from the vector index and its stored upload.")
        with st.form("delete_document"):
            document_id = st.text_input("Document ID to delete")
            delete_clicked = st.form_submit_button("Delete document")
        if delete_clicked:
            if document_id.strip():
                send_request("DELETE", f"/v1/documents/{quote(document_id.strip(), safe='')}")
            else:
                st.error("Enter a document ID.")

with search_tab:
    st.subheader("Semantic search")
    st.caption("Search only within the department and cohort you specify.")
    with st.form("search_documents"):
        query = st.text_area("Question", placeholder="What does the course material say about ...?")
        col1, col2 = st.columns(2)
        department = col1.selectbox(
            "Department",
            [
                "ml", "web-frontend", "mobile", "cyber-security",
                "embedded-system", "design", "web-backend", "gen-ai",
            ],
            key="search_department",
        )
        cohort_id = col2.text_input("Cohort ID", key="search_cohort")
        col3, col4 = st.columns(2)
        top_k = col3.number_input("Results", min_value=1, max_value=20, value=5)
        score_threshold = col4.number_input(
            "Minimum score", min_value=0.0, max_value=1.0, value=0.35, step=0.05
        )
        search_clicked = st.form_submit_button("Search documents")
    if search_clicked:
        if len(query.strip()) < 2:
            st.error("Enter a question with at least two characters.")
        elif not cohort_id.strip():
            st.error("Enter a cohort ID.")
        else:
            send_request(
                "POST",
                "/v1/search",
                json_body={
                    "query": query.strip(),
                    "department": department,
                    "cohort_id": cohort_id.strip(),
                    "top_k": int(top_k),
                    "score_threshold": score_threshold,
                },
            )

with digests_tab:
    st.subheader("Opportunity digest endpoints")
    st.caption("Preview a segment, queue a weekly run, inspect saved digests, or publish an approved digest.")
    digest_action = st.radio(
        "Digest action",
        ["Preview segment", "Queue run", "Run status", "List digests", "Get digest", "Student digest", "Publish"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if digest_action == "Preview segment":
        with st.form("digest_preview"):
            col1, col2 = st.columns(2)
            department = col1.text_input("Department", placeholder="e.g. ml")
            location = col2.text_input("Location (optional)", placeholder="e.g. Bamenda")
            col3, col4 = st.columns(2)
            skills = col3.text_input("Skills (comma-separated)")
            interests = col4.text_input("Interests (comma-separated)")
            level = st.text_input("Level (optional)", placeholder="e.g. intermediate")
            preview_clicked = st.form_submit_button("Generate preview")
        if preview_clicked:
            if not department.strip():
                st.error("Enter a department.")
            else:
                preview_body = {
                    "department": department.strip(),
                    "location": location.strip() or None,
                    "skills": csv_values(skills),
                    "interests": csv_values(interests),
                    "level": level.strip() or None,
                }
                send_request("POST", "/v1/digests/preview", json_body=preview_body)

    elif digest_action == "Queue run":
        st.info("A run is queued asynchronously. Make sure the digest worker is running.")
        with st.form("digest_run"):
            dry_run = st.checkbox("Dry run (do not deliver)", value=True)
            force = st.checkbox("Force a new run")
            profiles_text = st.text_area(
                "Profiles override (optional JSON array)",
                placeholder='[{"id":"student-1","department":"ml","skills":["python"]}]',
                help="Leave blank to pull profiles from the configured Zigex API.",
            )
            run_clicked = st.form_submit_button("Queue weekly digest")
        if run_clicked:
            run_body = {"dry_run": dry_run, "force": force}
            if profiles_text.strip():
                try:
                    profiles = json.loads(profiles_text)
                except json.JSONDecodeError as exc:
                    st.error(f"Profiles JSON is invalid: {exc}")
                else:
                    if not isinstance(profiles, list):
                        st.error("Profiles override must be a JSON array.")
                    else:
                        run_body["profiles"] = profiles
                        send_request("POST", "/v1/digests/run", json_body=run_body)
            else:
                send_request("POST", "/v1/digests/run", json_body=run_body)

    elif digest_action == "Run status":
        week = st.text_input("Week (optional)", placeholder="Defaults to the current week, e.g. 2026-W42")
        if st.button("Fetch run status"):
            send_request("GET", "/v1/digests/run-status", params={"week": week} if week.strip() else None)

    elif digest_action == "List digests":
        week = st.text_input("Week (optional)", placeholder="Defaults to the current week, e.g. 2026-W42", key="list_week")
        if st.button("List digests"):
            send_request("GET", "/v1/digests", params={"week": week} if week.strip() else None)

    elif digest_action == "Get digest":
        col1, col2 = st.columns(2)
        week = col1.text_input("Week", placeholder="e.g. 2026-W42", key="digest_week")
        segment_id = col2.text_input("Segment ID", placeholder="e.g. ml__bamenda")
        if st.button("Fetch digest"):
            if week.strip() and segment_id.strip():
                path = f"/v1/digests/{quote(week.strip(), safe='')}/{quote(segment_id.strip(), safe='')}"
                send_request("GET", path)
            else:
                st.error("Enter both a week and segment ID.")

    elif digest_action == "Student digest":
        student_id = st.text_input("Student ID")
        if st.button("Fetch student digest"):
            if student_id.strip():
                send_request("GET", f"/v1/digests/student/{quote(student_id.strip(), safe='')}")
            else:
                st.error("Enter a student ID.")

    else:
        st.warning("Publishing approves the digest and attempts delivery to the configured webhook.")
        col1, col2 = st.columns(2)
        week = col1.text_input("Week", placeholder="e.g. 2026-W42", key="publish_week")
        segment_id = col2.text_input("Segment ID", placeholder="e.g. ml__bamenda", key="publish_segment")
        if st.button("Publish digest"):
            if week.strip() and segment_id.strip():
                path = (
                    f"/v1/digests/{quote(week.strip(), safe='')}/"
                    f"{quote(segment_id.strip(), safe='')}/publish"
                )
                send_request("POST", path)
            else:
                st.error("Enter both a week and segment ID.")

st.divider()
st.caption("Zila API Studio · Requests are sent directly from this Streamlit session to your API.")
