"""
AI Research Bot - Production Ready Research Paper Intelligence System

Features:
- PDF Loading with Validation
- Text Extraction & Chunking with Chunk IDs
- Semantic Embeddings
- ChromaDB with Advanced Metadata
- RAG Question Answering with Detailed Citations
- Paper Summarization
- Paper Comparison
- Literature Review Generation
- Research Gap Analysis
- Multi-Paper Analysis
- Research Recommendations
- Survey Paper Generation
- Robust Error Handling
"""

from pypdf import PdfReader
import hashlib
import os
import nltk
import chromadb
import traceback
from pathlib import Path

from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
from google.api_core import exceptions as google_api_exceptions
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
    RequestException,
    Timeout as RequestsTimeout,
)

nltk.download("punkt")
nltk.download("punkt_tab")
nltk.download("stopwords")


# ===================================================================
# CONFIGURATION
# ===================================================================

print("\nInitializing AI Research Bot 3.0...")

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
CHROMADB_PATH = os.getenv("CHROMADB_PATH", str(BASE_DIR / "chromadb"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
NOT_FOUND_RESPONSE = "Information not found in the uploaded papers."
_embedding_model = None

try:
    GEMINI_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "120"))
except ValueError:
    GEMINI_TIMEOUT_SECONDS = 120


def _log_step(message):
    print(f"[ResearchGPT upload] {message}", flush=True)


def _log_exception(context, error):
    print(
        f"[ResearchGPT upload][ERROR] {context}: "
        f"{type(error).__name__}: {error}",
        flush=True,
    )
    traceback.print_exc()


