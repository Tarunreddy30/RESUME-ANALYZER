# Project Explanation (in simple English)

## 1. What is a Resume Analyzer?

A resume analyzer is a program that reads a resume and compares it with a job description. It tells the candidate how well the two match and what could be improved. Humans do this by reading; the program does it by processing text.

## 2. What is ATS?

**ATS = Applicant Tracking System.** It is software that companies use to collect, store, filter and rank job applications. Different companies use different ATS products with different (usually secret) rules. Common ideas: keyword matching, checking sections, parsing contact details.

**Our project is NOT an ATS and does not copy any real ATS.** Our score is a *semantic similarity score*: a number showing how close the *meaning* of the resume text is to the *meaning* of the job-description text. It is not a "shortlisting chance".

## 3. What problem does it solve?

Students often send the same resume to every job. They do not know:

- whether the resume talks about what the job asks for,
- which required skills are not visible in the resume,
- whether basic sections (education, projects, contact) are present.

## 4. Objective

Build a simple web application that, for one resume and one job description, shows a similarity score, matching skills, skills not detected, a section check and practical suggestions - using only free tools.

## 5. Proposed solution

1. The user uploads a PDF resume and pastes a job description.
2. The server validates the input.
3. PyMuPDF extracts the resume text.
4. A pretrained AI model converts both texts into numbers (embeddings); cosine similarity compares them.
5. A skill dictionary + regular expressions find skills in both texts and compare them.
6. Rules check sections and generate suggestions.
7. The page shows the results.

## 6. Main features

Upload PDF - paste job description - extract text - AI similarity score - matching skills - not-detected skills - section check - suggestions - friendly error messages (wrong file type, corrupted/empty/scanned PDF) - sample data - responsive design.

## 7. Technologies and why

| Technology | Why it is used |
|-----------|----------------|
| Python 3.12 | Simple, popular language for web + AI |
| Flask | Small web framework - easy for beginners; routes are plain functions |
| HTML | Structure of the page (form, sections) |
| CSS | Design: colours, cards, responsive layout |
| Jinja2 | Flask's template language: puts Python data into HTML (`{{ }}`, `{% %}`) |
| PyMuPDF | Fast, free PDF text extraction |
| Sentence Transformers | Library to use pretrained text-embedding models |
| `all-MiniLM-L6-v2` | Small (~90 MB), fast, free model that turns sentences into 384 numbers capturing meaning |
| Cosine similarity | Standard way to compare two embeddings |
| Regular expressions | Find skill names in text as whole words |

## 8. Which parts use AI and which do not?

| Component | Method |
|-----------|--------|
| Similarity score | **AI** (pretrained neural network, no training by us) |
| PDF text extraction | Library, no AI |
| Skill finding | **Rules** (dictionary + regex) |
| Missing-skill list | **Rules** (set comparison) |
| Section check | **Rules** (keywords) |
| Suggestions | **Rules** (if/else). *Not generative AI.* |

## 9. System architecture

```
 Browser (HTML form)
        |  POST: PDF + job description
        v
 Flask app (app.py)
   1. validate file & text
   2. PyMuPDF  -> resume text
   3. SentenceTransformer -> embeddings -> cosine similarity   (AI)
   4. regex + dictionary -> skills   | keyword rules -> sections
   5. rules -> suggestions
        |  result dictionary
        v
 Jinja template (index.html) -> HTML page shown in browser
```

## 10. Data flow

1. User fills the form -> browser sends a `multipart/form-data` POST request.
2. `index()` reads `request.files["resume"]` and `request.form["job_description"]`.
3. The PDF is kept **in memory** (never written to disk).
4. Text -> chunks -> embeddings -> one vector per document -> cosine similarity.
5. Skills/sections/suggestions are computed.
6. A dictionary `result` is passed to `render_template`.
7. The HTML shows the results. Nothing is stored after the response.

## 11. Advantages

- Free, runs on a normal laptop (CPU only), no API key.
- Understands meaning, not just exact words (e.g., "built web services" is close to "REST API development").
- Simple code, easy to explain.
- Privacy friendly: files are not saved.
- Honest explanations of what the score means.

## 12. Limitations

- The score is only a rough guide; it is not calibrated and not an ATS score.
- The embedding model sees limited text at a time; we split long text into chunks and average them, which blurs details.
- Averaging chunk vectors can hide a very strong or very weak part of the resume.
- The skill dictionary is small; unknown skills are ignored; ambiguous words can cause rare false matches (for example the word "excel" used as a verb).
- "Not detected" does not prove the candidate lacks a skill.
- Scanned (image) PDFs are not supported (no OCR).
- Complex layouts (columns, tables) may be extracted in a confusing order.
- English only.
- Suggestions are generic rules, not personalised writing.
- The model may carry biases from its training data; it must not be used to make hiring decisions.

## 13. Possible future improvements

- OCR (e.g., Tesseract) for scanned PDFs.
- A larger or editable skill list, or skill extraction with a trained NER model.
- Semantic skill matching (compare skill names with resume sentences using embeddings).
- DOCX support.
- A generative language model for personalised rewriting (clearly labelled if added).
- Show which resume sentences are closest to each job requirement.
- User accounts and history (with proper security and consent).
- Deployment with a production server and HTTPS.
- A larger test set and a proper evaluation against human judgement.
