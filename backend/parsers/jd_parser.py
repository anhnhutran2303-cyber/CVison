"""Conservative clause extraction; headings and duplicate keywords are excluded."""
import re

from backend.models import JDRequirement, JobDescription
from backend.normalization import duration_years, extract_known_skills, normalize_skill, normalized_text
from constants import SOFT_SKILLS
from processor import _is_preferred_heading, _is_required_heading

CONTENT_HEADINGS = {"responsibilities", "key responsibilities", "about the role", "job description",
                    "duties", "position", "jd", "mô tả công việc", "nhiệm vụ",
                    "trách nhiệm", "hạng mục công việc cụ thể", "công việc cụ thể"}
EXCLUDED_HEADINGS = {"about us", "about the company", "company overview", "benefits",
                     "employee benefits", "compensation and benefits", "what we offer",
                     "perks", "how to apply", "application process", "quyền lợi",
                     "quyền lợi ứng viên", "quyền lợi được hưởng", "phúc lợi",
                     "chế độ đãi ngộ", "về chúng tôi", "giới thiệu công ty",
                     "cách ứng tuyển", "thông tin ứng tuyển"}
EDUCATION_PATTERN = r"\b(bachelor|master|ph\.?d|doctorate|degree|diploma|undergraduate|bsc|msc|mba|đại học|cao đẳng|thạc sĩ|tiến sĩ)\b"
PREFERRED_PATTERN = r"\b(?:preferred|optional|bonus|desired|desirable|advantage|plus|ưu tiên|điểm cộng)\b|nice to have"
REQUIRED_PATTERN = r"\b(?:must|required|essential|mandatory|minimum|bắt buộc|tối thiểu)\b"


class JDParser:
    def assessable_lines(self, text: str):
        """Reuse section exclusion for parsing and keyword counts."""
        preferred_zone = False
        excluded_zone = False
        for original in text.splitlines():
            line = re.sub(r"^\s*(?:#+\s*|[-•●*]\s*|\d+[.)]\s+)*", "", original).strip()
            if not line:
                continue
            heading, separator, body = line.partition(":")
            key = normalized_text(heading if separator else line).rstrip(":")
            if key in EXCLUDED_HEADINGS:
                excluded_zone = True
                continue
            if _is_required_heading(key) or _is_preferred_heading(key) or key in CONTENT_HEADINGS:
                excluded_zone = False
                preferred_zone = _is_preferred_heading(key)
                if not separator or not body.strip():
                    continue
                line = body.strip()
            if excluded_zone:
                continue
            yield line, preferred_zone

    def parse(self, text: str) -> JobDescription:
        requirements = []
        title = None
        for line, preferred_zone in self.assessable_lines(text):
            lower = normalized_text(line)
            # A short role/title line is kept in the role component, never as a skill.
            if title is None and len(line.split()) <= 8 and re.search(r"\b(intern|analyst|engineer|developer|manager|designer|consultant|specialist|officer|content creator|nhân viên|chuyên viên|thực tập sinh)\b", lower) and not re.search(r"\b(must|required|preferred|experience|years?|bắt buộc|kinh nghiệm|năm)\b", lower):
                title = line
                requirements.append(JDRequirement(requirement=line, category="role"))
                continue
            # Split mixed clauses before applying preferred markers, preserving local context.
            clauses = re.split(r";|[.!?]\s+|\bbut\b|\bwhile\b", line)
            for clause in clauses:
                clause = clause.strip(" ,.")
                if not clause:
                    continue
                # 'Python required and Power BI preferred' needs separate clauses.
                # Commas in a responsibility retain its meaning. Only split a
                # list when a following fragment has its own requirement marker.
                fragments = re.split(r",\s*(?=[^,;]*(?:" + PREFERRED_PATTERN + "|" + REQUIRED_PATTERN + r"))|\band\b(?=[^,;]*(?:" + PREFERRED_PATTERN + r"))", clause, flags=re.I)
                for fragment in fragments:
                    fragment = fragment.strip(" ,.")
                    if not fragment:
                        continue
                    is_preferred = bool(re.search(PREFERRED_PATTERN, fragment, re.I))
                    is_required = bool(re.search(REQUIRED_PATTERN, fragment, re.I))
                    preferred = is_preferred or (preferred_zone and not is_required)
                    skills = extract_known_skills(fragment)
                    if re.search(EDUCATION_PATTERN, fragment, re.I):
                        category = "education"
                    elif duration_years(fragment) is not None or re.search(r"\b(?:professional|work) experience\b", fragment, re.I):
                        category = "experience"
                    elif re.search(r"\b(?:projects?|dự án)\b", fragment, re.I):
                        category = "project"
                    else:
                        category = None
                    if category:
                        requirements.append(JDRequirement(requirement=fragment, category=category, preferred=preferred,
                                                          skill_name=skills[0] if len(skills) == 1 else None))
                    elif skills:
                        for skill in skills:
                            requirements.append(JDRequirement(requirement=skill, skill_name=skill,
                                category="other" if skill.lower() in SOFT_SKILLS else "hard_skill", preferred=preferred))
                    else:
                        # Unknown prose stays an explicit requirement for AI to evaluate.
                        requirements.append(JDRequirement(requirement=fragment, category="other", preferred=preferred))
        unique = {}
        for requirement in requirements:
            key = normalize_skill(requirement.requirement).casefold()
            if key not in unique or (unique[key].preferred and not requirement.preferred):
                unique[key] = requirement
        return JobDescription(raw_text=text.strip(), job_title=title, requirements=list(unique.values()))
