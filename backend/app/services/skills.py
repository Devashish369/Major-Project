"""
services/skills.py – skill names and how related two skills are (no LLM, no internet, free).

1. canonical(name): one name per skill, so "ReactJS", "react.js" and "react" match, and
   "ML" matches "machine learning".
2. relatedness(a, b) in [0, 1]: how close two skills are, used to suggest WHO should learn a
   skill nobody on the team has (services/skill_gaps.py).  It is a hand-made map, so every
   number can be explained in a viva:
     1.0   same skill
     edge  an explicit pair below, e.g. rag ↔ generative ai 0.9
     0.6   same family, e.g. react ↔ css (both "frontend")
     link  related families, e.g. genai ↔ ai_ml 0.7  (scaled by 0.8)
     else  shared words, e.g. "cloud security" ↔ "network security" (at most 0.5)
   The largest applicable value wins.
"""
from __future__ import annotations

import re

SYNONYMS = {
    "reactjs": "react", "react.js": "react", "react js": "react",
    "js": "javascript", "es6": "javascript", "ts": "typescript",
    "node": "node.js", "nodejs": "node.js", "node js": "node.js", "express.js": "express",
    "py": "python", "postgres": "postgresql", "psql": "postgresql",
    "ml": "machine learning", "dl": "deep learning", "ai": "artificial intelligence",
    "genai": "generative ai", "gen ai": "generative ai", "generative-ai": "generative ai",
    "large language models": "llm", "llms": "llm", "retrieval augmented generation": "rag",
    "retrieval-augmented generation": "rag", "prompting": "prompt engineering",
    "vector db": "vector databases", "vector database": "vector databases",
    "natural language processing": "nlp", "cv": "computer vision", "sklearn": "scikit-learn",
    "ci": "ci/cd", "cicd": "ci/cd", "ci-cd": "ci/cd", "k8s": "kubernetes",
    "amazon web services": "aws", "google cloud": "gcp",
    "ux": "ui/ux", "ui": "ui/ux", "ux design": "ui/ux", "ui design": "ui/ux",
    "qa": "testing", "unit testing": "testing", "test automation": "automation",
    "pentesting": "penetration testing", "pen testing": "penetration testing", "vapt": "penetration testing",
    "ethical hacker": "ethical hacking", "crypto": "cryptography", "forensics": "digital forensics",
    "soc": "soc analysis", "siem": "threat detection", "infosec": "security", "cybersecurity": "security",
    "cyber security": "security", "appsec": "application security", "rest": "rest api", "restful api": "rest api",
    "data analytics": "data analysis", "powerbi": "power bi", "golang": "go", "c sharp": "c#",
    "android development": "android", "ios development": "ios", "mobile development": "mobile",
}

FAMILIES = {
    "frontend": ["react", "javascript", "typescript", "html", "css", "tailwind", "vue", "angular",
                 "next.js", "redux", "frontend"],
    "mobile": ["mobile", "react native", "flutter", "android", "ios", "kotlin", "swift", "dart"],
    "backend": ["python", "fastapi", "django", "flask", "node.js", "express", "java", "spring", "go",
                "c#", ".net", "php", "rest api", "graphql", "backend", "microservices"],
    "database": ["sql", "postgresql", "mysql", "mongodb", "redis", "sqlite", "database"],
    "ai_ml": ["machine learning", "deep learning", "nlp", "computer vision", "pytorch", "tensorflow",
              "scikit-learn", "data science", "statistics", "artificial intelligence"],
    "genai": ["generative ai", "llm", "rag", "prompt engineering", "langchain", "vector databases",
              "fine-tuning", "embeddings", "agents"],
    "data": ["data", "data analysis", "pandas", "numpy", "power bi", "tableau", "data engineering",
             "etl", "spark", "excel"],
    "devops": ["devops", "docker", "kubernetes", "ci/cd", "aws", "azure", "gcp", "linux", "terraform",
               "git", "cloud", "automation"],
    "security": ["security", "network security", "ethical hacking", "penetration testing", "cryptography",
                 "threat detection", "digital forensics", "soc analysis", "cloud security",
                 "application security", "owasp"],
    "design": ["ui/ux", "figma", "ux research", "graphic design", "prototyping"],
    "testing": ["testing", "selenium", "pytest", "jest", "playwright", "cypress"],
    "management": ["project management", "agile", "scrum", "documentation", "communication"],
}

# Related families (symmetric).  Used scaled by 0.8 so a same-family skill always ranks higher.
FAMILY_LINKS = {
    ("genai", "ai_ml"): 0.7, ("ai_ml", "data"): 0.6, ("genai", "data"): 0.4, ("genai", "backend"): 0.35,
    ("frontend", "mobile"): 0.6, ("frontend", "design"): 0.5, ("frontend", "backend"): 0.35,
    ("backend", "database"): 0.6, ("database", "data"): 0.5, ("backend", "devops"): 0.45,
    ("devops", "security"): 0.5, ("backend", "security"): 0.35, ("testing", "frontend"): 0.35,
    ("testing", "backend"): 0.35, ("testing", "security"): 0.4, ("testing", "devops"): 0.35,
    ("ai_ml", "backend"): 0.35, ("mobile", "design"): 0.4,
}

