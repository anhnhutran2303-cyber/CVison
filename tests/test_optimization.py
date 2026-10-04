from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from backend.config import Settings
from backend.exceptions import LLMUnavailableError
from backend.models import CVDocument
from backend.normalization import keyword_count
from backend.review_models import AnalyzerReview, KeywordComparison
from backend.services.analyzer_review_service import AnalyzerReviewService
from backend.services.optimization_service import NUMERIC_DETAIL
from backend.services.report_service import generate_report
from frontend.optimization_ui import keyword_csv
from tests.helpers import CV, JD, MockProvider, document, semantic_payload

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def service(jd=None, error=None):
    provider = MockProvider(semantic_payload(jd), error=error)
    return AnalyzerReviewService(settings=Settings(), provider=provider), provider


def click(app, label):
    next(button for button in app.button if button.label == label).click().run(timeout=20)
    assert not app.exception


def analyzed_app(jd=JD):
    app = AppTest.from_file(APP)
    app.session_state["page"] = "Analyzer"
    app.session_state["cv_text"] = CV
    app.session_state["jd_text"] = jd
    app.run(timeout=20)
    analyzer, provider = service(jd or None)
    with patch("frontend.review_ui.AnalyzerReviewService", return_value=analyzer):
        next(button for button in app.button if "Analyze CV" in button.label).click().run(timeout=20)
    assert not app.exception
    return app, provider


def test_alias_occurrences_are_not_double_counted():
    assert keyword_count("Python", "Python 3, Python3 and Python") == 3
    assert keyword_count("Power BI", "Microsoft Power BI and PowerBI") == 2
    assert keyword_count("communication", "Kỹ năng giao tiếp, communication skills") == 2


def test_unicode_counts_reject_r_in_vietnamese_words_and_rd():
    assert keyword_count("R", "rèn kỹ năng, R&D, quản lý dự án") == 0
    assert keyword_count("R", "R, Python, SQL") == 1


def test_jd_counts_exclude_benefits_and_resume_at_requirements():
    jd = """Data Analyst
Requirements:
Python required. SQL required.
Benefits:
Python training and Canva workshops.
Quyền lợi:
12 ngày nghỉ phép và giao tiếp với chuyên gia.
Yêu cầu:
SQL required. Communication preferred.
"""
    analyzer, provider = service(jd)
    review = analyzer.analyze_cv(document(), jd)
    rows = {row.keyword: row for row in review.optimization.keywords}
    assert rows["Python"].jd_count == 1
    assert rows["SQL"].jd_count == 2
    assert "Canva" not in rows
    assert rows["communication"].jd_count == 1
    assert not rows["communication"].required
    assert len(provider.calls) == 1


def test_keyword_mention_keeps_duration_requirement_partial():
    analyzer, _ = service(JD)
    review = analyzer.analyze_cv(document(), JD)
    row = next(row for row in review.optimization.keywords if row.keyword == "Power BI")
    assert row.cv_count == 2
    assert row.jd_count == 2
    assert any(match.status == "partial" and "2 years" in match.requirement for match in row.requirements)


def test_vietnamese_soft_skills_and_creative_tools_are_grouped():
    jd = """Content Creator
Yêu cầu:
Adobe Premiere Pro, Canva, làm việc nhóm và giao tiếp bắt buộc.
"""
    analyzer, _ = service(jd, LLMUnavailableError("offline"))
    review = analyzer.analyze_cv(document(CV + "\nCanva, kỹ năng giao tiếp"), jd)
    rows = {row.keyword: row for row in review.optimization.keywords}
    assert rows["Canva"].group == "hard_skill"
    assert rows["communication"].group == "soft_skill"
    assert rows["communication"].cv_count == 1
    assert rows["teamwork"].cv_count == 0
    assert rows["Content Creator"].group == "job_title"


def test_dates_and_years_are_not_numeric_outcomes():
    assert not NUMERIC_DETAIL.search("Worked from 2023–2024 with 2 years experience.")
    assert NUMERIC_DETAIL.search("Processed 300 records, giảm thời gian xử lý 20%.")
    assert NUMERIC_DETAIL.search("Tạo báo cáo từ 1000 bản ghi.")


def test_layout_is_unassessed_and_low_extraction_warns():
    analyzer, _ = service()
    review = analyzer.analyze_cv(CVDocument(raw_text=CV, source_type="pdf", extraction_quality="low"))
    checks = {check.id: check for check in review.optimization.checks}
    assert checks["extraction"].status == "warning"
    assert checks["layout"].status == "not_assessed"
    assert checks["email"].status == "passed"
    assert "ATS" in checks["layout"].detail


def test_numeric_detail_only_checks_work_and_project_bullets():
    analyzer, _ = service()
    cv = CV.replace("Built SQL data cleaning pipeline.", "Built SQL pipeline processing 200 records.")
    review = analyzer.analyze_cv(document(cv))
    check = next(check for check in review.optimization.checks if check.id == "numeric_detail")
    assert check.status == "passed"
    assert "1 of 3" in check.detail


