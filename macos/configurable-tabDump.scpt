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

-- Automation defaults (used by external runner)
property MAX_TABS : 30
property CHECK_EVERY_MINUTES : 5
property COOLDOWN_MINUTES : 30

-- Post-processing model hint (used by external runner)
property TAG_MODEL : "gpt-4.1-mini"

-- Optional: JSON config file. If empty, resolves via default locations.
property CONFIG_PATH : ""

-- =========================
-- END CONFIG
-- =========================

-- ---------- JSON config loading ----------
on loadJsonConfig(pathStr)
  set py to "CONFIG_PATH=" & quoted form of pathStr & " python3 - <<'PY'\n" & ¬
    "import json, os\n" & ¬
    "p = os.path.expanduser(os.environ.get('CONFIG_PATH', ''))\n" & ¬
    "if not p or not os.path.exists(p):\n" & ¬
    "  print('')\n" & ¬
    "  raise SystemExit\n" & ¬
    "with open(p, 'r', encoding='utf-8') as f:\n" & ¬
    "  data = json.load(f)\n" & ¬
    "\n" & ¬
    "key_map = {\n" & ¬
    "  'vaultInbox': 'VAULT_INBOX',\n" & ¬
    "  'outputFilenameTemplate': 'OUTPUT_FILENAME_TEMPLATE',\n" & ¬
    "  'browsers': 'BROWSERS',\n" & ¬
    "  'allowlistUrlContains': 'ALLOWLIST_URL_CONTAINS',\n" & ¬
    "  'keepPinnedTabs': 'KEEP_PINNED_TABS',\n" & ¬
    "  'skipUrlPrefixes': 'SKIP_URL_PREFIXES',\n" & ¬
    "  'skipTitlesExact': 'SKIP_TITLES_EXACT',\n" & ¬
    "  'outputGroupByWindow': 'OUTPUT_GROUP_BY_WINDOW',\n" & ¬
    "  'outputIncludeMetadata': 'OUTPUT_INCLUDE_METADATA',\n" & ¬
    "  'dryRun': 'DRY_RUN',\n" & ¬
    "  'maxTabs': 'MAX_TABS',\n" & ¬
    "  'checkEveryMinutes': 'CHECK_EVERY_MINUTES',\n" & ¬
    "  'cooldownMinutes': 'COOLDOWN_MINUTES',\n" & ¬
    "  'tagModel': 'TAG_MODEL',\n" & ¬
    "}\n" & ¬
    "allowed = set(key_map.values())\n" & ¬
    "\n" & ¬
    "def esc(s):\n" & ¬
    "  return str(s).replace('\\\\', '\\\\\\\\').replace('\"', '\\\\\"').replace('\\n', '\\\\n').replace('\\r', '\\\\r')\n" & ¬
    "\n" & ¬
    "def as_as(v):\n" & ¬
    "  if isinstance(v, bool):\n" & ¬
    "    return 'true' if v else 'false'\n" & ¬
    "  if isinstance(v, (int, float)):\n" & ¬
    "    return str(v)\n" & ¬
    "  if isinstance(v, list):\n" & ¬
    "    return '{' + ', '.join(as_as(x) for x in v) + '}'\n" & ¬
    "  if isinstance(v, dict):\n" & ¬
    "    return '{' + ', '.join([f'|{k}|:' + as_as(val) for k, val in v.items()]) + '}'\n" & ¬
    "  return '\"' + esc(v) + '\"'\n" & ¬
    "\n" & ¬
    "pairs = []\n" & ¬
    "for k, v in data.items():\n" & ¬
    "  k2 = key_map.get(k, k)\n" & ¬
    "  if k2 == 'VAULT_INBOX' and isinstance(v, str):\n" & ¬
    "    v = os.path.expanduser(v)\n" & ¬
    "  if k2 in allowed:\n" & ¬
    "    pairs.append(f'|{k2}|:' + as_as(v))\n" & ¬
    "print('{' + ', '.join(pairs) + '}')\n" & ¬
    "PY"

  set recText to do shell script py
  if recText is "" then return missing value
  return run script recText
end loadJsonConfig

