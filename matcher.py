import re
# ==============================================================================
# MATCHER.PY — CVision Matching Engine
# ==============================================================================
# Chức năng DUY NHẤT: So sánh cv_data ↔ jd_data, tính coverage & score.
# KHÔNG đọc UI. KHÔNG tự parse CV. KHÔNG tạo suggestion.
# ==============================================================================

from constants import SCORE_WEIGHTS, MATCH_SCORE_LABELS, SOFT_SKILLS
from processor import normalize_skill


# ==============================================================================
# PUBLIC API — Đúng contract, không đổi tên
# ==============================================================================

def calculate_match(cv_data: dict, jd_data: dict) -> dict:
    """
    So sánh CV với JD và tính Match Score.

    Parameters:
        cv_data: Dictionary từ processor.process_data()
        jd_data: Dictionary từ processor.process_data()

    Returns:
        match_result: Dictionary chứa score, coverage, matched/missing lists
    """
    # --- Normalize all skills ---
    cv_skills = _normalize_list(cv_data.get("skills", []))
    cv_keywords = _normalize_list(cv_data.get("keywords", []))
    cv_education = cv_data.get("education", [])

    jd_required = _normalize_list(jd_data.get("required_skills", []))
    jd_preferred = _normalize_list(jd_data.get("preferred_skills", []))
    jd_keywords = _normalize_list(jd_data.get("keywords", []))
    jd_hard_skills = _normalize_list(jd_data.get("hard_skills", []))
    jd_soft_skills = _normalize_list(jd_data.get("soft_skills", []))
    jd_qualifications = jd_data.get("qualifications", [])

    # --- All CV terms combined for matching ---
    cv_all = set(cv_skills) | set(cv_keywords)

    # --- Required Skills Matching ---
    matched_required, missing_required = _match_lists(cv_all, jd_required)
    required_coverage = _safe_percentage(len(matched_required), len(jd_required))

    # --- Preferred Skills Matching ---
    matched_preferred, missing_preferred = _match_lists(cv_all, jd_preferred)
    preferred_coverage = _safe_percentage(len(matched_preferred), len(jd_preferred))

    # --- Keyword Matching ---
    matched_keywords, missing_keywords = _match_lists(cv_all, jd_keywords)
    keyword_coverage = _safe_percentage(len(matched_keywords), len(jd_keywords))

    # --- Hard/Soft Skills Matching ---
    matched_hard, missing_hard = _match_lists(cv_all, jd_hard_skills)
    matched_soft, missing_soft = _match_lists(cv_all, jd_soft_skills)

    # --- Qualification Matching ---
    qualification_score = _calculate_qualification_match(cv_education, jd_qualifications)

    # --- Score Breakdown ---
    score_breakdown = {
        "required_skills": round(required_coverage),
        "keywords": round(keyword_coverage),
        "preferred_skills": round(preferred_coverage),
        "qualification": round(qualification_score),
    }

    # --- Overall Match Score (with weight redistribution) ---
    match_score = _calculate_overall_score(
        required_coverage,
        keyword_coverage,
        preferred_coverage,
        qualification_score,
        has_required=len(jd_required) > 0,
        has_keywords=len(jd_keywords) > 0,
        has_preferred=len(jd_preferred) > 0,
        has_qualification=len(jd_qualifications) > 0,
    )

    # --- Match Score Label ---
    score_label, score_emoji = _get_score_label(match_score)

    return {
        "match_score": match_score,
        "score_label": score_label,
        "score_emoji": score_emoji,
        "required_coverage": round(required_coverage),
        "preferred_coverage": round(preferred_coverage),
        "keyword_coverage": round(keyword_coverage),
        "qualification_score": round(qualification_score),
        "matched_keywords": sorted(matched_keywords),
        "missing_keywords": sorted(missing_keywords),
        "matched_required_skills": sorted(matched_required),
        "missing_required_skills": sorted(missing_required),
        "matched_preferred_skills": sorted(matched_preferred),
        "missing_preferred_skills": sorted(missing_preferred),
        "matched_hard_skills": sorted(matched_hard),
        "missing_hard_skills": sorted(missing_hard),
        "matched_soft_skills": sorted(matched_soft),
        "missing_soft_skills": sorted(missing_soft),
        "score_breakdown": score_breakdown,
        "total_required": len(jd_required),
        "total_preferred": len(jd_preferred),
        "total_keywords": len(jd_keywords),
    }


