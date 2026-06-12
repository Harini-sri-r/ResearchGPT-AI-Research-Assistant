
from pathlib import Path
from time import perf_counter
import traceback

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import hash_password, verify_password
from database import get_db
from jwt_handler import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_current_token,
    get_current_user,
    revoke_token,
)
from models import ChatHistory, Favorite, QueryLog, SearchHistory, UploadedPaper, User
from schemas import (
    ChatHistoryResponse,
    FavoriteCreate,
    FavoriteResponse,
    LoginRequest,
    MessageResponse,
    QueryLogResponse,
    RegisterRequest,
    SearchHistoryResponse,
    TokenResponse,
    UploadedPaperResponse,
    UserResponse,
)
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


def error_response(
    status_code: int,
    message,
    error_type: str,
    details=None,
    headers=None,
):
    content = {
        "error": {
            "code": status_code,
            "type": error_type,
            "message": message,
        }
    }

    if details is not None:
        content["error"]["details"] = details

    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=headers,
    )


def log_upload_step(message):
    print(f"[ResearchGPT upload] {message}", flush=True)


def log_upload_exception(context, error):
    print(
        f"[ResearchGPT upload][ERROR] {context}: "
        f"{type(error).__name__}: {error}",
        flush=True,
    )
    traceback.print_exc()


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException,
):
    return error_response(
        status_code=exc.status_code,
        message=exc.detail,
        error_type="http_error",
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    return error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        message="Validation error.",
        error_type="validation_error",
        details=jsonable_encoder(exc.errors()),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
):
    print(
        f"[ResearchGPT][ERROR] Unhandled exception for "
        f"{request.method} {request.url.path}: {type(exc).__name__}: {exc}",
        flush=True,
    )
    traceback.print_exc()

    return error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="Internal server error.",
        error_type="internal_server_error",
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


@app.get("/debug/research-import", tags=["Debug"])
def debug_research_import(
    current_user: User = Depends(get_current_user),
):
    try:
        log_upload_step(
            f"debug research import requested by user_id={current_user.id}"
        )
        import research

        return {
            "message": "research.py imported successfully",
            "chromadb_path": research.CHROMADB_PATH,
            "embedding_model": research.EMBEDDING_MODEL_NAME,
            "embedding_model_loaded": research.is_embedding_model_loaded(),
            "ollama_base_url": research.OLLAMA_BASE_URL,
            "ollama_model": research.OLLAMA_MODEL,
        }
    except Exception as error:
        log_upload_exception("debug research import failed", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"research.py import failed: {type(error).__name__}: {error}",
        ) from error


@app.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
    summary="Register a new user",
)
def register_user(
    user_data: RegisterRequest,
    db: Session = Depends(get_db),
):
    username_exists = (
        db.query(User)
        .filter(func.lower(User.username) == user_data.username.lower())
        .first()
    )
    if username_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists.",
        )

    email_exists = (
        db.query(User)
        .filter(func.lower(User.email) == user_data.email.lower())
        .first()
    )
    if email_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists.",
        )

    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists.",
        ) from error

    return new_user


@app.post(
    "/login",
    response_model=TokenResponse,
    tags=["Authentication"],
    summary="Log in and receive a bearer token",
)
def login_user(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
):
    identifier = login_data.username_or_email.lower()
    user = (
        db.query(User)
        .filter(
            or_(
                func.lower(User.username) == identifier,
                func.lower(User.email) == identifier,
            )
        )
        .first()
    )

    if user is None or not verify_password(
        login_data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username, email, or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        {
            "sub": str(user.id),
            "username": user.username,
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user,
    }


@app.get(
    "/me",
    response_model=UserResponse,
    tags=["Authentication"],
    summary="Get the current logged-in user",
)
def read_current_user(
    current_user: User = Depends(get_current_user),
):
    return current_user


@app.get(
    "/profile",
    response_model=UserResponse,
    tags=["Dashboard"],
    summary="Get the current user's profile",
)
def read_profile(
    current_user: User = Depends(get_current_user),
):
    return current_user


@app.get(
    "/my-papers",
    response_model=list[UploadedPaperResponse],
    tags=["Dashboard"],
    summary="List papers uploaded by the current user",
)
def list_my_papers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(UploadedPaper)
        .filter(UploadedPaper.user_id == current_user.id)
        .order_by(UploadedPaper.upload_time.desc())
        .all()
    )


def get_current_user_paper(
    paper_id: int,
    current_user: User,
    db: Session,
):
    paper = (
        db.query(UploadedPaper)
        .filter(
            UploadedPaper.id == paper_id,
            UploadedPaper.user_id == current_user.id,
        )
        .first()
    )

    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found.",
        )

    return paper


def resolve_paper_path(
    paper: UploadedPaper,
    require_exists: bool = True,
):
    paper_path = Path(paper.filepath)
    if not paper_path.is_absolute():
        paper_path = BASE_DIR / paper_path

    user_papers_dir = (PAPERS_DIR / f"user_{paper.user_id}").resolve()
    resolved_path = paper_path.resolve()

    try:
        resolved_path.relative_to(user_papers_dir)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Paper file path is invalid.",
        ) from error

    if require_exists and not resolved_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper file not found on the server.",
        )

    return resolved_path