on applyConfig(cfg)
  try
    set VAULT_INBOX to VAULT_INBOX of cfg
  end try
  try
    set OUTPUT_FILENAME_TEMPLATE to OUTPUT_FILENAME_TEMPLATE of cfg
  end try
  try
    set BROWSERS to BROWSERS of cfg
  end try
  try
    set ALLOWLIST_URL_CONTAINS to ALLOWLIST_URL_CONTAINS of cfg
  end try
  try
    set KEEP_PINNED_TABS to KEEP_PINNED_TABS of cfg
  end try
  try
    set SKIP_URL_PREFIXES to SKIP_URL_PREFIXES of cfg
  end try
  try
    set SKIP_TITLES_EXACT to SKIP_TITLES_EXACT of cfg
  end try
  try
    set OUTPUT_GROUP_BY_WINDOW to OUTPUT_GROUP_BY_WINDOW of cfg
  end try
  try
    set OUTPUT_INCLUDE_METADATA to OUTPUT_INCLUDE_METADATA of cfg
  end try
  try
    set DRY_RUN to DRY_RUN of cfg
  end try
  try
    set MAX_TABS to MAX_TABS of cfg
  end try
  try
    set CHECK_EVERY_MINUTES to CHECK_EVERY_MINUTES of cfg
  end try
  try
    set COOLDOWN_MINUTES to COOLDOWN_MINUTES of cfg
  end try
  try
    set TAG_MODEL to TAG_MODEL of cfg
  end try
end applyConfig

set configPathResolved to my resolveConfigPath()
set cfg to my loadJsonConfig(configPathResolved)
if cfg is not missing value then
  my applyConfig(cfg)
else
  error "Config not found at: " & configPathResolved & " — run install.sh or set CONFIG_PATH."
end if
set VAULT_INBOX to my normalizeDirPath(VAULT_INBOX)


-- ---------- Helpers ----------
on resolveConfigPath()
  if CONFIG_PATH is not "" then return CONFIG_PATH

  set appSupportPath to my appSupportConfigPath()
  if my fileExists(appSupportPath) then return appSupportPath

  set scriptPath to my scriptDirConfigPath()
  if scriptPath is not "" and my fileExists(scriptPath) then return scriptPath

  return appSupportPath
end resolveConfigPath

on appSupportConfigPath()
  set homePath to do shell script "printf %s \"$HOME\""
  return homePath & "/Library/Application Support/TabDump/config.json"
end appSupportConfigPath

on scriptDirConfigPath()
  try
    set scriptPath to POSIX path of (path to me)
    set scriptDir to do shell script "dirname " & quoted form of scriptPath
    return scriptDir & "/config.json"
  on error
    return ""
  end try
end scriptDirConfigPath

on fileExists(pathStr)
  try
    do shell script "test -f " & quoted form of pathStr
    return true
  on error
    return false
  end try
end fileExists

on normalizeDirPath(pathStr)
  set p to pathStr as text
  if p is "" then
    error "VAULT_INBOX is empty. Set vaultInbox in the JSON config."
  end if
  if p ends with "/" then return p
  return p & "/"
end normalizeDirPath

on nowTimestamp()
  return do shell script "date '+%Y-%m-%d %H-%M-%S'"
end nowTimestamp

on nowEpochSeconds()
  return (do shell script "date +%s") as integer
end nowEpochSeconds

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

on stateFilePath()
  set homePath to do shell script "printf %s \"$HOME\""
  return homePath & "/Library/Application Support/TabDump/state.json"
end stateFilePath

on stateDirPath()
  set statePath to my stateFilePath()
  return do shell script "dirname " & quoted form of statePath
end stateDirPath

on readState(pathStr)
  set py to "STATE_PATH=" & quoted form of pathStr & " python3 - <<'PY'\n" & ¬
    "import json, os\n" & ¬
    "p = os.environ.get('STATE_PATH', '')\n" & ¬
    "if not p or not os.path.exists(p):\n" & ¬
    "  print('0 0 0')\n" & ¬
    "  raise SystemExit\n" & ¬
    "with open(p, 'r', encoding='utf-8') as f:\n" & ¬
    "  data = json.load(f)\n" & ¬
    "last_check = int(data.get('lastCheck', 0))\n" & ¬
    "last_dump = int(data.get('lastDump', 0))\n" & ¬
    "last_tabs = int(data.get('lastTabs', 0))\n" & ¬
    "print(f\"{last_check} {last_dump} {last_tabs}\")\n" & ¬
    "PY"

  set outText to do shell script py
  set AppleScript's text item delimiters to " "
  set parts to text items of outText
  set AppleScript's text item delimiters to ""

  set lastCheck to 0
  set lastDump to 0
  set lastTabs to 0
  try
    if (count of parts) ≥ 1 then set lastCheck to (item 1 of parts) as integer
    if (count of parts) ≥ 2 then set lastDump to (item 2 of parts) as integer
    if (count of parts) ≥ 3 then set lastTabs to (item 3 of parts) as integer
  end try

  return {lastCheck:lastCheck, lastDump:lastDump, lastTabs:lastTabs}
