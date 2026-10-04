# ==============================================================================
# PROCESSOR.PY — CVision Text Processor
# ==============================================================================
# Chức năng DUY NHẤT: Convert raw CV/JD text → structured data.
# KHÔNG chấm điểm. KHÔNG so sánh. KHÔNG tạo suggestion.
# ==============================================================================

import re
import unicodedata
from constants import (
    SECTION_NAMES,
    SKILL_SYNONYMS,
    INDUSTRY_KEYWORDS,
    REQUIRED_SIGNAL_WORDS,
    PREFERRED_SIGNAL_WORDS,
    SOFT_SKILLS,
    QUALIFICATION_LEVELS,
)


# ==============================================================================
# PUBLIC API — Đúng contract, không đổi tên
# ==============================================================================

def process_data(cv_text: str, jd_text: str, industry: str):
    """
    Nhận raw CV/JD text → trả về (cv_data, jd_data).

    Parameters:
        cv_text: Nội dung CV dạng plain text
        jd_text: Nội dung JD dạng plain text
        industry: Ngành nghề đã chọn

    Returns:
        (cv_data, jd_data): Hai dictionary chứa thông tin đã extract
    """
    industry_key = industry.strip().lower()
    cv_data = _process_cv(cv_text, industry_key)
    jd_data = _process_jd(jd_text, industry_key)
    return cv_data, jd_data


# ==============================================================================
# CV PROCESSING
# ==============================================================================

def _process_cv(cv_text: str, industry_key: str) -> dict:
    """Parse CV text → structured cv_data dictionary."""
    cleaned = _normalize_text(cv_text)
    sections = _detect_sections(cleaned)
    skills = _extract_cv_skills(sections, cleaned, industry_key)
    keywords = _extract_cv_keywords(cleaned, industry_key, skills)
    raw_bullets = _extract_bullets(sections.get("experience", ""))

    return {
        "education": _extract_list_items(sections.get("education", "")),
        "experience": _extract_list_items(sections.get("experience", "")),
        "skills": skills,
        "projects": _extract_list_items(sections.get("projects", "")),
        "certifications": _extract_list_items(sections.get("certifications", "")),
        "activities": _extract_list_items(sections.get("activities", "")),
        "keywords": keywords,
        "raw_bullets": raw_bullets,
        "detected_sections": list(sections.keys()),
    }


def _process_jd(jd_text: str, industry_key: str) -> dict:
    """Parse JD text → structured jd_data dictionary."""
    cleaned = _normalize_text(jd_text)
    job_title = _extract_job_title(cleaned)
    required_skills, preferred_skills = _classify_jd_requirements(cleaned)
    hard_skills, soft_skills = _split_hard_soft_skills(
        required_skills + preferred_skills
    )
    qualifications = _extract_qualifications(cleaned)
    experience_requirements = _extract_experience_requirements(cleaned)
    keywords = _extract_jd_keywords(cleaned, industry_key, required_skills + preferred_skills)

    return {
        "job_title": job_title,
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "hard_skills": hard_skills,
        "soft_skills": soft_skills,
        "qualifications": qualifications,
        "experience_requirements": experience_requirements,
        "keywords": keywords,
    }


# ==============================================================================
# TEXT NORMALIZATION
# ==============================================================================

def _normalize_text(text: str) -> str:
    """Normalize whitespace, newlines, punctuation. Giữ nguyên cấu trúc dòng."""
    if not text:
        return ""
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Remove excessive blank lines (3+ → 2)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove trailing whitespace per line
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def normalize_skill(skill: str) -> str:
    """Chuẩn hóa tên skill: lowercase, strip, áp dụng synonym."""
    if not skill:
        return ""
    s = skill.strip().lower()
    # Remove trailing punctuation
    s = re.sub(r"[.,;:!?]+$", "", s).strip()
    # Apply synonym mapping
    return SKILL_SYNONYMS.get(s, s)


# ==============================================================================
# SECTION DETECTION
# ==============================================================================

