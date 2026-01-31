(*
TabDump — Dump & Close Tabs into Obsidian (Config-first template)

What it does:
- Dumps title + URL from supported browsers (all windows)
- Skips allowlisted URLs + internal pages + optional title filters
- Writes Markdown into your Obsidian vault
- Closes only the dumped tabs
- Does NOT launch browsers (only acts if already running)

Supported browsers today: Chrome, Safari
Planned: Firefox (via UI scripting)

*)

-- =========================
-- CONFIG (EDIT ONLY THIS)
-- =========================

-- 1) Vault path (must exist or will be created)
property VAULT_INBOX : "/Users/i.bisarnov/obsidian/3d brain/Inbox/"

-- 2) Output filename template
--    Tokens supported: {ts}
property OUTPUT_FILENAME_TEMPLATE : "TabDump {ts}.md"

-- 3) Which browsers to process
--    Allowed values: "Chrome", "Safari", "Firefox" (Firefox is stub for later)
property BROWSERS : {"Chrome", "Safari"} -- e.g. {"Chrome"} or {"Safari", "Chrome"}

-- 4) Exclusions: if URL contains any substring => KEEP OPEN (not dumped, not closed)
property ALLOWLIST_URL_CONTAINS : {"mail.google.com", "calendar.google.com", "slack.com", "notion.so", "github.com", "postgres.ai", "gemini.google.com"}

-- 5) Additional recommended configs
property KEEP_PINNED_TABS : true

-- Skip URLs with these prefixes (internal pages, extensions, local files)
property SKIP_URL_PREFIXES : {"chrome://", "chrome-extension://", "about:", "file://", "safari-web-extension://", "favorites://", "safari://"}

-- Skip tabs whose title is one of these (helps avoid “New Tab” / “Start Page” noise)
property SKIP_TITLES_EXACT : {"New Tab", "Start Page"}

-- If true: group output by browser + window sections. If false: flat list.
property OUTPUT_GROUP_BY_WINDOW : true

-- If true: include per-link metadata line (domain::, browser::)
property OUTPUT_INCLUDE_METADATA : false

-- Safety: if true, don’t close anything, only dump (dry run)
property DRY_RUN : true

-- =========================
-- END CONFIG
-- =========================


-- ---------- Helpers ----------
on nowTimestamp()
  return do shell script "date '+%Y-%m-%d %H-%M-%S'"
end nowTimestamp

on ensureFolder(pathStr)
  do shell script "mkdir -p " & quoted form of pathStr
end ensureFolder

on joinLines(linesList)
  set outText to ""
  repeat with l in linesList
    set outText to outText & (l as text) & linefeed
  end repeat
  return outText
end joinLines

on safeTitle(t, fallback)
  if t is missing value then return fallback
  if t is "" then return fallback
  return t
end safeTitle

on hasAnyPrefix(theURL, prefixes)
  if theURL is missing value or theURL is "" then return true
  repeat with pref in prefixes
    if theURL starts with (pref as text) then return true
  end repeat
  return false
end hasAnyPrefix

on isAllowlisted(theURL, patterns)
  if theURL is missing value then return true
  if theURL is "" then return true
  repeat with p in patterns
    if theURL contains (p as text) then return true
  end repeat
  return false
end isAllowlisted

on isTitleSkipped(theTitle, skippedTitles)
  if theTitle is missing value then return false
  repeat with skippedTitle in skippedTitles
    if theTitle is (skippedTitle as text) then return true
  end repeat
  return false
end isTitleSkipped

on writeUtf8File(outPath, contentText)
  set outFile to POSIX file outPath
  try
    set f to open for access outFile with write permission
    set eof of f to 0
    write contentText to f as «class utf8»
    close access f
  on error errMsg number errNum
    try
      close access outFile
    end try
    error "Failed to write markdown file: " & errMsg number errNum
  end try
end writeUtf8File

on replaceAll(theText, token, replacement)
  set AppleScript's text item delimiters to token
  set parts to every text item of theText
  set AppleScript's text item delimiters to replacement
  set outText to parts as text
  set AppleScript's text item delimiters to ""
  return outText
end replaceAll

