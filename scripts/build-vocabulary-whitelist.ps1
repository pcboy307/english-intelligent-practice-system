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
$officialPath = Join-Path $PSScriptRoot "..\contracts\vocabulary\kebiao-2022-level3.json"
$officialSource = Get-Content -Raw -Encoding UTF8 -LiteralPath $officialPath | ConvertFrom-Json
$supplementPath = Join-Path $PSScriptRoot "..\contracts\vocabulary\kebiao-2022-supplements.json"
$supplementSource = Get-Content -Raw -Encoding UTF8 -LiteralPath $supplementPath | ConvertFrom-Json

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
foreach ($baseWord in $officialSource.words) {
  $word = ([string]$baseWord).Trim().ToLowerInvariant()
  if ([string]::IsNullOrWhiteSpace($word)) {
    continue
  }
  $entriesByWord[$word] = [ordered]@{
    word = $word
    sources = @("课程标准2022|三级词汇表")
    closed_class = $closedClassWords -contains $word
  }
}

foreach ($basePhrase in $officialSource.phrase_entries) {
  $phrase = ([string]$basePhrase).Trim().ToLowerInvariant()
  if ($entriesByWord.ContainsKey($phrase)) {
    continue
  }
  $entriesByWord[$phrase] = [ordered]@{
    word = $phrase
    sources = @("课程标准2022|三级词汇表")
    closed_class = $false
  }
}

foreach ($supplementWord in $supplementSource.single_words) {
  $word = ([string]$supplementWord).Trim().ToLowerInvariant()
  if ($entriesByWord.ContainsKey($word)) {
    if ($entriesByWord[$word].sources -notcontains "课程标准2022|补充词表") {
      $entriesByWord[$word].sources += "课程标准2022|补充词表"
    }
    continue
  }
  $entriesByWord[$word] = [ordered]@{
    word = $word
    sources = @("课程标准2022|补充词表")
    closed_class = $closedClassWords -contains $word
  }
}

foreach ($supplementPhrase in $supplementSource.phrases) {
  $phrase = ([string]$supplementPhrase).Trim().ToLowerInvariant()
  if ($entriesByWord.ContainsKey($phrase)) {
    if ($entriesByWord[$phrase].sources -notcontains "课程标准2022|补充词表") {
      $entriesByWord[$phrase].sources += "课程标准2022|补充词表"
    }
    continue
  }
  $entriesByWord[$phrase] = [ordered]@{
    word = $phrase
    sources = @("课程标准2022|补充词表")
    closed_class = $false
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
      name = "义务教育英语课程标准（2022年版）附录3三级词汇表"
      publisher = "中华人民共和国教育部"
      url = $officialSource.source.url
      sha256 = $officialSource.source.sha256
      file = "contracts/vocabulary/kebiao-2022-level3.json"
      entry_count = $officialSource.counts.total_entries
    },
    [ordered]@{
      name = "义务教育英语课程标准（2022年版）附录3补充词表"
      publisher = "中华人民共和国教育部"
      url = $supplementSource.source.url
      sha256 = $supplementSource.source.sha256
      file = "contracts/vocabulary/kebiao-2022-supplements.json"
      entry_count = @($supplementSource.single_words).Count + @($supplementSource.phrases).Count
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
    base_compulsory_single_words = @($officialSource.words).Count
    base_compulsory_phrases = @($officialSource.phrase_entries).Count
    official_supplement_single_words = @($supplementSource.single_words).Count
    official_supplement_phrases = @($supplementSource.phrases).Count
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
