"""
Automated tests for the Resume Analyzer.   Run with:   python -m unittest -v

Most tests replace the AI similarity function with a fixed number, so they run
fast and do not need the 90 MB model. One optional test uses the real model:
set the environment variable RUN_MODEL_TEST=1 to enable it (PowerShell:
$env:RUN_MODEL_TEST = "1").
"""

import io
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module

SAMPLE_DIR = Path(__file__).parent / "sample_data"
SAMPLE_RESUME_PDF = (SAMPLE_DIR / "sample_resume.pdf").read_bytes()
SAMPLE_JOB_TEXT = (SAMPLE_DIR / "sample_job_description.txt").read_text(encoding="utf-8")


def make_simple_pdf(text):
    """Build a tiny valid PDF by hand (no extra libraries). Empty text = a page with no text."""
    content = b""
    if text:
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content = f"BT /F1 12 Tf 50 750 Td ({safe}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_start = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n".encode()
    pdf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode()
    return pdf


class RouteTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()

    def post(self, pdf_bytes, filename="resume.pdf", job_description=SAMPLE_JOB_TEXT):
        data = {"job_description": job_description}
        if pdf_bytes is not None:
            data["resume"] = (io.BytesIO(pdf_bytes), filename)
        return self.client.post("/", data=data, content_type="multipart/form-data")

    # 9. Website loading
    def test_home_page_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"AI-Powered Resume Analyzer", response.data)
        self.assertIn(b"Analyze Resume", response.data)

    # 1 + 9. Valid PDF + valid job description, results rendered
    @patch.object(app_module, "calculate_similarity", return_value=0.55)
    def test_valid_pdf_and_job_description(self, _mock):
        response = self.post(SAMPLE_RESUME_PDF)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"55.0%", response.data)
        self.assertIn(b"Moderate semantic overlap", response.data)
        self.assertIn(b"not</strong> an employer", response.data)  # limitation note is shown

    # 2. Missing resume
    def test_missing_resume(self):
        response = self.post(None)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Please choose a resume PDF", response.data)

    # 3. Invalid file type
    def test_invalid_file_type(self):
        response = self.post(b"just some text", filename="resume.txt")
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Only PDF files are supported", response.data)

    def test_text_file_renamed_to_pdf(self):
        response = self.post(b"this is not a pdf at all", filename="fake.pdf")
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"not a valid PDF", response.data)

    # 4. Corrupted PDF (has the PDF header but the rest is garbage)
    def test_corrupted_pdf(self):
        response = self.post(b"%PDF-1.4\n" + b"\x00\x01garbage" * 20)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"could not", response.data.lower())

    # 5. Empty job description
    def test_empty_job_description(self):
        response = self.post(SAMPLE_RESUME_PDF, job_description="   ")
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Please paste a job description", response.data)

    def test_too_long_job_description(self):
        response = self.post(SAMPLE_RESUME_PDF, job_description="python " * 5000)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"too long", response.data)

    # 6. PDF with no extractable text (like a scanned resume)
    def test_pdf_without_text(self):
        response = self.post(make_simple_pdf(""))
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"scanned or image-only", response.data)

    def test_upload_too_large(self):
        big_file = b"%PDF-1.4\n" + b"0" * (app_module.MAX_UPLOAD_MB * 1024 * 1024 + 10)
        response = self.post(big_file)
        self.assertEqual(response.status_code, 413)
        self.assertIn(b"too large", response.data)

    # Security: user text must be escaped in the HTML
    def test_job_description_is_escaped(self):
        response = self.post(SAMPLE_RESUME_PDF, job_description="<script>alert(1)</script>")  # too short -> error page
        self.assertNotIn(b"<script>alert(1)</script>", response.data)
        self.assertIn(b"&lt;script&gt;alert(1)&lt;/script&gt;", response.data)

    # Unexpected errors must not leak details
    @patch.object(app_module, "calculate_similarity", side_effect=RuntimeError("secret internal detail"))
    def test_unexpected_error_is_hidden(self, _mock):
        response = self.post(SAMPLE_RESUME_PDF)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(b"secret internal detail", response.data)
        self.assertIn(b"Something went wrong", response.data)


