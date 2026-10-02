import logging
import secrets
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import func, select, text, update
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
from .data_retention import delete_candidate_data
from .experiment import record_event
from .services.conversation import (
    apply_ai_role_updates,
    can_publish,
    candidate_reply,
    employer_reply,
    expected_candidate_criterion,
    expected_employer_skill,
    summarize_job_requirements,
    update_candidate_turn,
    update_employer_profile,
    wants_to_publish,
)
from .services.context import build_chat_context
from .services.matching import match_profiles, rank_jobs, summarize_match
from .services.ai import generate_reply, generate_turn
from .services.email import send_recruiter_login_code
from .settings import get_settings


settings = get_settings()
logger = logging.getLogger(__name__)
RECRUITER_CODE_REQUEST_MESSAGE = (
    "If this recruiter email is approved, a sign-in code has been sent. "
    "New access requests wait for approval."
)
app = FastAPI(
    title="Job Talk API",
    version="0.1.0",
    docs_url="/docs" if settings.api_docs_enabled else None,
    redoc_url="/redoc" if settings.api_docs_enabled else None,
    openapi_url="/openapi.json" if settings.api_docs_enabled else None,
)
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
        and chat.status == "draft"
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


@app.post("/api/experiment/visit", status_code=status.HTTP_204_NO_CONTENT)
def record_visit(
    x_job_talk_visitor: str = Header(
        min_length=16, max_length=100, pattern=r"^[A-Za-z0-9_-]+$"
    ),
    db: Session = Depends(get_db),
):
    record_event(db, "visit", x_job_talk_visitor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/auth/guest", response_model=schemas.AuthResponse, status_code=status.HTTP_201_CREATED)
def start_guest_session(
    payload: schemas.GuestSessionRequest,
    x_job_talk_visitor: str | None = Header(
        default=None, min_length=16, max_length=100, pattern=r"^[A-Za-z0-9_-]+$"
    ),
    db: Session = Depends(get_db),
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
                f"You're applying for {job.title}. "
                f"{summarize_job_requirements(job.title, job.target_profile)} "
                "Tell me which requirement you can meet and give one work example."
            ),
        )
    )
    record_event(
        db,
        "application_started",
        x_job_talk_visitor,
        subject_type="chat",
        subject_id=chat.id,
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
        latest_code = db.scalar(
            select(models.RecruiterLoginCode)
            .where(models.RecruiterLoginCode.user_id == user.id)
            .order_by(models.RecruiterLoginCode.created_at.desc())
            .limit(1)
        )
        latest_created_at = latest_code.created_at if latest_code else None
        if latest_created_at and latest_created_at.tzinfo is None:
            latest_created_at = latest_created_at.replace(tzinfo=timezone.utc)
        requests_in_last_hour = db.scalar(
            select(func.count(models.RecruiterLoginCode.id)).where(
                models.RecruiterLoginCode.user_id == user.id,
                models.RecruiterLoginCode.created_at >= now - timedelta(hours=1),
            )
        ) or 0
        request_is_limited = bool(
            (
                latest_created_at
                and latest_created_at
                > now - timedelta(seconds=settings.recruiter_code_request_cooldown_seconds)
            )
            or requests_in_last_hour >= settings.recruiter_code_request_max_per_hour
        )
        if request_is_limited:
            return schemas.MessageResponseStatus(
                message=RECRUITER_CODE_REQUEST_MESSAGE
            )
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
        message=RECRUITER_CODE_REQUEST_MESSAGE
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


@app.delete("/api/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate_account(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "candidate":
        raise HTTPException(
            status_code=403,
            detail="Recruiters must contact support to delete an account with hiring records",
        )
    delete_candidate_data(db, [current_user.id])
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/chats", response_model=list[schemas.ChatSummary])
def list_chats(
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return db.scalars(
        select(models.Chat)
        .where(models.Chat.user_id == current_user.id)
        .options(
            selectinload(models.Chat.job_post),
            selectinload(models.Chat.target_job),
        )
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

    target_profile = chat.target_job.target_profile if chat.target_job else None
    last_assistant_text = next(
        (
            message.content
            for message in reversed(chat.messages)
            if message.sender == "assistant"
        ),
        "",
    )
    expected_criterion = expected_candidate_criterion(
        target_profile, last_assistant_text
    )
    employer_profile = chat.job_post.target_profile if chat.job_post else chat.profile
    expected_skill = expected_employer_skill(employer_profile, last_assistant_text)
    employer_profile_before = deepcopy(employer_profile or {})
    employer_title_before = chat.job_post.title if chat.job_post else None
    candidate_answer_status = None
    interpret_employer_answer = False

    expected_intent = "candidate" if current_user.role == "candidate" else "employer"
    if chat.intent and chat.intent != expected_intent:
        raise HTTPException(status_code=403, detail="This conversation belongs to another account type")

    if not chat.intent:
        chat.intent = expected_intent
        if chat.intent == "employer":
            interpret_employer_answer = True
            chat.profile, details = update_employer_profile(
                chat.profile, text, expected_skill=expected_skill
            )
            job = models.JobPost(
                chat=chat,
                user_id=chat.user_id,
                title=details.get("title") or "Untitled role",
                description=text,
                target_profile=chat.profile,
            )
            db.add(job)
            reply = employer_reply(
                chat.profile,
                can_publish(chat.profile, job.title),
                job.title,
            )
        else:
            chat.profile, candidate_answer_status = update_candidate_turn(
                chat.profile,
                text,
                target_profile,
                expected_criterion,
            )
    elif chat.intent == "employer":
        job = chat.job_post
        if wants_to_publish(text):
            if not job:
                reply = employer_reply({}, False)
            elif job.published:
                reply = f"{job.title} is already published and visible to candidates."
            elif can_publish(job.target_profile, job.title):
                reply = (
                    f"{job.title} is ready for your final review. "
                    "Use the Publish job button when the criteria are correct."
                )
            else:
                reply = (
                    "The role is not ready to publish yet. "
                    + employer_reply(job.target_profile, False, job.title)
                )
        else:
            interpret_employer_answer = True
            chat.profile, details = update_employer_profile(
                chat.profile,
                text,
                job.title if job else None,
                expected_skill,
            )
            if not job:
                job = models.JobPost(chat=chat, user_id=chat.user_id)
                db.add(job)
            if details.get("title"):
                job.title = details["title"]
            job.description = f"{job.description}\n{text}".strip()
            job.target_profile = chat.profile
            reply = employer_reply(
                chat.profile,
                can_publish(chat.profile, job.title),
                job.title,
            )
    else:
        chat.profile, candidate_answer_status = update_candidate_turn(
            chat.profile,
            text,
            target_profile,
            expected_criterion,
        )

    context = build_chat_context(chat)
    if chat.intent == "candidate":
        target_profile = context["job"]["criteria"] if context["job"] else None
        reply = candidate_reply(
            context["draft"], target_profile, candidate_answer_status
        )
    if interpret_employer_answer:
        turn = generate_turn(context, chat.intent, text, reply)
        reply = turn.reply
        if turn.role_updates is not None:
            validated_profile, details = apply_ai_role_updates(
                employer_profile_before,
                employer_title_before,
                [update.model_dump() for update in turn.role_updates],
                text,
                expected_skill,
            )
            chat.profile = validated_profile
            job.target_profile = validated_profile
            job.title = details.get("title") or "Untitled role"
    else:
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
    if job.published:
        return job
    if not can_publish(job.target_profile, job.title):
        raise HTTPException(
            status_code=400,
            detail="Complete the guided role questions before publishing",
        )
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
    x_job_talk_visitor: str | None = Header(
        default=None, min_length=16, max_length=100, pattern=r"^[A-Za-z0-9_-]+$"
    ),
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
    db.flush()
    record_event(
        db,
        "application_submitted",
        x_job_talk_visitor,
        subject_type="application",
        subject_id=application.id,
    )
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
    x_job_talk_visitor: str | None = Header(
        default=None, min_length=16, max_length=100, pattern=r"^[A-Za-z0-9_-]+$"
    ),
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
        record_event(
            db,
            "comparison_opened",
            x_job_talk_visitor,
            subject_type="job",
            subject_id=job_id,
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return applications


@app.post("/api/experiment/feedback", response_model=schemas.MessageResponseStatus)
def submit_experiment_feedback(
    payload: schemas.FeedbackCreate,
    current_user: models.User = Depends(get_current_user),
    x_job_talk_visitor: str = Header(
        min_length=16, max_length=100, pattern=r"^[A-Za-z0-9_-]+$"
    ),
    db: Session = Depends(get_db),
):
    if payload.kind == "candidate":
        if current_user.role != "candidate":
            raise HTTPException(
                status_code=403,
                detail="Candidate feedback requires candidate access",
            )
        subject = db.scalar(
            select(models.Application.id).where(
                models.Application.id == payload.context_id,
                models.Application.candidate_user_id == current_user.id,
            )
        )
        subject_type = "application"
    else:
        if current_user.role != "recruiter":
            raise HTTPException(
                status_code=403,
                detail="Recruiter feedback requires recruiter access",
            )
        subject = db.scalar(
            select(models.JobPost.id).where(
                models.JobPost.id == payload.context_id,
                models.JobPost.user_id == current_user.id,
            )
        )
        subject_type = "job"
    if not subject:
        raise HTTPException(status_code=404, detail="Feedback context not found")
    record_event(
        db,
        f"{payload.kind}_feedback",
        x_job_talk_visitor,
        subject_type=subject_type,
        subject_id=payload.context_id,
        useful=payload.useful,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return schemas.MessageResponseStatus(message="Thank you for the feedback")
