# Interview / Viva Questions and Answers

Answer in your own words. Short, honest answers are better than memorised long ones.

## A. Objective and problem

**1. What is your project about?**
A Flask web app where you upload a resume PDF and paste a job description. It shows an AI-based semantic similarity score, matching skills, skills not detected, a section check and improvement suggestions.

**2. What problem does it solve?**
Students send one generic resume everywhere and do not know whether it reflects what a job asks for. The app gives quick, free feedback.

**3. Is this an ATS?**
No. An ATS is software used by employers and each uses its own rules. My score only measures how similar the meaning of two texts is. It is not a hiring probability.

**4. Why did you choose this project?**
It combines web development, text processing and a real pretrained AI model, and it is useful for placements.

## B. Python and Flask

**5. Why Flask and not Django?**
Flask is small and simple: a route is just a function. For one page and one form, Django would add unnecessary complexity.

**6. What is a route?**
A URL mapped to a Python function with `@app.route`. Mine is `/` with methods GET and POST.

**7. Difference between GET and POST?**
GET requests a page (no data changed). POST sends data in the request body, such as a form with a file. I use GET to show the form and POST to submit it.

**8. How do you read the uploaded file?**
`request.files.get("resume")` gives a file object. I call `.read()` to get bytes and process them in memory.

**9. What is `render_template`?**
It fills an HTML template (Jinja) with Python data and returns the final HTML.

**10. Why `if __name__ == "__main__"`?**
So the server starts only when I run `python app.py`, not when the file is imported (for example by the tests).

## C. HTML and CSS

**11. Why `enctype="multipart/form-data"`?**
Without it the browser does not send the file contents, only the filename.

**12. How is the page responsive?**
Flexible widths (`max-width`, `flex-wrap`), a viewport meta tag and a media query for screens under 600 px.

## D. PDF extraction

**13. How do you extract text?**
PyMuPDF opens the PDF from memory and `page.get_text()` returns each page's text.

**14. What about scanned PDFs?**
They contain images, not text, so extraction returns nothing. I detect this and show a message. Supporting them would need OCR, which I list as future work.

**15. Any weakness of PDF extraction?**
Complex layouts (columns, tables, icons) may be extracted in a different order than they look.

## E. AI and NLP

**16. Which AI model do you use?**
`sentence-transformers/all-MiniLM-L6-v2`, a small pretrained model (about 90 MB) that converts text into 384-number embeddings.

**17. Did you train it?**
No. It is pretrained; I only use it for inference. Training from scratch needs huge data and compute.

**18. What is an embedding?**
A list of numbers representing the meaning of a text, so similar meanings give similar numbers.

**19. What is cosine similarity?**
The cosine of the angle between two vectors: `(A.B)/(|A||B|)`. Near 1 means very similar direction; near 0 means unrelated.

**20. Why cosine and not just counting common words?**
Word counting misses synonyms ("developed APIs" vs "built web services"). Embeddings capture meaning, so related wording still scores well.

**21. The model reads limited text. How do you handle long resumes?**
I split each text into overlapping 120-word chunks, encode all of them and average the vectors. Nothing is dropped, but averaging does blur details - I mention this as a limitation.

**22. Do you use generative AI?**
No. Suggestions come from if/else rules. Only the similarity score uses a pretrained model.

**23. Does the model download every time?**
No. It downloads on the first run and is then loaded from the local cache. I also load it once and keep it in memory (`get_model`).

## F. Skills and score

**24. How do you detect skills?**
A dictionary of skills with alternative names, searched with whole-word regular expressions. Example: "sklearn" counts as scikit-learn, and "java" does not match inside "javascript".

**25. How do you avoid wrongly calling a skill missing?**
Aliases, and the page says "not detected", not "missing". I also explain that the resume may use wording my dictionary lacks.

**26. How should the score be interpreted?**
As a rough sign of topical closeness. The labels (>=60% high, >=40% moderate) are my own rough guides, not calibrated. A high score does not mean selection.

**27. Can the score be 100%?**
Practically no; even identical-topic texts rarely reach 100%, and I clamp the value between 0 and 100%.

## G. Testing, security, limits

**28. How did you test it?**
`unittest` with Flask's test client: valid PDF, missing file, wrong type, fake PDF, corrupted PDF, empty job description, PDF with no text, oversized file, skill matching, HTML escaping. The AI function is replaced by a fixed value in most tests; one optional test uses the real model. (State honestly which tests you have run on your own machine.)

**29. How is the app secured?**
Server-side checks of extension, size, page count and the `%PDF-` header; files are processed in memory, never saved or executed; Jinja auto-escapes output; debug mode is off; users see friendly messages, not stack traces; no secrets in the code.

**30. What if someone uploads a huge file or malicious PDF?**
There is a 5 MB limit and 10-page limit, and I only read text. PDF parsers can still have bugs, so in production I would keep PyMuPDF updated and run the parser in a sandboxed process.

**31. What are the main limitations?**
Not an ATS score; small skill dictionary; no OCR; English only; chunk averaging; model bias; no evaluation against real recruiter decisions.

**32. What would you improve next?**
OCR, semantic skill matching, a bigger skill list, DOCX support, highlighting the closest resume sentences, and a proper evaluation.

**33. Why is `debug=True` dangerous?**
Flask's debugger lets anyone who reaches the page run code on the server.

**34. Why validate on the server if the browser already checks?**
Browser checks are only convenience; a user can bypass them.

---

## One-minute explanation (practise aloud)

"My project is an AI-Powered Resume Analyzer built with Python and Flask. The user uploads a resume PDF and pastes a job description. The app extracts the resume text with PyMuPDF, then uses a pretrained Sentence Transformers model, all-MiniLM-L6-v2, to convert both texts into embeddings and measures their cosine similarity. That gives a semantic similarity score - not an ATS score and not a hiring probability. Separately, a skill dictionary with regular expressions finds matching skills and skills not detected, and simple rules check sections and give suggestions. Everything runs free on a laptop and uploaded files are not stored."

## Two-minute explanation

"Students often send one resume to every job without knowing how well it fits. I built a web application that gives quick feedback.

The user opens the Flask site, uploads a PDF and pastes a job description. On the server I first validate the file - extension, size, the PDF header - and the text. PyMuPDF extracts the text in memory; if the PDF is corrupted, password protected or scanned, the user gets a clear message.

For the AI part I use a pretrained model, all-MiniLM-L6-v2. I do not train anything. Long texts are split into overlapping 120-word chunks because the model reads limited text at once; each chunk becomes an embedding, I average them into one vector per document and compute cosine similarity. I show it as a percentage with a label, and a clear note that it is semantic similarity, not an ATS score.

The rest uses ordinary Python rules, and I am careful to say so. Skill detection uses a dictionary with alternative names and whole-word regular expressions, so 'sklearn' counts as scikit-learn. Skills from the job that I cannot find are shown as 'not detected', because the resume might word them differently. Then rule-based code checks sections like education and projects, and builds suggestions. These are not generated by a language model.

For security, files are never saved or executed, output is auto-escaped by Jinja, debug mode is off and errors are shown as friendly messages.

The limitations are a small skill dictionary, no OCR for scanned PDFs, English only, and no evaluation against real recruiters. Future work includes OCR, semantic skill matching and highlighting the resume sentences closest to each requirement."
