import re
from collections.abc import Mapping

from .criteria import normalize_candidate_evidence, normalize_target_profile


SKILLS = {
    "python": "Python",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "react": "React",
    "vue": "Vue",
    "angular": "Angular",
    "node": "Node.js",
    "node.js": "Node.js",
    "java": "Java",
    "spring": "Spring",
    "c#": "C#",
    ".net": ".NET",
    "go": "Go",
    "golang": "Go",
    "sql": "SQL",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "figma": "Figma",
    "sales": "Sales",
    "marketing": "Marketing",
    "accounting": "Accounting",
    "cashier": "Cash handling",
    "customer service": "Customer service",
    "stock": "Stock handling",
    "inventory": "Inventory control",
    "packing": "Packing",
    "warehouse": "Warehouse work",
    "security": "Security work",
    "gardening": "Gardening",
    "retail": "Retail work",
    "hospitality": "Hospitality",
    "food preparation": "Food preparation",
    "machine operation": "Machine operation",
    "project management": "Project management",
    "welder": "Welding",
    "welding": "Welding",
    "electrician": "Electrical wiring",
    "electrical wiring": "Electrical wiring",
    "plumber": "Plumbing",
    "plumbing": "Plumbing",
    "leak repair": "Leak repair",
    "pipe fitting": "Pipe fitting",
    "geyser installation": "Geyser installation",
    "geyser repair": "Geyser repair",
    "carpenter": "Carpentry",
    "carpentry": "Carpentry",
    "bricklayer": "Bricklaying",
    "bricklaying": "Bricklaying",
    "cleaner": "Cleaner",
    "cleaning": "Cleaning",
    "driver": "Driving",
    "driving": "Driving",
    "forklift": "Forklift operation",
    "3-phase lathe": "3-phase lathe",
    "mechanic": "Mechanic",
    "cook": "Cook",
}


def detect_intent(text: str) -> str | None:
    lower = text.lower()
    candidate_phrases = ("looking for a job", "find a job", "need a job", "looking for work", "need work", "looking for employment", "job seeker", "i want a job", "hire me", "candidate")
    employer_phrases = ("looking to hire", "someone to hire", "need a developer", "need an engineer", "hiring", "recruit", "employer")
    hiring_pattern = r"\b(?:need|hire|hiring|find)\b.{0,45}\b(?:developer|engineer|designer|manager|analyst|specialist|assistant|accountant|welder|electrician|plumber|carpenter|bricklayer|cleaner|driver|operator|mechanic|cook|candidate|person|someone)\b"
    if any(phrase in lower for phrase in employer_phrases) or re.search(hiring_pattern, lower):
        return "employer"
    if any(phrase in lower for phrase in candidate_phrases):
        return "candidate"
    if re.search(r"\b(?:i am|i'm|im)\s+(?:an?\s+)?(?:welder|electrician|plumber|carpenter|bricklayer|cleaner|driver|operator|mechanic|cook)\b", lower):
        return "candidate"
    return None


