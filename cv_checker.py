# ==============================================================================
# CV_CHECKER.PY — CVision CV Quality Checker
# ==============================================================================
# Chức năng DUY NHẤT: Kiểm tra chất lượng nội dung CV.
# KHÔNG quyết định Match Score. KHÔNG so sánh CV ↔ JD.
# Trả lời câu hỏi: "CV này đang có vấn đề gì về nội dung?"
# ==============================================================================

import re
from constants import WEAK_VERBS, IMPACT_VERBS


# ==============================================================================
# PUBLIC API — Đúng contract, không đổi tên
# ==============================================================================

def check_cv(cv_text: str, cv_data: dict, jd_data: dict) -> dict:
    """
    Kiểm tra chất lượng nội dung CV.

    Parameters:
        cv_text: Nội dung CV gốc (plain text)
        cv_data: Dictionary từ processor
        jd_data: Dictionary từ processor

    Returns:
        check_result: Dictionary chứa issues, bullet analysis, suggestions, priorities
    """
    ats_issues = _check_ats_structure(cv_text, cv_data)
    bullets = cv_data.get("raw_bullets", [])
    bullet_analyses = _analyze_bullets(bullets)

    content_issues = _collect_content_issues(bullet_analyses)
    task_based = [b for b in bullet_analyses if b["classification"] == "task-based"]
    impact_based = [b for b in bullet_analyses if b["classification"] == "impact-oriented"]

    suggestions = _generate_suggestions(bullet_analyses, ats_issues)
    top_3 = _generate_top_priorities(
        ats_issues, bullet_analyses, content_issues, cv_data, jd_data
    )

    return {
        "ats_issues": ats_issues,
        "content_issues": content_issues,
        "task_based_bullets": task_based,
        "impact_based_bullets": impact_based,
        "bullet_analyses": bullet_analyses,
        "total_bullets": len(bullets),
        "suggestions": suggestions,
        "top_3_priorities": top_3,
    }


# ==============================================================================
# ATS STRUCTURE CHECK
# ==============================================================================

def _check_ats_structure(cv_text: str, cv_data: dict) -> list:
    """
    Kiểm tra cấu trúc ATS cơ bản từ text.
    CHỈ check những gì có thể check từ plain text.
    KHÔNG giả vờ check layout, fonts, columns, icons.
    """
    issues = []
    detected = cv_data.get("detected_sections", [])

    # --- Section checks ---
    section_checks = [
        ("education", "Education section", "A clear Education section helps recruiters verify your academic background."),
        ("experience", "Experience section", "An Experience section is essential for showcasing your work history."),
        ("skills", "Skills section", "A dedicated Skills section makes relevant technical skills easier to identify."),
    ]
    for section_key, section_name, suggestion in section_checks:
        found = section_key in detected
        issues.append({
            "check": section_name,
            "passed": found,
            "message": f"✓ {section_name} detected" if found else f"⚠ {section_name} not detected",
            "suggestion": "" if found else suggestion,
        })

    # --- Contact info checks ---
    # Email
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    has_email = bool(re.search(email_pattern, cv_text))
    issues.append({
        "check": "Email",
        "passed": has_email,
        "message": "✓ Email detected" if has_email else "⚠ Email not detected",
        "suggestion": "" if has_email else "Include your email address so recruiters can contact you.",
    })

    # Phone
    phone_pattern = r"(?:\+?\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}"
    has_phone = bool(re.search(phone_pattern, cv_text))
    issues.append({
        "check": "Phone number",
        "passed": has_phone,
        "message": "✓ Phone number detected" if has_phone else "⚠ Phone number not detected",
        "suggestion": "" if has_phone else "Consider adding a phone number for direct contact.",
    })

    return issues


# ==============================================================================
# BULLET ANALYSIS
# ==============================================================================

def _analyze_bullets(bullets: list) -> list:
    """Phân tích từng bullet point trong CV."""
    analyses = []
    for bullet in bullets:
        analysis = _analyze_single_bullet(bullet)
        analyses.append(analysis)
    return analyses