on shouldProcess(browserName, enabledList)
  repeat with b in enabledList
    if (b as text) is browserName then return true
  end repeat
  return false
end shouldProcess


-- ---------- Detect running processes (don’t auto-launch) ----------
tell application "System Events"
set chromeRunning to (exists process "Google Chrome")
set safariRunning to (exists process "Safari")
set firefoxRunning to (exists process "Firefox")
end tell


-- ---------- Prepare output ----------
set ts to nowTimestamp()
my ensureFolder(VAULT_INBOX)

set outName to replaceAll(OUTPUT_FILENAME_TEMPLATE, "{ts}", ts)
set outPath to VAULT_INBOX & outName

set mdLines to {}
set end of mdLines to "---"
set end of mdLines to "created: " & ts
set end of mdLines to "tags: [tabs, dump]"
set end of mdLines to "---"
set end of mdLines to ""
set end of mdLines to "# Tab dump " & ts
set end of mdLines to ""


-- =========================
-- CHROME: Dump
-- =========================
set chromeDumpedAny to false
if shouldProcess("Chrome", BROWSERS) and chromeRunning then
  set end of mdLines to "## Chrome"
  set end of mdLines to ""

  tell application "Google Chrome"
  -- snapshot stable window IDs
    set winIds to {}
    repeat with w in (every window)
      try
        set end of winIds to (id of w)
      end try
    end repeat

    repeat with wid in winIds
      try
        tell window id (wid as integer)
          set windowHeaderWritten to false
          set tabCount to (count of tabs)

          repeat with i from 1 to tabCount
            set t to tab i
            set u to URL of t
            set ttlRaw to title of t

            if u is not missing value and u is not "" then
              if my isTitleSkipped(ttlRaw, SKIP_TITLES_EXACT) is false then
                if my hasAnyPrefix(u, SKIP_URL_PREFIXES) is false then
                  if my isAllowlisted(u, ALLOWLIST_URL_CONTAINS) is false then

                  -- pinned filter (best-effort)
                    set isPinned to false
                    if KEEP_PINNED_TABS then
                      try
                        set isPinned to (pinned of t)
                      end try
                    end if

                    if (KEEP_PINNED_TABS is false) or (isPinned is false) then
                      if OUTPUT_GROUP_BY_WINDOW then
                        if windowHeaderWritten is false then
                          set end of mdLines to "### Window " & (wid as text)
                          set windowHeaderWritten to true
                        end if
                      end if

                      set ttlOut to my safeTitle(ttlRaw, u)
                      if OUTPUT_INCLUDE_METADATA then
                        set end of mdLines to "- [" & ttlOut & "](" & u & ")
  - browser:: chrome"
                      else
                        set end of mdLines to "- [" & ttlOut & "](" & u & ")"
                      end if
                      set chromeDumpedAny to true
                    end if
                  end if
                end if
              end if
            end if
          end repeat

          if OUTPUT_GROUP_BY_WINDOW and windowHeaderWritten then set end of mdLines to ""
        end tell
      end try
    end repeat
  end tell

  if chromeDumpedAny is false then
    set end of mdLines to "_(Nothing dumped from Chrome — everything was allowlisted / internal / pinned.)_"
    set end of mdLines to ""
  end if
end if