def wants_to_publish(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9']+", " ", text.lower()).strip()
    return bool(
        re.fullmatch(
            r"(?:(?:i(?:'m| am)?|we(?:'re| are)?) )?"
            r"(?:am |are )?(?:done|finished|ready to publish)(?: now)?",
            normalized,
        )
        or normalized
        in {
            "publish",
            "publish it",
            "publish the job",
            "publish this job",
            "publish the role",
            "make it public",
            "make the job public",
            "make this job public",
            "the role is ready",
            "the job is ready",
        }
    )


def _skill_hits(text: str) -> list[tuple[str, str]]:
    lower = text.lower()
    found = []
    for needle, label in SKILLS.items():
        if re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", lower):
            key = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
            if key not in {item[0] for item in found}:
                found.append((key, label))
    return found


def _experience_scope_conflicts(text: str, requirement: dict | None) -> bool:
    """Reject an explicitly different known trade/tool as scoped experience.

    Bare follow-up durations and general experience criteria remain valid. This
    is a narrow grounding guard; richer language still needs model verification.
    """
    if not requirement:
        return False
    required = {key for key, _ in _skill_hits(
        f"{requirement.get('label', '')} {requirement.get('description', '')}"
    )}
    stated = {key for key, _ in _skill_hits(text)}
    return bool(required and stated and required.isdisjoint(stated))


NEGATION_PATTERN = re.compile(
    r"\b(?:no|not|never|without|cannot|can't|dont|don't|do not|haven't|have not|lack|lacking)\b",
    re.I,
)

CRITERION_STOP_WORDS = {
    "applicant",
    "applicants",
    "candidate",
    "experience",
    "important",
    "minimum",
    "preferred",
    "relevant",
    "required",
    "requirement",
    "should",
    "year",
    "years",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
}


def _criterion_terms(key: str, requirement: dict | None = None) -> set[str]:
    terms = {part for part in key.lower().split("_") if len(part) > 2}
    if key.endswith("ing"):
        terms.add(key[:-3])
    if key.endswith("ation"):
        terms.add(key[:-5])
    description = (requirement or {}).get("description", "")
    terms.update(
        token
        for token in re.findall(r"[a-z]+", description.lower())
        if len(token) > 4
        and token not in CRITERION_STOP_WORDS
    )
    return terms


def _criterion_denied(text: str, key: str, requirement: dict | None = None) -> bool:
    lower = text.lower().strip()
    # Willingness is not a denial; preserve other negatives in the same answer.
    lower = re.sub(r"\b(?:don't|dont|do not) mind\b", "am open to", lower)
    if not NEGATION_PATTERN.search(lower):
        return False
    if lower in {"no", "none", "not yet", "never", "i don't", "i do not"}:
        return True
    terms = _criterion_terms(key, requirement)
    clauses = re.split(r"\b(?:but|however|although)\b|[.;]", lower)
    general_terms = {
        "experience": r"\b(?:experience|years?)\b",
        "location": r"\b(?:location|based|located|relocate|commute)\b",
        "availability": r"\b(?:available|availability|start|notice)\b",
        "working_arrangement": r"\b(?:remote|hybrid|on-site|onsite)\b",
        "working_hours": r"\b(?:hours?|shifts?|weekdays?|weekends?|schedule)\b",
        "education": r"\b(?:degree|diploma|qualification|education|certificate|college|school)\b",
    }
    if key in general_terms:
        scoped_experience = bool(_skill_hits(
            f"{(requirement or {}).get('label', '')} {(requirement or {}).get('description', '')}"
        ))
        return any(NEGATION_PATTERN.search(clause) and re.search(general_terms[key], clause)
                   and (key != "experience" or not _skill_hits(clause)
                        or (scoped_experience and not _experience_scope_conflicts(clause, requirement)))
                   for clause in clauses)
    return any(
        NEGATION_PATTERN.search(clause)
        and (
            any(term in clause for term in terms)
            or (key == "experience" and "year" in clause)
            or (key == "availability" and "available" in clause)
            or (
                key == "education"
                and any(term in clause for term in ("degree", "diploma", "school", "college"))
            )
        )
        for clause in clauses
    )


def _gap_evidence(text: str) -> dict:
    return {
        "evidence": f"The candidate reported a gap: {text.strip()}",
        "assessment": "gap",
    }


def _claimed_evidence(text: str) -> dict:
    return {
        "evidence": f"The candidate said: {text.strip()}",
        "assessment": "claimed",
    }


def _supports_expected_criterion(
    text: str,
    key: str,
    requirement: dict,
    allow_unmatched_example: bool = False,
) -> bool:
    lower = text.lower()
    if key == "experience":
        if _experience_scope_conflicts(text, requirement):
            return False
        return bool(_years(text) or re.search(r"\b(?:worked|experience|apprentice|employed)\b", lower))
    if key == "location":
        return bool(_location(text))
    if key == "availability":
        return bool(
            re.search(
                r"\b(?:available|immediately|notice period|next (?:week|month|monday)|\d+ (?:day|week|month)s?)\b",
                lower,
            )
        )
    if key == "working_arrangement":
        return any(item in lower for item in ("remote", "hybrid", "on-site", "onsite"))
    if key == "working_hours":
        return bool(re.search(r"\b(?:hours?|shifts?|weekdays?|weekends?|monday|schedule)\b", lower))
    if key == "education":
        return any(
            item in lower
            for item in ("degree", "diploma", "certificate", "college", "university", "school")
        )
    terms = _criterion_terms(key, requirement)
    overlap = sum(term in lower for term in terms)
    concrete_action = bool(
        re.search(
            r"\b(?:built|completed|coordinated|created|fixed|installed|launched|maintained|managed|operated|repaired|used|worked|welded)\b",
            lower,
        )
    )
    return (
        overlap >= 1 and (concrete_action or len(text.split()) >= 6)
    ) or (
        allow_unmatched_example and concrete_action and len(text.split()) >= 5
    )


def _location(text: str) -> str | None:
    known = re.search(
        r"\b(?:in|from|near) (Cape Town|Johannesburg|Pretoria|Durban|Gqeberha|Bloemfontein|Stellenbosch|London|New York|Berlin|Nairobi)\b",
        text, re.I,
    )
    if known:
        return known.group(1).title()
    patterns = [
        r"(?:based|located|role|position|job) in ([A-Z][A-Za-z .'-]{2,40})",
        r"(?:from|near) ([A-Z][A-Za-z .'-]{2,40})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = re.split(r"[.;]|\b(?:with|and|but|who|for)\b", match.group(1))[0].strip(" .,")
            return value
    return None


def _years(text: str) -> str | None:
    match = re.search(r"(?:at least |minimum (?:of )?)?(\d+|one|two|three|four|five|six|seven|eight|nine|ten)[+-]? years?", text, re.I)
    return match.group(0) if match else None


def _importance(text: str) -> str | None:
    lower = text.lower()
    if any(term in lower for term in ("optional", "preferred", "nice to have", "nice-to-have")):
        return "preferred"
    if any(term in lower for term in ("required", "essential", "must have", "must-have", "important")):
        return "required"
    return None


def _skill_requirement(label: str, importance: str | None, years: str | None) -> dict:
    importance_text = importance or "importance not confirmed"
    years_text = years or "experience level not confirmed"
    return {
        "kind": "skill",
        "label": label,
        "importance": importance,
        "years_required": years,
        "confirmed": bool(importance and years),
        "weight": 0.85 if importance == "required" else 0.35 if importance == "preferred" else 0.5,
        "description": f"{importance_text}; {years_text}.",
        **({"optional": True} if importance == "preferred" else {}),
    }


def _clean_role_text(value: object, limit: int = 240) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" .,;")[:limit]


def _role_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:80]


