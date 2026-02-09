"""Shared tab taxonomy used by postprocess and renderer."""

from __future__ import annotations

# Postprocess classification output contract.
POSTPROCESS_KIND_ORDER = (
    "video",
    "music",
    "repo",
    "paper",
    "docs",
    "article",
    "tool",
    "misc",
    "local",
    "auth",
    "internal",
)
POSTPROCESS_KINDS = set(POSTPROCESS_KIND_ORDER)

POSTPROCESS_ACTION_ORDER = (
    "read",
    "watch",
    "reference",
    "build",
    "triage",
    "ignore",
    "deep_work",
)
POSTPROCESS_ACTIONS = set(POSTPROCESS_ACTION_ORDER)

# Renderer keeps a couple of presentation-only kinds.
RENDERER_EXTRA_KINDS = ("spec", "admin")
RENDERER_ALLOWED_KINDS = set(POSTPROCESS_KIND_ORDER + RENDERER_EXTRA_KINDS)

# Shared domain and URL hint sets.
CODE_HOST_DOMAINS = ("github.com", "gitlab.com", "bitbucket.org")

VIDEO_DOMAINS = (
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "vimeo.com",
    "twitch.tv",
    "netflix.com",
    "disneyplus.com",
    "hulu.com",
    "primevideo.com",
    "tv.apple.com",
    "loom.com",
    "v.redd.it",
)

MUSIC_DOMAINS = (
    "music.apple.com",
    "open.spotify.com",
    "music.youtube.com",
    "uppbeat.io",
    "music.yandex.ru",
)

DOC_PATH_HINTS = (
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

BLOG_PATH_HINTS = (
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

TOOL_DOMAINS = (
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
    "contextmapper.org",
    "smithery.ai",
)

SENSITIVE_HOSTS = (
    "accounts.google.com",
    "auth.openai.com",
    "platform.openai.com",
    "chat.openai.com",
    "github.com/settings",
)

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
