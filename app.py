"""
AI-Powered Resume Analyzer - a simple Flask web application.

What uses AI:
    - calculate_similarity(): a pretrained Sentence Transformers model
      (all-MiniLM-L6-v2) turns text into embeddings, and cosine similarity
      compares them.

What uses ordinary Python rules (no AI):
    - extract_resume_text()  : PyMuPDF reads the text layer of the PDF
    - find_skills()          : regular expressions + a predefined skill dictionary
    - check_resume_sections(): keyword rules
    - generate_suggestions() : if/else rules based on the analysis
"""

import re

import fitz  # PyMuPDF (the package name is "PyMuPDF", the import name is "fitz")
from flask import Flask, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge

# NOTE: sentence_transformers (and torch) are slow to import, so we import them
# only when the model is first needed. This keeps validation fast and lets the
# unit tests run without downloading the AI model.

# ---------------------------------------------------------------------------
# Settings (change these numbers if you want different limits)
# ---------------------------------------------------------------------------
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

MAX_UPLOAD_MB = 5                 # maximum size of the uploaded PDF
MAX_PDF_PAGES = 10                # resumes longer than this are rejected
MIN_RESUME_CHARS = 50             # fewer characters than this = "no usable text"
MIN_JOB_DESCRIPTION_CHARS = 30    # too short to compare meaningfully
MAX_JOB_DESCRIPTION_CHARS = 15000 # about 2,500 words

# The model can read only about 256 word-pieces at once, so long texts are cut
# into small overlapping chunks. Nothing is thrown away: every chunk is encoded.
WORDS_PER_CHUNK = 120
WORDS_OVERLAP = 20