def _detect_sections(text: str) -> dict:
    """
    Tìm các section heading trong CV và extract nội dung tương ứng.
    Return dict: section_name → content string
    """
    lines = text.split("\n")
    sections = {}
    current_section = None
    current_content = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_section:
                current_content.append("")
            continue

        detected = _match_section_heading(stripped)
        if detected:
            # Save previous section
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = detected
            current_content = []
        elif current_section:
            current_content.append(line)

    # Save last section
    if current_section:
        sections[current_section] = "\n".join(current_content).strip()

    return sections


def _match_section_heading(line: str) -> str | None:
    """
    Kiểm tra xem dòng có phải là section heading không.
    Return tên section chuẩn hoặc None.
    """
    clean = unicodedata.normalize("NFKC", line).strip().casefold()
    # Remove common decorators
    clean = re.sub(r"^[#\-=*_|►▸▹●○◆◇■□▪▫]+\s*", "", clean)
    clean = re.sub(r"\s*[#\-=*_|►▸▹●○◆◇■□▪▫]+$", "", clean)
    clean = clean.strip().rstrip(":")

    if not clean or len(clean) > 50:  # Heading thường ngắn
        return None

    for section_name, patterns in SECTION_NAMES.items():
        for pattern in patterns:
            if clean == pattern or clean == pattern.upper().lower():
                return section_name
    return None



def _term_pattern(term: str) -> str:
    """Use the same Unicode boundaries for term presence and occurrence counts."""
    term_l = unicodedata.normalize("NFKC", term).casefold().strip()
    # Alphanumeric terms need token boundaries. Phrases and symbols are escaped literally.
    # Unicode boundaries prevent 'R' matching the first letter of Vietnamese
    # words such as 'rèn'; normalization also handles decomposed PDF accents.
    pattern = r"(?<!\w)" + re.escape(term_l) + r"(?!\w)"
    if term_l == "r":
        # Research and development is not evidence of the R programming tool.
        pattern += r"(?!\s*&\s*d\b)"
    return pattern


def _contains_term(text: str, term: str) -> bool:
    """Boundary-aware term search to avoid false positives such as skill 'r' in ordinary words."""
    if not text or not term or not term.strip():
        return False
    return re.search(_term_pattern(term), unicodedata.normalize("NFKC", text).casefold()) is not None

# ==============================================================================
# SKILL EXTRACTION
# ==============================================================================

def _extract_cv_skills(sections: dict, full_text: str, industry_key: str) -> list:
    """Extract skills từ CV sections và text."""
    skills = set()

    # 1. Extract từ Skills section
    skills_text = sections.get("skills", "")
    if skills_text:
        for skill in _parse_skill_list(skills_text):
            normalized = normalize_skill(skill)
            if normalized and len(normalized) > 1:
                skills.add(normalized)

    # 2. Scan toàn bộ CV text với industry keywords
    industry_kws = INDUSTRY_KEYWORDS.get(industry_key, [])
    text_lower = full_text.lower()
    for kw in industry_kws:
        if _contains_term(text_lower, kw):
            skills.add(normalize_skill(kw))

    # 3. Scan soft skills
    for ss in SOFT_SKILLS:
        if _contains_term(text_lower, ss):
            skills.add(ss)

    return sorted(list(skills))


def _parse_skill_list(text: str) -> list:
    """Parse danh sách skills từ text (có thể ngăn cách bởi newline, comma, bullet)."""
    # Split by newline first
    lines = text.split("\n")
    skills = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Remove bullet markers
        line = re.sub(r"^[\-•●○◆▪▸►*]\s*", "", line)
        # Split by comma, semicolon, or pipe
        parts = re.split(r"[,;|]", line)
        for part in parts:
            part = part.strip()
            if part and len(part) > 1 and len(part) < 60:
                skills.append(part)
    return skills


def _extract_cv_keywords(text: str, industry_key: str, existing_skills: list) -> list:
    """Extract keywords từ CV text, bổ sung thêm từ industry library."""
    keywords = set(existing_skills)
    text_lower = text.lower()

    industry_kws = INDUSTRY_KEYWORDS.get(industry_key, [])
    for kw in industry_kws:
        if _contains_term(text_lower, kw):
            keywords.add(normalize_skill(kw))

    return sorted(list(keywords))


