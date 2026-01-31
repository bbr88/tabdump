(*
Dump & Close Tabs (Chrome + Safari) — All windows
Vault: /Users/i.bisarnov/obsidian/3d brain/Inbox/

Behavior:
- Dumps title + URL for all tabs in all windows (Chrome + Safari)
- Skips allowlisted URLs (keeps them open)
- Skips internal URL schemes (chrome://, about:, etc.)
- Optionally keeps pinned tabs (Chrome reliably; Safari best-effort)
- Closes only the dumped tabs
*)

-- ====== CONFIG ======
set vaultInbox to "/Users/i.bisarnov/obsidian/3d brain/Inbox/"
set keepPinnedTabs to true

-- If URL contains any of these substrings => KEEP OPEN (not dumped, not closed)
set allowlistPatterns to {"mail.google.com", "calendar.google.com", "slack.com", "notion.so", "github.com", "postgres.ai", "gemini.google.com"}

-- Skip internal pages from dumping/closing
set skipUrlPrefixes to {"chrome://", "chrome-extension://", "about:", "file://", "safari-web-extension://", "favorites://", "safari://"}
-- ====================

-- Don’t auto-launch Chrome or Safari
tell application "System Events"
set chromeRunning to (exists process "Google Chrome")
set safariRunning to (exists process "Safari")
end tell

on isAllowlisted(theURL, patterns)
  if theURL is missing value then return true
  if theURL is "" then return true
  repeat with p in patterns
    if theURL contains (p as text) then return true
  end repeat
  return false
end isAllowlisted

on hasAnyPrefix(theURL, prefixes)
  if theURL is missing value or theURL is "" then return true
  repeat with pref in prefixes
    if theURL starts with (pref as text) then return true
  end repeat
  return false
end hasAnyPrefix

on safeTitle(t, fallback)
  if t is missing value then return fallback
  if t is "" then return fallback
  return t
end safeTitle

-- Ensure folder exists
do shell script "mkdir -p " & quoted form of vaultInbox

set ts to do shell script "date '+%Y-%m-%d %H-%M-%S'"
set outPath to vaultInbox & "TabDump " & ts & ".md"

set md to "---" & linefeed & ¬
  "created: " & ts & linefeed & ¬
  "tags: [tabs, dump]" & linefeed & ¬
  "---" & linefeed & linefeed & ¬
  "# Tab dump " & ts & linefeed & linefeed

-- =========================
-- 1) DUMP CHROME (stable window IDs)
-- =========================
set chromeDumpedAny to false

if chromeRunning then
  tell application "Google Chrome"
    set chromeWinIds to {}
    repeat with w in (every window)
      try
        set end of chromeWinIds to (id of w)
      end try
    end repeat

    if (count of chromeWinIds) > 0 then
      set md to md & "## Chrome" & linefeed & linefeed

      repeat with wid in chromeWinIds
        try
          tell window id (wid as integer)
            set windowHeaderWritten to false

            set tabCount to (count of tabs)
            repeat with i from 1 to tabCount
              set t to tab i
              set u to URL of t
              set ttlRaw to title of t

              -- Skip empty/new-tab-ish entries
              if u is not missing value and u is not "" and ttlRaw is not "New Tab" then
                if my hasAnyPrefix(u, skipUrlPrefixes) is false then
                  if my isAllowlisted(u, allowlistPatterns) is false then
                    set isPinned to false
                    if keepPinnedTabs then
                      try
                        set isPinned to (pinned of t)
                      end try
                    end if

                    if (keepPinnedTabs is false) or (isPinned is false) then
                      if windowHeaderWritten is false then
                        set md to md & "### Window " & (wid as text) & linefeed
                        set windowHeaderWritten to true
                      end if

                      set ttlOut to my safeTitle(ttlRaw, u)
                      set md to md & "- [" & ttlOut & "](" & u & ")" & linefeed
                      set chromeDumpedAny to true
                    end if
                  end if
                end if
              end if
            end repeat

            if windowHeaderWritten is true then set md to md & linefeed
          end tell
        end try
      end repeat

      if chromeDumpedAny is false then
        set md to md & "_(Nothing dumped from Chrome — everything was allowlisted / internal / pinned.)_" & linefeed & linefeed
      end if
    end if
  end tell
