from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, desc, update, delete, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database import get_db
from database.models import (
    MovieModel, CountryModel, GenreModel, ActorModel, LanguageModel,
    MoviesGenresModel, ActorsMoviesModel, MoviesLanguagesModel
)

from schemas.movies import (
    MovieListResponseSchema,
    MovieListItemSchema,
    MovieDetailSchema,
    MovieCreateSchema,
    MovieUpdateSchema
)

router = APIRouter(prefix="/movies", tags=["Movies"])

MOVIE_URL_PREFIX = "/theater/movies/"

def get_pagination_links(page, per_page, total_pages, url_prefix):
    prev_page = None
    next_page = None
    if page > 1:
        prev_page = f"{url_prefix}?page={page-1}&per_page={per_page}"
    if page < total_pages:
        next_page = f"{url_prefix}?page={page+1}&per_page={per_page}"
    return prev_page, next_page

@router.get("/", response_model=MovieListResponseSchema)
async def list_movies(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=20),
):
    total_items_result = await db.execute(select(func.count(MovieModel.id)))
    total_items = total_items_result.scalar()
    if total_items == 0 or (page - 1) * per_page >= total_items:
        raise HTTPException(status_code=404, detail="No movies found.")

    total_pages = (total_items + per_page - 1) // per_page

    movies_stmt = (
        select(MovieModel)
        .order_by(desc(MovieModel.id))
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(movies_stmt)
    movies = result.scalars().all()

    movies_list = [
        MovieListItemSchema.from_orm(movie)
        for movie in movies
    ]

    prev_page, next_page = get_pagination_links(page, per_page, total_pages, MOVIE_URL_PREFIX)

    return MovieListResponseSchema(
        movies=movies_list,
        prev_page=prev_page,
        next_page=next_page,
        total_pages=total_pages,
        total_items=total_items,
    )



@router.post("/", response_model=MovieDetailSchema, status_code=status.HTTP_201_CREATED)
async def create_movie(
    movie_data: MovieCreateSchema,
    db: AsyncSession = Depends(get_db),
):
    # Проверка на дубликат фильма
    stmt = select(MovieModel).where(
        MovieModel.name == movie_data.name,
        MovieModel.date == movie_data.date
    )
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"A movie with the name '{movie_data.name}' and release date '{movie_data.date}' already exists."
        )

    # Найти/создать страну
    stmt = select(CountryModel).where(CountryModel.code == movie_data.country)
    result = await db.execute(stmt)
    country = result.scalar_one_or_none()
    if not country:
        country = CountryModel(code=movie_data.country, name=None)
        db.add(country)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=409, detail=f"Country with code '{movie_data.country}' already exists.")

    # Найти/создать жанры
    genres = []
    for genre_name in set(movie_data.genres):
        stmt = select(GenreModel).where(GenreModel.name == genre_name)
        res = await db.execute(stmt)
        genre = res.scalar_one_or_none()
        if not genre:
            genre = GenreModel(name=genre_name)
            db.add(genre)
            try:
                await db.flush()
            except IntegrityError:
                await db.rollback()
                raise HTTPException(status_code=409, detail=f"Genre '{genre_name}' already exists.")
        genres.append(genre)

    # Найти/создать актёров
    actors = []
    for actor_name in set(movie_data.actors):
        stmt = select(ActorModel).where(ActorModel.name == actor_name)
        res = await db.execute(stmt)
        actor = res.scalar_one_or_none()
        if not actor:
            actor = ActorModel(name=actor_name)
            db.add(actor)
            try:
                await db.flush()
            except IntegrityError:
                await db.rollback()
                raise HTTPException(status_code=409, detail=f"Actor '{actor_name}' already exists.")
        actors.append(actor)

    # Найти/создать языки
    languages = []
    for lang_name in set(movie_data.languages):
        stmt = select(LanguageModel).where(LanguageModel.name == lang_name)
        res = await db.execute(stmt)
        lang = res.scalar_one_or_none()
        if not lang:
            lang = LanguageModel(name=lang_name)
            db.add(lang)
            try:
                await db.flush()
            except IntegrityError:
                await db.rollback()
                raise HTTPException(status_code=409, detail=f"Language '{lang_name}' already exists.")
        languages.append(lang)

    # Создать фильм
    movie = MovieModel(
        name=movie_data.name,
        date=movie_data.date,
        score=movie_data.score,
        overview=movie_data.overview,
        status=movie_data.status,
        budget=movie_data.budget,
        revenue=movie_data.revenue,
        country_id=country.id,
        genres=genres,
        actors=actors,
        languages=languages,
    )
    db.add(movie)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A movie with such parameters already exists.")

    # refresh(country) больше не нужен
    return await get_movie_details(movie.id, db=db)


@router.get("/{movie_id}/", response_model=MovieDetailSchema)
async def get_movie_details(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(MovieModel)
        .options(
            joinedload(MovieModel.country),
            joinedload(MovieModel.genres),
            joinedload(MovieModel.actors),
            joinedload(MovieModel.languages),
        )
        .where(MovieModel.id == movie_id)
    )
    result = await db.execute(stmt)
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")
    return MovieDetailSchema.from_orm(movie)

@router.delete("/{movie_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_movie(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")
    await db.delete(movie)
    await db.commit()
    return

@router.patch("/{movie_id}/", status_code=status.HTTP_200_OK)
async def update_movie(
    movie_id: int,
    movie_data: MovieUpdateSchema,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")

    updated = False
    try:
        data = movie_data.dict(exclude_unset=True)
        for key, value in data.items():
            setattr(movie, key, value)
            updated = True
        if updated:
            await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

    return {"detail": "Movie updated successfully."}
