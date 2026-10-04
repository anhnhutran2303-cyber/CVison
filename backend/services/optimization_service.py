"""Explain keyword presence and readable text without generating another score."""
import re

from backend.models import CVDocument, CVAnalysisResult
from backend.normalization import extract_known_skills, keyword_count, normalized_text, skill_in_text
from backend.parsers.jd_parser import JDParser
from backend.review_models import KeywordComparison, OptimizationReport, SearchabilityCheck
from backend.services.bullet_review_service import section_bullets
from constants import SOFT_SKILLS

NUMERIC_DETAIL = re.compile(
    r"(?<!\w)\d+(?:[.,]\d+)?\s*(?:%|percent\b|phần trăm\b|"
    r"(?:million|thousand|triệu|nghìn)\b|"
    r"(?:rows?|records?|users?|customers?|clients?|samples?|datasets?|reports?|"
    r"seconds?|minutes?|hours?|ms|dòng|bản ghi|người dùng|khách hàng|mẫu|báo cáo|giây|phút|giờ)(?!\w))",
    re.I,
)


def compare_keywords(document, jd_text, analysis):
    if not jd_text:
        return []
    parser = JDParser()
    jd = parser.parse(jd_text)
    source = "\n".join(line for line, _ in parser.assessable_lines(jd_text))
    matches = {normalized_text(item.requirement): item for item in analysis.requirement_matches}
    requirements_by_skill = {}
    for requirement in jd.requirements:
        if requirement.category == "role":
            continue
        for skill in extract_known_skills(requirement.requirement):
            requirements_by_skill.setdefault(skill, []).append(requirement)
    rows = []
    for skill, requirements in requirements_by_skill.items():
        evidence = [line.strip() for line in document.raw_text.splitlines() if skill_in_text(skill, line)]
        rows.append(KeywordComparison(keyword=skill,
            group="soft_skill" if skill.casefold() in SOFT_SKILLS else "hard_skill",
            required=any(not item.preferred for item in requirements),
            cv_count=keyword_count(skill, document.raw_text), jd_count=keyword_count(skill, source),
            evidence=list(dict.fromkeys(evidence))[:5],
            requirements=[matches[normalized_text(item.requirement)] for item in requirements
                          if normalized_text(item.requirement) in matches]))
    if jd.job_title:
        match = matches.get(normalized_text(jd.job_title))
        rows.append(KeywordComparison(keyword=jd.job_title, group="job_title",
            cv_count=keyword_count(jd.job_title, document.raw_text, aliases=False),
            jd_count=keyword_count(jd.job_title, source, aliases=False),
            evidence=[line.strip() for line in document.raw_text.splitlines()
                      if keyword_count(jd.job_title, line, aliases=False)][:5],
            requirements=[match] if match else []))
    return sorted(rows, key=lambda row: (row.cv_count > 0, not row.required, row.group, row.keyword.casefold()))


def searchability_checks(document: CVDocument, analysis: CVAnalysisResult, target=None):
    basic = analysis.basic_checks
    checks = []
    for field, label, present, action in (
        ("email", "Email address", basic.has_email, "Add a contact email in the CV text."),
        ("phone", "Phone number", basic.has_phone, "Add a phone number with a country code if appropriate."),
    ):
        checks.append(SearchabilityCheck(id=field, label=label, status="passed" if present else "warning",
            detail="Detected in the supplied CV text." if present else "Not detected in the supplied CV text.",
            action="" if present else action))
    checks.append(SearchabilityCheck(id="sections", label="Recognizable section headings",
        status="warning" if basic.missing_sections else "passed",
        detail=("Sections not detected: " + ", ".join(basic.missing_sections)) if basic.missing_sections
               else "Core section headings were detected.",
        action="Use clear headings such as Education / Học vấn, Skills / Kỹ năng, and Projects / Dự án. Include work experience when you have it." if basic.missing_sections else ""))
    low = document.extraction_quality == "low"
    checks.append(SearchabilityCheck(id="extraction", label="Readable extracted text",
        status="warning" if low else "passed",
        detail="The file parser flagged incomplete or disordered text." if low else "Readable text was supplied for this review.",
        action="Check the text order against your original file. Use a text-based PDF or DOCX if text is missing." if low else ""))
    bullets = section_bullets(document)
    quantified = sum(bool(NUMERIC_DETAIL.search(text)) for _, text in bullets)
    checks.append(SearchabilityCheck(id="numeric_detail", label="Concrete numbers in work / project bullets",
        status="passed" if quantified else "warning",
        detail=f"{quantified} of {len(bullets)} detected bullets contain numeric scope or result details. Dates and years of experience are not counted.",
        action="Add scope or measured outcomes only when you can verify them. Concrete nonnumeric outputs are also useful." if not quantified else ""))
    checks.append(SearchabilityCheck(id="word_count", label="CV length",
        status="not_assessed", detail=f"{basic.word_count} words in the supplied text. Appropriate length depends on your experience and the role."))
    if target:
        found = keyword_count(target, document.raw_text, aliases=False) > 0
        checks.append(SearchabilityCheck(id="job_title", label="Target job title wording",
            status="passed" if found else "warning",
            detail=f'Exact phrase "{target}" ' + ("was found." if found else "was not found."),
            action="If this is the role you are seeking, clarify it in your headline or summary. Keep past job titles accurate." if not found else ""))
    checks.append(SearchabilityCheck(id="layout", label="Original file layout / ATS compatibility",
        status="not_assessed", detail="Text checks cannot verify fonts, columns, image-only content, page layout or compatibility with a particular ATS.",
        action="Review your original document and confirm that its text can be selected and copied in the correct reading order."))
    return checks


def build_optimization(document, jd_text, analysis, target=None):
    return OptimizationReport(keywords=compare_keywords(document, jd_text, analysis),
                              checks=searchability_checks(document, analysis, target))