def _analyze_single_bullet(bullet: str) -> dict:
    """
    Phân tích một bullet point.
    Return dict chứa classification, issues, signals.
    """
    word_count = len(bullet.split())
    issues = []
    signals = []

    # --- Long bullet check ---
    is_long = word_count > 35
    if is_long:
        issues.append({
            "type": "long_bullet",
            "message": f"Long bullet detected ({word_count} words)",
            "suggestion": "Consider breaking this into shorter, more focused points.",
        })

    # --- Weak verb check ---
    bullet_lower = bullet.lower().strip()
    weak_verb_found = None
    for verb in WEAK_VERBS:
        if bullet_lower.startswith(verb):
            weak_verb_found = verb
            issues.append({
                "type": "weak_verb",
                "message": f"Opens with \"{verb}\"",
                "suggestion": "This bullet may focus more on responsibility than contribution.",
            })
            break

    # --- Quantification check ---
    has_quantification = bool(re.search(r"\d+|%|\$|£|€", bullet))
    if has_quantification:
        signals.append("quantification")

    # --- Impact verb check ---
    impact_found = []
    for verb in IMPACT_VERBS:
        pattern = r"\b" + re.escape(verb) + r"\b"
        if re.search(pattern, bullet_lower):
            impact_found.append(verb)
            signals.append(f"impact_verb:{verb}")

    # --- Classification ---
    classification = _classify_bullet(
        has_quantification=has_quantification,
        has_impact_verb=len(impact_found) > 0,
        has_weak_verb=weak_verb_found is not None,
        word_count=word_count,
    )

    # --- Reason ---
    if classification == "impact-oriented":
        reason_parts = []
        if impact_found:
            reason_parts.append("✓ Action verb")
        if has_quantification:
            reason_parts.append("✓ Quantified context")
        if word_count >= 5:
            reason_parts.append("✓ Specific work")
        reason = "\n".join(reason_parts) if reason_parts else "Contains specific details."
    else:
        reason = "Describes responsibility but does not show a result."

    return {
        "bullet": bullet,
        "word_count": word_count,
        "classification": classification,
        "is_long": is_long,
        "has_quantification": has_quantification,
        "has_weak_verb": weak_verb_found is not None,
        "weak_verb": weak_verb_found,
        "impact_verbs": impact_found,
        "issues": issues,
        "signals": signals,
        "reason": reason,
        "improvement_questions": _get_improvement_questions(bullet) if classification == "task-based" else [],
    }


def _classify_bullet(
    has_quantification: bool,
    has_impact_verb: bool,
    has_weak_verb: bool,
    word_count: int,
) -> str:
    """
    Phân loại bullet thành task-based hoặc impact-oriented.
    KHÔNG mặc định câu task-based là sai.
    """
    score = 0
    if has_impact_verb:
        score += 2
    if has_quantification:
        score += 2
    if has_weak_verb:
        score -= 2
    if word_count >= 8:
        score += 1

    return "impact-oriented" if score >= 2 else "task-based"


def _get_improvement_questions(bullet: str) -> list:
    """Tạo câu hỏi gợi ý cải thiện cho task-based bullet."""
    questions = []
    bullet_lower = bullet.lower()

    # Generic questions
    questions.append("What specific outcome resulted from this work?")

    if "report" in bullet_lower:
        questions.extend([
            "What reports did you prepare?",
            "How often?",
            "Who used the report?",
        ])
    elif "data" in bullet_lower or "analy" in bullet_lower:
        questions.extend([
            "What data did you analyze?",
            "What insights did you find?",
            "Was there a measurable result?",
        ])
    elif "support" in bullet_lower or "assist" in bullet_lower:
        questions.extend([
            "What was your specific contribution?",
            "What tasks did you own?",
            "What was the scope?",
        ])
    else:
        questions.extend([
            "How often did you do this?",
            "What was the scope?",
            "Was there a measurable result?",
        ])

    return questions[:4]  # Max 4 questions


# ==============================================================================
# CONTENT ISSUES
# ==============================================================================

def _collect_content_issues(bullet_analyses: list) -> list:
    """Thu thập tất cả content issues từ bullet analyses."""
    issues = []
    for analysis in bullet_analyses:
        for issue in analysis.get("issues", []):
            issues.append({
                "bullet": analysis["bullet"],
                "type": issue["type"],
                "message": issue["message"],
                "suggestion": issue["suggestion"],
            })
    return issues