class ResearchIndexingError(Exception):
    def __init__(
        self,
        message,
        status_code=500,
        error_type="research_indexing_error",
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type


class PDFExtractionError(ResearchIndexingError):
    def __init__(self, message):
        super().__init__(
            message=message,
            status_code=400,
            error_type="pdf_extraction_error",
        )


class NoExtractableTextError(ResearchIndexingError):
    def __init__(self, message):
        super().__init__(
            message=message,
            status_code=400,
            error_type="pdf_no_extractable_text",
        )


class EmbeddingGenerationError(ResearchIndexingError):
    def __init__(self, message):
        super().__init__(
            message=message,
            status_code=503,
            error_type="embedding_generation_error",
        )


class ChromaDBIndexError(ResearchIndexingError):
    def __init__(self, message):
        super().__init__(
            message=message,
            status_code=500,
            error_type="chromadb_index_error",
        )


def is_embedding_model_loaded():
    return _embedding_model is not None


def _get_embedding_model():
    global _embedding_model

    if _embedding_model is None:
        try:
            _log_step(f"Loading SentenceTransformer model: {EMBEDDING_MODEL_NAME}")
            _embedding_model = SentenceTransformer(
                EMBEDDING_MODEL_NAME,
                local_files_only=False
            )
            _log_step("SentenceTransformer model loaded")
        except Exception as error:
            _log_exception("SentenceTransformer model initialization failed", error)
            raise EmbeddingGenerationError(
                "Unable to load the embedding model."
            ) from error

    return _embedding_model


def _encode_texts(texts):
    try:
        return _get_embedding_model().encode(texts)
    except ResearchIndexingError:
        raise
    except Exception as error:
        _log_exception("SentenceTransformer model.encode failed", error)
        raise EmbeddingGenerationError(
            "Unable to generate embeddings."
        ) from error


class GeminiGenerationError(Exception):
    def __init__(
        self,
        message,
        status_code=503,
        error_type="gemini_api_error",
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type


class GeminiLLM:
    def __init__(
        self,
        model_name,
        timeout_seconds,
    ):
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self._model = None

    def _get_model(self):
        api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        if not api_key:
            raise GeminiGenerationError(
                "Gemini API key is not configured. Set GEMINI_API_KEY in your environment.",
                status_code=503,
                error_type="gemini_api_key_missing",
            )

        if self._model is None:
            genai.configure(
                api_key=api_key,
                transport="rest",
            )
            self._model = genai.GenerativeModel(
                self.model_name,
                generation_config={
                    "temperature": 0.2,
                    "top_p": 0.95,
                    "max_output_tokens": 2048,
                },
            )

        return self._model

    def invoke(self, prompt):
        try:
            response = self._get_model().generate_content(
                prompt,
                request_options={
                    "timeout": self.timeout_seconds
                },
            )
        except (
            google_api_exceptions.Unauthenticated,
            google_api_exceptions.PermissionDenied,
        ) as error:
            _log_exception("Gemini authentication failed", error)
            raise GeminiGenerationError(
                "Gemini API key is invalid or does not have access to this model.",
                status_code=401,
                error_type="gemini_invalid_api_key",
            ) from error
        except google_api_exceptions.ResourceExhausted as error:
            _log_exception("Gemini quota exceeded", error)
            raise GeminiGenerationError(
                "Gemini quota or rate limit exceeded. Please try again later.",
                status_code=429,
                error_type="gemini_quota_exceeded",
            ) from error
        except google_api_exceptions.DeadlineExceeded as error:
            _log_exception("Gemini request timed out", error)
            raise GeminiGenerationError(
                "Gemini request timed out. Please try again.",
                status_code=504,
                error_type="gemini_timeout",
            ) from error
        except google_api_exceptions.ServiceUnavailable as error:
            _log_exception("Gemini API unavailable", error)
            raise GeminiGenerationError(
                "Gemini API is temporarily unavailable. Please try again later.",
                status_code=503,
                error_type="gemini_unavailable",
            ) from error
        except google_api_exceptions.RetryError as error:
            _log_exception("Gemini retry failed", error)
            cause = getattr(error, "cause", None) or error.__cause__
            if isinstance(cause, google_api_exceptions.DeadlineExceeded):
                raise GeminiGenerationError(
                    "Gemini request timed out. Please try again.",
                    status_code=504,
                    error_type="gemini_timeout",
                ) from error

            raise GeminiGenerationError(
                "Gemini API is temporarily unavailable. Please try again later.",
                status_code=503,
                error_type="gemini_unavailable",
            ) from error
        except (RequestsTimeout, TimeoutError) as error:
            _log_exception("Gemini network timeout", error)
            raise GeminiGenerationError(
                "Gemini request timed out. Please try again.",
                status_code=504,
                error_type="gemini_timeout",
            ) from error
        except (RequestsConnectionError, RequestException, OSError) as error:
            _log_exception("Gemini network failure", error)
            raise GeminiGenerationError(
                "Network error while contacting Gemini. Please check your connection and try again.",
                status_code=503,
                error_type="gemini_network_error",
            ) from error
        except google_api_exceptions.GoogleAPICallError as error:
            _log_exception("Gemini API call failed", error)
            raise GeminiGenerationError(
                "Gemini API request failed. Please try again later.",
                status_code=502,
                error_type="gemini_api_error",
            ) from error
        except Exception as error:
            _log_exception("Gemini unexpected failure", error)
            raise GeminiGenerationError(
                "Gemini API is unavailable right now. Please try again later.",
                status_code=503,
                error_type="gemini_unavailable",
            ) from error

        try:
            answer = response.text.strip()
        except (AttributeError, ValueError) as error:
            _log_exception("Gemini response parsing failed", error)
            raise GeminiGenerationError(
                "Gemini did not return a usable answer. Please try again.",
                status_code=502,
                error_type="gemini_empty_response",
            ) from error

        if not answer:
            raise GeminiGenerationError(
                "Gemini did not return a usable answer. Please try again.",
                status_code=502,
                error_type="gemini_empty_response",
            )

        return answer


llm = GeminiLLM(
    model_name=GEMINI_MODEL,
    timeout_seconds=GEMINI_TIMEOUT_SECONDS,
)

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50
)

# ===================================================================
# PDF LOADING WITH VALIDATION
# ===================================================================

print("\nValidating papers folder...")

PDF_BASE_DIR = BASE_DIR / "papers"
pdf_folder = str(PDF_BASE_DIR)
print("Startup PDF indexing disabled. Uploaded papers are indexed per user.")
pdf_files = []

# ===================================================================
# LOAD PDFs AND CREATE CHUNKS
# ===================================================================

print("\nLoading PDFs...")

all_text = ""
chunks = []
sources = []
papers = {}
user_papers = {}
page_numbers = []
chunk_counter = 0

for file in pdf_files:

    print(f"Reading: {file}")

    pdf_path = os.path.join(pdf_folder, file)

    try:
        reader = PdfReader(pdf_path)
    except Exception as error:
        print(f"Skipping unreadable PDF {file}: {error}")
        continue

    current_text = ""

    for page_num, page in enumerate(reader.pages, start=1):

        try:
            page_text = page.extract_text()
        except Exception as error:
            print(f"Skipping unreadable page {page_num} in {file}: {error}")
            continue

        if page_text:

            current_text += page_text + "\n"

            doc_chunks = splitter.split_text(page_text)

            for chunk in doc_chunks:

                chunks.append(chunk)
                sources.append(file)
                page_numbers.append(page_num)

    all_text += current_text
    papers[file] = current_text


print(f"\nTotal chunks created: {len(chunks)}")

# ===================================================================
# TEXT EXTRACTION
# ===================================================================

print("\n" + "=" * 70)
print("STEP 1 : TEXT EXTRACTION")
print("=" * 70)

print(all_text[:500])

# ===================================================================
# TOKENIZATION
# ===================================================================

tokens = word_tokenize(all_text)

print("\n" + "=" * 70)
print("STEP 2 : TOKENIZATION")
print("=" * 70)

print("Total Tokens:", len(tokens))

# ===================================================================
# STOP WORD REMOVAL
# ===================================================================

stop_words = set(stopwords.words("english"))

filtered_tokens = []

for word in tokens:

    if (
        word.lower() not in stop_words
        and word.isalpha()
    ):

        filtered_tokens.append(word)

print("\n" + "=" * 70)
print("STEP 3 : STOP WORD REMOVAL")
print("=" * 70)

print("Filtered Tokens:", len(filtered_tokens))

# ===================================================================
# EMBEDDINGS
# ===================================================================

print("\n" + "=" * 70)
print("STEP 4 : EMBEDDINGS")
print("=" * 70)

chunk_embeddings = _encode_texts(chunks) if chunks else []

# ===================================================================
# CHROMADB WITH CHUNK IDS
# ===================================================================

client = chromadb.PersistentClient(path=CHROMADB_PATH)

collection = client.get_or_create_collection(
    name="research_papers"
)

print(
    "\nDocuments in DB:",
    collection.count()
)

collection = client.get_or_create_collection(
    name="research_papers"
)

print("Chunks:", len(chunks))
print("Sources:", len(sources))
print("Pages:", len(page_numbers))

if chunks:
    print("Skipping global ChromaDB indexing. Use index_uploaded_paper per user.")


# ===================================================================
# RESEARCH ASSISTANT
# ===================================================================

print("\n" + "=" * 70)
print("STEP 5 : RESEARCH ASSISTANT")
print("=" * 70)

# Helper functions

def _paper_key(user_id, filename):
    return (int(user_id), filename)


def _user_filename_filter(user_id, filename):
    return {
        "$and": [
            {"user_id": int(user_id)},
            {"filename": filename},
        ]
    }


def _get_paper_text(filename, user_id=None):
    filename = Path(filename).name

    if user_id is not None:
        key = _paper_key(user_id, filename)
        cached_paper = user_papers.get(key)

        if cached_paper:
            return cached_paper

        paper_path = PDF_BASE_DIR / f"user_{int(user_id)}" / filename
        if not paper_path.is_file():
            return None

        paper_text, _, _ = _extract_pdf_text_and_chunks(paper_path)
        user_papers[key] = paper_text
        return paper_text

    return papers.get(filename)


def _extract_pdf_text_and_chunks(file_path):
    file_path = Path(file_path)
    _log_step(f"Opening PDF: {file_path}")

    try:
        reader = PdfReader(str(file_path))
        _log_step(f"PDF opened: pages={len(reader.pages)}")
    except Exception as error:
        _log_exception(f"PDF open failed for {file_path}", error)
        raise PDFExtractionError(
            "Unable to open the uploaded PDF. The file may be corrupted or encrypted."
        ) from error

    paper_text = ""
    extracted_chunks = []
    extracted_pages = []

    for page_num, page in enumerate(reader.pages, start=1):
        try:
            _log_step(f"Extracting text from page {page_num}")
            page_text = page.extract_text()
        except Exception as error:
            _log_exception(f"Text extraction failed on page {page_num}", error)
            raise PDFExtractionError(
                f"Unable to extract text from page {page_num} of the uploaded PDF."
            ) from error

        if not page_text:
            _log_step(f"No text extracted from page {page_num}")
            continue

        paper_text += page_text + "\n"

        try:
            doc_chunks = splitter.split_text(page_text)
            _log_step(
                f"Chunks created from page {page_num}: count={len(doc_chunks)}"
            )
        except Exception as error:
            _log_exception(f"Chunking failed on page {page_num}", error)
            raise PDFExtractionError(
                f"Unable to chunk extracted text from page {page_num}."
            ) from error

        for chunk in doc_chunks:
            extracted_chunks.append(chunk)
            extracted_pages.append(page_num)

    _log_step(
        "Text extraction completed: "
        f"characters={len(paper_text)}, chunks={len(extracted_chunks)}"
    )

    return paper_text, extracted_chunks, extracted_pages


def index_uploaded_paper(file_path, filename, user_id):
    file_path = Path(file_path)
    filename = Path(filename).name
    _log_step(
        f"index_uploaded_paper started: user_id={user_id}, "
        f"filename={filename}, path={file_path}"
    )

    try:
        paper_text, extracted_chunks, extracted_pages = _extract_pdf_text_and_chunks(
            file_path
        )
    except ResearchIndexingError:
        raise
    except Exception as error:
        _log_exception("Unexpected PDF extraction failure", error)
        raise PDFExtractionError(
            "Unable to process the uploaded PDF."
        ) from error

    if not extracted_chunks:
        _log_step("No chunks created because no text was extracted")
        raise NoExtractableTextError(
            "No extractable text found in the uploaded PDF. "
            "Please upload a text-based PDF instead of a scanned image PDF."
        )

    try:
        _log_step(f"Generating embeddings: chunks={len(extracted_chunks)}")
        embeddings = _encode_texts(extracted_chunks)
        _log_step(f"Embeddings generated: count={len(embeddings)}")
    except ResearchIndexingError:
        raise
    except Exception as error:
        _log_exception("SentenceTransformer model.encode failed", error)
        raise EmbeddingGenerationError(
            "Unable to generate embeddings for the uploaded PDF."
        ) from error

    filename_hash = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:16]

    try:
        _log_step(
            f"Deleting old ChromaDB chunks for user_id={user_id}, "
            f"filename={filename}"
        )
        collection.delete(
            where=_user_filename_filter(user_id, filename)
        )
        _log_step("Old ChromaDB chunks deleted")
    except Exception as error:
        _log_exception("ChromaDB delete failed", error)
        raise ChromaDBIndexError(
            "Unable to prepare the search index for this PDF."
        ) from error

    ids = []
    metadatas = []

    for index, chunk in enumerate(extracted_chunks):
        chunk_hash = hashlib.sha256(
            f"{user_id}:{filename}:{extracted_pages[index]}:{index}:{chunk}".encode(
                "utf-8"
            )
        ).hexdigest()[:16]
        ids.append(
            f"user:{user_id}:file:{filename_hash}:page:{extracted_pages[index]}:"
            f"chunk:{index}:{chunk_hash}"
        )
        metadatas.append(
            {
                "user_id": int(user_id),
                "filename": filename,
                "source": filename,
                "page": extracted_pages[index],
            }
        )

    try:
        _log_step(f"Starting ChromaDB upsert: ids={len(ids)}")
        collection.upsert(
            ids=ids,
            documents=extracted_chunks,
            embeddings=[
                embedding.tolist()
                for embedding in embeddings
            ],
            metadatas=metadatas,
        )
        _log_step("ChromaDB upsert completed")
    except Exception as error:
        _log_exception("ChromaDB upsert failed", error)
        raise ChromaDBIndexError(
            "Unable to store this PDF in the search index."
        ) from error

    user_papers[_paper_key(user_id, filename)] = paper_text
    _log_step(
        f"index_uploaded_paper completed: filename={filename}, "
        f"chunks={len(extracted_chunks)}"
    )

    return len(extracted_chunks)


