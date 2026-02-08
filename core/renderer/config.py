"""Renderer configuration and shared constants."""

from __future__ import annotations

from typing import Dict

from core.tab_policy.taxonomy import (
    BLOG_PATH_HINTS,
    CODE_HOST_DOMAINS,
    DOC_PATH_HINTS,
    RENDERER_ALLOWED_KINDS,
    SENSITIVE_QUERY_KEYS,
    VIDEO_DOMAINS,
)

DEFAULT_CFG: Dict = {
    "rendererVersion": "3.2.4.1",
    "titleMaxLen": 96,
    "stripWwwForGrouping": True,
    "includeFocusLine": True,
    "frontmatterInclude": [
        "dump_date",
        "tab_count",
        "top_domains",
        "top_kinds",
        "status",
        "renderer",
        "source",
        "deduped",
    ],
    "highPriorityLimit": 5,
    "highPriorityMinScore": 4,
    "highPriorityMinIntentConfidence": 0.70,
    "highPriorityEligibleCategories": ["docs_site", "blog", "code_host"],
    "includeQuickWins": True,
    "includeEmptySections": False,
    "quickWinsMaxItems": 15,
    "quickWinsOverflowToBacklog": True,
    "backlogMaxItems": 50,
    "adminAlwaysLast": True,
    "adminVerboseBullets": False,
    "adminIncludeSrcWhenMultiBrowser": True,
    "groupingMode": "domain_first",
    "groupWithinSectionsBy": ["domain_category", "domain_display"],
    "compactBullets": True,
    "includeInlineBadges": True,
    "includeInlineTopicIfAvailable": False,
    "includeDetailTopicIfAvailable": False,
    "skipPrefixes": [
        "chrome://",
        "chrome-extension://",
        "about:",
        "file://",
        "safari://",
        "safari-web-extension://",
    ],
    "chatDomains": ["chatgpt.com", "gemini.google.com", "claude.ai", "copilot.microsoft.com"],
    "codeHostDomains": list(CODE_HOST_DOMAINS),
    "videoDomains": list(VIDEO_DOMAINS),
    "projectDomains": [
        "notion.so",
        "notion.site",
        "trello.com",
        "atlassian.net",
        "jira.atlassian.com",
        "drive.google.com",
        "figma.com",
    ],
    "projectNotionDomains": ["notion.so", "notion.site"],
    "projectJiraDomains": ["atlassian.net", "jira.atlassian.com"],
    "projectNotionHints": [
        "project",
        "roadmap",
        "sprint",
        "backlog",
        "kanban",
        "task",
        "milestone",
        "okr",
        "plan",
        "planning",
    ],
    "projectTitleHints": [
        "project",
        "roadmap",
        "sprint",
        "backlog",
        "kanban",
        "task",
        "milestone",
        "okr",
        "plan",
        "planning",
        "board",
    ],
    "projectJiraPathHints": ["/jira/software/", "/secure/rapidboard.jspa", "/boards/", "/browse/"],
    "projectFigmaPathHints": ["/file/", "/design/", "/proto/", "/board/"],
    "projectNotionRequireHint": True,
    "projectDomainSuffixMatching": True,
    "docsDomainPrefix": "docs.",
    "docsPathHints": list(DOC_PATH_HINTS),
    "blogPathHints": list(BLOG_PATH_HINTS),
    "authPathRegex": [
        "(?i)(^|/)(login|signin|sign-in|sso|oauth)(/|$)",
        "(?i)(^|/)(api-keys|credentials)(/|$)",
    ],
    "authContainsHintsSoft": list(SENSITIVE_QUERY_KEYS),
    "adminAuthRequiresStrongSignal": True,
    "consoleDomains": ["console.aws.amazon.com", "console.cloud.google.com", "portal.azure.com"],
    "emptyBucketMessage": "_(empty)_",
    "canonicalTitleEnabled": True,
    "canonicalTitleMaxLen": 88,
    "canonicalTitleStripSuffixes": [
        " - YouTube",
        " | YouTube",
        " · GitHub",
        " - GitHub",
        " | GitHub",
    ],
    "canonicalTitleStripPrefixesRegex": [
        "^\\(\\d+\\)\\s+",
    ],
    "canonicalTitleHostRules": {
        "youtube.com": {"stripSuffixes": [" - YouTube", " | YouTube"]},
        "github.com": {"preferRepoSlug": True},
    },
    "docsOmitDomInBullets": True,
    "docsOmitKindFor": ["docs", "article"],
    "docsIncludeSrcWhenMultiBrowser": False,
    "docsLargeSectionItemsGte": 20,
    "docsLargeSectionDomainsGte": 10,
    "docsMultiDomainMinItems": 2,
    "docsOneOffGroupByKindWhenDomainsGt": 8,
    "showDomChipInDomainGroupedSections": False,
    "showKindChipInSections": {"media": False, "repos": False, "projects": False, "tools": False, "docs": False},
    "quickWinsEnableMiniCategories": True,
    "quickWinsMiniCategories": ["leisure", "shopping"],
    "quickWinsLowEffortReasons": [
        "leisure_domain",
        "leisure_keyword",
        "shopping_domain",
        "shopping_keyword",
    ],
    "quickWinsDomainSuffixMatching": True,
    "render": {
        "badges": {
            "enabled": True,
            "maxPerBullet": 3,
            "includeTopicInHighPriority": True,
            "includeQuickWinsWhy": False,
        },
        "ordering": {
            "domains": {"byCountThenAlpha": True, "pinned": []},
            "items": {"alphaByTitleThenUrl": True},
        },
    },
}

ALLOWED_KINDS = set(RENDERER_ALLOWED_KINDS)

KIND_PRIORITY = ["paper", "spec", "docs", "repo", "article", "video", "tool", "misc", "admin"]
KIND_PRIORITY_INDEX = {k: i for i, k in enumerate(KIND_PRIORITY)}

DOMAIN_CATEGORY_ORDER = ["docs_site", "blog", "code_host", "console", "generic", "video"]
ADMIN_CATEGORY_ORDER = ["admin_auth", "admin_chat", "admin_local", "admin_internal"]

AGGREGATOR_MARKERS = ["trending", "top", "best of", "weekly", "digest", "list of", "directory"]
DEPTH_HINTS = ["/reference/", "/docs/", "/guide/", "/internals/", "/config", "/api-reference/"]

SECTION_ORDER = ["HIGH", "MEDIA", "REPOS", "PROJECTS", "TOOLS", "DOCS", "QUICK", "BACKLOG", "ADMIN"]


def merge_cfg(payload_cfg: Dict | None, override_cfg: Dict | None) -> Dict:
    merged = dict(DEFAULT_CFG)
    if payload_cfg:
        merged.update(payload_cfg)
    if override_cfg:
        merged.update(override_cfg)
    return merged
