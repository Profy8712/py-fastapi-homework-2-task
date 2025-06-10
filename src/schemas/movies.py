from datetime import date, timedelta, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, constr, validator, root_validator

# Базовые схемы для связанных сущностей

class GenreSchema(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True

class ActorSchema(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True

class LanguageSchema(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True

class CountrySchema(BaseModel):
    id: int
    code: str
    name: Optional[str]

    class Config:
        orm_mode = True

# ===== СХЕМЫ ДЛЯ MOVIE =====

class MovieListItemSchema(BaseModel):
    id: int
    name: str
    date: date
    score: float
    overview: str

    class Config:
        orm_mode = True

class MovieListResponseSchema(BaseModel):
    movies: List[MovieListItemSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int

# Для детального отображения фильма
class MovieDetailSchema(BaseModel):
    id: int
    name: str
    date: date
    score: float
    overview: str
    status: str
    budget: float
    revenue: float
    country: CountrySchema
    genres: List[GenreSchema]
    actors: List[ActorSchema]
    languages: List[LanguageSchema]

    class Config:
        orm_mode = True

# Схема для создания фильма (POST)
class MovieCreateSchema(BaseModel):
    name: constr(max_length=255)
    date: date
    score: float = Field(..., ge=0, le=100)
    overview: str
    status: str
    budget: float = Field(..., ge=0)
    revenue: float = Field(..., ge=0)
    country: constr(min_length=3, max_length=3)
    genres: List[constr(strip_whitespace=True, min_length=1)]
    actors: List[constr(strip_whitespace=True, min_length=1)]
    languages: List[constr(strip_whitespace=True, min_length=1)]

    @validator('status')
    def status_check(cls, v):
        allowed = {"Released", "Post Production", "In Production"}
        if v not in allowed:
            raise ValueError(f"Status must be one of {allowed}")
        return v

    @validator('date')
    def date_not_far_future(cls, v):
        one_year_later = date.today() + timedelta(days=366)
        if v > one_year_later:
            raise ValueError("Date must not be more than one year in the future.")
        return v

# PATCH (обновление фильма, все поля опциональны)
class MovieUpdateSchema(BaseModel):
    name: Optional[constr(max_length=255)] = None
    date: Optional[date] = None
    score: Optional[float] = Field(None, ge=0, le=100)
    overview: Optional[str] = None
    status: Optional[str] = None
    budget: Optional[float] = Field(None, ge=0)
    revenue: Optional[float] = Field(None, ge=0)

    @validator('status')
    def status_check(cls, v):
        if v is None:
            return v
        allowed = {"Released", "Post Production", "In Production"}
        if v not in allowed:
            raise ValueError(f"Status must be one of {allowed}")
        return v

    @validator('date')
    def date_not_far_future(cls, v):
        if v is None:
            return v
        one_year_later = date.today() + timedelta(days=366)
        if v > one_year_later:
            raise ValueError("Date must not be more than one year in the future.")
        return v

    class Config:
        extra = 'forbid'