def _supported_description(proposed: str, fallback: str, source: str) -> str:
    description = _clean_role_text(proposed)
    source_numbers = set(re.findall(r"\d+", source))
    description_numbers = set(re.findall(r"\d+", description))
    if len(description) < 15 or not description_numbers.issubset(source_numbers):
        return fallback
    return description


def apply_ai_role_updates(
    profile: dict,
    current_title: str | None,
    updates: list[Mapping[str, object]],
    current_text: str,
    expected_skill: str | None = None,
) -> tuple[dict, dict]:
    """Apply model-proposed role fields only when this message supports them.

    The model chooses the semantic category and wording. This function keeps the
    database contract authoritative: it requires an exact quote from the current
    recruiter message, owns weights/readiness, and refuses unsupported new skills.
    """
    accepted_profile = dict(profile or {})
    title = current_title
    accepted = 0
    normalized_message = _clean_role_text(current_text, 5000).casefold()

    for update in updates[:12]:
        category = _clean_role_text(update.get("category"), 30).lower()
        if category == "ignore":
            continue
        source = _clean_role_text(update.get("source_quote"), 500)
        if not source or source.casefold() not in normalized_message:
            continue
        label = _clean_role_text(update.get("label"), 100)
        proposed_description = _clean_role_text(
            update.get("measurable_description"), 240
        )

        if category == "title":
            proposed_title = label if label and label.casefold() in source.casefold() else source
            if 2 <= len(proposed_title) <= 80:
                title = proposed_title.title()
                accepted += 1
            continue

        if category == "skill":
            label_key = _role_key(label)
            field_key = _role_key(str(update.get("field_key") or ""))
            label_is_supported = bool(label and label.casefold() in source.casefold())
            expected_key = expected_skill if expected_skill in accepted_profile else None
            if label_is_supported:
                proposed_key = field_key if field_key in accepted_profile else label_key
            else:
                proposed_key = expected_key
            if not proposed_key:
                continue
            key = proposed_key
            existing = accepted_profile.get(key, {})
            saved_label = existing.get("label") or label
            importance_value = _clean_role_text(update.get("importance"), 20).lower()
            importance = (
                importance_value
                if importance_value in {"required", "preferred"}
                else existing.get("importance")
            )
            years = _years(source) or existing.get("years_required")
            requirement = _skill_requirement(saved_label, importance, years)
            default_description = (
                f"{importance.title() if importance else 'Importance not confirmed'}; "
                f"{years or 'experience level not confirmed'}. Applicants should describe "
                f"work using {saved_label}."
            )
            requirement["description"] = _supported_description(
                proposed_description, default_description, source
            )
            requirement["source_quote"] = source
            accepted_profile[key] = requirement
            accepted += 1
            continue

        fixed_fields = {
            "experience": ("experience", 0.8),
            "location": ("location", 0.55),
            "working_arrangement": ("working_arrangement", 0.5),
            "availability": ("availability", 0.5),
        }
        if category not in fixed_fields:
            continue
        key, weight = fixed_fields[category]
        years = _years(source) if category == "experience" else None
        defaults = {
            "experience": (
                f"Applicants should describe responsibilities and outcomes from "
                f"{years or source} of relevant experience."
            ),
            "location": f"Applicants should confirm they can work in {label or source}.",
            "working_arrangement": (
                f"Applicants should confirm they can work {label or source}."
            ),
            "availability": (
                f"Applicants should confirm whether they meet this start requirement: {source}."
            ),
        }
        accepted_profile[key] = {
            "weight": weight,
            "description": _supported_description(
                proposed_description, defaults[category], source
            ),
            "source_quote": source,
        }
        accepted += 1

    return normalize_target_profile(accepted_profile), {
        "title": title,
        "accepted": accepted,
    }