end readState

on writeState(pathStr, lastCheck, lastDump, lastTabs)
  my ensureFolder(my stateDirPath())
  set py to "STATE_PATH=" & quoted form of pathStr & " LAST_CHECK=" & quoted form of (lastCheck as text) & " LAST_DUMP=" & quoted form of (lastDump as text) & " LAST_TABS=" & quoted form of (lastTabs as text) & " python3 - <<'PY'\n" & ¬
    "import json, os\n" & ¬
    "p = os.environ['STATE_PATH']\n" & ¬
    "def to_int(val):\n" & ¬
    "  s = str(val).replace(',', '')\n" & ¬
    "  try:\n" & ¬
    "    return int(s)\n" & ¬
    "  except Exception:\n" & ¬
    "    return int(float(s))\n" & ¬
    "data = {\n" & ¬
    "  'lastCheck': to_int(os.environ.get('LAST_CHECK', 0)),\n" & ¬
    "  'lastDump': to_int(os.environ.get('LAST_DUMP', 0)),\n" & ¬
    "  'lastTabs': to_int(os.environ.get('LAST_TABS', 0)),\n" & ¬
    "}\n" & ¬
    "with open(p, 'w', encoding='utf-8') as f:\n" & ¬
    "  json.dump(data, f, indent=2)\n" & ¬
    "  f.write('\\n')\n" & ¬
    "PY"
  do shell script py
end writeState

on countOpenTabs()
  set totalTabs to 0

  tell application "System Events"
    set chromeRunning to (exists process "Google Chrome")
    set safariRunning to (exists process "Safari")
  end tell

  if chromeRunning and my shouldProcess("Chrome", BROWSERS) then
    tell application "Google Chrome"
      repeat with w in windows
        set totalTabs to totalTabs + (count of tabs of w)
      end repeat
    end tell
  end if

  if safariRunning and my shouldProcess("Safari", BROWSERS) then
    tell application "Safari"
      repeat with w in windows
        set totalTabs to totalTabs + (count of tabs of w)
      end repeat
    end tell
  end if

  return totalTabs
end countOpenTabs

-- ---------- Self-gating ----------
set statePath to my stateFilePath()
set stateRec to my readState(statePath)

set lastCheck to lastCheck of stateRec
set lastDump to lastDump of stateRec
set lastTabs to lastTabs of stateRec

set nowEpoch to my nowEpochSeconds()
set checkEverySec to (CHECK_EVERY_MINUTES as integer) * 60
set cooldownSec to (COOLDOWN_MINUTES as integer) * 60

if checkEverySec > 0 then
  if (nowEpoch - lastCheck) < checkEverySec then return
end if

set totalTabs to my countOpenTabs()
set lastCheck to nowEpoch
set lastTabs to totalTabs

if (MAX_TABS as integer) > 0 then
  if totalTabs < (MAX_TABS as integer) then
    my writeState(statePath, lastCheck, lastDump, lastTabs)
    return
  end if
end if

if cooldownSec > 0 then
  if (nowEpoch - lastDump) < cooldownSec then
    my writeState(statePath, lastCheck, lastDump, lastTabs)
    return
  end if
end if


-- ---------- Detect running processes (don’t auto-launch) ----------
tell application "System Events"
set chromeRunning to (exists process "Google Chrome")
set safariRunning to (exists process "Safari")
set firefoxRunning to (exists process "Firefox")
end tell


-- ---------- Prepare output ----------
set ts to nowTimestamp()
my ensureFolder(VAULT_INBOX)
set dumpId to do shell script "uuidgen"

set outName to replaceAll(OUTPUT_FILENAME_TEMPLATE, "{ts}", ts)
set outPath to VAULT_INBOX & outName

set mdLines to {}
set end of mdLines to "---"
set end of mdLines to "created: " & ts
set end of mdLines to "tabdump_id: " & dumpId
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
set lastDump to my nowEpochSeconds()
my writeState(statePath, lastCheck, lastDump, totalTabs)


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
