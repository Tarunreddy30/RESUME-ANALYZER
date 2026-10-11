# Code Explanation (for beginners)

This document walks through `app.py`, `templates/index.html`, `static/style.css` and `test_app.py`.
Open `app.py` next to this file and read both together.

---

## Part 1 - `app.py`

### 1.1 Imports

```python
import re
import fitz
from flask import Flask, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge
```

| Line | Meaning |
|------|---------|
| `import re` | Python's built-in **regular expression** module, used to search text patterns |
| `import fitz` | PyMuPDF. The package is installed as `PyMuPDF` but imported as `fitz` (historical name) |
| `Flask` | The class that creates the web application |
| `render_template` | Fills an HTML template with data and returns the page |
| `request` | Holds the data sent by the browser (form fields, uploaded file, HTTP method) |
| `RequestEntityTooLarge` | The error Flask raises when an upload is bigger than the allowed size |

`sentence_transformers` is **not** imported at the top. We import it inside functions the first time the model is needed, because importing PyTorch is slow. This keeps the app starting quickly and keeps validation tests independent of the model.

### 1.2 Settings

```python
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MAX_UPLOAD_MB = 5
MAX_PDF_PAGES = 10
...
WORDS_PER_CHUNK = 120
WORDS_OVERLAP = 20
```

Capital-letter names are **constants** (values we do not change while running). Putting limits at the top means you can change them in one place. Why a limit exists is explained in the README.

### 1.3 The skill dictionary

```python
SKILL_DICTIONARY = {
    "Machine Learning": ["machine learning", "machine-learning", "ml"],
    ...
}
```

A Python **dictionary** maps a key to a value. Here: official skill name -> list of alternative names (aliases). If a resume says "sklearn", it still counts as "scikit-learn". This is how we avoid calling a skill "missing" just because it was written differently. Specific databases (MySQL, PostgreSQL...) also count as "SQL".

`SECTION_KEYWORDS` works the same way: section name -> words that appear in its heading.

### 1.4 Creating the Flask app

```python
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
```

- `Flask(__name__)` creates the application. `__name__` tells Flask where the project folder is, so it finds `templates/` and `static/`.
- `MAX_CONTENT_LENGTH` is a Flask setting (in bytes). Larger requests are rejected automatically with HTTP error 413. 5 x 1024 x 1024 = 5 MB.

### 1.5 `ModelLoadError` and `get_model()`

```python
class ModelLoadError(Exception): ...
_model = None

def get_model():
    global _model
    if _model is None:
        ...
            _model = SentenceTransformer(MODEL_NAME)
    return _model
```

- **Purpose:** give the AI model to whoever needs it, loading it only once.
- **Input:** none. **Output:** the loaded `SentenceTransformer` object.
- **How:** `_model` starts as `None`. The first call loads the model (download on first ever use, then from the local cache folder), saves it in `_model`, and returns it. Later calls skip loading. This is called *lazy loading + caching*. `global` lets the function change the module-level variable.
- If loading fails (for example no internet on first run), we raise our own `ModelLoadError` with a friendly message. The real error is written to the terminal with `app.logger.exception`.

### 1.6 `validate_uploaded_file(uploaded_file)`

- **Purpose:** make sure the upload is a real, non-empty PDF.
- **Input:** a Flask/Werkzeug `FileStorage` object (or `None`). **Output:** the file contents as `bytes`.
- **How:** it checks, in order: a file was chosen; the name ends with `.pdf`; the file is not empty; the first bytes are `%PDF-`. The last check matters because anyone can rename `virus.exe` to `resume.pdf`; real PDFs always start with `%PDF-`.
- On any problem it does `raise ValueError("friendly message")`. The route catches it and shows the message.
- `uploaded_file.read()` reads the file into memory. We never call `.save()`, so **nothing is stored on disk**, and we never execute the content - we only read text from it.

### 1.7 `validate_job_description(job_description)`

