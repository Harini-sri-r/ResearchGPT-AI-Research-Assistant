from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import shutil

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
PAPERS_DIR = BASE_DIR / "papers"

app = FastAPI(title="AI Research Bot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {
        "message": "ResearchGPT Backend Running"
    }

@app.get("/api/health")
def health_check():
    return {
        "message": "AI Research Bot Backend Running"
    }

@app.get("/ask")
def ask_question(question: str):

    try:
        from research import (
            answer_question,
            summarize_paper,
            compare_papers,
            literature_review,
            research_gap,
            recommend_research,
            generate_survey
        )
    except ModuleNotFoundError as error:
        raise HTTPException(
            status_code=503,
            detail=f"Research engine dependency missing: {error.name}"
        ) from error

    question = question.strip()

    if question.startswith("summarize"):

        filename = question.split()[1]

        result = summarize_paper(filename)

    elif question.startswith("compare"):

        parts = question.split()

        file1 = parts[1]
        file2 = parts[2]

        result = compare_papers(
            file1,
            file2
        )

    elif question.startswith("review"):

        files = question.split()[1:]

        result = literature_review(files)

    elif question.startswith("gap"):

        files = question.split()[1:]

        result = research_gap(files)

    elif question.startswith("recommend"):

        files = question.split()[1:]

        result = recommend_research(files)

    elif question.startswith("survey"):

        files = question.split()[1:]

        result = generate_survey(files)

    else:

        result = answer_question(question)

    return {
        "answer": result
    }
@app.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...)
):

    filename = Path(file.filename or "").name

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a PDF file."
        )

    PAPERS_DIR.mkdir(
        exist_ok=True
    )

    file_path = PAPERS_DIR / filename

    with file_path.open(
        "wb"
    ) as buffer:

        shutil.copyfileobj(
            file.file,
            buffer
        )

    return {
        "message":
        f"{filename} uploaded successfully"
    }

# app.mount(
#     "/",
#     StaticFiles(directory=FRONTEND_DIR),
#     name="frontend"
# )
