"""Static constants for tab post-processing heuristics."""

from typing import Tuple

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

SENSITIVE_HOSTS = {
    "accounts.google.com",
    "auth.openai.com",
    "platform.openai.com",
    "chat.openai.com",
    "github.com/settings",
}

AUTH_PATH_HINTS = (
    "/login",
    "/signin",
    "/sign-in",
    "/oauth",
    "/sso",
    "/session",
    "/api-keys",
    "/credentials",
    "/token",
    "/profile",
)

SENSITIVE_QUERY_KEYS = (
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "apikey",
    "session",
    "code",
    "sig",
    "signature",
    "password",
)

VIDEO_DOMAINS = {
    "youtube.com",
    "youtu.be",
    "vimeo.com",
    "twitch.tv",
    "netflix.com",
    "disneyplus.com",
    "hulu.com",
    "primevideo.com",
    "music.apple.com",
    "tv.apple.com",
    "open.spotify.com",
    "music.youtube.com",
    "loom.com",
    "v.redd.it",
}

CODE_HOST_DOMAINS = {"github.com", "gitlab.com", "bitbucket.org"}

TOOL_DOMAINS = {
    "console.aws.amazon.com",
    "console.cloud.google.com",
    "portal.azure.com",
    "notion.so",
    "notion.site",
    "trello.com",
    "asana.com",
    "todoist.com",
    "airtable.com",
    "canva.com",
    "figma.com",
    "miro.com",
    "slack.com",
    "zoom.us",
    "meet.google.com",
    "calendar.google.com",
    "docs.google.com",
    "drive.google.com",
    "mail.google.com",
    "outlook.live.com",
    "dropbox.com",
    "maps.google.com",
    "translate.google.com",
}

DOC_HINTS = (
    "/docs/",
    "/docs",
    "/documentation/",
    "/documentation",
    "/reference/",
    "/reference",
    "/guides/",
    "/guides",
    "/guide/",
    "/guide",
    "/api/",
    "/api",
    "/manual",
    "/handbook",
    "/release",
    "/releases",
    "/changelog",
)

DOC_HOST_OVERRIDES = {"docs.github.com"}

BLOG_HINTS = (
    "/blog/",
    "/blog",
    "/blogs/",
    "/blogs",
    "/post/",
    "/posts/",
    "/posts",
    "/article",
    "/articles/",
    "/articles",
    "/stories/",
    "/story/",
)

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
    ("finance", ("finance", "investing", "stocks", "etf", "budget", "mortgage", "credit card", "retirement", "tax")),
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
