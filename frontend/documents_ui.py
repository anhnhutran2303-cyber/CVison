"""CV and cover-letter creation, kept in the current browser session."""
from hashlib import sha256
import json

from pydantic import ValidationError
import streamlit as st

from backend.exceptions import InvalidCVError
from backend.models import CVDocument
from backend.services.application_documents import (
    LetterRequest, ResumeDraft, cover_letter, evidence_options, letter_docx, resume_docx, resume_text,
)
from frontend.components import page_header, surface
from frontend.review_ui import _clear_review
from frontend.workspace_ui import clear_saved_context

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
LANGUAGES = {"English": "en", "Tiếng Việt": "vi"}
TEMPLATES = {"Modern": "modern", "Classic": "classic"}
FIELDS = {
    "full_name": "Full name", "headline": "Professional headline", "email": "Email",
    "phone": "Phone", "location": "Location", "links": "Portfolio / LinkedIn links",
    "summary": "Professional summary", "experience": "Work experience", "projects": "Projects",
    "education": "Education", "skills": "Skills", "certifications": "Certifications",
}


def _fingerprint(data):
    return sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _use_resume(draft, go):
    clear_saved_context()
    _clear_review()
    text = resume_text(draft)
    st.session_state.cv_text = text
    st.session_state.cv_document = CVDocument(raw_text=text, source_type="text")
    revision = st.session_state.get("cv_editor_revision", 0) + 1
    st.session_state.cv_editor_revision = revision
    st.session_state[f"input_cv_{revision}"] = text
    st.session_state.upload_revision = st.session_state.get("upload_revision", 0) + 1
    st.session_state.pop("_cv_upload_sig", None)
    st.session_state.target_position = draft.headline
    st.session_state.input_target = draft.headline
    go("Analyzer")


def render_builder(go):
    page_header("Build your CV", "Create a CV, download Word or text, then review it in Analyzer.", "CV Builder")
    st.caption("Your submitted draft stays in this session. Download it before closing the app.")
    saved = st.session_state.get("builder_submitted", {})
    with st.form("resume_builder"):
        a, b = st.columns(2)
        language = a.selectbox("Document language", list(LANGUAGES), key="builder_language",
                               index=1 if saved.get("language") == "vi" else 0)
        template = b.selectbox("Word template", list(TEMPLATES), key="builder_template",
                               index=1 if saved.get("template") == "classic" else 0)
        st.caption("Both templates use one column. Modern uses a left-aligned sans-serif heading; Classic uses a centered serif heading.")
        values = {}
        for number, field in enumerate(list(FIELDS)[:6]):
            column = a if number % 2 == 0 else b
            values[field] = column.text_input(FIELDS[field], value=saved.get(field, ""),
                                              key=f"builder_{field}", max_chars=1000 if field == "links" else 200)
        st.caption("Add your own facts. In each section, start a line with '- ' for a bullet. Empty sections are omitted.")
        for field in list(FIELDS)[6:]:
            values[field] = st.text_area(FIELDS[field], value=saved.get(field, ""), key=f"builder_{field}",
                                          height=100, max_chars=15000)
        submitted = st.form_submit_button("Build CV", type="primary")
    if submitted:
        try:
            draft = ResumeDraft(**values, language=LANGUAGES[language], template=TEMPLATES[template])
            output = resume_docx(draft)
        except ValidationError:
            st.error("Enter your name, at least one CV section, and a valid email if supplied. Keep contact fields short and remove unsupported control characters.")
        else:
            st.session_state.builder_submitted = draft.model_dump()
            st.session_state.builder_docx = output
            st.success("CV created. Submit Build CV again after editing to refresh the preview and downloads.")
    if st.session_state.get("builder_submitted"):
        draft = ResumeDraft.model_validate(st.session_state.builder_submitted)
        text = resume_text(draft)
        with surface("builder_preview"):
            st.subheader("Submitted CV preview")
            st.caption("Text preview. Open the Word download to see your chosen template.")
            st.text(text)
            a, b, c = st.columns(3)
            a.download_button("Download CV · Word", st.session_state.builder_docx, "CVision-CV.docx", DOCX_MIME)
            b.download_button("Download CV · TXT", text, "CVision-CV.txt", "text/plain")
            if c.button("Use this CV in Analyzer", type="primary"):
                _use_resume(draft, go)


