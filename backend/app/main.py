from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from . import models, schemas
from .database import Base, engine, get_db
from .services.conversation import (
    can_publish,
    candidate_reply,
    detect_intent,
    employer_reply,
    update_candidate_profile,
    update_employer_profile,
)
from .services.matching import match_profiles, rank_jobs, summarize_match
from .services.llm import generate_reply


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Job Talk API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_chat_or_404(db: Session, chat_id: int) -> models.Chat:
    chat = db.scalar(
        select(models.Chat)
        .where(models.Chat.id == chat_id)
        .options(selectinload(models.Chat.messages), selectinload(models.Chat.job_post))
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


def serialize_chat(chat: models.Chat) -> schemas.ChatOut:
    output = schemas.ChatOut.model_validate(chat)
    output.can_publish = bool(
        chat.intent == "employer"
        and chat.job_post
        and can_publish(chat.job_post.target_profile, chat.job_post.title)
        and not chat.job_post.published
    )
    return output


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/login", response_model=schemas.UserOut)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    user = db.scalar(select(models.User).where(models.User.email == email))
    if not user:
        user = models.User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@app.get("/api/chats", response_model=list[schemas.ChatSummary])
def list_chats(user_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(models.Chat).where(models.Chat.user_id == user_id).order_by(models.Chat.created_at.desc())
    ).all()


@app.post("/api/chats", response_model=schemas.ChatOut, status_code=status.HTTP_201_CREATED)
def create_chat(user_id: int, db: Session = Depends(get_db)):
    if not db.get(models.User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    chat = models.Chat(user_id=user_id)
    db.add(chat)
    db.flush()
    db.add(
        models.Message(
            chat_id=chat.id,
            sender="assistant",
            content="Hi! Are you looking for a job, or looking for someone to hire?",
        )
    )
    db.commit()
    return serialize_chat(get_chat_or_404(db, chat.id))


@app.get("/api/chats/{chat_id}", response_model=schemas.ChatOut)
def get_chat(chat_id: int, db: Session = Depends(get_db)):
    return serialize_chat(get_chat_or_404(db, chat_id))


@app.post("/api/chats/{chat_id}/messages", response_model=schemas.MessageResponse)
def send_message(chat_id: int, payload: schemas.MessageCreate, db: Session = Depends(get_db)):
    chat = get_chat_or_404(db, chat_id)
    text = payload.content.strip()
    db.add(models.Message(chat_id=chat.id, sender="user", content=text))

    if not chat.intent:
        chat.intent = detect_intent(text)
        if not chat.intent:
            reply = "I can help with either path. Are you looking for a job, or looking for someone to hire?"
        elif chat.intent == "employer":
            chat.profile, details = update_employer_profile(chat.profile, text)
            job = models.JobPost(
                chat_id=chat.id,
                user_id=chat.user_id,
                title=details.get("title") or "Untitled role",
                description=text,
                target_profile=chat.profile,
            )
            db.add(job)
            reply = employer_reply(chat.profile, can_publish(chat.profile, job.title))
        else:
            chat.profile = update_candidate_profile(chat.profile, text)
            reply = candidate_reply(chat.profile, False)
    elif chat.intent == "employer":
        chat.profile, details = update_employer_profile(chat.profile, text)
        job = chat.job_post
        if not job:
            job = models.JobPost(chat_id=chat.id, user_id=chat.user_id)
            db.add(job)
        if details.get("title"):
            job.title = details["title"]
        job.description = f"{job.description}\n{text}".strip()
        job.target_profile = chat.profile
        reply = employer_reply(chat.profile, can_publish(chat.profile, job.title))
    else:
        chat.profile = update_candidate_profile(chat.profile, text)
        published_jobs = db.scalars(select(models.JobPost).where(models.JobPost.published.is_(True))).all()
        reply = candidate_reply(chat.profile, bool(published_jobs and len(chat.profile) >= 2))

    reply = generate_reply(chat.intent, chat.profile, text, reply)
    assistant_message = models.Message(chat_id=chat.id, sender="assistant", content=reply)
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    chat = get_chat_or_404(db, chat_id)

    recommendations = []
    if chat.intent == "candidate" and len(chat.profile) >= 2:
        jobs = db.scalars(select(models.JobPost).where(models.JobPost.published.is_(True))).all()
        for job, result in rank_jobs(chat.profile, jobs):
            recommendations.append(
                schemas.RecommendationOut(
                    job=schemas.JobOut.model_validate(job),
                    match_score=result["overall_score"],
                    explanation=summarize_match(result),
                )
            )
    return schemas.MessageResponse(
        chat=serialize_chat(chat), assistant_message=assistant_message, recommendations=recommendations
    )


@app.post("/api/jobs/{job_id}/publish", response_model=schemas.JobOut)
def publish_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(models.JobPost, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not can_publish(job.target_profile, job.title):
        raise HTTPException(status_code=400, detail="Add a role title and at least two important criteria before publishing")
    job.published = True
    job.chat.status = "published"
    db.add(
        models.Message(
            chat_id=job.chat_id,
            sender="assistant",
            content=f"{job.title} is now published and visible to candidates.",
        )
    )
    db.commit()
    db.refresh(job)
    return job


@app.get("/api/jobs", response_model=list[schemas.JobOut])
def list_published_jobs(db: Session = Depends(get_db)):
    return db.scalars(
        select(models.JobPost).where(models.JobPost.published.is_(True)).order_by(models.JobPost.created_at.desc())
    ).all()


@app.get("/api/chats/{chat_id}/recommendations", response_model=list[schemas.RecommendationOut])
def get_recommendations(chat_id: int, db: Session = Depends(get_db)):
    chat = get_chat_or_404(db, chat_id)
    if chat.intent != "candidate":
        return []
    jobs = db.scalars(select(models.JobPost).where(models.JobPost.published.is_(True))).all()
    return [
        schemas.RecommendationOut(
            job=schemas.JobOut.model_validate(job),
            match_score=result["overall_score"],
            explanation=summarize_match(result),
        )
        for job, result in rank_jobs(chat.profile, jobs)
    ]


@app.post("/api/jobs/{job_id}/apply", response_model=schemas.ApplicationOut, status_code=status.HTTP_201_CREATED)
def apply(job_id: int, payload: schemas.ApplyRequest, db: Session = Depends(get_db)):
    job = db.get(models.JobPost, job_id)
    chat = db.get(models.Chat, payload.candidate_chat_id)
    if not job or not job.published:
        raise HTTPException(status_code=404, detail="Published job not found")
    if not chat or chat.intent != "candidate":
        raise HTTPException(status_code=400, detail="A candidate chat is required")
    result = match_profiles(chat.profile, job.target_profile)
    application = models.Application(
        candidate_user_id=chat.user_id,
        candidate_chat_id=chat.id,
        job_post_id=job.id,
        candidate_profile=chat.profile,
        match_result=result,
    )
    db.add(application)
    db.add(
        models.Message(
            chat_id=chat.id,
            sender="assistant",
            content=f"Your application for {job.title} has been submitted. Your profile was shared directly — no extra form needed.",
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="You have already applied for this role")
    db.refresh(application)
    return application


@app.get("/api/applications", response_model=list[schemas.ApplicationOut])
def list_applications(job_id: int | None = None, user_id: int | None = None, db: Session = Depends(get_db)):
    query = select(models.Application).order_by(models.Application.created_at.desc())
    if job_id is not None:
        query = query.where(models.Application.job_post_id == job_id)
    if user_id is not None:
        query = query.where(models.Application.candidate_user_id == user_id)
    return db.scalars(query).all()
