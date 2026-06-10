from datetime import datetime
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from auth import MAX_BCRYPT_PASSWORD_BYTES


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=100,
        pattern=r"^[A-Za-z0-9_]+$",
        description="Unique username containing letters, numbers, or underscores.",
    )
    email: str = Field(
        ...,
        min_length=5,
        max_length=200,
        description="Unique email address for the account.",
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Password used only for hashing. It is never stored directly.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "researcher01",
                "email": "researcher01@example.com",
                "password": "StrongPass123",
            }
        }
    }

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized_email = value.strip().lower()

        if not EMAIL_PATTERN.fullmatch(normalized_email):
            raise ValueError("Enter a valid email address.")

        return normalized_email

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_BCRYPT_PASSWORD_BYTES:
            raise ValueError("Password must be 72 bytes or fewer.")

        if value.strip() != value:
            raise ValueError("Password cannot start or end with spaces.")

        if not any(character.islower() for character in value):
            raise ValueError("Password must contain at least one lowercase letter.")

        if not any(character.isupper() for character in value):
            raise ValueError("Password must contain at least one uppercase letter.")

        if not any(character.isdigit() for character in value):
            raise ValueError("Password must contain at least one number.")

        return value


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    message: str


class LoginRequest(BaseModel):
    username_or_email: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="Username or email address for the account.",
    )
    password: str = Field(
        ...,
        min_length=1,
        description="Account password.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "username_or_email": "researcher01@example.com",
                "password": "StrongPass123",
            }
        }
    }

    @field_validator("username_or_email")
    @classmethod
    def normalize_username_or_email(cls, value: str) -> str:
        return value.strip()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class FavoriteCreate(BaseModel):
    paper_name: str = Field(
        ...,
        min_length=1,
        max_length=300,
        description="Paper name to save as a favorite.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "paper_name": "attention-is-all-you-need.pdf",
            }
        }
    }

    @field_validator("paper_name")
    @classmethod
    def normalize_paper_name(cls, value: str) -> str:
        normalized_name = value.strip()
        if not normalized_name:
            raise ValueError("Paper name cannot be empty.")

        return normalized_name


class FavoriteResponse(BaseModel):
    id: int
    paper_name: str
    saved_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UploadedPaperResponse(BaseModel):
    id: int
    filename: str
    filepath: str
    upload_time: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatHistoryResponse(BaseModel):
    id: int
    question: str
    answer: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SearchHistoryResponse(BaseModel):
    id: int
    query: str
    searched_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QueryLogResponse(BaseModel):
    id: int
    query: str
    response_time: str
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