# ==============================================================================
# SUGGESTIONS
# ==============================================================================

def _generate_suggestions(bullet_analyses: list, ats_issues: list) -> list:
    """Tạo danh sách suggestions dựa trên analysis."""
    suggestions = []

    # ATS suggestions
    for issue in ats_issues:
        if not issue["passed"] and issue["suggestion"]:
            suggestions.append({
                "category": "structure",
                "message": issue["suggestion"],
            })

    # Bullet suggestions
    task_count = sum(1 for b in bullet_analyses if b["classification"] == "task-based")
    total = len(bullet_analyses)

    if total > 0 and task_count > total / 2:
        suggestions.append({
            "category": "content",
            "message": f"{task_count} of {total} experience bullets appear task-based. "
                       f"Focus on showing what you did, scope, outcome, and measurable context.",
        })

    long_count = sum(1 for b in bullet_analyses if b["is_long"])
    if long_count > 0:
        suggestions.append({
            "category": "readability",
            "message": f"{long_count} bullet(s) exceed 35 words. "
                       f"Consider breaking them into shorter, more focused points.",
        })

    return suggestions


# ==============================================================================
# TOP 3 PRIORITIES
# ==============================================================================

def _generate_top_priorities(
    ats_issues: list,
    bullet_analyses: list,
    content_issues: list,
    cv_data: dict,
    jd_data: dict,
) -> list:
    """
    Tạo Top 3 Priorities — xếp hạng theo impact.
    Maximum 3 recommendations.
    """
    priorities = []

    # --- Priority: Missing required skills ---
    # (Lấy từ jd_data, check xem CV có không)
    missing_required = jd_data.get("required_skills", [])
    cv_skills_set = set(s.lower() for s in cv_data.get("skills", []))
    cv_keywords_set = set(k.lower() for k in cv_data.get("keywords", []))
    cv_all = cv_skills_set | cv_keywords_set

    truly_missing = [s for s in missing_required if s.lower() not in cv_all]
    if truly_missing:
        skills_str = ", ".join(truly_missing[:3])
        priorities.append({
            "priority": len(priorities) + 1,
            "title": f"Show {truly_missing[0].title()} Experience" if len(truly_missing) == 1
                     else "Address Missing Required Skills",
            "why": f"{skills_str} appear(s) in the job requirements but was not detected in your CV.",
            "action": "If you have used these skills in coursework, projects or work experience, "
                      "make that experience more explicit. Do not add skills that do not reflect "
                      "your actual experience.",
            "impact": "high",
        })

    # --- Priority: Task-based bullets ---
    task_based = [b for b in bullet_analyses if b["classification"] == "task-based"]
    total_bullets = len(bullet_analyses)
    if task_based and total_bullets > 0:
        priorities.append({
            "priority": len(priorities) + 1,
            "title": "Improve Experience Bullets",
            "why": f"{len(task_based)} of your {total_bullets} experience bullets "
                   f"appear task-based.",
            "action": "Focus on showing: what you did, scope, outcome, and measurable context.",
            "impact": "medium",
        })

    # --- Priority: Missing keywords ---
    missing_keywords = jd_data.get("keywords", [])
    kw_missing = [k for k in missing_keywords if k.lower() not in cv_all]
    if kw_missing and len(priorities) < 3:
        kw_str = ", ".join(kw_missing[:4])
        priorities.append({
            "priority": len(priorities) + 1,
            "title": "Align Relevant Keywords",
            "why": "Your CV uses different terminology from the JD for several related concepts.",
            "action": f"Review: {kw_str}",
            "impact": "medium",
        })

    # --- Priority: ATS issues ---
    ats_fails = [i for i in ats_issues if not i["passed"]]
    if ats_fails and len(priorities) < 3:
        priorities.append({
            "priority": len(priorities) + 1,
            "title": "Fix CV Structure Issues",
            "why": f"{len(ats_fails)} structural issue(s) detected.",
            "action": ats_fails[0]["suggestion"],
            "impact": "medium",
        })

    return priorities[:3]  # Maximum 3
