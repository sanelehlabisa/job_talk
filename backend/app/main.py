import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from . import models, schemas
from .auth import (
    generate_recruiter_code,
    get_current_session,
    get_current_user,
    issue_session,
    recruiter_code_digest,
)
from .database import get_db
from .services.conversation import (
    can_publish,
    candidate_reply,
    employer_reply,
    update_candidate_profile,
    update_employer_profile,
    wants_to_publish,
)
from .services.context import build_chat_context
from .services.matching import match_profiles, rank_jobs, summarize_match
from .services.ai import generate_reply
from .services.email import send_recruiter_login_code
from .settings import get_settings


settings = get_settings()
logger = logging.getLogger(__name__)
app = FastAPI(title="Job Talk API", version="0.1.0")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_chat_or_404(db: Session, chat_id: int, user_id: int) -> models.Chat:
    chat = db.scalar(
        select(models.Chat)
        .where(models.Chat.id == chat_id, models.Chat.user_id == user_id)
        .options(
            selectinload(models.Chat.messages),
            selectinload(models.Chat.job_post),
            selectinload(models.Chat.target_job),
        )
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


@app.get("/api/ready")
def readiness(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get("/api/public/jobs", response_model=list[schemas.JobOut])
def list_public_jobs(db: Session = Depends(get_db)):
    return db.scalars(
        select(models.JobPost)
        .where(models.JobPost.published.is_(True))
        .order_by(models.JobPost.created_at, models.JobPost.id)
    ).all()


@app.get("/api/public/jobs/{job_id}", response_model=schemas.JobOut)
def get_public_job(job_id: int, db: Session = Depends(get_db)):
    job = db.scalar(
        select(models.JobPost).where(
            models.JobPost.id == job_id,
            models.JobPost.published.is_(True),
        )
    )
    if not job:
        raise HTTPException(status_code=404, detail="Published job not found")
    return job


@app.post("/api/auth/guest", response_model=schemas.AuthResponse, status_code=status.HTTP_201_CREATED)
def start_guest_session(
    payload: schemas.GuestSessionRequest, db: Session = Depends(get_db)
):
    job = db.scalar(
        select(models.JobPost).where(
            models.JobPost.id == payload.job_id,
            models.JobPost.published.is_(True),
        )
    )
    if not job:
        raise HTTPException(status_code=404, detail="Published job not found")
    guest_id = secrets.token_urlsafe(24)
    user = models.User(
        email=f"guest-{guest_id}@guest.invalid",
        role="candidate",
        approval_status="not_required",
    )
    db.add(user)
    db.flush()
    chat = models.Chat(user_id=user.id, intent="candidate", target_job_id=job.id)
    db.add(chat)
    db.flush()
    db.add(
        models.Message(
            chat_id=chat.id,
            sender="assistant",
            content=(
                f"You're applying for {job.title}. Tell me about the work you can do "
                "and the experience you have that fits this role."
            ),
        )
    )
    return issue_session(db, user)


@app.post(
    "/api/auth/recruiter/request-code",
    response_model=schemas.MessageResponseStatus,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_recruiter_code(
    payload: schemas.RecruiterEmailRequest, db: Session = Depends(get_db)
):
    email = str(payload.email).lower()
    user = db.scalar(select(models.User).where(models.User.email == email))
    if not user:
        user = models.User(email=email, role="recruiter", approval_status="pending")
        db.add(user)
        db.commit()
        db.refresh(user)

    if user.role == "recruiter" and user.approval_status == "approved":
        now = datetime.now(timezone.utc)
        db.execute(
            update(models.RecruiterLoginCode)
            .where(
                models.RecruiterLoginCode.user_id == user.id,
                models.RecruiterLoginCode.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        code = generate_recruiter_code()
        db.add(
            models.RecruiterLoginCode(
                user_id=user.id,
                code_hash=recruiter_code_digest(user.id, code),
                expires_at=now + timedelta(minutes=settings.recruiter_code_ttl_minutes),
            )
        )
        db.commit()
        try:
            send_recruiter_login_code(email, code)
        except Exception:
            logger.exception("Could not deliver recruiter login code")

    return schemas.MessageResponseStatus(
        message=(
            "If this recruiter email is approved, a sign-in code has been sent. "
            "New access requests wait for approval."
        )
    )


@app.post("/api/auth/recruiter/verify-code", response_model=schemas.AuthResponse)
def verify_recruiter_code(
    payload: schemas.RecruiterCodeVerifyRequest, db: Session = Depends(get_db)
):
    email = str(payload.email).lower()
    user = db.scalar(select(models.User).where(models.User.email == email))
    now = datetime.now(timezone.utc)
    code_record = None
    if user and user.role == "recruiter" and user.approval_status == "approved":
        code_record = db.scalar(
            select(models.RecruiterLoginCode)
            .where(
                models.RecruiterLoginCode.user_id == user.id,
                models.RecruiterLoginCode.consumed_at.is_(None),
            )
            .order_by(models.RecruiterLoginCode.created_at.desc())
            .limit(1)
        )

    valid = False
    if code_record:
        expires_at = code_record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        valid = (
            expires_at > now
            and code_record.attempt_count < settings.recruiter_code_max_attempts
            and secrets.compare_digest(
                code_record.code_hash,
                recruiter_code_digest(user.id, payload.code),
            )
        )
        if not valid:
            code_record.attempt_count += 1
            if code_record.attempt_count >= settings.recruiter_code_max_attempts:
                code_record.consumed_at = now
            db.commit()

    if not valid:
        raise HTTPException(status_code=401, detail="Invalid or expired sign-in code")
    code_record.consumed_at = now
    return issue_session(db, user)


@app.get("/api/auth/me", response_model=schemas.UserOut)
def current_account(current_user: models.User = Depends(get_current_user)):
    return current_user


@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current_session: models.AuthSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    db.delete(current_session)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/chats", response_model=list[schemas.ChatSummary])
def list_chats(
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return db.scalars(
        select(models.Chat)
        .where(models.Chat.user_id == current_user.id)
        .order_by(models.Chat.created_at.desc())
    ).all()


@app.post("/api/chats", response_model=schemas.ChatOut, status_code=status.HTTP_201_CREATED)
def create_chat(
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if current_user.role == "candidate" and db.scalar(
        select(models.Chat.id).where(models.Chat.user_id == current_user.id).limit(1)
    ):
        raise HTTPException(status_code=409, detail="This guest session already has a conversation")
    intent = "candidate" if current_user.role == "candidate" else "employer"
    chat = models.Chat(
        user_id=current_user.id,
        intent=intent,
        status="draft" if intent == "employer" else "active",
    )
    db.add(chat)
    db.flush()
    db.add(
        models.Message(
            chat_id=chat.id,
            sender="assistant",
            content=(
                "Tell me about the work you can do and the experience you have."
                if intent == "candidate"
                else "Tell me about the role and the person you need to hire."
            ),
        )
    )
    db.commit()
    return serialize_chat(get_chat_or_404(db, chat.id, current_user.id))


@app.get("/api/chats/{chat_id}", response_model=schemas.ChatOut)
def get_chat(
    chat_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return serialize_chat(get_chat_or_404(db, chat_id, current_user.id))


@app.post("/api/chats/{chat_id}/messages", response_model=schemas.MessageResponse)
def send_message(
    chat_id: int,
    payload: schemas.MessageCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = get_chat_or_404(db, chat_id, current_user.id)
    if chat.status == "submitted":
        raise HTTPException(status_code=409, detail="This application has already been submitted")
    if chat.status == "closed":
        raise HTTPException(status_code=409, detail="This recruitment is closed")
    text = payload.content.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Message cannot be empty")
    db.add(models.Message(chat_id=chat.id, sender="user", content=text))

    expected_intent = "candidate" if current_user.role == "candidate" else "employer"
    if chat.intent and chat.intent != expected_intent:
        raise HTTPException(status_code=403, detail="This conversation belongs to another account type")

    if not chat.intent:
        chat.intent = expected_intent
        if chat.intent == "employer":
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
    elif chat.intent == "employer":
        job = chat.job_post
        if wants_to_publish(text):
            if not job:
                reply = "Describe the role and at least two important criteria before publishing."
            elif job.published:
                reply = f"{job.title} is already published and visible to candidates."
            elif can_publish(job.target_profile, job.title):
                job.published = True
                chat.status = "published"
                reply = f"{job.title} is now published and visible to candidates."
            else:
                reply = (
                    "The role is not ready to publish yet. "
                    + employer_reply(job.target_profile, False)
                )
        else:
            chat.profile, details = update_employer_profile(chat.profile, text)
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

    context = build_chat_context(chat)
    if chat.intent == "candidate":
        target_profile = context["job"]["criteria"] if context["job"] else None
        reply = candidate_reply(context["draft"], target_profile)
    reply = generate_reply(context, chat.intent, text, reply)
    assistant_message = models.Message(chat_id=chat.id, sender="assistant", content=reply)
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    chat = get_chat_or_404(db, chat_id, current_user.id)

    recommendations = []
    if chat.intent == "candidate" and len(chat.profile) >= 2:
        jobs = db.scalars(
            select(models.JobPost).where(
                models.JobPost.published.is_(True),
                *(
                    (models.JobPost.id == chat.target_job_id,)
                    if chat.target_job_id is not None
                    else ()
                ),
            )
        ).all()
        for job, result in rank_jobs(chat.profile, jobs):
            recommendations.append(
                schemas.RecommendationOut(
                    job=schemas.JobOut.model_validate(job),
                    match_score=result["overall_score"],
                    explanation=summarize_match(result),
                    criteria=result["criteria"],
                )
            )
    return schemas.MessageResponse(
        chat=serialize_chat(chat), assistant_message=assistant_message, recommendations=recommendations
    )


@app.post("/api/jobs/{job_id}/publish", response_model=schemas.JobOut)
def publish_job(
    job_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "recruiter":
        raise HTTPException(status_code=403, detail="Recruiter access required")
    job = db.scalar(
        select(models.JobPost).where(
            models.JobPost.id == job_id, models.JobPost.user_id == current_user.id
        )
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.chat.status == "closed":
        raise HTTPException(status_code=409, detail="Closed recruitment cannot be republished")
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


@app.post("/api/jobs/{job_id}/close", response_model=schemas.JobOut)
def close_job(
    job_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "recruiter":
        raise HTTPException(status_code=403, detail="Recruiter access required")
    job = db.scalar(
        select(models.JobPost).where(
            models.JobPost.id == job_id, models.JobPost.user_id == current_user.id
        )
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.chat.status == "closed":
        return job
    if not job.published:
        raise HTTPException(status_code=409, detail="Only published recruitment can be closed")
    job.published = False
    job.chat.status = "closed"
    db.add(
        models.Message(
            chat_id=job.chat_id,
            sender="assistant",
            content=(
                f"Recruitment for {job.title} is now closed. New applications are stopped, "
                "and the submitted candidate snapshots are preserved for review."
            ),
        )
    )
    db.commit()
    db.refresh(job)
    return job


@app.get("/api/jobs", response_model=list[schemas.JobOut])
def list_published_jobs(
    _: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return db.scalars(
        select(models.JobPost).where(models.JobPost.published.is_(True)).order_by(models.JobPost.created_at.desc())
    ).all()


@app.get("/api/chats/{chat_id}/recommendations", response_model=list[schemas.RecommendationOut])
def get_recommendations(
    chat_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = get_chat_or_404(db, chat_id, current_user.id)
    if chat.intent != "candidate":
        return []
    jobs = db.scalars(
        select(models.JobPost).where(
            models.JobPost.published.is_(True),
            *(
                (models.JobPost.id == chat.target_job_id,)
                if chat.target_job_id is not None
                else ()
            ),
        )
    ).all()
    return [
        schemas.RecommendationOut(
            job=schemas.JobOut.model_validate(job),
            match_score=result["overall_score"],
            explanation=summarize_match(result),
            criteria=result["criteria"],
        )
        for job, result in rank_jobs(chat.profile, jobs)
    ]


@app.post("/api/jobs/{job_id}/apply", response_model=schemas.ApplicationOut, status_code=status.HTTP_201_CREATED)
def apply(
    job_id: int,
    payload: schemas.ApplyRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "candidate":
        raise HTTPException(status_code=403, detail="Candidate access required")
    job = db.get(models.JobPost, job_id)
    chat = db.scalar(
        select(models.Chat).where(
            models.Chat.id == payload.candidate_chat_id,
            models.Chat.user_id == current_user.id,
        )
    )
    if not job or not job.published:
        raise HTTPException(status_code=404, detail="Published job not found")
    if not chat:
        raise HTTPException(status_code=404, detail="Candidate chat not found")
    if chat.intent != "candidate":
        raise HTTPException(status_code=400, detail="A candidate chat is required")
    if chat.target_job_id is not None and chat.target_job_id != job.id:
        raise HTTPException(status_code=403, detail="This guest session belongs to another job")
    candidate_name = payload.candidate_name.strip()
    preferred_contact = payload.preferred_contact.strip()
    if len(candidate_name) < 2 or len(preferred_contact) < 3:
        raise HTTPException(status_code=422, detail="Add your name and preferred contact details")
    submitted_at = datetime.now(timezone.utc)
    result = match_profiles(chat.profile, job.target_profile)
    profile_snapshot = {
        **chat.profile,
        "candidate_details": {
            "name": candidate_name,
            "preferred_contact": preferred_contact,
        },
        "consent": {
            "share_with_recruiter": True,
            "captured_at": submitted_at.isoformat(),
        },
    }
    application = models.Application(
        candidate_user_id=chat.user_id,
        candidate_chat_id=chat.id,
        job_post_id=job.id,
        candidate_profile=profile_snapshot,
        match_result=result,
    )
    chat.status = "submitted"
    db.add(application)
    db.add(
        models.Message(
            chat_id=chat.id,
            sender="assistant",
            content=(
                f"Your application for {job.title} has been submitted. The recruiter can now "
                "see your structured evidence and the contact details you approved."
            ),
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
def list_applications(
    job_id: int | None = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(models.Application).order_by(models.Application.created_at.desc())
    if job_id is not None:
        if current_user.role != "recruiter":
            raise HTTPException(status_code=403, detail="Recruiter access required")
        job = db.scalar(
            select(models.JobPost).where(
                models.JobPost.id == job_id, models.JobPost.user_id == current_user.id
            )
        )
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        query = query.where(models.Application.job_post_id == job_id)
    else:
        if current_user.role != "candidate":
            return []
        query = query.where(models.Application.candidate_user_id == current_user.id)
    applications = list(db.scalars(query).all())
    if job_id is not None:
        applications.sort(
            key=lambda item: (
                -float(item.match_result.get("overall_score", 0)),
                item.created_at,
                item.id,
            )
        )
    return applications