@app.get(
    "/papers/{paper_id}/view",
    tags=["Research"],
    summary="View one uploaded paper for the current user",
)
def view_paper(
    paper_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    paper = get_current_user_paper(
        paper_id=paper_id,
        current_user=current_user,
        db=db,
    )
    file_path = resolve_paper_path(paper)

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=paper.filename,
        content_disposition_type="inline",
    )


@app.get(
    "/papers/{paper_id}/download",
    tags=["Research"],
    summary="Download one uploaded paper for the current user",
)
def download_paper(
    paper_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    paper = get_current_user_paper(
        paper_id=paper_id,
        current_user=current_user,
        db=db,
    )
    file_path = resolve_paper_path(paper)

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=paper.filename,
        content_disposition_type="attachment",
    )


@app.delete(
    "/papers/{paper_id}",
    response_model=MessageResponse,
    tags=["Research"],
    summary="Delete one uploaded paper for the current user",
)
def delete_paper(
    paper_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    paper = get_current_user_paper(
        paper_id=paper_id,
        current_user=current_user,
        db=db,
    )
    file_path = resolve_paper_path(
        paper,
        require_exists=False,
    )
    filename = paper.filename

    try:
        from research import delete_indexed_paper

        delete_indexed_paper(
            filename=filename,
            user_id=current_user.id,
        )
    except ModuleNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Research engine dependency missing: {error.name}",
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to delete paper from search index: {error}",
        ) from error

    try:
        if file_path.exists():
            file_path.unlink()

        (
            db.query(Favorite)
            .filter(
                Favorite.user_id == current_user.id,
                Favorite.paper_name == filename,
            )
            .delete(synchronize_session=False)
        )
        db.delete(paper)
        db.commit()
    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to delete paper: {error}",
        ) from error

    return {
        "message": f"{filename} deleted successfully."
    }


@app.get(
    "/my-chat-history",
    response_model=list[ChatHistoryResponse],
    tags=["Dashboard"],
    summary="List chat history for the current user",
)
def list_my_chat_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == current_user.id)
        .order_by(ChatHistory.created_at.desc())
        .all()
    )


@app.post(
    "/logout",
    response_model=MessageResponse,
    tags=["Authentication"],
    summary="Log out the current user",
)
def logout_user(
    token: str = Depends(get_current_token),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    revoke_token(
        token=token,
        db=db,
        user_id=current_user.id,
    )
    return {
        "message": f"{current_user.username} logged out successfully."
    }


@app.get("/ask", tags=["Research"])
def ask_question(
    question: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    try:
        from research import (
            OllamaGenerationError,
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
    start_time = perf_counter()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty.",
        )

    parts = question.split()
    command = parts[0].lower()

    try:
        if command == "summarize":
            if len(parts) < 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Usage: summarize <filename>",
                )

            filename = parts[1]

            result = summarize_paper(filename, user_id=current_user.id)

        elif command == "compare":
            if len(parts) < 3:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Usage: compare <file1> <file2>",
                )

            file1 = parts[1]
            file2 = parts[2]

            result = compare_papers(
                file1,
                file2,
                user_id=current_user.id,
            )

        elif command == "review":
            files = parts[1:]

            result = literature_review(files, user_id=current_user.id)

        elif command == "gap":
            files = parts[1:]

            result = research_gap(files, user_id=current_user.id)

        elif command == "recommend":
            files = parts[1:]

            result = recommend_research(files, user_id=current_user.id)

        elif command == "survey":
            files = parts[1:]

            result = generate_survey(files, user_id=current_user.id)

        else:
            result = answer_question(question, user_id=current_user.id)
    except OllamaGenerationError as error:
        return error_response(
            status_code=error.status_code,
            message=error.message,
            error_type=error.error_type,
        )

    response_time = f"{perf_counter() - start_time:.2f}s"

    chat = ChatHistory(
        user_id=current_user.id,
        question=question,
        answer=result
    )
    search = SearchHistory(
        user_id=current_user.id,
        query=question,
    )
    query_log = QueryLog(
        user_id=current_user.id,
        query=question,
        response_time=response_time,
    )

    db.add(chat)
    db.add(search)
    db.add(query_log)
    db.commit()
        

    return {
        "answer": result
    }


