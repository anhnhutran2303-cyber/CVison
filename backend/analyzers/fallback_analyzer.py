"""Conservative deterministic requirement evaluation for AI fallback."""
import re

from backend.models import CandidateProfile, CVDocument, JDRequirement, RequirementMatch
from backend.normalization import duration_years, extract_known_skills, skill_in_text
from constants import QUALIFICATION_LEVELS
from processor import _contains_term


def match_requirement(requirement: JDRequirement, document: CVDocument, profile: CandidateProfile) -> RequirementMatch:
    text = document.raw_text
    evidence = []
    status = "missing"
    if requirement.skill_name and requirement.category in {"hard_skill", "other"}:
        evidence = [line.strip() for line in text.splitlines() if skill_in_text(requirement.skill_name, line)]
        supported = [line for line in profile.experience + profile.projects + profile.certifications
                     if skill_in_text(requirement.skill_name, line)]
        status = "matched" if supported else "partial" if evidence else "missing"
    elif requirement.category == "education":
        edu_text = " ".join(profile.education)
        levels = [level for level, aliases in QUALIFICATION_LEVELS.items()
                  if any(_contains_term(requirement.requirement, alias) for alias in aliases)]
        found = any(any(_contains_term(edu_text, alias) for alias in QUALIFICATION_LEVELS[level]) for level in levels)
        field = re.search(r"\b(?:in|ngành|chuyên ngành)\s+(.+?)(?:\s+(?:required|preferred|or|is|bắt buộc|ưu tiên|hoặc)\b|[,.;]|$)", requirement.requirement, re.I)
        if found:
            status = "matched" if field is None or _contains_term(edu_text, field[1].strip()) else "partial"
            evidence = profile.education
        elif profile.education:
            status, evidence = "partial", profile.education
    elif requirement.category in {"experience", "project"}:
        lines = profile.experience if requirement.category == "experience" else profile.projects
        skills = extract_known_skills(requirement.requirement)
        relevant = [line for line in lines if not skills or all(skill_in_text(skill, line) for skill in skills)]
        # Duration requirements are never fulfilled by keyword/project evidence alone.
        if relevant:
            status, evidence = "partial", relevant
            years = duration_years(requirement.requirement)
            explicit = [line for line in relevant if duration_years(line) is not None]
            if years is not None and explicit:
                # Still require the stated skill to be on the same evidence line.
                required_skills = extract_known_skills(requirement.requirement)
                qualified = [line for line in explicit
                             if duration_years(line) >= years
                             and all(skill_in_text(skill, line) for skill in required_skills)]
                if qualified:
                    status, evidence = "matched", qualified
        else:
            supporting = [line for line in profile.projects if skills and all(skill_in_text(skill, line) for skill in skills)]
            if supporting:
                status, evidence = "partial", supporting
    elif requirement.category == "role":
        evidence = [line.strip() for line in text.splitlines() if _contains_term(line, requirement.requirement)]
        status = "matched" if evidence else "missing"
    else:
        evidence = [line.strip() for line in text.splitlines() if _contains_term(line, requirement.requirement)]
        status = "partial" if evidence else "missing"
    # Profile strips bullet markers, so the cleaned quotations remain source substrings.
    return RequirementMatch(requirement=requirement.requirement, status=status, evidence=evidence[:3],
                            explanation="Conservative text evidence; proficiency and durations may need semantic review.")