def _skill_clarification_question(key: str, requirement: dict) -> str:
    label = requirement.get("label") or key.replace("_", " ").title()
    importance = requirement.get("importance")
    years = requirement.get("years_required")
    if not importance and not years:
        return f"For {label}, is it required or preferred, and how many years of experience should applicants have?"
    if not importance:
        return f"Is {label} required or preferred for this role?"
    return f"How many years of {label} experience should applicants have?"


def expected_employer_skill(profile: dict | None, assistant_text: str) -> str | None:
    if not profile or not assistant_text:
        return None
    return next(
        (
            key
            for key, requirement in profile.items()
            if requirement.get("kind") == "skill"
            and _skill_clarification_question(key, requirement) in assistant_text
        ),
        None,
    )


def summarize_job_requirements(title: str, profile: dict | None) -> str:
    items = []
    for key, requirement in (profile or {}).items():
        label = requirement.get("label") or key.replace("_", " ").title()
        items.append(f"{label}: {requirement.get('description', 'details not confirmed')}")
    summary = "; ".join(items[:8]) or "requirements are still being clarified"
    return f"The recruiter described {title} with these requirements: {summary}."


def update_employer_profile(
    profile: dict,
    text: str,
    current_title: str | None = None,
    expected_skill: str | None = None,
) -> tuple[dict, dict]:
    profile = dict(profile or {})
    lower = text.lower()
    missing_details = missing_job_details(profile, current_title or "Untitled role")
    expected_detail = missing_details[0] if missing_details else None
    skill_hits = _skill_hits(text)
    shared_years = _years(text)
    for key, label in skill_hits:
        existing = profile.get(key, {})
        importance = _importance(text) or existing.get("importance")
        years = shared_years or existing.get("years_required")
        profile[key] = _skill_requirement(label, importance, years)
    mentioned_skill_keys = {key for key, _label in skill_hits}
    if (
        expected_skill
        and expected_skill in profile
        and (not mentioned_skill_keys or expected_skill in mentioned_skill_keys)
    ):
        existing = profile[expected_skill]
        profile[expected_skill] = _skill_requirement(
            existing.get("label") or expected_skill.replace("_", " ").title(),
            _importance(text) or existing.get("importance"),
            _years(text) or existing.get("years_required"),
        )
    if expected_detail == "criteria" and not skill_hits and len(text.strip()) >= 3:
        profile["core_requirement"] = {
            "weight": 0.85,
            "description": f"Core requirement: {text.strip()[:180]}",
        }
    if "don't care" in lower and ("degree" in lower or "education" in lower):
        profile.pop("education", None)
    elif "degree" in lower or "education" in lower:
        profile["education"] = {"weight": 0.45, "description": "Relevant education is preferred."}
    years = shared_years
    if years and not expected_skill and not (
        len(skill_hits) == 1 and _importance(text)
    ):
        profile["experience"] = {"weight": 0.8, "description": f"The role asks for {years} of relevant experience."}
    location = _location(text)
    if (
        not location
        and expected_detail == "location"
        and not skill_hits
        and not _years(text)
        and not _importance(text)
        and not any(item in lower for item in ("remote", "hybrid", "on-site", "onsite"))
        and len(text.split()) <= 12
        and re.search(r"[A-Za-z]", text)
    ):
        location = text.strip(" .,")
    if location:
        profile["location"] = {"weight": 0.55, "description": f"The role is based in {location}."}
    if "remote" in lower or "hybrid" in lower or "on-site" in lower or "onsite" in lower:
        arrangement = "remote" if "remote" in lower else "hybrid" if "hybrid" in lower else "on-site"
        profile["working_arrangement"] = {"weight": 0.5, "description": f"The working arrangement is {arrangement}."}
    if expected_detail == "availability" or any(
        phrase in lower
        for phrase in (
            "available",
            "availability",
            "start date",
            "start immediately",
            "start within",
            "as soon as possible",
            "notice period",
            "flexible start",
        )
    ):
        if "immediate" in lower or "as soon as possible" in lower:
            availability = "The candidate should be available to start immediately."
        elif "flexible" in lower:
            availability = "The start date is flexible."
        else:
            availability = f"Availability requirement: {text.strip()[:180]}"
        profile["availability"] = {"weight": 0.5, "description": availability}

    role_words = r"developer|engineer|designer|manager|analyst|specialist|assistant|accountant|welder|electrician|plumber|carpenter|bricklayer|cleaner|driver|operator|mechanic|cook|cashier|packer|warehouse worker|general worker|security officer|retail assistant|waiter|gardener|machine operator"
    title_match = re.search(
        rf"(?:need|hire|hiring|for)\s+(?:an?\s+)?((?:[A-Za-z][A-Za-z +#.-]{{0,55}}\s+)?(?:{role_words}))\b",
        text,
        re.I,
    )
    explicit_title = re.search(
        r"(?:job title|role|position)\s*(?:is|:)\s*([A-Za-z][A-Za-z0-9 +#&/.'-]{1,80})",
        text,
        re.I,
    )
    title = title_match.group(1).strip().title() if title_match else None
    if explicit_title:
        title = re.split(
            r"\.(?:\s|$)|\b(?:with|requiring|based|located)\b",
            explicit_title.group(1),
            maxsplit=1,
            flags=re.I,
        )[0].strip(" .,").title()
    elif (
        not title
        and current_title in (None, "Untitled role")
        and len(text.split()) <= 6
        and re.fullmatch(r"[A-Za-z][A-Za-z0-9 +#&/.'-]{1,80}", text.strip())
    ):
        title = text.strip().title()
    return normalize_target_profile(profile), {"title": title}