- Checks empty / too short (< 30 characters) / too long (> 15,000 characters). Too long text is **rejected** with a message instead of being silently cut.

### 1.8 `clean_text(text)`

- **Purpose:** tidy the extracted text. **Input/Output:** string -> string.
- `re.sub(pattern, replacement, text)` replaces matches. `[ \t]+` = "one or more spaces/tabs" -> one space. `\n\s*\n+` = "line break, optional spaces, more line breaks" -> a single line break.
- Example: `"Skills\n\n\nPython,   Flask"` -> `"Skills\nPython, Flask"`.

### 1.9 `extract_resume_text(pdf_bytes)`

- **Purpose:** get text from the PDF. **Input:** bytes. **Output:** string (or `ValueError`).
- **How:**
  1. `fitz.open(stream=pdf_bytes, filetype="pdf")` opens the PDF from memory. Failure -> "may be corrupted".
  2. `document.needs_pass` -> password-protected PDFs are rejected.
  3. `document.page_count > MAX_PDF_PAGES` -> too long.
  4. `[page.get_text() for page in document]` is a **list comprehension**: it collects the text of every page.
  5. `finally: document.close()` always runs, so the file is released even after an error.
  6. After cleaning, empty text means a **scanned/image PDF** (no text layer; we do not do OCR) -> friendly message.
- **Limitation:** PyMuPDF reads the text layer in the order stored in the PDF. Multi-column resumes or tables may come out in a mixed order.

### 1.10 Skill identification

```python
def build_alias_pattern(alias):
    return re.compile(r"(?<![A-Za-z0-9+#.])" + re.escape(alias) + r"(?![A-Za-z0-9+#])", re.IGNORECASE)
```

- Goal: find the alias as a **whole word**. A simple `"java" in text` would wrongly match "javascript".
- `(?<![...])` is a *negative lookbehind*: "the character before must NOT be a letter/digit/+/#/.". `(?![...])` is a *negative lookahead*: "the character after must NOT be a letter/digit/+/#".
- `re.escape` makes special characters safe (the `+` in `c++`, the `.` in `node.js`).
- `re.IGNORECASE` ignores capital letters.
- `SKILL_PATTERNS` pre-compiles all patterns once at start-up (faster than compiling for every request).

```python
def find_skills(text):
    found = []
    for skill, patterns in SKILL_PATTERNS.items():
        if any(pattern.search(text) for pattern in patterns):
            found.append(skill)
    return found
```

- **Input:** text. **Output:** list of official skill names found.
- `any(...)` is `True` if at least one alias matches.
- Example: `find_skills("I use sklearn and JavaScript")` -> `["JavaScript", "scikit-learn"]` (order follows the dictionary).

```python
def compare_skills(resume_text, job_description):
```

- Finds the job's skills, then splits them into **matching** (also in resume) and **missing** (not detected in resume). We call them "not detected" in the page, because the resume may express the skill in a way our dictionary does not know.
- `set(...)` makes the membership test (`skill in resume_skills`) fast.

### 1.11 `check_resume_sections(resume_text)`

- Looks only at **short lines** (<= 40 characters) because headings are short. This avoids treating the sentence "I completed my education at..." as a heading.
- `any(keyword in line for line in short_lines for keyword in keywords)` -> `True` if any heading contains a keyword.
- Email: regex `[\w.+-]+@[\w-]+\.[\w.-]+`. Phone: finds digit runs and accepts them only if they contain 10-13 digits (so "2022 - 2026" is not a phone number).
- **Output:** `(sections_dict, has_email, has_phone)`.

### 1.12 `split_into_chunks(text, ...)`

- **Why:** the model reads only about 256 word-pieces; extra text would be **silently ignored** by the model. So we cut the text into pieces of 120 words, each overlapping the previous by 20 words, and encode every piece.
- Example with chunk size 5 and overlap 2 on words `a b c d e f g h`: chunks = `a b c d e`, `d e f g h`.
- The loop stops once a chunk reaches the end of the text.