-- =========================
-- SAFARI: Dump
-- =========================
set safariDumpedAny to false
if shouldProcess("Safari", BROWSERS) and safariRunning then
  set end of mdLines to "## Safari"
  set end of mdLines to ""

  tell application "Safari"
    set wIdx to 0
    repeat with w in (every window)
      set wIdx to wIdx + 1
      set windowHeaderWritten to false
      set tabCount to (count of tabs of w)

      repeat with i from 1 to tabCount
        set t to tab i of w
        set u to URL of t
        set ttlRaw to name of t

        if u is not missing value and u is not "" then
          if my isTitleSkipped(ttlRaw, SKIP_TITLES_EXACT) is false then
            if my hasAnyPrefix(u, SKIP_URL_PREFIXES) is false then
              if my isAllowlisted(u, ALLOWLIST_URL_CONTAINS) is false then

              -- pinned filter (best-effort; may not exist in some versions)
                set isPinned to false
                if KEEP_PINNED_TABS then
                  try
                    set isPinned to (pinned of t)
                  end try
                end if

                if (KEEP_PINNED_TABS is false) or (isPinned is false) then
                  if OUTPUT_GROUP_BY_WINDOW then
                    if windowHeaderWritten is false then
                      set end of mdLines to "### Window " & wIdx
                      set windowHeaderWritten to true
                    end if
                  end if

                  set ttlOut to my safeTitle(ttlRaw, u)
                  if OUTPUT_INCLUDE_METADATA then
                    set end of mdLines to "- [" & ttlOut & "](" & u & ")
  - browser:: safari"
                  else
                    set end of mdLines to "- [" & ttlOut & "](" & u & ")"
                  end if
                  set safariDumpedAny to true
                end if
              end if
            end if
          end if
        end if
      end repeat

      if OUTPUT_GROUP_BY_WINDOW and windowHeaderWritten then set end of mdLines to ""
    end repeat
  end tell

  if safariDumpedAny is false then
    set end of mdLines to "_(Nothing dumped from Safari.)_"
    set end of mdLines to ""
  end if
end if


-- =========================
-- FIREFOX: Stub (later)
-- =========================
if shouldProcess("Firefox", BROWSERS) then
  if firefoxRunning then
    set end of mdLines to "## Firefox"
    set end of mdLines to ""
    set end of mdLines to "_(Firefox support not implemented yet — will require UI scripting.)_"
    set end of mdLines to ""
  end if
end if


-- ---------- Write file ----------
set mdText to my joinLines(mdLines)
my writeUtf8File(outPath, mdText)


-- =========================
-- Close tabs (if not DRY_RUN)
-- =========================
if DRY_RUN is false then

-- CHROME close
  if shouldProcess("Chrome", BROWSERS) and chromeRunning then
    tell application "Google Chrome"
      set winIds2 to {}
      repeat with w in (every window)
        try
          set end of winIds2 to (id of w)
        end try
      end repeat

      repeat with wid in winIds2
        try
          tell window id (wid as integer)
            repeat with i from (count of tabs) to 1 by -1
              set t to tab i
              set u to URL of t
              set ttlRaw to title of t

              if u is not missing value and u is not "" then
                if my isTitleSkipped(ttlRaw, SKIP_TITLES_EXACT) is false then
                  if my hasAnyPrefix(u, SKIP_URL_PREFIXES) is false then
                    if my isAllowlisted(u, ALLOWLIST_URL_CONTAINS) is false then
                      set isPinned to false
                      if KEEP_PINNED_TABS then
                        try
                          set isPinned to (pinned of t)
                        end try
                      end if

                      if (KEEP_PINNED_TABS is false) or (isPinned is false) then
                        try
                          close t
                        end try
                      end if
                    end if
                  end if
                end if
              end if
            end repeat
          end tell
        end try
      end repeat
    end tell
  end if

  -- SAFARI close
  if shouldProcess("Safari", BROWSERS) and safariRunning then
    tell application "Safari"
      repeat with w in (every window)
        repeat with i from (count of tabs of w) to 1 by -1
          set t to tab i of w
          set u to URL of t
          set ttlRaw to name of t

          if u is not missing value and u is not "" then
            if my isTitleSkipped(ttlRaw, SKIP_TITLES_EXACT) is false then
              if my hasAnyPrefix(u, SKIP_URL_PREFIXES) is false then
                if my isAllowlisted(u, ALLOWLIST_URL_CONTAINS) is false then
                  set isPinned to false
                  if KEEP_PINNED_TABS then
                    try
                      set isPinned to (pinned of t)
                    end try
                  end if

                  if (KEEP_PINNED_TABS is false) or (isPinned is false) then
                    try
                      close t
                    end try
                  end if
                end if
              end if
            end if
          end if
        end repeat
      end repeat
    end tell
  end if

end if


if DRY_RUN then
  display notification "Dumped tabs (DRY_RUN=true, did not close any tabs)" with title "TabDump"
else
  display notification "Dumped & closed tabs (except allowlist/pinned)" with title "TabDump"
end if
