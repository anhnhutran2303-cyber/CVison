# Keyword comparison and iterative editing

The review includes four additions inspired by common resume scanner workflows:
keyword comparison, a searchability checklist, inline editing/re-scanning and a
before/after view. CVision retains its own scoring and evidence contracts.

## Keyword Match

- One row per known canonical skill, plus the parsed job title where available.
- Hard skills/tools, soft skills and job title groups; required/preferred priorities.
- CV and JD mention counts, with aliases (including Vietnamese skills) merged.
  Overlapping aliases are counted once. Unicode token boundaries avoid matching
  `R` inside Vietnamese words or `R&D`.
- JD counts use the same assessable sections as requirement parsing. Benefits,
  company information and application instructions are excluded until the next
  requirements/responsibilities heading.
- Filters, quoted CV context, the underlying requirement match status and CSV export.

Counts indicate vocabulary presence. They do not indicate proficiency, seniority
or fulfillment of an experience requirement. A Power BI mention may coexist with
a partial match for two years of Power BI experience. Free-text requirements that
are outside the keyword dictionary remain in Job Match. This is not a complete
keyword extraction model and does not reproduce any ATS vendor's algorithm.

Creative tool names and Vietnamese aliases were added to the shared dictionary.
Newly recognized requirements can therefore affect the inputs to existing scoring;
numeric formulas, weights and scoring version are unchanged.

## Searchability

The checklist uses the supplied text and file extraction metadata for email,
phone, recognizable section headings and extraction warnings. It counts numeric
scope/result details only in detected work/project bullets. Dates and years of
experience are excluded. Nonnumeric outcomes are still valuable, and every suggested
number must be verified by the user. Length is informational.

Original file layout, fonts, columns, image-only content and compatibility with a
particular ATS are explicitly **not assessed**. A successful text check is not a
guarantee of ATS compatibility. Upload extraction remains the existing parser's
responsibility; OCR has not been added.

## Optimize & Re-scan

The inline form starts with the analyzed CV and current JD. Editing does not call
Gemini. Submitting explicitly runs the existing analysis pipeline once, synchronizes
the Analyzer editors and refreshes the result. A failed scan keeps the prior review
and the unsuccessful draft for correction. TXT download uses the most recently
submitted form values; Markdown/CSV downloads include the latest successful review.

A before/after view compares the previous successful session review when the exact
trimmed JD, role/industry context, analysis mode, model, prompt/scoring version and
AI availability are unchanged. Changed conditions suppress score deltas. Both
fallback scans are labeled provisional. Numeric deltas do not establish a causal
improvement: repeated AI judgments can vary even with the same inputs.

Saved CV re-analysis still appends a history snapshot through the existing workspace
service. Opening a saved snapshot or starting another CV resets session comparison
and inline drafts. Comparison is session-only and is not persisted as a new score.

## Compatibility and validation

`AnalyzerReview.optimization` is an optional additive field, so old saved JSON
remains readable. Older snapshots prompt a re-analysis to populate the new tabs.
No database schema migration or new dependency is required.

Regression coverage checks Unicode and overlapping alias counts, JD exclusions,
contextual evidence, Vietnamese tool/skill grouping, readable text limitations,
report exports, older snapshots, UI filters, editor synchronization, scan failures
and suppression of comparisons when JD or AI availability changes.