### 1.13 `calculate_similarity(resume_text, job_description)` - the AI part

```python
model = get_model()
resume_embeddings = model.encode(split_into_chunks(resume_text), convert_to_tensor=True)
job_embeddings    = model.encode(split_into_chunks(job_description), convert_to_tensor=True)
resume_vector = resume_embeddings.mean(dim=0)
job_vector    = job_embeddings.mean(dim=0)
cosine_score = util.cos_sim(resume_vector, job_vector).item()
return max(0.0, min(1.0, cosine_score))
```

- **Embedding:** a list of 384 numbers that represents the meaning of a text. Similar meanings -> similar numbers. The model was pretrained by others on huge amounts of text; we only *use* it (no training).
- `model.encode(list_of_texts, convert_to_tensor=True)` returns one embedding per chunk (a table with one row per chunk).
- `.mean(dim=0)` averages the rows into **one vector** for the whole document.
- **Cosine similarity** measures the angle between two vectors: 1 = same direction (very similar), 0 = unrelated, negative = opposite. Formula: `cos = (A . B) / (|A| x |B|)`.
- `.item()` converts a one-number tensor into a normal Python float.
- `max(0.0, min(1.0, score))` forces the value into the range 0-1 (rare negative values become 0).
- Real-world feel: texts on the same topic usually score clearly higher than unrelated texts, but there is no universal "good" value.

### 1.14 `describe_score(score)`

Turns the number into a label: >= 0.60 high, >= 0.40 moderate, otherwise low. These cut-offs are **rough teaching guides** that we chose; they are not scientifically calibrated.

### 1.15 `generate_suggestions(...)`

- **Purpose:** produce a list of tips. **Output:** list of strings.
- **How:** a series of `if` rules: missing Education/Skills/Projects heading; no summary; no email/phone; skills not detected (shows up to 8: `missing[:8]` is *slicing*); resume shorter than 150 or longer than 1000 words; fewer than 5 numbers (suggest measurable results); low similarity. If no rule fires, a positive message is returned.
- **This is not generative AI.** The messages are written in advance by the programmer.

### 1.16 `analyze_resume(...)`

Calls all steps and returns one dictionary (`score_percent`, `score_label`, `matching_skills`, ...). Collecting everything into one dictionary makes the template simple: `result.score_percent`.

### 1.17 The route `index()`

```python
@app.route("/", methods=["GET", "POST"])
def index():
```

- `@app.route("/")` is a **decorator**: it tells Flask "run this function when the browser asks for `/`".
- **GET** = the browser just opens the page -> we show the empty form.
- **POST** = the user submitted the form -> we process it.
- `request.form.get("job_description", "")` reads a text field (empty string if missing). `request.files.get("resume")` reads the uploaded file.
- The `try/except` block:
  - `except (ValueError, ModelLoadError)`: *expected* problems; messages are safe for users.
  - `except Exception`: any *unexpected* bug; details go to the terminal log only, and the user sees a generic message. This prevents leaking internal information.
- `render_template("index.html", result=..., error=..., job_description=...)` sends data to the template. Returning a tuple `(page, 400)` sets the HTTP status code.

### 1.18 Error handlers

`@app.errorhandler(RequestEntityTooLarge)` shows a friendly page for uploads > 5 MB. `@app.errorhandler(500)` shows a friendly page instead of a stack trace.

### 1.19 Starting the server

```python
if __name__ == "__main__":
    get_model()          # preload (shows download progress)
    app.run(host="127.0.0.1", port=5000, debug=False)
```

- `if __name__ == "__main__":` runs only when you type `python app.py` (not when the file is imported by tests).
- `127.0.0.1` = "this computer only".
- `debug=False`: debug mode shows an interactive console that can run code; it must never be enabled on a public server.

---

## Part 2 - `templates/index.html`

### 2.1 Jinja basics

