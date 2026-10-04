"""Keyword inspection, document checks and an explicit edit/re-scan workflow."""
import csv
from io import StringIO

import streamlit as st

from frontend.components import badge, evidence_quote

GROUP_LABELS = {"hard_skill": "Hard skills / tools", "soft_skill": "Soft skills", "job_title": "Job title"}


def keyword_csv(rows):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Keyword", "Group", "Priority", "CV mentions", "JD mentions", "Presence"])
    for row in rows:
        # Treat exported user-provided titles as text in spreadsheet software.
        keyword = "'" + row.keyword if row.keyword.lstrip().startswith(("=", "+", "-", "@")) else row.keyword
        writer.writerow([keyword, GROUP_LABELS[row.group], "Required" if row.required else "Preferred",
                         row.cv_count, row.jd_count, "Found" if row.cv_count else "Not found"])
    return "\ufeff" + output.getvalue()


def render_keywords(review):
    st.subheader("Keyword Match")
    st.caption("Compare the vocabulary in your CV with the requirements in this JD. Counts include known aliases and exclude benefits / company sections.")
    if not review.optimization:
        st.info("Re-analyze this saved review to generate the keyword comparison.")
        return
    rows = review.optimization.keywords
    if not rows:
        st.info("No supported skill keywords or job title were identified. See Job Match for the full requirements, including free-text requirements.")
        return
    a, b, c = st.columns(3)
    a.metric("JD keywords", len(rows))
    b.metric("Found in CV", sum(row.cv_count > 0 for row in rows))
    c.metric("Not found", sum(row.cv_count == 0 for row in rows))
    a, b, c = st.columns([1, 1, 2])
    group = a.selectbox("Keyword group", ["All groups", *GROUP_LABELS.values()], key="keyword_group")
    presence = b.selectbox("Keyword presence", ["All keywords", "Not found", "Found"], key="keyword_presence")
    query = c.text_input("Search keywords", key="keyword_query", placeholder="e.g. Python, Canva, communication")
    filtered = [row for row in rows
                if (group == "All groups" or GROUP_LABELS[row.group] == group)
                and (presence == "All keywords" or bool(row.cv_count) == (presence == "Found"))
                and query.strip().casefold() in row.keyword.casefold()]
    if filtered:
        st.dataframe([{"Keyword": row.keyword, "Group": GROUP_LABELS[row.group],
                       "Priority": "Required" if row.required else "Preferred",
                       "JD mentions": row.jd_count, "CV mentions": row.cv_count,
                       "Presence": "Found" if row.cv_count else "Not found"} for row in filtered],
                     hide_index=True, width="stretch")
        st.download_button("Download keyword CSV", data=keyword_csv(filtered), file_name="CVision_keywords.csv", mime="text/csv")
        with st.expander("Keyword context and requirement evidence"):
            for row in filtered:
                st.markdown(f"**{row.keyword}** · {'Required' if row.required else 'Preferred'}")
                if row.evidence:
                    for quote in row.evidence:
                        evidence_quote(quote)
                else:
                    st.caption("No text mention was found in the CV.")
                for match in row.requirements:
                    st.write(f"Requirement: {match.requirement} · {match.status.title()}")
                    if match.explanation:
                        st.caption(match.explanation)
    else:
        st.info("No keywords match these filters. Clear the search or select All keywords.")
    st.caption("A mention does not prove proficiency or satisfy an experience requirement. The full Job Match evidence remains authoritative for this review. Only add keywords that reflect your background.")


def render_searchability(review):
    st.subheader("Searchability checklist")
    st.caption("Checks on the supplied text help you spot contact, heading and readability issues before applying.")
    if not review.optimization:
        st.info("Re-analyze this saved review to generate the checklist.")
        return
    labels = {"passed": ("Detected / checked", "success"), "warning": ("Review this", "warning"),
              "not_assessed": ("Information / not assessed", "neutral")}
    for check in review.optimization.checks:
        with st.container(border=True):
            st.markdown(f"**{check.label}**")
            label, tone = labels[check.status]
            badge(label, tone)
            st.write(check.detail)
            if check.action:
                st.caption(check.action)


def render_comparison(review):
    comparison = st.session_state.get("review_comparison")
    if not comparison:
        return
    st.subheader("Before / after this scan")
    if not comparison["comparable"]:
        st.info("The JD, role context or analysis settings changed. These scores cannot reliably measure the effect of the CV edits.")
        return
    before = comparison["before"]
    columns = st.columns(3 if review.analysis.mode == "job_match" else 2)
    columns[0].metric("CV quality", f"{review.cv_quality.overall_score}/100",
                      delta=review.cv_quality.overall_score - before.cv_quality.overall_score)
    if review.analysis.mode == "job_match":
        columns[1].metric("Job match", f"{review.analysis.overall_score}/100",
                          delta=review.analysis.overall_score - before.analysis.overall_score)
    previous_missing = sum(row.cv_count == 0 for row in before.optimization.keywords) if before.optimization else None
    if review.analysis.mode == "job_match" and previous_missing is not None and review.optimization:
        current_missing = sum(row.cv_count == 0 for row in review.optimization.keywords)
        columns[2].metric("Keywords not found", current_missing, delta=current_missing - previous_missing, delta_color="inverse")
    else:
        columns[-1].metric("Review issues", len(review.improvement_areas),
                           delta=len(review.improvement_areas) - len(before.improvement_areas), delta_color="inverse")
    st.caption(f"Previous CV quality: {before.cv_quality.overall_score}/100. " +
               (f"Previous job match: {before.analysis.overall_score}/100. " if review.analysis.mode == "job_match" else "") +
               "Same JD and review settings. Score changes are review signals, not hiring probabilities.")
    if not review.analysis.ai_available:
        st.caption("Both scans used basic fallback; score changes are provisional text-check estimates.")


def render_optimizer(review, apply_edits):
    st.subheader("Optimize & Re-scan")
    st.write("Edit your CV with the evidence and missing keywords above, then run a new review. Keep every skill, title and outcome truthful.")
    revision = st.session_state.get("optimizer_revision", 0)
    cv_key, jd_key = f"optimizer_cv_{revision}", f"optimizer_jd_{revision}"
    if cv_key not in st.session_state:
        document = st.session_state.get("cv_document")
        st.session_state[cv_key] = document.raw_text if document else st.session_state.get("cv_text", "")
    if jd_key not in st.session_state:
        st.session_state[jd_key] = st.session_state.get("jd_text", "")
    with st.form("optimizer_form"):
        a, b = st.columns(2)
        draft = a.text_area("CV draft", key=cv_key, height=360)
        jd = b.text_area("JD for this scan", key=jd_key, height=360,
                         help="Keep the JD unchanged to compare the effect of CV edits. Leave it blank for CV Review.")
        st.caption("Each submission runs one new analysis. Editing alone does not trigger an AI request.")
        submit = st.form_submit_button("Apply edits & re-scan", type="primary")
    st.download_button("Download CV draft (.txt)", data=draft, file_name="CVision_CV_draft.txt", mime="text/plain")
    st.caption("Draft download uses the last submitted text. Submit edits to update the review and this download.")
    if submit and apply_edits(draft, jd):
        st.rerun()