# ---------------------------------------------------------------------------
# Skill dictionary: "official name" -> list of other names people write.
# Matching uses these aliases, so "ML" or "machine-learning" both count as
# "Machine Learning". Add your own skills here.
# ---------------------------------------------------------------------------
SKILL_DICTIONARY = {
    # Programming languages
    "Python": ["python", "python3"],
    "Java": ["java", "core java"],
    "JavaScript": ["javascript", "ecmascript", "es6"],
    "TypeScript": ["typescript"],
    "C++": ["c++", "cpp"],
    "C#": ["c#", "csharp"],
    "C": ["c programming", "c language"],
    "Go": ["golang"],
    "R": ["r programming", "r language"],
    "PHP": ["php"],
    "Kotlin": ["kotlin"],
    "Swift": ["swift"],
    # Web
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "React": ["react", "react.js", "reactjs"],
    "Angular": ["angular", "angularjs"],
    "Node.js": ["node.js", "nodejs", "node js"],
    "Flask": ["flask"],
    "Django": ["django"],
    "FastAPI": ["fastapi"],
    "Spring Boot": ["spring boot", "springboot", "spring framework"],
    "Bootstrap": ["bootstrap"],
    "REST API": ["rest api", "rest apis", "restful api", "restful apis", "restful", "rest services", "web services"],
    "JSON": ["json"],
    # Databases
    "SQL": ["sql", "structured query language", "mysql", "postgresql", "postgres", "sqlite", "sql server", "t-sql", "pl/sql"],
    "MySQL": ["mysql"],
    "PostgreSQL": ["postgresql", "postgres"],
    "MongoDB": ["mongodb", "mongo db"],
    "SQLite": ["sqlite"],
    "Oracle": ["oracle database", "oracle db", "pl/sql"],
    # Data science and AI
    "Machine Learning": ["machine learning", "machine-learning", "ml"],
    "Deep Learning": ["deep learning", "deep-learning", "neural network", "neural networks"],
    "NLP": ["nlp", "natural language processing"],
    "Computer Vision": ["computer vision", "opencv"],
    "Data Analysis": ["data analysis", "data analytics", "data analyst"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "scikit-learn": ["scikit-learn", "scikit learn", "sklearn"],
    "TensorFlow": ["tensorflow"],
    "PyTorch": ["pytorch"],
    "Matplotlib": ["matplotlib"],
    "Power BI": ["power bi", "powerbi"],
    "Tableau": ["tableau"],
    "Excel": ["excel", "ms excel", "microsoft excel"],
    # Tools, cloud and DevOps
    "Git": ["git"],
    "GitHub": ["github"],
    "Docker": ["docker", "containerization", "containers"],
    "Kubernetes": ["kubernetes", "k8s"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure", "microsoft azure"],
    "Google Cloud": ["google cloud", "gcp"],
    "Linux": ["linux", "unix", "ubuntu"],
    "CI/CD": ["ci/cd", "ci cd", "continuous integration", "continuous delivery", "jenkins", "github actions"],
    "Postman": ["postman"],
    "Jira": ["jira"],
    # Concepts and practices
    "Data Structures": ["data structures", "dsa"],
    "Algorithms": ["algorithms", "algorithm design"],
    "OOP": ["oop", "oops", "object oriented", "object-oriented"],
    "Unit Testing": ["unit testing", "unit tests", "unit test", "pytest", "unittest", "junit", "test cases"],
    "Agile": ["agile", "scrum", "kanban"],
    "Problem Solving": ["problem solving", "problem-solving"],
    "Communication": ["communication skills", "communication", "good communicator"],
    "Teamwork": ["teamwork", "team player", "collaboration", "collaborative"],
}

# Section name -> words that usually appear in its heading.
SECTION_KEYWORDS = {
    "Education": ["education", "academic", "qualification"],
    "Skills": ["skills", "technical skills", "technologies"],
    "Projects": ["projects", "project work"],
    "Experience / Internship": ["experience", "internship", "work history", "employment"],
    "Summary / Objective": ["summary", "objective", "profile", "about me"],
    "Certifications": ["certification", "certifications", "courses", "achievements"],
}

# ---------------------------------------------------------------------------
# Flask application
# ---------------------------------------------------------------------------
app = Flask(__name__)
# Flask rejects bigger uploads automatically (we show a friendly message below).
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


class ModelLoadError(Exception):
    """Raised when the AI model cannot be loaded (for example: no internet on first run)."""


# The model is stored here after the first load, so it is never loaded twice.
_model = None


def get_model():
    """Return the Sentence Transformers model, loading it only the first time."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer

            # Downloads on first use, then loads from the local cache.
            _model = SentenceTransformer(MODEL_NAME)
        except Exception as error:
            app.logger.exception("Could not load the AI model")
            raise ModelLoadError(
                "The AI model could not be loaded. On the first run an internet "
                "connection is needed to download it (about 90 MB). Please check "
                "your connection and try again."
            ) from error
    return _model


# ---------------------------------------------------------------------------
# Step 1: validate the upload and extract text (ordinary Python rules)
# ---------------------------------------------------------------------------
def validate_uploaded_file(uploaded_file):
    """Check the uploaded file and return its bytes. Raises ValueError with a friendly message."""
    if uploaded_file is None or uploaded_file.filename == "":
        raise ValueError("Please choose a resume PDF to upload.")

    if not uploaded_file.filename.lower().endswith(".pdf"):
        raise ValueError("Only PDF files are supported. Please upload a .pdf resume.")

    pdf_bytes = uploaded_file.read()  # we keep the file in memory only - never saved to disk

    if len(pdf_bytes) == 0:
        raise ValueError("The uploaded file is empty.")

    # Real PDFs start with the bytes "%PDF-". This catches renamed files (e.g. a .txt renamed to .pdf).
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("This file is not a valid PDF. Please upload a real PDF resume.")

    return pdf_bytes


def validate_job_description(job_description):
    """Check the job description text. Raises ValueError with a friendly message."""
    if not job_description:
        raise ValueError("Please paste a job description.")
    if len(job_description) < MIN_JOB_DESCRIPTION_CHARS:
        raise ValueError("The job description is too short. Please paste the full description.")
    if len(job_description) > MAX_JOB_DESCRIPTION_CHARS:
        raise ValueError(
            f"The job description is too long (limit: {MAX_JOB_DESCRIPTION_CHARS:,} characters). "
            "Please paste only the main responsibilities and requirements."
        )


def clean_text(text):
    """Tidy extracted text: remove odd spaces and extra blank lines (keeps line breaks)."""
    text = text.replace("\u00a0", " ")           # non-breaking space -> normal space
    text = re.sub(r"[ \t]+", " ", text)          # many spaces/tabs -> one space
    text = re.sub(r"\n\s*\n+", "\n", text)       # many blank lines -> one line break
    return text.strip()


def extract_resume_text(pdf_bytes):
    """Read all text from a PDF (given as bytes) using PyMuPDF. Raises ValueError for bad PDFs."""
    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as error:
        raise ValueError("This PDF could not be opened. It may be corrupted.") from error

    try:
        if document.needs_pass:
            raise ValueError("This PDF is password protected. Please upload an unprotected copy.")

        if document.page_count > MAX_PDF_PAGES:
            raise ValueError(
                f"This PDF has {document.page_count} pages. Resumes longer than "
                f"{MAX_PDF_PAGES} pages are not supported."
            )

        page_texts = [page.get_text() for page in document]
    except ValueError:
        raise
    except Exception as error:
        raise ValueError("This PDF could not be read. It may be corrupted.") from error
    finally:
        document.close()

    text = clean_text("\n".join(page_texts))

    if len(text) == 0:
        raise ValueError(
            "No text could be extracted. This looks like a scanned or image-only PDF. "
            "Please upload a PDF with selectable text (for example, exported from Word or Google Docs)."
        )
    if len(text) < MIN_RESUME_CHARS:
        raise ValueError("Very little text was found in this PDF, so it cannot be analysed.")

    return text


# ---------------------------------------------------------------------------
# Step 2: skills, sections (ordinary Python rules - not AI)
# ---------------------------------------------------------------------------
def build_alias_pattern(alias):
    """Make a regex that matches the alias as a whole word (so 'java' does not match 'javascript')."""
    # (?<![A-Za-z0-9+#.]) = the previous character must not be a letter/digit/+/#/.
    # (?![A-Za-z0-9+#])   = the next character must not be a letter/digit/+/#
    return re.compile(r"(?<![A-Za-z0-9+#.])" + re.escape(alias) + r"(?![A-Za-z0-9+#])", re.IGNORECASE)


# Compile every pattern once when the program starts (faster than compiling per request).
SKILL_PATTERNS = {
    skill: [build_alias_pattern(alias) for alias in aliases]
    for skill, aliases in SKILL_DICTIONARY.items()
}


def find_skills(text):
    """Return the list of dictionary skills found in text (any alias counts)."""
    found = []
    for skill, patterns in SKILL_PATTERNS.items():
        if any(pattern.search(text) for pattern in patterns):
            found.append(skill)
    return found


def compare_skills(resume_text, job_description):
    """Split the job's skills into 'found in resume' and 'not detected in resume'."""
    job_skills = find_skills(job_description)
    resume_skills = set(find_skills(resume_text))
    matching = [skill for skill in job_skills if skill in resume_skills]
    missing = [skill for skill in job_skills if skill not in resume_skills]
    return job_skills, matching, missing


def check_resume_sections(resume_text):
    """Check which basic sections exist and whether contact details are present."""
    # A heading is normally a short line, so we only look at short lines.
    short_lines = [line.strip().lower() for line in resume_text.splitlines() if 0 < len(line.strip()) <= 40]

    sections = {}
    for section_name, keywords in SECTION_KEYWORDS.items():
        sections[section_name] = any(keyword in line for line in short_lines for keyword in keywords)

    has_email = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", resume_text) is not None
    # A phone number = a run of digits/spaces/dashes that contains 10 to 13 digits.
    # (Counting digits avoids mistaking a date range like "2022 - 2026" for a phone number.)
    has_phone = False
    for candidate in re.findall(r"\+?\d[\d\s().-]{8,}\d", resume_text):
        if 10 <= len(re.sub(r"\D", "", candidate)) <= 13:
            has_phone = True
            break
    return sections, has_email, has_phone


# ---------------------------------------------------------------------------
# Step 3: AI semantic similarity
# ---------------------------------------------------------------------------
def split_into_chunks(text, words_per_chunk=WORDS_PER_CHUNK, overlap=WORDS_OVERLAP):
    """Cut text into overlapping pieces of about 120 words so the model can read all of it."""
    words = text.split()
    step = words_per_chunk - overlap
    chunks = []
    for start in range(0, len(words), step):
        chunks.append(" ".join(words[start:start + words_per_chunk]))
        if start + words_per_chunk >= len(words):
            break
    return chunks


def calculate_similarity(resume_text, job_description):
    """Return a semantic similarity between 0.0 and 1.0 using AI embeddings + cosine similarity."""
    from sentence_transformers import util

    model = get_model()

    # Encode every chunk, then average the chunk embeddings into ONE vector per document.
    resume_embeddings = model.encode(split_into_chunks(resume_text), convert_to_tensor=True)
    job_embeddings = model.encode(split_into_chunks(job_description), convert_to_tensor=True)
    resume_vector = resume_embeddings.mean(dim=0)
    job_vector = job_embeddings.mean(dim=0)

    cosine_score = util.cos_sim(resume_vector, job_vector).item()
    return max(0.0, min(1.0, cosine_score))  # keep it between 0 and 1


def describe_score(score):
    """Turn the number into a plain-English label. The cut-offs are rough guides, not scientific."""
    if score >= 0.60:
        return "High semantic overlap", "The wording and topics of your resume are quite close to the job description."
    if score >= 0.40:
        return "Moderate semantic overlap", "Your resume shares some topics with the job description, but there is room to tailor it."
    return "Low semantic overlap", "Your resume and the job description talk about quite different things, or use very different wording."


# ---------------------------------------------------------------------------
# Step 4: suggestions (ordinary Python rules - not generative AI)
# ---------------------------------------------------------------------------
def generate_suggestions(resume_text, sections, has_email, has_phone, matching, missing, score):
    """Build a list of practical improvement tips using simple if/else rules."""
    suggestions = []

    for section_name, present in sections.items():
        if not present and section_name in ("Education", "Skills", "Projects"):
            suggestions.append(f"Add a clearly titled '{section_name}' section so readers (and software) can find it quickly.")
    if not sections["Summary / Objective"]:
        suggestions.append("Consider a 2-3 line summary at the top that mentions the role you are applying for.")

    if not has_email:
        suggestions.append("No email address was detected. Add a professional email address near the top.")
    if not has_phone:
        suggestions.append("No phone number was detected. Add a contact number.")

    if missing:
        shown = ", ".join(missing[:8])
        suggestions.append(
            f"The job description mentions skills we could not detect in your resume: {shown}. "
            "If you genuinely have them, add them using the same wording as the job description. "
            "If you do not, consider learning one or two and building a small project."
        )

    word_count = len(resume_text.split())
    if word_count < 150:
        suggestions.append("Your resume is quite short. Add more detail about projects, internships and results.")
    elif word_count > 1000:
        suggestions.append("Your resume is long. For freshers, aim for one page with only the most relevant points.")

    numbers_found = re.findall(r"\d+(?:[.,]\d+)?\s*%?", resume_text)
    if len(numbers_found) < 5:
        suggestions.append("Add measurable results (for example: 'reduced load time by 30%', 'handled 5,000 records').")

    if score < 0.40:
        suggestions.append("Tailor your summary, project descriptions and skills to the language used in this job description.")

    if not suggestions:
        suggestions.append("Good job! No major issues were found by these basic checks. Review your resume once more for spelling and clarity.")
    return suggestions


# ---------------------------------------------------------------------------
# Putting it all together
# ---------------------------------------------------------------------------
def analyze_resume(resume_text, job_description):
    """Run every analysis step and return one dictionary for the HTML template."""
    score = calculate_similarity(resume_text, job_description)
    label, explanation = describe_score(score)
    job_skills, matching, missing = compare_skills(resume_text, job_description)
    sections, has_email, has_phone = check_resume_sections(resume_text)
    suggestions = generate_suggestions(resume_text, sections, has_email, has_phone, matching, missing, score)

    return {
        "score_percent": round(score * 100, 1),
        "score_label": label,
        "score_explanation": explanation,
        "job_skills_count": len(job_skills),
        "matching_skills": matching,
        "missing_skills": missing,
        "sections": sections,
        "has_email": has_email,
        "has_phone": has_phone,
        "suggestions": suggestions,
        "resume_word_count": len(resume_text.split()),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    """GET shows the empty form. POST validates the form, analyses the resume and shows results."""
    if request.method == "GET":
        return render_template("index.html", result=None, error=None, job_description="")

    job_description = request.form.get("job_description", "").strip()
    result = None
    error = None

    try:
        pdf_bytes = validate_uploaded_file(request.files.get("resume"))
        validate_job_description(job_description)
        resume_text = extract_resume_text(pdf_bytes)
        result = analyze_resume(resume_text, job_description)
    except (ValueError, ModelLoadError) as known_error:
        error = str(known_error)  # these messages are written for users
    except Exception:
        app.logger.exception("Unexpected error while analysing the resume")  # details go to the terminal only
        error = "Something went wrong while analysing your resume. Please try again with a different PDF."

    status_code = 200 if error is None else 400
    return render_template("index.html", result=result, error=error, job_description=job_description), status_code


@app.errorhandler(RequestEntityTooLarge)
def file_too_large(_error):
    """Shown when the upload is bigger than MAX_UPLOAD_MB."""
    message = f"The uploaded file is too large. The limit is {MAX_UPLOAD_MB} MB."
    return render_template("index.html", result=None, error=message, job_description=""), 413


@app.errorhandler(500)
def server_error(_error):
    """Friendly page for unexpected errors - no stack trace is shown to the user."""
    message = "An unexpected server error occurred. Please try again."
    return render_template("index.html", result=None, error=message, job_description=""), 500


if __name__ == "__main__":
    # Load the AI model now so the first "Analyze" click is fast.
    try:
        print("Loading AI model (the first run downloads about 90 MB)...")
        get_model()
        print("AI model ready.")
    except ModelLoadError as model_error:
        print(f"WARNING: {model_error}")

    # debug=False is important: debug mode must never be used on a public server.
    # host 127.0.0.1 means only YOUR computer can open the site.
    app.run(host="127.0.0.1", port=5000, debug=False)