| Syntax | Meaning |
|--------|---------|
| `{{ value }}` | print a value (**auto-escaped**: `<script>` becomes harmless text, protecting against XSS) |
| `{% if x %} ... {% endif %}` | condition |
| `{% for item in list %} ... {% endfor %}` | loop |
| `{# comment #}` | comment |
| `{{ list\|length }}` | filter (here: number of items) |
| `url_for('static', filename='style.css')` | builds the correct URL of a static file |

We never use `|safe`, so user text can never become real HTML.

### 2.2 The form

```html
<form method="post" action="/" enctype="multipart/form-data">
  <input type="file" name="resume" accept=".pdf,application/pdf" required>
  <textarea name="job_description" required>{{ job_description }}</textarea>
  <button type="submit">Analyze Resume</button>
</form>
```

- `method="post"`: send data in the request body (needed for files).
- `action="/"`: where to send it (our `index()` route).
- `enctype="multipart/form-data"`: **required** for file uploads; without it the file is not sent.
- `name="resume"`: the key we read in Python (`request.files["resume"]`). `name="job_description"` -> `request.form["job_description"]`.
- `accept=".pdf"`: the file picker prefers PDFs. This is only a convenience; the **server validates again** because users can bypass browser checks.
- `required`: browser blocks empty submission (again, only a convenience).
- `{{ job_description }}` inside the textarea keeps the user's text after an error.

### 2.3 Showing results

`{% if result %}` shows the result cards only after a successful analysis. Inside, loops print skills (`{% for skill in result.matching_skills %}`), sections (`result.sections.items()` gives name/True-False pairs) and suggestions.

`style="width: {{ result.score_percent }}%"` sets the width of the coloured bar to the score. The value is a number we calculated, so it is safe.

### 2.4 JavaScript

Four lines disable the button and show "Analyzing..." after submit, because the first analysis can take a few seconds. The app works without JavaScript.

---

## Part 3 - `static/style.css`

- `:root { --primary: #3b5bdb; }` defines **CSS variables**; `var(--primary)` uses them. Change one line to re-theme the site.
- `* { box-sizing: border-box; }` makes widths include padding, so layouts do not overflow.
- `.container { max-width: 860px; margin: 0 auto; }` centres the content and limits width.
- `.card` = white box with border, rounded corners (`border-radius`) and soft shadow.
- `display: flex; flex-wrap: wrap; gap: 8px;` makes skill "tags" flow onto new lines.
- `.checklist { display: grid; grid-template-columns: repeat(2, 1fr); }` = two columns.
- `@media (max-width: 600px) { ... }` is a **media query**: these rules apply only on small (mobile) screens - one column, full-width button. The `<meta name="viewport">` tag in the HTML head is needed for this to work on phones.

---

## Part 4 - `test_app.py`

- `unittest` is Python's built-in testing library. Each method starting with `test_` is a test.
- `app.test_client()` pretends to be a browser: `client.post("/", data=...)` sends a fake form submission without starting the server.
- `@patch.object(app_module, "calculate_similarity", return_value=0.55)` temporarily replaces the AI function with a fixed value so the test is fast and does not need the model. This is called **mocking**.
- `make_simple_pdf()` builds a tiny valid PDF by hand, so we can test a PDF with and without text.
- `RealModelTest` runs only if you set `RUN_MODEL_TEST=1`; it checks that a related job description scores higher than an unrelated one.

---

## Part 5 - Mini examples to try in a Python shell

```python
>>> import re
>>> re.search(r"\bpython\b", "I like Python", re.IGNORECASE) is not None
True
>>> words = "a b c d e f g h".split()
>>> words[0:5]
['a', 'b', 'c', 'd', 'e']
>>> {"Python": ["python", "python3"]}["Python"]
['python', 'python3']
```

Cosine similarity by hand (2 numbers instead of 384):

```
A = (1, 0)    B = (1, 1)
A.B = 1*1 + 0*1 = 1
|A| = 1       |B| = sqrt(2) = 1.414
cos = 1 / 1.414 = 0.707
```
