param(
  [string]$OutputPath = "contracts/vocabulary-whitelist.json"
)

$ErrorActionPreference = "Stop"

$sourceUrl = "https://api.github.com/repos/lfcypo/pep-senior-eng-vocab-json/contents/vocabulary.json?ref=main"
$allowedBooks = @(
  "必修第一册",
  "必修第二册",
  "必修第三册",
  "选必修第一册",
  "选必修第二册"
)

$responseText = (curl.exe -L --max-time 90 -s -H "User-Agent: codex-local" $sourceUrl) -join "`n"
if ([string]::IsNullOrWhiteSpace($responseText)) {
  throw "Vocabulary source response was empty."
}

$response = $responseText | ConvertFrom-Json
if ($response.encoding -ne "base64" -or [string]::IsNullOrWhiteSpace($response.content)) {
  throw "Unexpected GitHub content response."
}

$bytes = [Convert]::FromBase64String(($response.content -replace "\s", ""))
$sourceItems = [Text.Encoding]::UTF8.GetString($bytes) | ConvertFrom-Json
$selectedItems = $sourceItems | Where-Object { $allowedBooks -contains $_.book }
$zkPath = Join-Path $PSScriptRoot "..\contracts\vocabulary\ecdict-zk.json"
$zkSource = Get-Content -Raw -Encoding UTF8 -LiteralPath $zkPath | ConvertFrom-Json

$closedClassWords = @(
  "a", "an", "the", "and", "or", "but", "nor", "so", "yet", "for",
  "i", "me", "my", "mine", "myself", "you", "your", "yours", "yourself",
  "yourselves", "he", "him", "his", "himself", "she", "her", "hers",
  "herself", "it", "its", "itself", "we", "us", "our", "ours", "ourselves",
  "they", "them", "their", "theirs", "themselves", "this", "that", "these",
  "those", "who", "whom", "whose", "which", "what", "when", "where", "why",
  "how", "if", "unless", "because", "although", "though", "while", "until",
  "since", "before", "after", "as", "than", "whether", "not", "no",
  "to", "of", "in", "on", "at", "by", "with", "from", "into", "onto",
  "over", "under", "between", "among", "through", "during", "without",
  "about", "against", "across", "along", "around", "behind", "below",
  "beneath", "beside", "beyond", "near", "off", "out", "up", "down",
  "there", "here", "some", "any", "all", "both", "each", "either",
  "neither", "none", "every", "many", "much", "more", "most", "few",
  "little", "other", "another", "same", "such", "one", "two"
)

$entriesByWord = @{}
foreach ($baseWord in $zkSource.words) {
  $word = ([string]$baseWord).Trim().ToLowerInvariant()
  if ([string]::IsNullOrWhiteSpace($word)) {
    continue
  }
  $entriesByWord[$word] = [ordered]@{
    word = $word
    sources = @("ECDICT:zk")
    closed_class = $closedClassWords -contains $word
  }
}

foreach ($item in $selectedItems) {
  $word = ([string]$item.english).Trim().ToLowerInvariant()
  if ([string]::IsNullOrWhiteSpace($word)) {
    continue
  }

  if (-not $entriesByWord.ContainsKey($word)) {
    $entriesByWord[$word] = [ordered]@{
      word = $word
      sources = @()
      closed_class = $closedClassWords -contains $word
    }
  }

  $sourceKey = "$($item.book)|$($item.unit)"
  if ($entriesByWord[$word].sources -notcontains $sourceKey) {
    $entriesByWord[$word].sources += $sourceKey
  }
}

foreach ($word in $closedClassWords) {
  if (-not $entriesByWord.ContainsKey($word)) {
    $entriesByWord[$word] = [ordered]@{
      word = $word
      sources = @("closed_class")
      closed_class = $true
    }
  }
}

$entries = $entriesByWord.Values | Sort-Object { $_.word }
$singleWordEntries = @($entries | Where-Object { $_.word -match "^[a-z]+(?:'[a-z]+)?$" }).Count
$phraseEntries = @($entries | Where-Object { $_.word -notmatch "^[a-z]+(?:'[a-z]+)?$" }).Count
$highSchoolUnique = @($selectedItems.english | ForEach-Object { ([string]$_).Trim().ToLowerInvariant() } | Where-Object { $_ } | Sort-Object -Unique).Count
$payload = [ordered]@{
  schema_version = "1.0.0"
  generated_at = "2026-11-07"
  scope = "义务教育基础词汇补充 + 人教版（2019）必修1-3 + 选择性必修1-2"
  normalization = [ordered]@{
    case = "lowercase"
    whitespace = "trim and collapse"
    deduplication = "headword exact match; single words and phrases are counted separately"
    inflection_policy = "headword list stores base entries; runtime matching applies the documented lemma resolver and does not count inflected forms as new headwords"
    derivation_policy = "derivatives are accepted only when present in a source headword list or produced by an approved curriculum word-formation rule; they do not increase the baseline estimate"
    phrase_policy = "phrases remain exact multiword allowlist entries and are excluded from the single-headword count"
    proper_noun_policy = "ordinary curriculum proper nouns may remain as lexical entries; generated content still must not use real people, schools, or exam identifiers"
  }
  sources = @(
    [ordered]@{
      name = "ECDICT zk-tagged 1600 vocabulary"
      repository = "https://github.com/skywind3000/ECDICT"
      commit = "39cfb9672c0906b63569e0453c2e6abfb9ab182a"
      file = "contracts/vocabulary/ecdict-zk.json"
      license = "MIT"
      entry_count = @($zkSource.words).Count
    },
    [ordered]@{
      name = "pep-senior-eng-vocab-json"
      repository = "https://github.com/lfcypo/pep-senior-eng-vocab-json"
      commit = "84ec909920f982cbf8e05d5e1eda9874f3766797"
      license_status = "word membership reference only; no meanings or textbook passages redistributed"
      entry_count = $highSchoolUnique
    }
  )
  counting = [ordered]@{
    base_compulsory_zk_entries = @($zkSource.words).Count
    high_school_source_rows = @($selectedItems).Count
    high_school_unique_headwords = $highSchoolUnique
    single_word_entries = $singleWordEntries
    phrase_entries = $phraseEntries
    closed_class_entries = @($closedClassWords).Count
    unique_whitelist_entries = @($entries).Count
  }
  allowed_books = $allowedBooks
  entries = $entries
}

$json = $payload | ConvertTo-Json -Depth 6
$resolvedOutput = [IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputPath))
$parent = Split-Path -Parent $resolvedOutput
if (-not (Test-Path -LiteralPath $parent)) {
  New-Item -ItemType Directory -Path $parent | Out-Null
}
[IO.File]::WriteAllText($resolvedOutput, $json + "`n", [Text.UTF8Encoding]::new($false))
Write-Output "Wrote $($entries.Count) entries to $resolvedOutput"
