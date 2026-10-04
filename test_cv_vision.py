import unittest
from processor import process_data
from matcher import calculate_match
from cv_checker import check_cv

CV = """EDUCATION
Foreign Trade University
Bachelor of Finance

EXPERIENCE
Finance Intern - ABC Company
• Prepared weekly financial reports.
• Analyzed revenue variances across 4 business units.
• Supported budgeting activities using Microsoft Excel.

SKILLS
Microsoft Excel, PowerPoint, Financial Analysis, English
"""

JD = """FINANCE INTERN
Requirements:
Strong Microsoft Excel skills.
Good English communication.
Experience with financial analysis.
Basic financial modeling knowledge.

Preferred:
Power BI experience is a plus.
Knowledge of valuation is preferred.
"""

class TestCVision(unittest.TestCase):
    def test_no_false_r_skill(self):
        cv,jd=process_data(CV,JD,"Finance")
        self.assertNotIn("r", jd["required_skills"])
        self.assertNotIn("r", jd["keywords"])

    def test_expected_finance_skills(self):
        cv,jd=process_data(CV,JD,"Finance")
        self.assertIn("excel", cv["skills"])
        self.assertIn("financial analysis", cv["skills"])
        self.assertIn("financial modeling", jd["required_skills"])
        self.assertIn("power bi", jd["preferred_skills"])

    def test_headers_not_bullets(self):
        cv,jd=process_data(CV,JD,"Finance")
        joined=" | ".join(cv["raw_bullets"]).lower()
        self.assertNotIn("finance intern - abc company", joined)
        self.assertTrue(any("4 business units" in x.lower() for x in cv["raw_bullets"]))

    def test_score_bounds(self):
        cv,jd=process_data(CV,JD,"Finance")
        result=calculate_match(cv,jd)
        self.assertGreaterEqual(result["match_score"],0)
        self.assertLessEqual(result["match_score"],100)

    def test_empty_data_does_not_crash(self):
        cv,jd=process_data("","","Finance")
        result=calculate_match(cv,jd)
        self.assertGreaterEqual(result["match_score"],0)

    def test_checker_runs(self):
        cv,jd=process_data(CV,JD,"Finance")
        c=check_cv(CV,cv,jd)
        self.assertIn("top_3_priorities",c)
        self.assertGreaterEqual(c["total_bullets"],2)

if __name__=="__main__":
    unittest.main()
