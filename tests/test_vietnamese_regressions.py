"""Regressions reproduced from the hosted Vietnamese CV/job review."""
import unicodedata

import pytest

from backend.config import Settings
from backend.models import CVDocument
from backend.normalization import extract_known_skills
from backend.parsers.cv_parser import CVParser
from backend.parsers.jd_parser import JDParser
from backend.services.analyzer_review_service import AnalyzerReviewService
from processor import _contains_term


@pytest.mark.parametrize("text", ["rèn luyện", "Reels", "khả năng", "cơ sở", "R&D"])
def test_vietnamese_words_and_rd_are_not_programming_r(text):
    assert "R" not in extract_known_skills(text)


@pytest.mark.parametrize("text", ["Skills: R, Python", "Dùng R để phân tích", "R/Python"])
def test_explicit_programming_r_is_still_detected(text):
    assert "R" in extract_known_skills(text)


def test_unicode_boundaries_handle_decomposed_accents_and_symbol_skills():
    assert not _contains_term(unicodedata.normalize("NFD", "rèn luyện"), "R")
    assert not _contains_term("user_id", "R")
    assert _contains_term("Tools: C++, C# and .NET", "C++")
    assert _contains_term("Tools: C++, C# and .NET", "C#")


def test_vietnamese_cv_sections_and_inline_content_are_preserved():
    profile = CVParser().parse(CVDocument(raw_text="""GIỚI THIỆU BẢN THÂN
Sinh viên có kinh nghiệm phân tích dữ liệu.
HỌC VẤN
Đại học ngành Tài chính
KỸ NĂNG: Python, SQL
KINH NGHIỆM LÀM VIỆC
• Đã phân tích dữ liệu bằng Python trong 3 năm.
DỰ ÁN
• Xây dựng báo cáo SQL cho dự án nghiên cứu.
CHỨNG CHỈ
Chứng chỉ phân tích dữ liệu
HOẠT ĐỘNG NGOẠI KHÓA
Tham gia câu lạc bộ học thuật
"""))
    assert {"summary", "education", "skills", "experience", "projects", "certifications", "activities"} <= set(profile.sections_detected)
    assert profile.summary.startswith("Sinh viên")
    assert profile.experience and profile.projects
    assert {"Python", "SQL"} <= set(profile.skills)


@pytest.mark.parametrize("benefits", ["Quyền lợi ứng viên", "Benefits", "What we offer"])
def test_benefit_section_is_not_scored_as_candidate_requirements(benefits):
    jd = JDParser().parse(f"""Yêu cầu ứng viên
- Python
{benefits}:
- Ít nhất 12 ngày nghỉ phép/năm
- Được đào tạo Python
- Bảo hiểm sức khỏe
Yêu cầu ưu tiên:
- SQL
""")
    assert [(item.requirement, item.preferred) for item in jd.requirements] == [("Python", False), ("SQL", True)]


def test_inline_benefits_and_company_information_are_excluded():
    jd = JDParser().parse("""About us: We build Python products.
Benefits: Training in SQL and paid leave.
How to apply:
Send a Python portfolio to the recruiting team.
Requirements: Python
""")
    assert [item.requirement for item in jd.requirements] == ["Python"]


def test_vietnamese_jd_classifies_degree_duration_and_preference():
    jd = JDParser().parse("""Yêu cầu ứng viên:
Tốt nghiệp Đại học ngành Tài chính
Có 5năm kinh nghiệm phân tích dữ liệu
Có hiểu biết về sản xuất nội dung là một điểm cộng
""")
    assert [item.category for item in jd.requirements] == ["education", "experience", "other"]
    assert jd.requirements[-1].preferred is True


def test_commas_keep_one_coherent_vietnamese_requirement():
    sentence = "Có kinh nghiệm sản xuất video từ concept, tiền kỳ, hậu kỳ đến final output"
    jd = JDParser().parse("Yêu cầu ứng viên\n" + sentence)
    assert [item.requirement for item in jd.requirements] == [sentence]


def test_end_to_end_fallback_does_not_add_r_or_leave_as_gaps():
    service = AnalyzerReviewService(settings=Settings())
    try:
        review = service.analyze_cv(CVDocument(raw_text="""GIỚI THIỆU BẢN THÂN
Ứng viên thử nghiệm đã rèn luyện kỹ năng làm việc nhóm và thích nghi trong các cuộc thi học thuật.
HỌC VẤN
Đại học ngành Tài chính
KỸ NĂNG: Python
KINH NGHIỆM LÀM VIỆC
• Đã sử dụng Python để phân tích dữ liệu trong 3 năm.
"""), """Yêu cầu ứng viên:
Python
Có 5 năm kinh nghiệm Python
Quyền lợi ứng viên:
Ít nhất 12 ngày nghỉ phép/năm
""")
    finally:
        service.close()
    assert not review.analysis.ai_available
    assert "R" not in review.analysis.detected_skills
    assert len(review.analysis.requirement_matches) == 2
    duration = next(item for item in review.analysis.requirement_matches if "5 năm" in item.requirement)
    assert duration.status == "partial"
    assert review.cv_quality.scores.experience > 0
    assert next(item for item in review.skill_evidence if item.skill == "Python").strength == "some_evidence"
    assert any("not configured" in message for message in review.display_warnings)


@pytest.mark.parametrize("years,expected", [(3, "partial"), (6, "matched")])
def test_vietnamese_duration_and_degree_match_use_actual_evidence(years, expected):
    from backend.analyzers.fallback_analyzer import match_requirement
    document = CVDocument(raw_text=f"HỌC VẤN\nĐại học ngành Tài chính\nKINH NGHIỆM\nCó {years} năm kinh nghiệm Python.")
    profile = CVParser().parse(document)
    jd = JDParser().parse("Tốt nghiệp Đại học ngành Tài chính\nCó 5 năm kinh nghiệm Python")
    assert match_requirement(jd.requirements[0], document, profile).status == "matched"
    assert match_requirement(jd.requirements[1], document, profile).status == expected


def test_vietnamese_comma_required_and_preferred_have_independent_weights():
    jd = JDParser().parse("Yêu cầu:\nPython bắt buộc, SQL ưu tiên")
    assert {item.requirement: item.preferred for item in jd.requirements} == {"Python": False, "SQL": True}


def test_fallback_report_marks_scores_as_provisional():
    from backend.services.report_service import generate_report
    service = AnalyzerReviewService(settings=Settings())
    try:
        review = service.analyze_cv(CVDocument(raw_text="""HỌC VẤN
Sinh viên đại học đang nghiên cứu dữ liệu và phát triển các kỹ năng phân tích để phục vụ công việc.
KỸ NĂNG: Python
DỰ ÁN
• Xây dựng báo cáo Python, giảm thời gian xử lý dữ liệu cho dự án học thuật.
"""))
    finally:
        service.close()
    assert "provisional estimates" in generate_report(review)
    assert "R" not in review.analysis.detected_skills
    assert review.skill_evidence[0].strength == "some_evidence"
    assert not review.bullet_reviews[0].issues