def delete_indexed_paper(filename, user_id):
    filename = Path(filename).name

    collection.delete(
        where=_user_filename_filter(user_id, filename)
    )

    user_papers.pop(_paper_key(user_id, filename), None)


def summarize_paper(filename, user_id=None):
    paper = _get_paper_text(filename, user_id=user_id)
    if not paper:
        return "Paper not found."
    
    prompt = f"""
Generate a structured summary.

Include:
1. Title
2. Objective
3. Methodology
4. Results
5. Conclusion

Paper:
{paper[:8000]}
"""
    return llm.invoke(prompt)

def compare_papers(file1, file2, user_id=None):
    p1 = _get_paper_text(file1, user_id=user_id)
    p2 = _get_paper_text(file2, user_id=user_id)
    
    if not p1 or not p2:
        return "Paper not found."
    
    prompt = f"""
Compare these papers.

Include:
1. Objective
2. Methodology
3. Contributions
4. Results
5. Strengths
6. Limitations

Paper 1:
{p1[:5000]}

Paper 2:
{p2[:5000]}
"""
    return llm.invoke(prompt)

def literature_review(files, user_id=None):
    summaries = []
    
    for f in files:
        paper = _get_paper_text(f, user_id=user_id)
        if paper:
            summary_prompt = f"""
Analyze this research paper in detail.

Provide:

1. Title
2. Objective
3. Methodology
4. Key Findings
5. Limitations
6. Future Work
7. Significance

Paper:

{paper[:8000]}
"""
            summaries.append(llm.invoke(summary_prompt))
    
    prompt = f"""
You are an expert research assistant.

Generate a comprehensive literature review.

Include:

1. Topic Overview
2. Findings from Each Paper
3. Common Trends and Methodologies
4. Research Challenges
5. Research Gaps Identified
6. Future Scope
7. Conclusion and Recommendations

Paper Summaries:

{chr(10).join(summaries)}
"""
    return llm.invoke(prompt)