# Explicit pairs that are closer than "same family" (symmetric)
EDGES = {
    ("rag", "generative ai"): 0.9, ("llm", "generative ai"): 0.95, ("prompt engineering", "generative ai"): 0.9,
    ("langchain", "rag"): 0.9, ("embeddings", "rag"): 0.9, ("vector databases", "rag"): 0.9,
    ("llm", "rag"): 0.9, ("llm", "nlp"): 0.8, ("nlp", "generative ai"): 0.75, ("fine-tuning", "llm"): 0.9,
    ("deep learning", "machine learning"): 0.9, ("deep learning", "generative ai"): 0.7,
    ("machine learning", "data science"): 0.9, ("scikit-learn", "machine learning"): 0.9,
    ("pytorch", "deep learning"): 0.9, ("tensorflow", "deep learning"): 0.9, ("python", "machine learning"): 0.55,
    ("python", "data analysis"): 0.55, ("pandas", "data analysis"): 0.9, ("python", "fastapi"): 0.75,
    ("python", "django"): 0.75, ("python", "flask"): 0.75, ("javascript", "typescript"): 0.9,
    ("javascript", "node.js"): 0.75, ("javascript", "react"): 0.75, ("react", "react native"): 0.85,
    ("react", "next.js"): 0.85, ("react", "redux"): 0.85, ("html", "css"): 0.85, ("css", "tailwind"): 0.85,
    ("sql", "postgresql"): 0.9, ("sql", "mysql"): 0.9, ("postgresql", "mysql"): 0.85, ("flutter", "dart"): 0.95,
    ("docker", "kubernetes"): 0.85, ("ci/cd", "devops"): 0.85, ("docker", "devops"): 0.8, ("aws", "cloud"): 0.9,
    ("azure", "cloud"): 0.9, ("gcp", "cloud"): 0.9, ("aws", "cloud security"): 0.6,
    ("ethical hacking", "penetration testing"): 0.95, ("network security", "penetration testing"): 0.75,
    ("network security", "cloud security"): 0.75, ("threat detection", "digital forensics"): 0.75,
    ("threat detection", "soc analysis"): 0.9, ("cryptography", "security"): 0.75,
    ("application security", "owasp"): 0.9, ("application security", "penetration testing"): 0.8,
    ("security", "network security"): 0.8, ("ui/ux", "figma"): 0.9, ("testing", "automation"): 0.75,
    ("pytest", "testing"): 0.85, ("jest", "testing"): 0.85, ("playwright", "testing"): 0.85,
    ("scrum", "agile"): 0.9, ("project management", "agile"): 0.75,
}

_FAMILY_OF: dict[str, set[str]] = {}
for _fam, _skills in FAMILIES.items():
    for _s in _skills:
        _FAMILY_OF.setdefault(_s, set()).add(_fam)

_EDGE = {}
for (_a, _b), _w in EDGES.items():
    _EDGE[(_a, _b)] = _EDGE[(_b, _a)] = _w
_LINK = {}
for (_a, _b), _w in FAMILY_LINKS.items():
    _LINK[(_a, _b)] = _LINK[(_b, _a)] = _w


def canonical(name: str) -> str:
    """Lower-case, trim, collapse spaces, then map known synonyms to one name."""
    key = re.sub(r"\s+", " ", (name or "").strip().lower())
    return SYNONYMS.get(key, key)


def canonical_levels(skills: dict | None) -> dict[str, int]:
    """A member's skills with canonical names (if two names collapse, the higher level wins)."""
    out: dict[str, int] = {}
    for name, level in (skills or {}).items():
        c = canonical(name)
        if c:
            out[c] = max(out.get(c, 0), int(level or 0))
    return out


def _words(s: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9+#]+", s) if len(w) > 1}


def relatedness(a: str, b: str) -> float:
    """How related two skills are, 0–1 (see module docstring)."""
    a, b = canonical(a), canonical(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    best = _EDGE.get((a, b), 0.0)
    fa, fb = _FAMILY_OF.get(a, set()), _FAMILY_OF.get(b, set())
    if fa & fb:
        best = max(best, 0.6)
    for x in fa:
        for y in fb:
            best = max(best, 0.8 * _LINK.get((x, y), 0.0))
    wa, wb = _words(a), _words(b)
    if wa and wb:
        best = max(best, 0.5 * len(wa & wb) / len(wa | wb))
    return round(best, 3)


def family(name: str) -> str | None:
    fams = sorted(_FAMILY_OF.get(canonical(name), ()))
    return fams[0] if fams else None
