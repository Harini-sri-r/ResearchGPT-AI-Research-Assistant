
from pathlib import Path
from time import perf_counter

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

    if question.startswith("summarize"):

        filename = question.split()[1]

        result = summarize_paper(filename, user_id=current_user.id)

    elif question.startswith("compare"):

        parts = question.split()

        file1 = parts[1]
        file2 = parts[2]

        result = compare_papers(
            file1,
            file2,
            user_id=current_user.id,
        )

    elif question.startswith("review"):

        files = question.split()[1:]

        result = literature_review(files, user_id=current_user.id)

    elif question.startswith("gap"):

        files = question.split()[1:]

        result = research_gap(files, user_id=current_user.id)

    elif question.startswith("recommend"):

        files = question.split()[1:]

        result = recommend_research(files, user_id=current_user.id)

    elif question.startswith("survey"):

        files = question.split()[1:]

        result = generate_survey(files, user_id=current_user.id)

    else:
        result = answer_question(question, user_id=current_user.id)

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

    filename = Path(file.filename or "").name

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a PDF file."
        )

    user_papers_dir = PAPERS_DIR / f"user_{current_user.id}"
    user_papers_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    file_path = user_papers_dir / filename

    with file_path.open(
        "wb"
    ) as buffer:

        shutil.copyfileobj(
            file.file,
            buffer
        )

    try:
        from research import index_uploaded_paper

        index_uploaded_paper(
            file_path=file_path,
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
            detail=f"Unable to index uploaded paper: {error}",
        ) from error

    paper = UploadedPaper(
        user_id=current_user.id,
        filename=filename,
        filepath=str(file_path)
    )

    db.add(paper)
    db.commit()
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
    "/favorites/{favorite_id}",
    response_model=MessageResponse,
    tags=["Favorites"],
    summary="Delete one favorite for the current user",
)
def delete_favorite(
    favorite_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    favorite = (
        db.query(Favorite)
        .filter(Favorite.id == favorite_id)
        .first()
    )

    if favorite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found.",
        )

    if favorite.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this favorite.",
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