def _update_candidate_fragment(
    profile: dict,
    text: str,
    target_profile: dict | None = None,
    expected_criterion: str | None = None,
) -> dict:
    profile = dict(profile or {})
    previous_experience = profile.get("experience")
    for key, label in _skill_hits(text):
        requirement = (target_profile or {}).get(key)
        profile[key] = (
            _gap_evidence(text)
            if _criterion_denied(text, key, requirement)
            else _claimed_evidence(text)
        )
    years = _years(text)
    if _criterion_denied(text, "experience", (target_profile or {}).get("experience")):
        profile["experience"] = _gap_evidence(text)
    elif years:
        profile["experience"] = _claimed_evidence(text)
    location = _location(text)
    if _criterion_denied(text, "location", (target_profile or {}).get("location")):
        profile["location"] = _gap_evidence(text)
    elif location:
        profile["location"] = {
            "evidence": f"The candidate is based in {location}.",
            "assessment": "claimed",
        }
    lower = text.lower()
    if _criterion_denied(text, "education", (target_profile or {}).get("education")):
        profile["education"] = _gap_evidence(text)
    elif "degree" in lower or "diploma" in lower or "university" in lower or "college" in lower:
        profile["education"] = _claimed_evidence(text)
    if any(
        phrase in lower
        for phrase in ("available", "availability", "notice period", "immediately", "start")
    ):
        profile["availability"] = (
            _gap_evidence(text)
            if _criterion_denied(
                text, "availability", (target_profile or {}).get("availability")
            )
            else _claimed_evidence(text)
        )
    if "remote" in lower or "hybrid" in lower or "on-site" in lower or "onsite" in lower:
        arrangement = "remote" if "remote" in lower else "hybrid" if "hybrid" in lower else "on-site"
        profile["working_arrangement"] = (
            _gap_evidence(text)
            if _criterion_denied(
                text,
                "working_arrangement",
                (target_profile or {}).get("working_arrangement"),
            )
            else {
                "evidence": f"The candidate is open to {arrangement} work.",
                "assessment": "claimed",
            }
        )
    if "built" in lower or "project" in lower or "created" in lower or "launched" in lower:
        profile["projects"] = _claimed_evidence(text)
    general_fields = {
        "availability",
        "education",
        "experience",
        "location",
        "working_arrangement",
    }
    for key, requirement in (target_profile or {}).items():
        if _criterion_denied(text, key, requirement):
            if text.strip().lower() not in {"no", "none", "not yet", "never", "i don't", "i do not"} or key == expected_criterion:
                profile[key] = _gap_evidence(text)
        elif key not in general_fields and _supports_expected_criterion(
            text, key, requirement
        ):
            profile[key] = _claimed_evidence(text)
    if target_profile and expected_criterion in target_profile:
        requirement = target_profile[expected_criterion]
        if _criterion_denied(text, expected_criterion, requirement):
            profile[expected_criterion] = _gap_evidence(text)
        elif (
            expected_criterion not in profile
            and _supports_expected_criterion(
                text,
                expected_criterion,
                requirement,
                allow_unmatched_example=False,
            )
        ):
            profile[expected_criterion] = _claimed_evidence(text)
    if _experience_scope_conflicts(text, (target_profile or {}).get("experience")):
        if previous_experience is None:
            profile.pop("experience", None)
        else:
            profile["experience"] = previous_experience
    return normalize_candidate_evidence(profile, target_profile)


