# AI-Powered Resume Analyzer and Job Matching System

**A B.Tech Project Report**

Student name: ____________________  Roll number: ____________________
Department: ____________________  College: ____________________
Guide: ____________________  Academic year: ____________________

*(Fill in the blanks above. Add your college's cover page and certificate pages as required.)*

---

## Abstract

Job applicants often use a single resume for many job postings without knowing how closely it reflects the requirements of a particular role. This project presents a simple web application, built with Python and Flask, that compares a PDF resume with a job description. The text of the resume is extracted using PyMuPDF. A pretrained Sentence Transformers model (`all-MiniLM-L6-v2`) converts the resume and the job description into embeddings, and cosine similarity between them is reported as a *semantic similarity score*. Skills are identified separately with a predefined skill dictionary and regular expressions, giving lists of matching skills and skills not detected in the resume. Basic section checks and rule-based suggestions complete the feedback. The system uses only free, open-source components and does not store uploaded files. The similarity score is not an employer ATS score and is not a prediction of hiring success. The report describes the design, implementation, test cases and limitations of the system. No accuracy or performance claims are made, because the system has not been evaluated against human recruiters.

## 1. Introduction

Recruiters and Applicant Tracking Systems (ATS) screen large numbers of resumes. Candidates, especially freshers, rarely receive feedback on how well their resume fits a role. Recent natural-language-processing models can represent the meaning of text as numeric vectors, making it possible to measure the similarity between two documents even when they use different words. This project applies such a pretrained model in a small, understandable application for educational purposes.

## 2. Problem Statement

To design and implement a free, easy-to-run web application that accepts a resume in PDF format and a job description, and provides (a) a semantic similarity measure, (b) a comparison of skills, (c) a check of basic resume sections, and (d) practical improvement suggestions, while being clear about the limits of each result.

## 3. Objectives

1. Extract text from text-based PDF resumes.
2. Measure semantic similarity between resume and job description using a pretrained model.
3. Identify matching skills and skills not detected, considering alternative skill names.
4. Check for basic resume sections and contact details.
5. Generate rule-based suggestions.
6. Present results on a clean, responsive website with clear error handling.
7. Use only free tools, with no model training and no stored user files.

## 4. Existing Approach and Its Limitations

- **Manual review:** slow, subjective, and feedback is rarely given to candidates.
- **Simple keyword matching:** counts exact words, so synonyms and differently worded descriptions are missed ("built web services" vs "REST API development").
- **Commercial resume tools:** often paid, closed-source, and their scoring methods are not transparent.
- **Real ATS products:** internal rules are not public, so students cannot reproduce or verify them.

## 5. Proposed System

A Flask application that combines:

- **AI component:** pretrained sentence embeddings + cosine similarity for the similarity score.
- **Rule-based components:** PDF extraction, skill dictionary with aliases and regular expressions, section checks, suggestion rules.

The system is intentionally simple (one Python file for logic, one template, one stylesheet) so that it can be understood and explained completely.

## 6. Requirements

**Software:** Python 3.12; Flask; PyMuPDF; sentence-transformers with PyTorch and transformers (versions pinned in `requirements.txt`); a web browser; Windows with VS Code was used as the development environment target.

**Hardware:** an ordinary laptop (CPU only), about 2-3 GB of free disk space, internet access for the first run to install packages and download the model (about 90 MB).

**Functional requirements:** upload PDF; enter job description; show similarity score, matching skills, skills not detected, section check and suggestions; show understandable errors for invalid input.

**Non-functional requirements:** simplicity, responsive design, privacy (no permanent storage of uploads), no paid services, clear explanation of limitations.

## 7. System Architecture

```
Browser form --POST--> Flask route "/"
                          |
          validation -> PyMuPDF text extraction
                          |
      +-------------------+--------------------+
      |                                        |
 Sentence Transformer (AI)          Rules: skills, sections, suggestions
 embeddings + cosine similarity
      |                                        |
      +-------------------+--------------------+
                          |
                Jinja template -> HTML results
```

## 8. Module Descriptions

| Module / function | Description |
|-------------------|-------------|
| `validate_uploaded_file` | Checks presence, `.pdf` extension, non-empty content, `%PDF-` header |
| `validate_job_description` | Checks emptiness and length limits |
| `extract_resume_text` | Opens PDF in memory with PyMuPDF; rejects corrupted, password-protected, too long and text-less (scanned) PDFs |
| `clean_text` | Normalises whitespace |
| `find_skills` / `compare_skills` | Dictionary + regex skill detection and comparison |
| `check_resume_sections` | Heading-keyword checks, email and phone detection |
| `split_into_chunks` | Splits long text into overlapping 120-word chunks |
| `get_model` | Loads the pretrained model once and reuses it |
| `calculate_similarity` | Encodes chunks, averages embeddings, computes cosine similarity |
| `generate_suggestions` | Rule-based advice |
| `index` route | Handles GET/POST and renders the page |
| `index.html`, `style.css` | User interface |

## 9. Implementation Methodology

1. **Input handling:** the file is read into memory; it is never saved or executed.
2. **Text extraction:** PyMuPDF reads each page's text layer; text is cleaned.
3. **Embeddings:** each text is divided into overlapping chunks of 120 words (20-word overlap) so that the model's limited input length does not cause silent loss of content. Each chunk is encoded by `all-MiniLM-L6-v2`; chunk embeddings are averaged into one vector per document.
4. **Similarity:** cosine similarity between the two vectors, limited to 0-1 and shown as a percentage. Labels (>=60% high, >=40% moderate, otherwise low) are informal guides chosen by the author and are not calibrated.
5. **Skills:** each dictionary skill has alternative names; whole-word regular expressions search both texts. Skills found in the job description but not in the resume are shown as "not detected".
6. **Suggestions:** if/else rules over the analysis results. No generative model is used.
7. **Presentation:** Jinja2 renders the results; output is auto-escaped.
8. **Security measures:** server-side validation, size and page limits, in-memory processing, debug mode off, generic error messages, no secrets.

## 10. Testing and Test Cases

Automated tests are in `test_app.py` (run `python -m unittest -v`). The table lists the planned test cases. **Record your own results in the last column after running them on your machine.**

| No. | Test case | Expected result | Your result (Pass/Fail) |
|-----|-----------|-----------------|--------------------------|
| 1 | Valid PDF + valid job description | Results page with score, skills, suggestions | |
| 2 | No file selected | Message asking to choose a PDF | |
| 3 | `.txt` file uploaded | "Only PDF files are supported" | |
| 4 | Text file renamed to `.pdf` | "not a valid PDF" | |
| 5 | Corrupted PDF | "could not be opened / read" message | |
| 6 | Empty job description | "Please paste a job description" | |
| 7 | PDF with no extractable text | "scanned or image-only" message | |
| 8 | File larger than 5 MB | "too large" message (HTTP 413) | |
| 9 | Resume containing job's skills | Skills listed as matching | |
| 10 | Resume lacking job's skills | Skills listed as not detected | |
| 11 | Alternative names (e.g., sklearn) | Skill not reported as missing | |
| 12 | `java` vs `javascript` | Java not matched inside JavaScript | |
| 13 | Script tag typed in job description | Shown as harmless text | |
| 14 | Unexpected internal error | Generic message, no technical details | |
| 15 | Home page loads on desktop and mobile width | Layout adapts | |
| 16 | Fresh install from `requirements.txt` on Python 3.12 | Installs and the app starts | |
| 17 | Real model: related vs unrelated job description | Related text scores higher (`RUN_MODEL_TEST=1`) | |

*Note on evidence:* test cases 1-15 (except real-model, installation and visual checks) are automated in `test_app.py`. Test 16 and 17 and the visual check in 15 must be performed by you on a machine with internet access. No results are claimed in this report.

## 11. Limitations

- The similarity score is not calibrated, not an ATS score, and not a probability of selection.
- Averaging chunk embeddings can hide details.
- The skill dictionary is small; unknown skills are ignored; ambiguous words may cause false matches.
- "Not detected" does not prove a skill is absent.
- No OCR: scanned PDFs are not supported.
- Complex layouts may be extracted in a confusing order.
- English-only; the model may reflect biases from its training data.
- The system has not been evaluated against human recruiters or real ATS decisions.

## 12. Future Scope

OCR for scanned resumes; DOCX support; larger or user-editable skill lists; semantic skill matching; highlighting the resume sentences closest to each requirement; optional generative suggestions (clearly labelled); formal evaluation with human raters; production deployment with HTTPS and a production web server.

## 13. Conclusion

The project demonstrates how a pretrained NLP model can be combined with ordinary Python rules to give useful, explainable feedback on a resume, using only free tools and a small, understandable code base. The results should be treated as guidance, not as a hiring decision, and further evaluation would be needed before drawing conclusions about accuracy.

## 14. References

1. Reimers, N. and Gurevych, I. (2019). *Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks.* Proceedings of EMNLP-IJCNLP 2019.
2. Wang, W. et al. (2020). *MiniLM: Deep Self-Attention Distillation for Task-Agnostic Compression of Pre-Trained Transformers.* NeurIPS 2020.
3. Sentence-Transformers documentation: https://www.sbert.net
4. Model card, `sentence-transformers/all-MiniLM-L6-v2`: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
5. Flask documentation: https://flask.palletsprojects.com
6. PyMuPDF documentation: https://pymupdf.readthedocs.io
7. Python `re` module documentation: https://docs.python.org/3/library/re.html
