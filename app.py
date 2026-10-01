import streamlit as st
from processor import process_data
from matcher import calculate_match
from cv_checker import check_cv
from constants import INDUSTRIES, MATCH_SCORE_LABELS
from file_reader import extract_text_from_upload

st.set_page_config(page_title="CVision", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html,body,[class*="st-"]{font-family:Inter,system-ui,sans-serif}
.stApp{background:#f7f8fc;color:#0f172a}
.block-container{max-width:1180px;padding-top:2.1rem;padding-bottom:5rem}
[data-testid="stSidebar"]{background:#0b1220;border-right:1px solid #1e293b}
[data-testid="stSidebar"] *{color:#dbe3ef}
[data-testid="stSidebar"] .stButton button{background:transparent;border:0;text-align:left;justify-content:flex-start}
h1,h2,h3{letter-spacing:-.035em}
.cv-kicker{font-size:.75rem;letter-spacing:.12em;text-transform:uppercase;color:#6366f1;font-weight:800}
.cv-hero{background:linear-gradient(135deg,#111827 0%,#1e293b 52%,#312e81 100%);padding:42px;border-radius:24px;color:white;margin:8px 0 24px;box-shadow:0 18px 45px rgba(15,23,42,.15)}
.cv-hero h1{font-size:2.55rem;color:white;margin:.25rem 0 .65rem}
.cv-hero p{max-width:720px;color:#dbeafe;font-size:1.04rem;line-height:1.7}
.cv-card{background:white;border:1px solid #e5e7eb;border-radius:18px;padding:20px;box-shadow:0 4px 16px rgba(15,23,42,.035);height:100%}
.cv-metric{font-size:2rem;font-weight:800;letter-spacing:-.04em;margin-top:5px}
.cv-label{font-size:.72rem;color:#64748b;font-weight:800;letter-spacing:.08em;text-transform:uppercase}
.cv-sub{color:#64748b;font-size:.9rem}
.cv-section{font-size:1.22rem;font-weight:800;margin:1.9rem 0 .8rem}
.cv-badge-ok,.cv-badge-bad,.cv-badge-neutral{display:inline-block;padding:6px 10px;border-radius:999px;font-size:.78rem;font-weight:700;margin:3px}
.cv-badge-ok{background:#ecfdf5;color:#047857}.cv-badge-bad{background:#fff1f2;color:#be123c}.cv-badge-neutral{background:#eef2ff;color:#4338ca}
.cv-priority{background:white;border:1px solid #e5e7eb;border-left:4px solid #6366f1;border-radius:14px;padding:16px 18px;margin:10px 0}
.cv-note{background:#eef2ff;border:1px solid #c7d2fe;color:#3730a3;padding:12px 14px;border-radius:12px;font-size:.85rem}
div[data-testid="stFileUploader"]{background:white;border:1px dashed #cbd5e1;border-radius:16px;padding:7px}
div[data-testid="stTextArea"] textarea,div[data-testid="stTextInput"] input{border-radius:12px}
.stButton>button,.stFormSubmitButton>button{border-radius:11px;min-height:44px;font-weight:750;transition:.15s}
.stButton>button:hover,.stFormSubmitButton>button:hover{transform:translateY(-1px);box-shadow:0 8px 20px rgba(79,70,229,.12)}
hr{border-color:#e5e7eb}
</style>
""", unsafe_allow_html=True)

defaults = {
    "page":"Dashboard","cv_text":"","jd_text":"","industry":"Finance","target_position":"",
    "cv_data":None,"jd_data":None,"match_result":None,"check_result":None,
}
for k,v in defaults.items():
    if k not in st.session_state: st.session_state[k]=v

def go(page):
    st.session_state.page=page
    st.rerun()

def score_label(score):
    for lo,hi,label,icon in MATCH_SCORE_LABELS:
        if lo <= score <= hi: return f"{icon} {label}"
    return "Match"

def badge(text, ok=True):
    cls="cv-badge-ok" if ok else "cv-badge-bad"
    return f'<span class="{cls}">{"✓" if ok else "✕"} {text}</span>'

with st.sidebar:
    st.markdown("## ◈ CVision")
    st.caption("CV & Job Match Analyzer")
    st.markdown("---")
    if st.button("⌂  Dashboard", use_container_width=True): go("Dashboard")
    if st.button("◎  Analyzer", use_container_width=True): go("Analyzer")
    st.markdown("##### CAREER WORKSPACE")
    for label in ["▤  My CVs","▥  Jobs","◇  Insights","▣  Applications"]:
        st.button(label, use_container_width=True, disabled=True)
    st.markdown("---")
    st.caption("MVP • Explainable scoring • No fabricated experience")

if st.session_state.page=="Dashboard":
    st.markdown('<div class="cv-kicker">CV + JOB INTELLIGENCE</div>', unsafe_allow_html=True)
    st.markdown("""<div class="cv-hero"><h1>Build a CV that speaks the job’s language.</h1>
    <p>Compare your CV with a specific Job Description, see the evidence behind your match score,
    identify missing requirements, and focus on the improvements that matter first.</p></div>""", unsafe_allow_html=True)
    c1,c2,c3=st.columns(3)
    with c1: st.markdown('<div class="cv-card"><div class="cv-label">01 · MATCH</div><h3>Explainable Match Score</h3><p class="cv-sub">Required skills, preferred criteria, keywords and qualifications — shown separately.</p></div>',unsafe_allow_html=True)
    with c2: st.markdown('<div class="cv-card"><div class="cv-label">02 · EVIDENCE</div><h3>Keyword & Skill Gaps</h3><p class="cv-sub">See what is already represented and what the JD asks for but your CV does not clearly show.</p></div>',unsafe_allow_html=True)
    with c3: st.markdown('<div class="cv-card"><div class="cv-label">03 · IMPROVE</div><h3>Content Quality Check</h3><p class="cv-sub">Review structure, task-based bullets and measurable impact without inventing achievements.</p></div>',unsafe_allow_html=True)
    st.write("")
    if st.button("Analyze my CV  →", type="primary", use_container_width=False): go("Analyzer")
    st.markdown("### How it works")
    a,b,c=st.columns(3)
    a.info("**1. Add your CV**\n\nUpload PDF/DOCX/TXT or paste the text.")
    b.info("**2. Add the JD**\n\nPaste the role you want to apply for.")
    c.info("**3. Review evidence**\n\nUnderstand the score and what to fix first.")

elif st.session_state.page=="Analyzer":
    st.markdown('<div class="cv-kicker">ANALYZER</div>', unsafe_allow_html=True)
    st.title("Compare your CV with a job")
    st.caption("Upload a CV or paste its text. CVision will always show the extracted text before analysis.")
    st.caption("Uploaded files are processed for the current analysis. Avoid uploading sensitive information you do not want to process.")
    with st.container(border=True):
        st.markdown("### 1 · Job details")
        a,b=st.columns(2)
        with a:
            industry=st.selectbox("Industry", INDUSTRIES, index=INDUSTRIES.index(st.session_state.industry) if st.session_state.industry in INDUSTRIES else 0)
        with b:
            position=st.text_input("Target position", value=st.session_state.target_position, placeholder="e.g. Finance Intern")

    left,right=st.columns(2,gap="large")
    with left:
        st.markdown("### 2 · Your CV")
        upload=st.file_uploader("Upload CV", type=["pdf","docx","txt"], help="PDF, DOCX or TXT")
        if upload:
            txt,err=extract_text_from_upload(upload)
            if err: st.error(err)
            elif txt and st.session_state.get("_upload_sig") != (upload.name,len(upload.getvalue())):
                st.session_state.cv_text=txt
                st.session_state["_upload_sig"]=(upload.name,len(upload.getvalue()))
                st.success(f"✓ {upload.name} đã được đọc. Kiểm tra nội dung bên dưới.")
        cv_text=st.text_area("CV text", value=st.session_state.cv_text, height=360, placeholder="Paste your CV here...")
        st.caption(f"{len(cv_text.split())} words")
    with right:
        st.markdown("### 3 · Job Description")
        jd_upload=st.file_uploader("Upload JD (optional)", type=["pdf","docx","txt"], key="jd_upload", help="Or paste the Job Description below.")
        if jd_upload:
            jd_up_text,jd_err=extract_text_from_upload(jd_upload)
            if jd_err: st.error(jd_err)
            elif jd_up_text and st.session_state.get("_jd_upload_sig") != (jd_upload.name,len(jd_upload.getvalue())):
                st.session_state.jd_text=jd_up_text
                st.session_state["_jd_upload_sig"]=(jd_upload.name,len(jd_upload.getvalue()))
                st.success(f"✓ {jd_upload.name} đã được đọc. Kiểm tra nội dung bên dưới.")
        jd_text=st.text_area("Job Description", value=st.session_state.jd_text, height=380, placeholder="Paste the full Job Description here...")
        st.caption(f"{len(jd_text.split())} words")

    st.markdown('<div class="cv-note">Your CV is compared only with the JD you provide. Missing keywords are suggestions for review — never add skills or experience that are not true.</div>',unsafe_allow_html=True)
    st.write("")
    if st.button("Analyze CV  →", type="primary", use_container_width=True):
        errs=[]
        if not industry: errs.append("Chọn ngành.")
        if len(cv_text.split())<20: errs.append("CV quá ngắn hoặc chưa được nhập đầy đủ.")
        if len(jd_text.split())<15: errs.append("Job Description quá ngắn hoặc chưa được nhập đầy đủ.")
        if errs:
            for e in errs: st.error(e)
        else:
            with st.spinner("Reading CV, matching requirements and checking content..."):
                cv_data,jd_data=process_data(cv_text,jd_text,industry)
                match_result=calculate_match(cv_data,jd_data)
                check_result=check_cv(cv_text,cv_data,jd_data)
                st.session_state.update({
                    "industry":industry,"target_position":position,"cv_text":cv_text,"jd_text":jd_text,
                    "cv_data":cv_data,"jd_data":jd_data,"match_result":match_result,"check_result":check_result,
                    "page":"Results"
                })
            st.rerun()

elif st.session_state.page=="Results":
    m=st.session_state.match_result or {}
    c=st.session_state.check_result or {}
    jd=st.session_state.jd_data or {}
    score=int(m.get("match_score",0))
    st.markdown('<div class="cv-kicker">ANALYSIS REPORT</div>',unsafe_allow_html=True)
    st.title(st.session_state.target_position or jd.get("job_title") or "CV Analysis")
    st.caption(f"{st.session_state.industry} · Evidence-based CV ↔ JD comparison")
    m1,m2,m3,m4=st.columns(4)
    metrics=[
        ("Match score",f"{score}/100",score_label(score)),
        ("Required",f'{int(m.get("required_coverage",0))}%',"Core criteria"),
        ("Keywords",f'{len(m.get("matched_keywords",[]))} / {len(m.get("matched_keywords",[]))+len(m.get("missing_keywords",[]))}',"JD terminology"),
        ("CV issues",str(len(c.get("ats_issues",[]))+len(c.get("content_issues",[]))),"Review needed"),
    ]
    for col,(lab,val,sub) in zip([m1,m2,m3,m4],metrics):
        with col: st.markdown(f'<div class="cv-card"><div class="cv-label">{lab}</div><div class="cv-metric">{val}</div><div class="cv-sub">{sub}</div></div>',unsafe_allow_html=True)

    st.markdown('<div class="cv-section">Why this score?</div>',unsafe_allow_html=True)
    br=m.get("score_breakdown",{})
    for key,label in [("required_skills","Required skills"),("keywords","Keywords"),("preferred_skills","Preferred skills"),("qualification","Qualification")]:
        if key in br:
            v=int(br.get(key,0)); st.write(f"**{label}**  ·  {v}%"); st.progress(v/100)

    st.markdown('<div class="cv-section">Required criteria</div>',unsafe_allow_html=True)
    a,b=st.columns(2)
    with a:
        st.markdown("**Covered**")
        st.markdown("".join(badge(x,True) for x in m.get("matched_required_skills",[])) or '<span class="cv-sub">None detected</span>',unsafe_allow_html=True)
    with b:
        st.markdown("**Missing / needs clearer evidence**")
        st.markdown("".join(badge(x,False) for x in m.get("missing_required_skills",[])) or '<span class="cv-sub">None</span>',unsafe_allow_html=True)

    st.markdown('<div class="cv-section">Keyword analysis</div>',unsafe_allow_html=True)
    a,b=st.columns(2)
    with a:
        st.markdown("**Matched keywords**")
        st.markdown("".join(badge(x,True) for x in m.get("matched_keywords",[])) or "—",unsafe_allow_html=True)
    with b:
        st.markdown("**Missing keywords**")
        st.markdown("".join(badge(x,False) for x in m.get("missing_keywords",[])) or "—",unsafe_allow_html=True)
    st.markdown('<div class="cv-note">Only add a missing skill or keyword when it accurately reflects your real background.</div>',unsafe_allow_html=True)

    st.markdown('<div class="cv-section">CV quality</div>',unsafe_allow_html=True)
    q1,q2,q3=st.columns(3)
    q1.metric("Bullets analyzed",c.get("total_bullets",0))
    q2.metric("Impact-oriented",len(c.get("impact_based_bullets",[])))
    q3.metric("Task-based",len(c.get("task_based_bullets",[])))
    for issue in c.get("ats_issues",[])[:5]:
        st.warning(issue if isinstance(issue,str) else issue.get("message",str(issue)))

    st.markdown('<div class="cv-section">Fix these first</div>',unsafe_allow_html=True)
    priorities=c.get("top_3_priorities",[])
    if priorities:
        for i,p in enumerate(priorities[:3],1):
            if isinstance(p,dict):
                title=p.get("title",f"Priority {i}"); desc=p.get("description") or p.get("message") or p.get("action","")
            else: title=f"Priority {i}"; desc=str(p)
            st.markdown(f'<div class="cv-priority"><b>{i} · {title}</b><div class="cv-sub" style="margin-top:6px">{desc}</div></div>',unsafe_allow_html=True)
    else:
        st.success("No high-priority content issues were detected by the current rule set.")

    st.markdown('<div class="cv-section">Scoring methodology</div>',unsafe_allow_html=True)
    with st.expander("How CVision calculates this score"):
        st.markdown("""
        CVision uses deterministic rules rather than an LLM-generated rating. The base weighting is:
        **Required skills 50% · Keywords 25% · Preferred skills 15% · Qualifications 10%**.
        If a JD does not contain one of these components, its weight is redistributed across the components that are present.
        The score measures text alignment with the supplied JD; it is **not** a hiring probability or an official ATS score.
        """)
    report_lines = [
        "CVISION ANALYSIS REPORT",
        f"Target: {st.session_state.target_position or jd.get('job_title') or 'Not specified'}",
        f"Industry: {st.session_state.industry}",
        f"Match score: {score}/100",
        f"Required coverage: {int(m.get('required_coverage',0))}%",
        f"Keyword coverage: {int(m.get('keyword_coverage',0))}%",
        "",
        "Matched required skills:",
        ", ".join(m.get("matched_required_skills",[])) or "None",
        "",
        "Missing required skills:",
        ", ".join(m.get("missing_required_skills",[])) or "None",
        "",
        "Note: Only add skills or experience that accurately reflect your real background.",
    ]
    st.download_button("↓ Download text report", data="\n".join(report_lines), file_name="CVision_analysis.txt", mime="text/plain")

    st.write("")
    a,b=st.columns([1,1])
    if a.button("← Edit CV & analyze again",use_container_width=True): go("Analyzer")
    if b.button("Back to dashboard",use_container_width=True): go("Dashboard")