def update_candidate_profile(profile: dict, text: str, target_profile: dict | None = None,
                             expected_criterion: str | None = None) -> dict:
    # Keep durations and denials with their own clause instead of copying a whole
    # multi-answer message to every criterion. The live model handles richer prose.
    if re.fullmatch(r"(?:that['’]?s fine|fine|ok(?:ay)?|yes|sure)[.! ]*", text.strip(), re.I):
        return dict(profile or {})
    if target_profile and expected_criterion and re.fullmatch(
        r"(?:no|none|not yet|never|i (?:don't|do not) have (?:that|this) (?:skill|experience))[.! ]*", text.strip(), re.I
    ):
        return normalize_candidate_evidence({**profile, expected_criterion: _gap_evidence(text)}, target_profile)
    result = dict(profile or {})
    fragments = re.split(r"[;\n]|(?<!\d)[.!?](?!\d)|\b(?:but|however)\b", text)
    for fragment in fragments:
        fragment = fragment.strip(" ,")
        if fragment:
            before = result
            result = _update_candidate_fragment(result, fragment, target_profile, expected_criterion)
            for key, item in result.items():
                if item != before.get(key):
                    item["source_quote"] = fragment
                    previous = before.get(key, {})
                    if (target_profile is None and previous.get("assessment") != "gap"
                            and item.get("assessment") != "gap" and _years(previous.get("evidence", ""))
                            and not _years(item.get("evidence", ""))):
                        item["evidence"] = previous["evidence"] + " " + item["evidence"]
                        item["source_quote"] = previous.get("source_quote", "") + "; " + fragment
                    if (normalize_target_profile(target_profile).get(key, {}).get("type") == "number"
                            and item.get("value") is None and item.get("assessment") != "gap"
                            and previous.get("value") is not None and previous.get("assessment") != "gap"):
                        item["value"] = previous["value"]
                        item["evidence"] = previous["evidence"] + " " + item["evidence"]
                        item["source_quote"] = previous.get("source_quote", "") + "; " + fragment
    if (expected_criterion == "core_requirement" and expected_criterion not in result
            and _supports_expected_criterion(text, expected_criterion, target_profile[expected_criterion], allow_unmatched_example=True)):
        result[expected_criterion] = {**_claimed_evidence(text), "state": "needs_clarification", "value": None, "source_quote": text}
    return result