# ==============================================================================
# JD PROCESSING
# ==============================================================================

def _extract_job_title(text: str) -> str:
    """Extract job title từ dòng đầu tiên hoặc heading của JD."""
    lines = text.strip().split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped and len(stripped) < 80:
            # Skip common JD headers
            lower = stripped.lower()
            if lower in ("job description", "jd", "position", "about the role"):
                continue
            return stripped
    return ""


def _classify_jd_requirements(text: str) -> tuple:
    """
    Phân loại yêu cầu JD thành required vs preferred.
    Return (required_skills, preferred_skills)
    """
    lines = text.split("\n")
    required = []
    preferred = []
    current_zone = "required"  # Default zone

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        lower = stripped.lower()

        # Detect zone changes
        if _is_preferred_heading(lower):
            current_zone = "preferred"
            continue
        elif _is_required_heading(lower):
            current_zone = "required"
            continue

        # Check inline preferred signals
        is_preferred_line = any(sig in lower for sig in PREFERRED_SIGNAL_WORDS)

        # Extract skills from line
        skills_in_line = _extract_skills_from_line(stripped)

        if is_preferred_line:
            preferred.extend(skills_in_line)
        elif current_zone == "preferred":
            preferred.extend(skills_in_line)
        elif skills_in_line:
            required.extend(skills_in_line)

    # Deduplicate
    required = _deduplicate_skills(required)
    preferred = _deduplicate_skills(preferred)

    # Remove from preferred anything already in required
    required_set = set(required)
    preferred = [s for s in preferred if s not in required_set]

    return required, preferred


def _is_required_heading(line: str) -> bool:
    """Check xem dòng có phải heading required section."""
    clean = re.sub(r"^[#\-*:]+\s*", "", line).strip().rstrip(":")
    req_headings = [
        "requirements", "required", "required skills",
        "qualifications", "required qualifications",
        "minimum qualifications", "key requirements",
        "what we're looking for", "what you need",
        "must have", "essential",
        "yêu cầu", "yêu cầu ứng viên", "yêu cầu công việc", "yêu cầu bắt buộc",
        "kỹ năng bắt buộc", "tiêu chuẩn ứng viên",
    ]
    return clean in req_headings


def _is_preferred_heading(line: str) -> bool:
    """Check xem dòng có phải heading preferred section."""
    clean = re.sub(r"^[#\-*:]+\s*", "", line).strip().rstrip(":")
    pref_headings = [
        "preferred", "preferred qualifications", "preferred skills",
        "nice to have", "bonus", "desirable",
        "good to have", "additional qualifications",
        "what would be a plus",
        "ưu tiên", "yêu cầu ưu tiên", "kỹ năng ưu tiên", "điểm cộng",
    ]
    return clean in pref_headings


def _extract_skills_from_line(line: str) -> list:
    """Extract skill phrases từ một dòng JD."""
    # Remove bullet markers
    clean = re.sub(r"^[\-•●○◆▪▸►*\d.)\]]+\s*", "", line).strip()
    if not clean or len(clean) < 3:
        return []

    # Nếu dòng quá dài, coi nó là mô tả → extract riêng
    normalized = normalize_skill(clean)

    # Tìm các cụm từ skill đã biết trong dòng
    found = []
    line_lower = clean.lower()

    # Check synonym keys using token/phrase boundaries.
    # This avoids false positives such as the skill "r" matching any word
    # that merely contains the letter r.
    all_known = list(SKILL_SYNONYMS.keys()) + list(set(SKILL_SYNONYMS.values()))
    for known in all_known:
        pattern = r"(?<![A-Za-z0-9])" + re.escape(known) + r"(?![A-Za-z0-9])"
        if re.search(pattern, line_lower):
            found.append(normalize_skill(known))

    # Check soft skills
    for ss in SOFT_SKILLS:
        pattern = r"(?<![A-Za-z0-9])" + re.escape(ss) + r"(?![A-Za-z0-9])"
        if re.search(pattern, line_lower):
            found.append(ss)

    # Check all industry keywords
    for industry, kws in INDUSTRY_KEYWORDS.items():
        for kw in kws:
            pattern = r"(?<![A-Za-z0-9])" + re.escape(kw) + r"(?![A-Za-z0-9])"
            if re.search(pattern, line_lower) and normalize_skill(kw) not in found:
                found.append(normalize_skill(kw))

    if found:
        return list(set(found))

    # Fallback: nếu dòng ngắn gọn, coi toàn dòng là 1 skill
    if len(clean.split()) <= 5:
        return [normalized] if normalized else []

    return []


