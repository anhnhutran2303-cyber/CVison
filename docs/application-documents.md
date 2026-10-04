# CV Builder and Cover Letter

## CV Builder

Open **Create → CV Builder**, enter your name and at least one CV section, then select
**Build CV**. Contact details and other sections are optional. Add a line starting with
`- ` for a bullet. The document keeps the supplied content and omits empty sections.

Choose English or Vietnamese for section headings. This does not translate your
content. Modern uses a left-aligned sans-serif title; Classic uses a centered serif
title. Both export a single-column Word document with contact information in the body,
real headings and real list paragraphs. The preview shows text; open Word to see layout.
Long content can span multiple pages. No vendor-specific ATS compatibility is promised.

Download Word or TXT. Submit **Build CV** again after edits to update the output.
**Use this CV in Analyzer** replaces the current CV input, clears the prior review and
saved-CV identity, retains the current JD, and opens Analyzer without making an AI call.
Choose Analyze explicitly when ready. Saving a reviewed CV is a separate action.

## Cover Letter

Open **Create → Cover Letter**. Paste CV/JD text, load the current Analyzer inputs,
or use a submitted Builder CV. Enter applicant name, target role and company; optionally
add a recipient and your own motivation. Select one to three excerpts from your CV.

The app orders actual excerpts using known skill overlaps with assessable JD sections,
excluding benefits and company descriptions. It then fills an English or Vietnamese
letter template with your selected excerpts. It does not translate excerpts, infer
unlisted qualifications, generate performance figures, or call Gemini. This is a
starting draft, not a semantic assessment or a fully AI-written letter.

**Create letter draft** produces text you can edit. Both downloads use the edited text.
Changing applicant information, the sources, selected evidence or language marks the
draft as out of date and hides downloads until regeneration. Regenerating replaces
manual edits; the editor remains available beforehand so they can be copied.

## State and validation

Submitted CVs, letter inputs and edited letters survive page navigation in the same
session. They are not automatically written to SQLite. Closing/reconnecting the session
may lose them; download before leaving. The existing saved workspace remains shared.

Validation rejects blank required fields, malformed optional email addresses,
unsupported XML control characters, overly long fields and evidence not found among
the current CV excerpts. Error messages omit private input values. No upload or
application submission happens from these pages. Both features work without an API key.

Implementation: `backend/services/application_documents.py` and
`frontend/documents_ui.py`. Coverage includes Unicode exports, parseable headings,
source grounding, JD exclusions, state retention, Analyzer handoff, stale drafts and
edited downloads. Synthetic Word exports are rendered to verify accents and layout.
