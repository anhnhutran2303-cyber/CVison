# CVision — CV & Job Match Analyzer

CVision là website hỗ trợ ứng viên kiểm tra CV trước khi ứng tuyển. Hệ thống so sánh CV với Job Description cụ thể để trả lời:

- CV phù hợp với công việc này đến mức nào?
- CV đang thiếu yêu cầu nào của JD?
- Nên sửa phần nào trước?

## Cài đặt

```bash
pip install -r requirements.txt
```

## Chạy

```bash
streamlit run app.py
```

## Cấu trúc

| File | Chức năng |
|------|-----------|
| `app.py` | Giao diện Streamlit (Dashboard, Analyzer, Results) |
| `processor.py` | Xử lý text CV/JD → dữ liệu có cấu trúc |
| `matcher.py` | So khớp CV ↔ JD, tính điểm |
| `cv_checker.py` | Kiểm tra chất lượng nội dung CV |
| `constants.py` | Keyword, synonym, trọng số, rule |

## Module Responsibility

- **app.py**: Navigation, UI, Form, Validation, Render results. KHÔNG tự extract keyword hay tính score.
- **processor.py**: Clean text, detect section, extract CV/JD info, normalize skills. Return `cv_data, jd_data`.
- **matcher.py**: Compare CV/JD, calculate coverage, calculate score. Return `match_result`.
- **cv_checker.py**: Structure checks, bullet analysis, content issues, suggestions. Return `check_result`.

## Final MVP features
- Upload CV: PDF, DOCX, TXT
- Upload JD: PDF, DOCX, TXT, or paste text
- Review extracted text before analysis
- Deterministic CV–JD score with weight redistribution
- Required / preferred skill coverage
- Keyword gap analysis
- CV structure and bullet quality checks
- Top priorities
- Downloadable text report
- Conservative matching rules designed to reduce substring false positives

## Important interpretation
CVision's Match Score measures alignment between the supplied CV text and Job Description using the project's deterministic rules. It is not an official ATS score, hiring probability, or guarantee of interview selection.