class ExtractionTests(unittest.TestCase):
    def test_extracts_text_from_sample_pdf(self):
        text = app_module.extract_resume_text(SAMPLE_RESUME_PDF)
        self.assertIn("RAHUL SHARMA", text)
        self.assertIn("scikit-learn", text)
        self.assertIn("Student Management System", text)

    def test_extracts_text_from_handmade_pdf(self):
        text = app_module.extract_resume_text(make_simple_pdf("Hello resume text " * 5))
        self.assertIn("Hello resume text", text)


class SkillTests(unittest.TestCase):
    # 7. Resume with matching skills
    def test_matching_skills(self):
        resume = "I know Python, Flask, HTML and MySQL."
        job = "Required: Python, Flask and SQL knowledge, MySQL."
        _, matching, missing = app_module.compare_skills(resume, job)
        self.assertIn("Python", matching)
        self.assertIn("Flask", matching)
        self.assertIn("MySQL", matching)

    # 8. Resume with missing skills
    def test_missing_skills(self):
        resume = "I know Python and HTML."
        job = "We need Python, Docker and Kubernetes."
        _, matching, missing = app_module.compare_skills(resume, job)
        self.assertEqual(matching, ["Python"])
        self.assertEqual(missing, ["Docker", "Kubernetes"])

    def test_alternative_names_are_not_reported_missing(self):
        resume = "Used sklearn and ML techniques; wrote RESTful services."
        job = "Experience with scikit-learn, machine learning and REST APIs."
        _, matching, missing = app_module.compare_skills(resume, job)
        self.assertEqual(missing, [])
        self.assertIn("scikit-learn", matching)
        self.assertIn("Machine Learning", matching)

    def test_specific_database_counts_as_sql(self):
        _, matching, missing = app_module.compare_skills("Worked with MySQL databases.", "Strong SQL skills required.")
        self.assertEqual(matching, ["SQL"])
        self.assertEqual(missing, [])

    def test_java_does_not_match_javascript(self):
        self.assertEqual(app_module.find_skills("I use JavaScript daily."), ["JavaScript"])

    def test_special_character_skills(self):
        found = app_module.find_skills("Languages: C++, C# and Node.js")
        self.assertIn("C++", found)
        self.assertIn("C#", found)
        self.assertIn("Node.js", found)


class HelperTests(unittest.TestCase):
    def test_sections_and_contact(self):
        text = (SAMPLE_DIR / "sample_resume.txt").read_text(encoding="utf-8")
        sections, has_email, has_phone = app_module.check_resume_sections(text)
        self.assertTrue(sections["Education"])
        self.assertTrue(sections["Projects"])
        self.assertTrue(has_email)
        self.assertTrue(has_phone)

    def test_date_range_is_not_a_phone_number(self):
        _, _, has_phone = app_module.check_resume_sections("B.Tech 2022 - 2026\nProjects\nEducation")
        self.assertFalse(has_phone)

    def test_chunking_keeps_all_words(self):
        words = [f"w{i}" for i in range(500)]
        chunks = app_module.split_into_chunks(" ".join(words))
        self.assertGreater(len(chunks), 1)
        covered = set(" ".join(chunks).split())
        self.assertEqual(covered, set(words))

    def test_score_labels(self):
        self.assertEqual(app_module.describe_score(0.7)[0], "High semantic overlap")
        self.assertEqual(app_module.describe_score(0.5)[0], "Moderate semantic overlap")
        self.assertEqual(app_module.describe_score(0.1)[0], "Low semantic overlap")


@unittest.skipUnless(os.environ.get("RUN_MODEL_TEST") == "1", "set RUN_MODEL_TEST=1 to run the real-model test")
class RealModelTest(unittest.TestCase):
    def test_related_texts_score_higher_than_unrelated(self):
        resume = "Python developer with Flask, REST APIs and MySQL experience."
        related_job = "Looking for a Python backend developer to build Flask REST APIs with SQL databases."
        unrelated_job = "Hiring a pastry chef to bake bread and cakes in a busy bakery kitchen."
        related = app_module.calculate_similarity(resume, related_job)
        unrelated = app_module.calculate_similarity(resume, unrelated_job)
        self.assertGreater(related, unrelated)


if __name__ == "__main__":
    unittest.main()
