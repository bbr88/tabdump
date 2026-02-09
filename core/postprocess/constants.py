"""Static constants for tab post-processing heuristics."""

from typing import Tuple

from core.tab_policy.taxonomy import (
    AUTH_PATH_HINTS,
    BLOG_PATH_HINTS,
    CODE_HOST_DOMAINS,
    DOC_PATH_HINTS,
    MUSIC_DOMAINS,
    SENSITIVE_HOSTS,
    SENSITIVE_QUERY_KEYS,
    TOOL_DOMAINS,
    VIDEO_DOMAINS,
)

TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "mkt_tok",
    "msclkid",
    "ref",
    "ref_src",
    "spm",
    "yclid",
}

DOC_HINTS = DOC_PATH_HINTS
BLOG_HINTS = BLOG_PATH_HINTS
MUSIC_HINT_DOMAINS = MUSIC_DOMAINS

DOC_HOST_OVERRIDES = {"docs.github.com"}

REFERENCE_HINTS = ("reference", "api", "spec", "documentation", "docs")

DEEP_READ_HINTS = (
    "guide",
    "tutorial",
    "internals",
    "architecture",
    "design",
    "how to",
    "how-to",
    "beginner",
    "beginners",
    "step by step",
    "step-by-step",
    "explained",
    "explainer",
    "tips",
    "checklist",
    "overview",
    "faq",
    "what is",
    ".pdf",
    "whitepaper",
)

LOW_SIGNAL_HINTS = ("best", "top", "vs", "review", "reviews", "news", "trending")

SOCIAL_DOMAINS = {
    "x.com",
    "twitter.com",
    "threads.net",
    "reddit.com",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
}

UI_UX_HINTS = ("design-system", "figma", "storybook", "tailwind", "component")
PAPER_HINTS = (".pdf", "arxiv.org", "researchgate", "vldb", "acm.org")
PROJECT_HINTS = ("jira", "confluence", "linear.app", "notion.so/view")
MCP_HINTS = ("mcp", "/server/")
VIDEO_KEYWORD_HINTS = (
    "серия",
    "seriya",
    "сезон",
    "sezon",
    "фильм",
    "film",
    "смотреть",
    "smotret",
)
MUSIC_KEYWORD_HINTS = (
    "музыка",
    "muzyka",
    "песня",
    "pesnya",
    "альбом",
    "albom",
    "подкаст",
    "podkast",
    "слушать",
    "slushat",
)

GO_CONTEXT_HINTS = (
    "golang",
    "go-lang",
    "go language",
    "learning go",
    "learn go",
    "go tutorial",
    "go by example",
    "go.dev",
    "go module",
    "go modules",
    "goroutine",
    "go package",
    "go sdk",
)

TOPIC_KEYWORDS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("architecture", ("patterns", "ddd", "microservices", "event-driven", "distributed")),
    ("postgres", ("postgres", "pgbouncer", "pganalyze", "sql", "wal")),
    ("python", ("python", "pypi", "django", "fastapi", "flask")),
    ("javascript", ("javascript", "typescript", "node.js", "nodejs", "npm")),
    ("rust", ("rust", "cargo", "crates.io")),
    ("go", ("golang", "go.dev", "go-lang", "learning go", "go language", "go")),
    ("kubernetes", ("kubernetes", "k8s")),
    ("docker", ("docker", "container")),
    ("terraform", ("terraform", "iac")),
    ("redis", ("redis",)),
    ("linux", ("linux", "ubuntu", "debian")),
    ("cloud", ("aws", "gcp", "azure", "cloud")),
    ("llm", ("llm", "openai", "anthropic", "chatgpt", "huggingface")),
    ("frontend", ("react", "vue", "angular", "frontend", "css")),
    ("security", ("security", "oauth", "sso", "token", "auth")),
    (
        "finance",
        ("finance", "investing", "stocks", "etf", "budget", "mortgage", "credit card", "retirement", "tax"),
    ),
    ("health", ("health", "wellness", "nutrition", "diet", "mental health", "therapy", "mindfulness")),
    ("fitness", ("workout", "fitness", "exercise", "gym", "running", "yoga", "pilates")),
    ("food", ("recipe", "cooking", "baking", "meal prep", "kitchen", "restaurant")),
    ("travel", ("travel", "trip", "flight", "hotel", "vacation", "itinerary", "airbnb")),
    ("shopping", ("shopping", "buy", "price", "deal", "discount", "coupon", "cart", "product")),
    ("entertainment", ("movie", "tv show", "music", "podcast", "series", "trailer", "celebrity")),
    ("sports", ("sports", "football", "soccer", "basketball", "tennis", "nfl", "nba", "mlb")),
    ("education", ("course", "lesson", "study", "university", "school", "exam", "homework")),
    ("career", ("career", "resume", "cv", "interview", "job", "salary", "linkedin", "agile", "scrum")),
    ("productivity", ("productivity", "planner", "to-do", "todo", "calendar", "organize", "habit")),
    ("personal-development", ("self improvement", "motivation", "mindset", "goal setting", "discipline")),
    ("parenting", ("parenting", "kids", "child", "baby", "toddler", "family")),
    ("home", ("home improvement", "diy", "garden", "gardening", "cleaning", "organization")),
    ("automotive", ("car", "automotive", "vehicle", "motorcycle", "maintenance", "road trip")),
)

CODE_HOST_RESERVED_PATHS = {
    "",
    "about",
    "contact",
    "collections",
    "enterprise",
    "events",
    "explore",
    "features",
    "join",
    "login",
    "marketplace",
    "new",
    "notifications",
    "orgs",
    "organizations",
    "pricing",
    "search",
    "settings",
    "site",
    "sponsors",
    "topics",
}