@app.post("/upload", tags=["Research"])
async def upload_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    log_upload_step(
        f"file received: original_filename={file.filename!r}, "
        f"content_type={file.content_type!r}, user_id={current_user.id}"
    )

    filename = Path(file.filename or "").name

    if not filename:
        log_upload_step("upload rejected: missing filename")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must include a filename.",
        )

    if not filename.lower().endswith(".pdf"):
        log_upload_step(f"upload rejected: non-PDF filename={filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload a PDF file."
        )

    user_papers_dir = PAPERS_DIR / f"user_{current_user.id}"
    try:
        log_upload_step(f"creating user papers folder: {user_papers_dir}")
        user_papers_dir.mkdir(
            parents=True,
            exist_ok=True
        )
    except Exception as error:
        log_upload_exception("Unable to create user papers folder", error)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to prepare upload storage.",
        ) from error

    file_path = user_papers_dir / filename

    try:
        log_upload_step(f"saving uploaded file to disk: {file_path}")
        with file_path.open(
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                file.file,
                buffer
            )
        log_upload_step(
            f"file saved: path={file_path}, size_bytes={file_path.stat().st_size}"
        )
    except Exception as error:
        log_upload_exception("Unable to save uploaded file", error)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save uploaded PDF.",
        ) from error

    try:
        log_upload_step("importing research.index_uploaded_paper")
        from research import ResearchIndexingError, index_uploaded_paper
        log_upload_step("research.index_uploaded_paper imported")
    except ModuleNotFoundError as error:
        log_upload_exception("Research engine dependency missing", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Research engine dependency missing: {error.name}",
        ) from error
    except Exception as error:
        log_upload_exception("Research engine import failed", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Research engine failed to initialize: {type(error).__name__}: {error}",
        ) from error

    try:
        log_upload_step(
            f"calling index_uploaded_paper: filename={filename}, "
            f"user_id={current_user.id}"
        )
        chunk_count = index_uploaded_paper(
            file_path=file_path,
            filename=filename,
            user_id=current_user.id,
        )
        log_upload_step(
            f"index_uploaded_paper returned successfully: chunks={chunk_count}"
        )
    except ResearchIndexingError as error:
        log_upload_exception("Research indexing failed", error)
        raise HTTPException(
            status_code=error.status_code,
            detail=error.message,
        ) from error
    except ValueError as error:
        log_upload_exception("Research indexing validation failed", error)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except Exception as error:
        log_upload_exception("Unexpected research indexing failure", error)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to index uploaded paper: {type(error).__name__}: {error}",
        ) from error

    paper = UploadedPaper(
        user_id=current_user.id,
        filename=filename,
        filepath=str(file_path)
    )

    try:
        log_upload_step(f"saving uploaded paper row to PostgreSQL: {filename}")
        db.add(paper)
        db.commit()
        db.refresh(paper)
        log_upload_step(f"PostgreSQL save completed: paper_id={paper.id}")
    except Exception as error:
        db.rollback()
        log_upload_exception("Unable to save uploaded paper row", error)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF was indexed but the upload record could not be saved.",
        ) from error

    return {
        "message":
        f"{filename} uploaded successfully"
    }


@app.post(
    "/favorites",
    response_model=FavoriteResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Favorites"],
    summary="Save a paper as a favorite",
)
def create_favorite(
    favorite_data: FavoriteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing_favorite = (
        db.query(Favorite)
        .filter(
            Favorite.user_id == current_user.id,
            Favorite.paper_name == favorite_data.paper_name,
        )
        .first()
    )
    if existing_favorite:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Favorite already exists.",
        )

    favorite = Favorite(
        user_id=current_user.id,
        paper_name=favorite_data.paper_name,
    )

    db.add(favorite)
    db.commit()
    db.refresh(favorite)

    return favorite


@app.get(
    "/favorites",
    response_model=list[FavoriteResponse],
    tags=["Favorites"],
    summary="List favorites for the current user",
)
def list_favorites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user.id)
        .order_by(Favorite.saved_at.desc())
        .all()
    )


@app.delete(
    "/favorites/{id}",
    response_model=MessageResponse,
    tags=["Favorites"],
    summary="Delete one favorite for the current user",
)
def delete_favorite(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    favorite = (
        db.query(Favorite)
        .filter(
            Favorite.id == id,
            Favorite.user_id == current_user.id,
        )
        .first()
    )

    if favorite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found.",
        )

    db.delete(favorite)
    db.commit()

    return {
        "message": "Favorite deleted successfully."
    }


@app.get(
    "/search-history",
    response_model=list[SearchHistoryResponse],
    tags=["History"],
    summary="List search history for the current user",
)
def list_search_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(SearchHistory)
        .filter(SearchHistory.user_id == current_user.id)
        .order_by(SearchHistory.searched_at.desc())
        .all()
    )


@app.delete(
    "/search-history",
    response_model=MessageResponse,
    tags=["History"],
    summary="Delete search history for the current user",
)
def delete_search_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    deleted_count = (
        db.query(SearchHistory)
        .filter(SearchHistory.user_id == current_user.id)
        .delete(synchronize_session=False)
    )
    db.commit()

    return {
        "message": f"Deleted {deleted_count} search history item(s)."
    }


@app.get(
    "/query-logs",
    response_model=list[QueryLogResponse],
    tags=["History"],
    summary="List query logs for the current user",
)
def list_query_logs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(QueryLog)
        .filter(QueryLog.user_id == current_user.id)
        .order_by(QueryLog.timestamp.desc())
        .all()
    )

# app.mount(
#     "/",
#     StaticFiles(directory=FRONTEND_DIR),
#     name="frontend"
# )