def research_gap(files, user_id=None):
    summaries = []
    
    for f in files:
        paper = _get_paper_text(f, user_id=user_id)
        if paper:
            gap_prompt = f"""
Analyze this research paper in detail.

Extract:

1. Objective and Problem Statement
2. Methodology Used
3. Key Findings
4. Limitations and Challenges
5. Future Work Suggested
6. Open Questions

Paper:

{paper[:8000]}
"""
            summaries.append(llm.invoke(gap_prompt))
    
    prompt = f"""
You are a senior research analyst.

Analyze all provided research papers.

Generate:

1. Existing Work Summary
2. Common Methodologies Used
3. Identified Limitations
4. Research Challenges
5. Unsolved Problems
6. Identified Research Gaps
7. Novel Research Opportunities
8. Recommended Next Steps

Research Papers Analysis:

{chr(10).join(summaries)}
"""
    return llm.invoke(prompt)

def analyze_papers(files, user_id=None):
    content = ""
    
    for f in files:
        paper = _get_paper_text(f, user_id=user_id)
        if paper:
            content += f"\n\n===== {f} =====\n"
            content += paper[:5000]
    
    if not content:
        return "No valid papers found."
    
    prompt = f"""
Analyze all research papers.

Generate:

1. Research Domain
2. Common Methodologies
3. Key Contributions
4. Strengths
5. Limitations
6. Research Trends
7. Future Scope
8. Best Performing Approach

Research Papers:

{content}
"""
    return llm.invoke(prompt)

