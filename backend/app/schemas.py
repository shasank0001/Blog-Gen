from pydantic import BaseModel, EmailStr, UUID4
from typing import Optional, List
from datetime import datetime
from app.core.models import DocumentStatus

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: UUID4
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    sub: Optional[str] = None

class BinBase(BaseModel):
    name: str
    description: Optional[str] = None

class BinCreate(BinBase):
    pass

class BinUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class BinResponse(BinBase):
    id: UUID4
    user_id: UUID4
    created_at: datetime

    class Config:
        from_attributes = True

class DocumentResponse(BaseModel):
    id: UUID4
    filename: str
    status: DocumentStatus
    created_at: datetime
    error_message: Optional[str] = None

    class Config:
        from_attributes = True

class ProfileBase(BaseModel):
    name: str
    description: Optional[str] = None
    tone_urls: Optional[List[str]] = None

class ProfileCreate(ProfileBase):
    pass

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tone_urls: Optional[List[str]] = None
    style_dna: Optional[dict] = None

class ProfileResponse(ProfileBase):
    id: UUID4
    user_id: UUID4
    style_dna: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True