def _load_letter_sources(cv, jd, name="", role=""):
    inputs = st.session_state.get("letter_inputs", {}).copy()
    inputs.update(cv_text=cv, jd_text=jd)
    if name:
        inputs["full_name"] = name
    if role:
        inputs["role"] = role
    st.session_state.letter_inputs = inputs
    for key, value in inputs.items():
        st.session_state[f"letter_{key}"] = value


def render_cover_letter(go):
    page_header("Write a cover letter", "Choose CV evidence, create a draft, then edit and download it.", "Cover Letter")
    st.caption("Template-based drafting works without an API key. JD keywords help order CV excerpts; selected excerpts keep their original language. Drafts stay in this session.")
    a, b = st.columns(2)
    if a.button("Use current Analyzer inputs", disabled=not st.session_state.get("cv_text")):
        _load_letter_sources(st.session_state.cv_text, st.session_state.jd_text,
                             role=st.session_state.target_position)
    built = st.session_state.get("builder_submitted")
    if b.button("Use CV Builder draft", disabled=not built):
        draft = ResumeDraft.model_validate(built)
        _load_letter_sources(resume_text(draft), st.session_state.get("jd_text", ""), draft.full_name, draft.headline)
    saved = st.session_state.get("letter_inputs", {})
    defaults = {"cv_text": st.session_state.get("cv_text", ""), "jd_text": st.session_state.get("jd_text", ""),
                "role": st.session_state.get("target_position", ""), "language": "English"}
    for key in ("cv_text", "jd_text", "full_name", "role", "company", "recipient", "motivation", "language"):
        st.session_state.setdefault(f"letter_{key}", saved.get(key, defaults.get(key, "")))
    a, b = st.columns(2)
    cv = a.text_area("CV source", key="letter_cv_text", height=220, max_chars=100000)
    jd = b.text_area("Target job description", key="letter_jd_text", height=220, max_chars=100000)
    a, b = st.columns(2)
    a.text_input("Applicant name", key="letter_full_name", max_chars=120)
    b.text_input("Target role", key="letter_role", max_chars=200)
    a.text_input("Company", key="letter_company", max_chars=200)
    b.text_input("Recipient (optional)", key="letter_recipient", max_chars=200)
    st.selectbox("Letter language", list(LANGUAGES), key="letter_language")
    st.text_area("Why this role interests you (optional)", key="letter_motivation", max_chars=2000)
    inputs = {key: st.session_state[f"letter_{key}"] for key in defaults.keys() | {
        "full_name", "company", "recipient", "motivation"}}
    st.session_state.letter_inputs = inputs
    options = evidence_options(cv, jd)
    source_hash = _fingerprint({"cv": cv, "jd": jd})
    if st.session_state.get("letter_source_hash") != source_hash:
        st.session_state.letter_evidence = options[:2]
        st.session_state.letter_source_hash = source_hash
    st.session_state.setdefault("letter_evidence", st.session_state.get("letter_selected", options[:2]))
    selected = st.multiselect("CV excerpts to include (choose 1–3)", options, key="letter_evidence", max_selections=3)
    st.session_state.letter_selected = selected
    if not options:
        st.info("Add CV sections such as Experience, Projects, Education or Skills with details to select.")
    payload = {**inputs, "language": LANGUAGES[inputs["language"]], "evidence": selected}
    current_hash = _fingerprint(payload)
    if st.button("Create letter draft", type="primary"):
        try:
            text = cover_letter(LetterRequest.model_validate(payload))
        except ValidationError:
            st.error("Enter your name, role, company, CV and JD; select 1–3 current CV excerpts. Remove unsupported control characters.")
        else:
            st.session_state.letter_draft_text = text
            st.session_state.letter_editor = text
            st.session_state.letter_generated_hash = current_hash
    if "letter_draft_text" in st.session_state:
        stale = current_hash != st.session_state.get("letter_generated_hash")
        if stale:
            st.warning("Inputs changed. Create a new letter draft before downloading. Your previous text is kept below.")
        st.session_state.setdefault("letter_editor", st.session_state.letter_draft_text)
        edited = st.text_area("Edit your letter", key="letter_editor", height=350, max_chars=20000)
        st.session_state.letter_draft_text = edited
        st.caption("Review the company, role and every statement before using this letter. Creating another draft replaces your edits.")
        if not stale:
            try:
                output = letter_docx(edited)
            except InvalidCVError as error:
                st.error(str(error))
            else:
                a, b = st.columns(2)
                a.download_button("Download letter · Word", output, "CVision-cover-letter.docx", DOCX_MIME)
                b.download_button("Download letter · TXT", edited, "CVision-cover-letter.txt", "text/plain")