def update_candidate_turn(
    profile: dict,
    text: str,
    target_profile: dict | None = None,
    expected_criterion: str | None = None,
) -> tuple[dict, str | None]:
    previous = dict(profile or {})
    updated = update_candidate_profile(
        previous, text, target_profile, expected_criterion
    )
    new_gap = any(
        item.get("assessment") == "gap" and item != previous.get(key)
        for key, item in updated.items()
    )
    if new_gap:
        return updated, "gap"
    if expected_criterion:
        if updated.get(expected_criterion) == previous.get(expected_criterion):
            return updated, "unclear"
        return updated, "accepted"
    return updated, None


def missing_job_details(profile: dict, title: str) -> list[str]:
    missing = []
    if not title or title == "Untitled role":
        missing.append("title")
    general_fields = {
        "availability",
        "education",
        "experience",
        "location",
        "working_arrangement",
    }
    if not any(key not in general_fields for key in profile):
        missing.append("criteria")
    missing.extend(
        f"skill:{key}"
        for key, requirement in profile.items()
        if requirement.get("kind") == "skill"
        and not requirement.get("confirmed", True)
    )
    has_skill_experience = any(
        requirement.get("kind") == "skill"
        and requirement.get("years_required")
        for requirement in profile.values()
    )
    if "experience" not in profile and not has_skill_experience:
        missing.append("experience")
    if "location" not in profile and "working_arrangement" not in profile:
        missing.append("location")
    if "availability" not in profile:
        missing.append("availability")
    return missing