def test_older_saved_review_without_optimization_still_reads_and_renders():
    analyzer, _ = service(JD)
    data = analyzer.analyze_cv(document(), JD).model_dump()
    del data["optimization"]
    review = AnalyzerReview.model_validate(data)
    assert review.optimization is None
    app = AppTest.from_file(APP)
    app.session_state["page"] = "Results"
    app.session_state["review_result"] = review
    app.run(timeout=20)
    assert not app.exception
    assert any("Re-analyze this saved review" in info.value for info in app.info)


def test_markdown_export_includes_keywords_and_checks():
    analyzer, _ = service(JD)
    report = generate_report(analyzer.analyze_cv(document(), JD))
    assert "## Keyword comparison" in report
    assert "| Python | hard skill | Required | 2 | 1 |" in report
    assert "## Searchability checklist" in report
    assert "not proficiency" in report


def test_keyword_csv_protects_formula_like_titles():
    row = KeywordComparison(keyword="=SUM(1,2) Analyst", group="job_title", cv_count=0, jd_count=1)
    assert "'=SUM(1,2) Analyst" in keyword_csv([row])


def test_filter_keywords_without_triggering_ai():
    app, provider = analyzed_app()
    next(select for select in app.selectbox if select.label == "Keyword presence").select("Not found").run()
    next(field for field in app.text_input if field.label == "Search keywords").set_value("communication").run()
    assert not app.exception
    assert app.dataframe[0].value["Keyword"].tolist() == ["communication"]
    assert len(provider.calls) == 1
    next(field for field in app.text_input if field.label == "Search keywords").set_value("nosuchkeyword").run()
    assert any("No keywords match" in info.value for info in app.info)


def test_inline_edits_rescan_once_and_sync_input_editor():
    app, _ = analyzed_app()
    edited = CV + "\nCommunication through teamwork on university projects."
    next(field for field in app.text_area if field.label == "CV draft").set_value(edited)
    analyzer, provider = service(JD)
    with patch("frontend.review_ui.AnalyzerReviewService", return_value=analyzer):
        click(app, "Apply edits & re-scan")
    assert len(provider.calls) == 1
    assert app.session_state["cv_document"].raw_text == edited
    assert app.session_state["review_comparison"]["comparable"]
    assert any(metric.label == "Job match" for metric in app.metric)
    click(app, "Edit inputs")
    assert app.text_area[0].value == edited
    assert app.text_area[1].value == JD


def test_changed_jd_does_not_claim_score_improvement():
    app, _ = analyzed_app()
    jd = JD + "\nCanva required."
    next(field for field in app.text_area if field.label == "JD for this scan").set_value(jd)
    analyzer, _ = service(jd)
    with patch("frontend.review_ui.AnalyzerReviewService", return_value=analyzer):
        click(app, "Apply edits & re-scan")
    assert not app.session_state["review_comparison"]["comparable"]
    assert any("cannot reliably measure" in item.value for item in app.info)
    assert not any(metric.label == "Job match" for metric in app.metric)


def test_changed_provider_availability_suppresses_delta():
    app, _ = analyzed_app()
    analyzer, _ = service(JD, LLMUnavailableError("offline"))
    with patch("frontend.review_ui.AnalyzerReviewService", return_value=analyzer):
        click(app, "Apply edits & re-scan")
    assert not app.session_state["review_comparison"]["comparable"]


def test_failed_inline_rescan_preserves_review_and_draft():
    app, _ = analyzed_app()
    original = app.session_state["review_result"].model_dump_json()
    next(field for field in app.text_area if field.label == "CV draft").set_value("Too short")
    analyzer, provider = service(JD)
    with patch("frontend.review_ui.AnalyzerReviewService", return_value=analyzer):
        click(app, "Apply edits & re-scan")
    assert provider.calls == []
    assert app.session_state["review_result"].model_dump_json() == original
    assert app.session_state["cv_text"] == CV
    assert next(field for field in app.text_area if field.label == "CV draft").value == "Too short"
    assert any("too short" in item.value for item in app.error)


def test_new_cv_clears_comparison_and_inline_draft():
    app, _ = analyzed_app()
    analyzer, _ = service(JD)
    with patch("frontend.review_ui.AnalyzerReviewService", return_value=analyzer):
        click(app, "Apply edits & re-scan")
    draft_key = next(field.key for field in app.text_area if field.label == "CV draft")
    click(app, "Analyze another CV")
    assert "review_comparison" not in app.session_state
    assert draft_key not in app.session_state


def test_cv_only_has_checklist_and_inline_editor_without_keyword_tab():
    app, _ = analyzed_app("")
    assert [tab.label for tab in app.tabs] == ["CV Review", "Searchability", "Optimize & Re-scan"]
    assert any(field.label == "CV draft" for field in app.text_area)