def _split_hard_soft_skills(skills: list) -> tuple:
    """Tách skills thành hard skills và soft skills."""
    hard = []
    soft = []
    soft_set = set(SOFT_SKILLS)
    for skill in skills:
        if skill in soft_set:
            soft.append(skill)
        else:
            hard.append(skill)
    return _deduplicate_skills(hard), _deduplicate_skills(soft)


def _extract_qualifications(text: str) -> list:
    """Extract qualification requirements từ JD."""
    qualifications = []
    text_lower = text.lower()

    for level, keywords in QUALIFICATION_LEVELS.items():
        for kw in keywords:
            if _contains_term(text_lower, kw):
                qualifications.append(level)
                break

    return list(set(qualifications))


def _extract_experience_requirements(text: str) -> list:
    """Extract experience requirements (e.g., '2+ years')."""
    patterns = [
        r"(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)",
        r"(?:at least|minimum)\s*(\d+)\s*(?:years?|yrs?)",
        r"(\d+)\s*-\s*(\d+)\s*(?:years?|yrs?)",
    ]
    requirements = []
    for pattern in patterns:
        matches = re.findall(pattern, text.lower())
        for match in matches:
            if isinstance(match, tuple):
                requirements.append(f"{match[0]}-{match[1]} years")
            else:
                requirements.append(f"{match}+ years")
    return requirements


def _extract_jd_keywords(text: str, industry_key: str, skills: list) -> list:
    """Extract tất cả keywords quan trọng từ JD."""
    keywords = set(normalize_skill(s) for s in skills if s)
    text_lower = text.lower()

    # Add industry keywords found in JD
    industry_kws = INDUSTRY_KEYWORDS.get(industry_key, [])
    for kw in industry_kws:
        if _contains_term(text_lower, kw):
            keywords.add(normalize_skill(kw))

    # Remove empty
    keywords.discard("")
    return sorted(list(keywords))


# ==============================================================================
# HELPERS
# ==============================================================================

def _extract_list_items(text: str) -> list:
    """Extract items từ section text (mỗi dòng non-empty là 1 item)."""
    if not text:
        return []
    items = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped:
            # Remove bullet markers
            stripped = re.sub(r"^[\-•●○◆▪▸►*]\s*", "", stripped).strip()
            if stripped:
                items.append(stripped)
    return items


def _extract_bullets(text: str) -> list:
    """Extract actual bullet points from the Experience section.

    Prefer lines with explicit bullet markers. For plain-text CVs without markers,
    keep sentence-like lines that begin with a likely action phrase while avoiding
    obvious company/title/date headers.
    """
    if not text:
        return []

    bullets = []
    bullet_pattern = r"^[\-•●○◆▪▸►*]\s+"
    date_pattern = r"(?:19|20)\d{2}|present|current|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue

        has_marker = bool(re.match(bullet_pattern, stripped))
        clean = re.sub(bullet_pattern, "", stripped).strip()
        if len(clean.split()) < 3:
            continue

        if has_marker:
            bullets.append(clean)
            continue

        # Conservative fallback for CVs pasted without bullet characters.
        # Skip likely role/company/date header lines.
        if re.search(date_pattern, clean.lower()) and len(clean.split()) <= 10:
            continue
        if " - " in clean or " | " in clean:
            continue
        if clean.endswith(":"):
            continue

        # Sentence-like responsibility/achievement lines are usually longer.
        if len(clean.split()) >= 7:
            bullets.append(clean)

    return bullets


def _deduplicate_skills(skills: list) -> list:
    """Deduplicate skills giữ thứ tự."""
    seen = set()
    result = []
    for skill in skills:
        normalized = normalize_skill(skill)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result
