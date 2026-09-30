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


def update_employer_profile(profile: dict, text: str) -> tuple[dict, dict]:
    profile = dict(profile or {})
    lower = text.lower()
    for key, label in _skill_hits(text):
        optional = bool(re.search(rf"{re.escape(label.lower())}.{{0,20}}optional|optional.{{0,20}}{re.escape(label.lower())}", lower))
        profile[key] = {
            "weight": 0.35 if optional else 0.85,
            "description": f"{label} experience is {'preferred' if optional else 'required'}.",
            **({"optional": True} if optional else {}),
        }
    if "don't care" in lower and ("degree" in lower or "education" in lower):
        profile.pop("education", None)
    elif "degree" in lower or "education" in lower:
        profile["education"] = {"weight": 0.45, "description": "Relevant education is preferred."}
    years = _years(text)
    if years:
        profile["experience"] = {"weight": 0.8, "description": f"The role asks for {years} of relevant experience."}
    location = _location(text)
    if location:
        profile["location"] = {"weight": 0.55, "description": f"The role is based in {location}."}
    if "remote" in lower or "hybrid" in lower or "on-site" in lower or "onsite" in lower:
        arrangement = "remote" if "remote" in lower else "hybrid" if "hybrid" in lower else "on-site"
        profile["working_arrangement"] = {"weight": 0.5, "description": f"The working arrangement is {arrangement}."}

    role_words = r"developer|engineer|designer|manager|analyst|specialist|assistant|accountant|welder|electrician|plumber|carpenter|bricklayer|cleaner|driver|operator|mechanic|cook"
    title_match = re.search(
        rf"(?:need|hire|hiring|for)\s+(?:an?\s+)?((?:[A-Za-z][A-Za-z +#.-]{{0,55}}\s+)?(?:{role_words}))\b",
        text,
        re.I,
    )
    title = title_match.group(1).strip().title() if title_match else None
    return profile, {"title": title}


def update_candidate_profile(profile: dict, text: str) -> dict:
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
    if "available" in lower or "notice period" in lower or "immediately" in lower:
        profile["availability"] = {"evidence": f"The candidate said: {text.strip()}"}
    if "remote" in lower or "hybrid" in lower or "on-site" in lower or "onsite" in lower:
        arrangement = "remote" if "remote" in lower else "hybrid" if "hybrid" in lower else "on-site"
        profile["working_arrangement"] = {"evidence": f"The candidate is open to {arrangement} work."}
    if "built" in lower or "project" in lower or "created" in lower or "launched" in lower:
        profile["projects"] = {"evidence": f"The candidate said: {text.strip()}"}
    return profile


def employer_reply(profile: dict, can_publish: bool) -> str:
    if can_publish:
        return "I’ve updated the role profile. It has enough detail to publish now, or you can keep refining it in plain language."
    if not profile:
        return "What role are you hiring for, and which skills matter most?"
    if "experience" not in profile:
        return "I’ve added that. How much relevant experience should the person have?"
    if "location" not in profile and "working_arrangement" not in profile:
        return "Got it. Where is the role based, and is it remote, hybrid, or on-site?"
    return "What are the most important responsibilities or preferred skills for this role?"


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
    substantive = [key for key in profile if key not in {"location", "working_arrangement", "education"}]
    return title != "Untitled role" and len(substantive) >= 2