def recommend_research(files, user_id=None):
    content = ""
    
    for f in files:
        paper = _get_paper_text(f, user_id=user_id)
        if paper:
            content += f"\n\n=== {f} ===\n{paper[:4000]}"
    
    if not content:
        return "No valid papers found."
    
    prompt = f"""
You are an expert research strategist.

Based on these research papers, suggest:

1. Novel Research Topics
   - Unexplored Areas
   - Emerging Trends
   - Interdisciplinary Opportunities

2. Open Problems
   - Unsolved Challenges
   - Current Limitations
   - Technical Barriers

3. Innovative Future Directions
   - New Methodologies
   - Hybrid Approaches
   - Cross-Domain Applications

4. Publication-Worthy Ideas
   - High-Impact Research Areas
   - Grant-Worthy Topics
   - Conference-Ready Ideas

5. Commercialization Opportunities
   - Industry Applications
   - Startup Ideas
   - Real-World Solutions

Research Papers:

{content}
"""
    return llm.invoke(prompt)

def generate_survey(files, user_id=None):
    summaries = []
    
    for f in files:
        paper = _get_paper_text(f, user_id=user_id)
        if paper:
            summary_prompt = f"""
Analyze this research paper.

Provide:

1. Title and Authors
2. Problem Statement
3. Methodology
4. Key Contributions
5. Experimental Results
6. Strengths and Weaknesses
7. Related Work
8. Future Directions

Paper:

{paper[:8000]}
"""
            summaries.append(llm.invoke(summary_prompt))
    
    prompt = f"""
You are an expert survey paper writer.

Generate a comprehensive survey paper based on these research papers.

Structure:

1. Abstract
   - Clear summary of the survey topic
   - Number of papers reviewed
   - Key insights

2. Introduction
   - Motivation for the survey
   - Scope and coverage
   - Paper organization

3. Related Work
   - Historical context
   - Evolution of the field
   - Current state of research

4. Comparative Analysis
   - Methodologies comparison
   - Strengths and limitations of each approach
   - Classification of techniques

5. Open Challenges
   - Unsolved problems
   - Current limitations
   - Technical barriers

6. Future Research Directions
   - Emerging opportunities
   - Interdisciplinary connections
   - Predicted trends

7. Conclusion
   - Key takeaways
   - Research priorities
   - Closing remarks

Research Papers Summaries:

{chr(10).join(summaries)}
"""
    return llm.invoke(prompt)

