import re


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
    "welder": "Welder",
    "welding": "Welding",
    "electrician": "Electrician",
    "electrical wiring": "Electrical wiring",
    "plumber": "Plumber",
    "plumbing": "Plumbing",
    "carpenter": "Carpenter",
    "carpentry": "Carpentry",
    "bricklayer": "Bricklayer",
    "bricklaying": "Bricklaying",
    "cleaner": "Cleaner",
    "cleaning": "Cleaning",
    "driver": "Driver",
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


def _location(text: str) -> str | None:
    patterns = [
        r"(?:based|located|role|position|job) in ([A-Z][A-Za-z .'-]{2,40})",
        r"(?:from|near) ([A-Z][A-Za-z .'-]{2,40})",
        r"\bin (Cape Town|Johannesburg|Pretoria|Durban|Gqeberha|Bloemfontein|Stellenbosch|London|New York|Berlin|Nairobi)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = re.split(r"\b(?:with|and|but|who|for)\b", match.group(1))[0].strip(" .,")
            return value
    return None


def _years(text: str) -> str | None:
    match = re.search(r"(?:at least |minimum (?:of )?)?(\d+|one|two|three|four|five|six|seven|eight|nine|ten)[+-]? years?", text, re.I)
    return match.group(0) if match else None


def update_employer_profile(
    profile: dict, text: str, current_title: str | None = None
) -> tuple[dict, dict]:
    profile = dict(profile or {})
    lower = text.lower()
    missing_details = missing_job_details(profile, current_title or "Untitled role")
    expected_detail = missing_details[0] if missing_details else None
    skill_hits = _skill_hits(text)
    for key, label in skill_hits:
        optional = bool(re.search(rf"{re.escape(label.lower())}.{{0,20}}optional|optional.{{0,20}}{re.escape(label.lower())}", lower))
        profile[key] = {
            "weight": 0.35 if optional else 0.85,
            "description": f"{label} experience is {'preferred' if optional else 'required'}.",
            **({"optional": True} if optional else {}),
        }
    if expected_detail == "criteria" and not skill_hits and len(text.strip()) >= 3:
        profile["core_requirement"] = {
            "weight": 0.85,
            "description": f"Core requirement: {text.strip()[:180]}",
        }
    if "don't care" in lower and ("degree" in lower or "education" in lower):
        profile.pop("education", None)
    elif "degree" in lower or "education" in lower:
        profile["education"] = {"weight": 0.45, "description": "Relevant education is preferred."}
    years = _years(text)
    if years:
        profile["experience"] = {"weight": 0.8, "description": f"The role asks for {years} of relevant experience."}
    location = _location(text)
    if (
        not location
        and expected_detail == "location"
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
            r"\b(?:with|requiring|based|located)\b",
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
    return profile, {"title": title}


def update_candidate_profile(
    profile: dict,
    text: str,
    target_profile: dict | None = None,
    expected_criterion: str | None = None,
) -> dict:
    profile = dict(profile or {})
    for key, label in _skill_hits(text):
        profile[key] = {"evidence": f"The candidate said: {text.strip()}"}
    years = _years(text)
    if years:
        profile["experience"] = {"evidence": f"The candidate reported {years} of experience."}
    location = _location(text)
    if location:
        profile["location"] = {"evidence": f"The candidate is based in {location}."}
    lower = text.lower()
    if "degree" in lower or "diploma" in lower or "university" in lower or "college" in lower:
        profile["education"] = {"evidence": f"The candidate said: {text.strip()}"}
    if any(
        phrase in lower
        for phrase in ("available", "availability", "notice period", "immediately", "start")
    ):
        profile["availability"] = {"evidence": f"The candidate said: {text.strip()}"}
    if "remote" in lower or "hybrid" in lower or "on-site" in lower or "onsite" in lower:
        arrangement = "remote" if "remote" in lower else "hybrid" if "hybrid" in lower else "on-site"
        profile["working_arrangement"] = {"evidence": f"The candidate is open to {arrangement} work."}
    if "built" in lower or "project" in lower or "created" in lower or "launched" in lower:
        profile["projects"] = {"evidence": f"The candidate said: {text.strip()}"}
    if (
        target_profile
        and expected_criterion in target_profile
        and expected_criterion not in profile
    ):
        profile[expected_criterion] = {"evidence": f"The candidate said: {text.strip()}"}
    return profile


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
    if "experience" not in profile:
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
    if next_detail == "experience":
        return "I’ve added that. How much relevant experience should the person have?"
    if next_detail == "location":
        return "Got it. Where is the role based, and is it remote, hybrid, or on-site?"
    return "When should the successful candidate be available to start?"


def _candidate_criterion_question(key: str) -> str:
    label = key.replace("_", " ")
    questions = {
        "experience": "How many years of relevant experience do you have, and what did you do?",
        "location": "Where are you based, and can you work at the location described for this role?",
        "availability": "When would you be available to start this role?",
        "working_arrangement": "Are you available for the working arrangement described for this role?",
        "education": "What relevant education, training, or certificates do you have?",
    }
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
            if _candidate_criterion_question(key) in assistant_text
        ),
        None,
    )


def candidate_reply(profile: dict, target_profile: dict | None = None) -> str:
    if target_profile:
        missing = sorted(
            (
                (key, requirement)
                for key, requirement in target_profile.items()
                if not profile.get(key, {}).get("evidence")
            ),
            key=lambda item: (-float(item[1].get("weight", 0.5)), item[0]),
        )
        if missing:
            return _candidate_criterion_question(missing[0][0])
        return "I’ve captured evidence for this role’s criteria. Review the structured application below when you’re ready to submit."
    if len(profile) < 2:
        return "Tell me about the skills you use, your experience, or a project you’re proud of."
    if "experience" not in profile:
        return "That’s helpful. How many years of experience do you have, and what have you built or achieved?"
    if "location" not in profile:
        return "Great. Where are you based, and are you open to remote or hybrid work?"
    return "I’ve updated your profile. I’ll show matching published jobs here as they become available."


def can_publish(profile: dict, title: str) -> bool:
    return not missing_job_details(profile, title)
