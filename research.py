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
import os
import nltk
import chromadb

from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from langchain_ollama import OllamaLLM

nltk.download("punkt", quiet=True)
nltk.download("stopwords", quiet=True)

# ===================================================================
# CONFIGURATION
# ===================================================================

print("\nInitializing AI Research Bot 3.0...")

llm = OllamaLLM(model="llama3")

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50
)

try:
    model = SentenceTransformer(
        "all-MiniLM-L6-v2",
        local_files_only=True
    )
except Exception as error:
    raise RuntimeError(
        "Unable to load the SentenceTransformer model locally. "
        "If you are offline, make sure the model is cached or run once with internet access "
        "and set HF_TOKEN if needed."
    ) from error

# ===================================================================
# PDF LOADING WITH VALIDATION
# ===================================================================

print("\nValidating papers folder...")

pdf_folder = "papers"

if not os.path.isdir(pdf_folder):
    raise FileNotFoundError(
        f"Folder not found: {pdf_folder}"
    )

pdf_files = [
    f for f in os.listdir(pdf_folder)
    if f.endswith(".pdf")
]

if len(pdf_files) == 0:
    raise Exception(
        "No PDF files found in papers folder."
    )

print(f"Found {len(pdf_files)} PDF files")

# ===================================================================
# LOAD PDFs AND CREATE CHUNKS
# ===================================================================

print("\nLoading PDFs...")

all_text = ""
chunks = []
sources = []
papers = {}
page_numbers = []
chunk_counter = 0

for file in pdf_files:

    print(f"Reading: {file}")

    pdf_path = os.path.join(pdf_folder, file)

    reader = PdfReader(pdf_path)

    current_text = ""

    for page_num, page in enumerate(reader.pages, start=1):

        page_text = page.extract_text()

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

chunk_embeddings = model.encode(chunks)

# ===================================================================
# CHROMADB WITH CHUNK IDS
# ===================================================================

client = chromadb.PersistentClient(path="./chromadb")

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

for i, chunk in enumerate(chunks):

    collection.add(
        ids=[str(i)],
        documents=[chunk],
        embeddings=[
            chunk_embeddings[i].tolist()
        ],
        metadatas=[
        {
            "source": sources[i],
            "page": page_numbers[i]
        }
    ]
)


# ===================================================================
# RESEARCH ASSISTANT
# ===================================================================

print("\n" + "=" * 70)
print("STEP 5 : RESEARCH ASSISTANT")
print("=" * 70)

# Helper functions

def summarize_paper(filename):
    paper = papers.get(filename)
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

def compare_papers(file1, file2):
    p1 = papers.get(file1)
    p2 = papers.get(file2)
    
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

def literature_review(files):
    summaries = []
    
    for f in files:
        paper = papers.get(f)
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

def research_gap(files):
    summaries = []
    
    for f in files:
        paper = papers.get(f)
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

def analyze_papers(files):
    content = ""
    
    for f in files:
        paper = papers.get(f)
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

def recommend_research(files):
    content = ""
    
    for f in files:
        paper = papers.get(f)
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

def generate_survey(files):
    summaries = []
    
    for f in files:
        paper = papers.get(f)
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

def answer_question(question):

    query_embedding = model.encode(question)

    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=3
    )

    retrieved_chunks = results["documents"][0]
    retrieved_metas = results["metadatas"][0]

    context = "\n\n".join(retrieved_chunks)

    prompt = f"""
Answer ONLY using the provided context.

If the answer is not available in the context,
reply with:
'Information not found in uploaded papers.'

Context:
{context}

Question:
{question}

Answer:
"""

    answer = llm.invoke(prompt)

    evidence = set()

    for meta in retrieved_metas:
        if meta:
            evidence.add(meta["source"])

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