def employer_reply(
    profile: dict, ready_to_publish: bool, title: str = "Untitled role"
) -> str:
    if ready_to_publish:
        return "I’ve updated the role profile. It has enough detail to publish now, or you can keep refining it in plain language."
    next_detail = missing_job_details(profile, title)[0]
    if next_detail == "title":
        return "What is the job title for this role?"
    if next_detail == "criteria":
        return "Which skill or responsibility is essential for this role?"
    if next_detail.startswith("skill:"):
        key = next_detail.split(":", 1)[1]
        return _skill_clarification_question(key, profile[key])
    if next_detail == "experience":
        return "I’ve added that. How much relevant experience should the person have?"
    if next_detail == "location":
        return "Got it. Where is the role based, and is it remote, hybrid, or on-site?"
    return "When should the successful candidate be available to start?"


def _candidate_criterion_question(key: str, requirement: dict | None = None) -> str:
    label = key.replace("_", " ")
    questions = {
        "experience": "How many years of relevant experience do you have, and what did you do?",
        "location": "Where are you based, and can you work at the location described for this role?",
        "availability": "When would you be available to start this role?",
        "working_arrangement": "Are you available for the working arrangement described for this role?",
        "education": "What relevant education, training, or certificates do you have?",
    }
    if requirement and requirement.get("type") == "number" and requirement.get("unit") not in {None, "year", "years"}:
        return f"For {requirement.get('label', label)}, how many {requirement['unit']} can you report, and what is the example?"
    if requirement and key == "experience" and requirement.get("type") == "text":
        return f"What experience or practical example can you share for this requirement: {requirement.get('target')}?"
    if key == "working_hours":
        return "What hours or shifts can you work?"
    return questions.get(
        key,
        f"Tell me about your {label} experience and one example that shows it.",
    )


def expected_candidate_criterion(
    target_profile: dict | None, assistant_text: str
) -> str | None:
    if not target_profile or not assistant_text:
        return None
    return next(
        (
            key
            for key in target_profile
            if _candidate_criterion_question(key, normalize_target_profile(target_profile)[key]) in assistant_text
        ),
        None,
    )


def candidate_reply(
    profile: dict,
    target_profile: dict | None = None,
    answer_status: str | None = None,
) -> str:
    if target_profile:
        target_profile = normalize_target_profile(target_profile)
        missing = sorted(
            (
                (key, requirement)
                for key, requirement in target_profile.items()
                if not profile.get(key, {}).get("evidence")
                or profile.get(key, {}).get("state") == "needs_clarification"
                or (requirement["type"] == "number" and profile.get(key, {}).get("assessment") != "gap"
                    and profile.get(key, {}).get("value") is None)
            ),
            key=lambda item: (-float(item[1].get("weight", 0.5)), item[0]),
        )
        if missing:
            question = _candidate_criterion_question(missing[0][0], missing[0][1])
            if answer_status == "unclear":
                return f"I couldn't connect that answer to the requested evidence yet. {question}"
            if answer_status == "gap":
                return f"Thanks for clarifying. I'll record that as a gap, not a match. {question}"
            return question
        if answer_status == "gap":
            return "Thanks for clarifying. I recorded that as a gap, not a match. Review the structured application below when you're ready to submit."
        return "I’ve captured the candidate-provided claims for this role’s criteria. Review the structured application below when you’re ready to submit."
    if len(profile) < 2:
        return "Tell me about the skills you use, your experience, or a project you’re proud of."
    if "experience" not in profile:
        return "That’s helpful. How many years of experience do you have, and what have you built or achieved?"
    if "location" not in profile:
        return "Great. Where are you based, and are you open to remote or hybrid work?"
    return "I’ve updated your profile. I’ll show matching published jobs here as they become available."


def can_publish(profile: dict, title: str) -> bool:
    return not missing_job_details(profile, title)