def answer_question(question, user_id=None):
    if user_id is None:
        raise ValueError("user_id is required for document retrieval.")

    query_embedding = _encode_texts([question])[0]

    query_kwargs = {
        "query_embeddings": [query_embedding.tolist()],
        "n_results": 3,
        "where": {
            "user_id": int(user_id)
        },
    }

    results = collection.query(**query_kwargs)

    retrieved_chunks = results["documents"][0]
    retrieved_metas = results["metadatas"][0]

    if not retrieved_chunks:
        return NOT_FOUND_RESPONSE

    context = "\n\n".join(retrieved_chunks)

    prompt = f"""
You are an AI Research Assistant.

Answer ONLY using the provided context.

If the answer is not found in the context, respond:

"Information not found in the uploaded papers."

Context:
{context}

Question:
{question}

Answer:
"""

    answer = llm.invoke(prompt)

    if answer.strip().strip("\"'") == NOT_FOUND_RESPONSE:
        return NOT_FOUND_RESPONSE

    evidence = set()

    for meta in retrieved_metas:
        if meta:
            evidence.add(meta.get("filename") or meta.get("source"))

    return (
        answer
        + "\n\nEvidence:\n"
        + "\n".join(sorted(evidence))
    )
# ===================================================================
# INTERACTIVE LOOP
# ===================================================================

if __name__ == "__main__":

    print("\nAI Research Bot 3.0 Ready")
    print("\n" + "=" * 70)
    print("AVAILABLE COMMANDS")
    print("=" * 70)
    print("\n📄 PAPER ANALYSIS:")
    print("  summarize paper.pdf")
    print("  compare paper1.pdf paper2.pdf")
    print("\n📚 RESEARCH SYNTHESIS:")
    print("  review paper1.pdf paper2.pdf paper3.pdf")
    print("  gap paper1.pdf paper2.pdf paper3.pdf")
    print("  analyze paper1.pdf paper2.pdf paper3.pdf")
    print("\n💡 RESEARCH INTELLIGENCE:")
    print("  recommend paper1.pdf paper2.pdf")
    print("  survey paper1.pdf paper2.pdf paper3.pdf")
    print("\n🔍 RAG QUESTION ANSWERING:")
    print("  Ask any natural language question")
    print("\n⏹️  exit - quit the program")
    print("=" * 70)

    while True:

        query = input("\n> ").strip()

        if query.lower() == "exit":
            break

        try:

            if query.startswith("summarize"):
                _, file = query.split(maxsplit=1)
                print("\n" + "=" * 70)
                print("PAPER SUMMARY")
                print("=" * 70)
                print(summarize_paper(file))

            elif query.startswith("compare"):
                _, f1, f2 = query.split()
                print("\n" + "=" * 70)
                print("PAPER COMPARISON")
                print("=" * 70)
                print(compare_papers(f1, f2))

            elif query.startswith("review"):
                files = query.split()[1:]
                print("\n" + "=" * 70)
                print("LITERATURE REVIEW")
                print("=" * 70)
                print(literature_review(files))

            elif query.startswith("gap"):
                files = query.split()[1:]
                print("\n" + "=" * 70)
                print("RESEARCH GAP ANALYSIS")
                print("=" * 70)
                print(research_gap(files))

            elif query.startswith("analyze"):
                files = query.split()[1:]
                print("\n" + "=" * 70)
                print("MULTI-PAPER ANALYSIS")
                print("=" * 70)
                print(analyze_papers(files))

            elif query.startswith("recommend"):
                files = query.split()[1:]
                print("\n" + "=" * 70)
                print("RESEARCH RECOMMENDATIONS")
                print("=" * 70)
                print(recommend_research(files))

            elif query.startswith("survey"):
                files = query.split()[1:]
                print("\n" + "=" * 70)
                print("SURVEY PAPER")
                print("=" * 70)
                print(generate_survey(files))

            else:
                print("\n" + "=" * 70)
                print("RAG QUESTION ANSWERING")
                print("=" * 70)
                print(answer_question(query))

        except FileNotFoundError as e:
            print(f"\n❌ File Error: {e}")

        except ValueError as e:
            print(f"\n❌ Command Error: {e}")
            print("Please check your command format.")

        except Exception as e:
            print(f"\n❌ Unexpected Error: {e}")
            print("Please try again.")

    print("\nProgram Ended.")