# ==============================================================================
# SCORING LOGIC
# ==============================================================================

def _calculate_overall_score(
    required_cov: float,
    keyword_cov: float,
    preferred_cov: float,
    qualification_score: float,
    has_required: bool,
    has_keywords: bool,
    has_preferred: bool,
    has_qualification: bool,
) -> int:
    """
    Tính Overall Match Score với weight redistribution.

    Nếu một component không có dữ liệu (ví dụ JD không có preferred skills),
    weight của nó được phân bổ lại cho các component còn lại.
    KHÔNG BAO GIỜ penalize ứng viên vì JD thiếu dữ liệu.
    """
    components = []
    base_weights = SCORE_WEIGHTS

    if has_required:
        components.append(("required", required_cov, base_weights["required"]))
    if has_keywords:
        components.append(("keywords", keyword_cov, base_weights["keywords"]))
    if has_preferred:
        components.append(("preferred", preferred_cov, base_weights["preferred"]))
    if has_qualification:
        components.append(("qualification", qualification_score, base_weights["qualification"]))

    if not components:
        return 0

    # Redistribute weights proportionally
    total_active_weight = sum(w for _, _, w in components)
    if total_active_weight == 0:
        return 0

    score = 0.0
    for name, coverage, weight in components:
        adjusted_weight = weight / total_active_weight
        score += coverage * adjusted_weight

    # Clamp to [0, 100] and round
    return max(0, min(100, round(score)))


def _calculate_qualification_match(cv_education: list, jd_qualifications: list) -> float:
    """
    Tính qualification match dựa trên education level.
    Return 0-100.
    """
    if not jd_qualifications:
        return 100.0  # Không yêu cầu → mặc định đạt

    cv_text = " ".join(cv_education).lower()

    # Check từng level yêu cầu
    matched = 0
    for qual in jd_qualifications:
        if qual.lower() in cv_text:
            matched += 1
        else:
            # Broader check
            from constants import QUALIFICATION_LEVELS
            for kw in QUALIFICATION_LEVELS.get(qual, []):
                if kw in cv_text:
                    matched += 1
                    break

    return _safe_percentage(matched, len(jd_qualifications))


# ==============================================================================
# MATCHING HELPERS
# ==============================================================================

def _match_lists(cv_set: set, jd_list: list) -> tuple:
    """
    So sánh CV skills với JD requirements.
    Return (matched_list, missing_list)
    """
    if not jd_list:
        return [], []

    matched = []
    missing = []
    for item in jd_list:
        if item in cv_set:
            matched.append(item)
        else:
            missing.append(item)

    return matched, missing



def _canonical_term(term: str) -> str:
    """Conservative canonicalization for deterministic matching."""
    t = normalize_skill(term).strip().lower()
    t = re.sub(r"\s+", " ", t)
    replacements = {
        "modelling": "modeling",
        "visualisation": "visualization",
        "organisation": "organization",
        "analyse": "analyze",
    }
    for a, b in replacements.items():
        t = t.replace(a, b)
    return t

def _normalize_list(items: list) -> list:
    """Normalize và deduplicate danh sách skills/keywords."""
    seen = set()
    result = []
    for item in items:
        normalized = _canonical_term(item)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _safe_percentage(numerator: int, denominator: int) -> float:
    """Tính phần trăm an toàn, tránh division by zero."""
    if denominator == 0:
        return 0.0
    return (numerator / denominator) * 100


def _get_score_label(score: int) -> tuple:
    """Return (label, emoji) dựa trên ngưỡng cố định."""
    for low, high, label, emoji in MATCH_SCORE_LABELS:
        if low <= score <= high:
            return label, emoji
    return "Unknown", "⚪"