end if


-- =========================
-- 2) DUMP SAFARI (ONLY if already running)
-- =========================
set safariDumpedAny to false

if safariRunning then
  tell application "Safari"
    if (count of windows) > 0 then
      set md to md & "## Safari" & linefeed & linefeed
      set wIdx to 0

      repeat with w in (every window)
        set wIdx to wIdx + 1
        set windowHeaderWritten to false

        set tabCount to (count of tabs of w)
        repeat with i from 1 to tabCount
          set t to tab i of w
          set u to URL of t
          set ttl to name of t

          -- Skip Start Page / empty URL / internal pages
          if u is not missing value and u is not "" and ttl is not "Start Page" then
            if my hasAnyPrefix(u, skipUrlPrefixes) is false then
              if my isAllowlisted(u, allowlistPatterns) is false then
                if windowHeaderWritten is false then
                  set md to md & "### Window " & wIdx & linefeed
                  set windowHeaderWritten to true
                end if

                set ttl2 to my safeTitle(ttl, u)
                set md to md & "- [" & ttl2 & "](" & u & ")" & linefeed
                set safariDumpedAny to true
              end if
            end if
          end if
        end repeat

        if windowHeaderWritten is true then set md to md & linefeed
      end repeat

      if safariDumpedAny is false then
        set md to md & "_(Nothing dumped from Safari.)_" & linefeed & linefeed
      end if
    end if
  end tell
end if

-- =========================
-- 3) WRITE MARKDOWN (UTF-8) — AppleScript-native
-- =========================
set outFile to POSIX file outPath
try
  set f to open for access outFile with write permission
  set eof of f to 0
  write md to f as «class utf8»
  close access f
on error errMsg number errNum
  try
    close access outFile
  end try
  error "Failed to write markdown file: " & errMsg number errNum
end try

-- =========================
-- 4) CLOSE TABS — CHROME (reverse order, stable window IDs)
-- =========================
if chromeRunning then
  tell application "Google Chrome"
    set chromeWinIds2 to {}
    repeat with w in (every window)
      try
        set end of chromeWinIds2 to (id of w)
      end try
    end repeat

    repeat with wid in chromeWinIds2
      try
        tell window id (wid as integer)
          repeat with i from (count of tabs) to 1 by -1
            set t to tab i
            set u to URL of t
            set ttlRaw to title of t

            if u is not missing value and u is not "" and ttlRaw is not "New Tab" then
              if my hasAnyPrefix(u, skipUrlPrefixes) is false then
                if my isAllowlisted(u, allowlistPatterns) is false then
                  set isPinned to false
                  if keepPinnedTabs then
                    try
                      set isPinned to (pinned of t)
                    end try
                  end if

                  if (keepPinnedTabs is false) or (isPinned is false) then
                    try
                      close t
                    end try
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


-- =========================
-- 5) CLOSE TABS — SAFARI (ONLY if already running)
-- =========================
if safariRunning then
  tell application "Safari"
    repeat with w in (every window)
      repeat with i from (count of tabs of w) to 1 by -1
        set t to tab i of w
        set u to URL of t
        set ttl to name of t

        -- Skip Start Page / empty URL / internal pages
        if u is not missing value and u is not "" and ttl is not "Start Page" then
          if my hasAnyPrefix(u, skipUrlPrefixes) is false then
            if my isAllowlisted(u, allowlistPatterns) is false then
              try
                close t
              end try
            end if
          end if
        end if
      end repeat
    end repeat
  end tell
end if

display notification "Dumped tabs to Obsidian Inbox and closed them (except allowlist/pinned)." with title "TabDump"
