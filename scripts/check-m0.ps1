$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

function Read-Json([string]$Path) {
  return Get-Content -Raw -Encoding UTF8 -LiteralPath $Path | ConvertFrom-Json
}

function Assert-True([bool]$Condition, [string]$Message) {
  if (-not $Condition) {
    throw "ASSERTION_FAILED: $Message"
  }
}

$requiredFiles = @(
  "contracts/openapi.yaml",
  "contracts/VERSION",
  "contracts/curriculum.json",
  "contracts/bank-model.md",
  "contracts/design-tokens.json",
  "contracts/config-spec.md",
  "contracts/ownership.md",
  "contracts/error-codes.md",
  "contracts/admin-auth.md",
  "contracts/vocabulary-whitelist.json",
  "contracts/vocabulary/kebiao-2022-level3.json",
  "contracts/vocabulary/kebiao-2022-supplements.json",
  "docs/curriculum/grammar-by-unit.md",
  "docs/curriculum/grammar-id-ownership.md",
  "docs/curriculum/grammar-whitelist-mapping.md",
  "docs/curriculum/textbook-evidence.md",
  "docs/requirements-confirmation.md"
)
foreach ($file in $requiredFiles) {
  Assert-True (Test-Path -LiteralPath $file) "Missing required file: $file"
}

$schemas = Get-ChildItem -LiteralPath "contracts/schemas" -Filter "*.json"
foreach ($schema in $schemas) {
  Read-Json $schema.FullName | Out-Null
}
Write-Output "PASS json-schemas count=$($schemas.Count)"

$configs = Get-ChildItem -LiteralPath "config" -Filter "*.json"
foreach ($config in $configs) {
  Read-Json $config.FullName | Out-Null
}
Write-Output "PASS config-json count=$($configs.Count)"

$curriculum = Read-Json "contracts/curriculum.json"
$manifestVersion = (Get-Content -Raw -Encoding UTF8 -LiteralPath "contracts/VERSION").Trim()
$units = @($curriculum.units)
Assert-True ($units.Count -eq 25) "Expected 25 curriculum units"
$unitGroups = @($units | Group-Object book)
Assert-True ($unitGroups.Count -eq 5) "Expected 5 textbooks"
Assert-True (@($unitGroups | Where-Object Count -ne 5).Count -eq 0) "Each textbook must contain 5 units"

$grammarIds = @($curriculum.grammar_whitelist.id)
Assert-True ($manifestVersion -eq $curriculum.requirement_version) "Requirement version mismatch"
Assert-True ($grammarIds.Count -eq 21) "Expected 21 grammar IDs"
Assert-True ($grammarIds -contains "infinitive_nonfinite") "Infinitive grammar ID missing"
Assert-True ($curriculum.quality_gates.grammar_fill_min_questions_per_grammar_id -eq 12) "Grammar coverage minimum mismatch"
$unknownTags = @($units | ForEach-Object { $_.grammar_tags } | Where-Object { $grammarIds -notcontains $_ } | Sort-Object -Unique)
Assert-True ($unknownTags.Count -eq 0) "Unit contains unknown grammar tags"

$difficulty = @($curriculum.difficulty.bank_default_distribution.PSObject.Properties.Value)
$bookDistribution = @($curriculum.book_distribution.question_point_distribution.PSObject.Properties.Value)
Assert-True ([math]::Abs((($difficulty | Measure-Object -Sum).Sum) - 1.0) -lt 1e-9) "Difficulty distribution must sum to 1"
Assert-True ([math]::Abs((($bookDistribution | Measure-Object -Sum).Sum) - 1.0) -lt 1e-9) "Book distribution must sum to 1"
Assert-True ($curriculum.difficulty.paper_distribution.easy_d1_d2 -eq 0.40) "Easy ratio mismatch"
Assert-True ($curriculum.difficulty.paper_distribution.medium_d3 -eq 0.40) "Medium ratio mismatch"
Assert-True ($curriculum.difficulty.paper_distribution.hard_d4_d5 -eq 0.20) "Hard ratio mismatch"
Assert-True ($curriculum.difficulty.paper_hard_adaptive_min -eq 0.15) "Hard minimum mismatch"
Assert-True ($curriculum.difficulty.paper_hard_adaptive_max -eq 0.25) "Hard maximum mismatch"
Assert-True ($curriculum.book_distribution.reading_topic_min_elective_share -eq 0.50) "Reading elective share mismatch"
Assert-True ($curriculum.m1_exemption.seven_day_repeat_rate_requirement -eq "deferred_to_m3") "M1 exemption mismatch"
Write-Output "PASS curriculum units=25 grammarTags=$($grammarIds.Count)"

$practiceModes = Read-Json "config/practice-modes.json"
$mode30 = $practiceModes.modes.'30'
$mode60 = $practiceModes.modes.'60'
Assert-True ((15 + 10 + 4) -in @($mode30.expected_question_counts)) "30-minute count mismatch"
Assert-True ((15 + 10 + 5) -in @($mode30.expected_question_counts)) "30-minute gap count mismatch"
Assert-True (42 -in @($mode60.expected_question_counts)) "60-minute count mismatch"
Assert-True ($practiceModes.bank_scope.allow_cross_bank_sampling -eq $false) "Cross-bank sampling must be forbidden"
Write-Output "PASS practice-modes counts=29/30,42"

$reporting = Read-Json "config/reporting.json"
Assert-True ($reporting.mastery.ewma_alpha -eq 0.3) "EWMA alpha mismatch"
Assert-True ($reporting.stage_report.require_cross_bank_notice -eq $true) "Cross-bank notice must be required"
$appConfig = Read-Json "config/app.json"
Assert-True ($appConfig.time_authority -eq "server_deadline") "Time authority mismatch"
Assert-True (@($appConfig.data_clear_scope).Count -eq 2) "Data clear must include local and backend"
Write-Output "PASS report-and-app invariants"

$tokens = Read-Json "contracts/design-tokens.json"
Assert-True ($tokens.color.pageBackground -eq "#FFFFFF") "Page background mismatch"
Assert-True ($tokens.color.primaryText -eq "#111111") "Primary text mismatch"
Assert-True ($tokens.color.accent -match "^#[0-9A-F]{6}$") "Accent must be a six-digit uppercase hex token"
Assert-True ($tokens.radius.maximum -eq 14) "Radius maximum mismatch"
Assert-True ($tokens.font.sizes.minimum -eq 13) "Minimum font size mismatch"
Assert-True ($tokens.control.touchTargetMin -eq 44) "Touch target mismatch"
$accentOnly = @($tokens.color_usage.accent_only_for)
$accentNever = @($tokens.color_usage.accent_never_for)
Assert-True (($accentOnly -join ",") -eq "progress_bar,selected_control,radar_chart_stroke") "Accent allowed uses mismatch"
Assert-True (($accentNever -join ",") -eq "button_background,body_text,card_background,large_surface,border_default") "Accent forbidden uses mismatch"
Assert-True ($tokens.color.primaryButtonBackground -eq "#111111") "Primary button background mismatch"
Assert-True ($tokens.color.primaryButtonText -eq "#FFFFFF") "Primary button text mismatch"
Write-Output "PASS design-tokens"

$officialVocabulary = Read-Json "contracts/vocabulary/kebiao-2022-level3.json"
Assert-True ($officialVocabulary.source.declared_total -eq 1600) "Official vocabulary declared total mismatch"
Assert-True ($officialVocabulary.counts.declared_entries -eq 1600) "Official vocabulary declared count mismatch"
Assert-True ($officialVocabulary.counts.normalized_single_words -eq 1603) "Official vocabulary normalized headword count mismatch"
Assert-True ($officialVocabulary.source_comparison.jaccard_difference_percent -eq 29.47) "ECDICT comparison mismatch"
$supplementVocabulary = Read-Json "contracts/vocabulary/kebiao-2022-supplements.json"
Assert-True (@($supplementVocabulary.single_words).Count -eq 120) "Supplement headword count mismatch"
Assert-True (@($supplementVocabulary.phrases).Count -eq 44) "Supplement phrase count mismatch"

$vocabulary = Read-Json "contracts/vocabulary-whitelist.json"
$words = @($vocabulary.entries.word)
Assert-True ($words.Count -gt 0) "Vocabulary whitelist cannot be empty"
Assert-True ($words.Count -eq @($words | Sort-Object -Unique).Count) "Vocabulary whitelist has duplicate words"
Assert-True ($words.Count -eq $vocabulary.counting.unique_whitelist_entries) "Vocabulary count declaration mismatch"
Assert-True ($vocabulary.counting.base_compulsory_single_words -eq 1603) "Compulsory baseline count mismatch"
Assert-True ($vocabulary.counting.single_word_entries -eq 3021) "Single-headword count mismatch"
Assert-True ($vocabulary.counting.phrase_entries -eq 392) "Phrase count mismatch"
Assert-True ($vocabulary.counting.unique_whitelist_entries -eq 3413) "Full allowlist count mismatch"
Write-Output "PASS vocabulary entries=$($words.Count) singleWords=3021 phrases=392 officialBase=1600"

$grammarDoc = Get-Content -Raw -Encoding UTF8 -LiteralPath "docs/curriculum/grammar-by-unit.md"
$grammarRows = [regex]::Matches($grammarDoc, "(?m)^\| \d+ \|").Count
Assert-True ($grammarRows -eq 25) "Grammar document must contain 25 unit rows"
$grammarUnitRows = @(Get-Content -Encoding UTF8 -LiteralPath "docs/curriculum/grammar-by-unit.md" | Where-Object { $_ -match "^\| \d+ \|" })
$exactRows = @($grammarUnitRows | Where-Object { $_ -match "\| 完全一致" }).Count
$narrowedRows = @($grammarUnitRows | Where-Object { $_ -match "\| 教材范围更窄" }).Count
$widerRows = @($grammarUnitRows | Where-Object { $_ -match "\| 教材范围更宽" }).Count
$excludedRows = @($grammarUnitRows | Where-Object { $_ -match "\| 白名单外" }).Count
Assert-True ($exactRows -eq 9) "Grammar exact-match count mismatch"
Assert-True ($narrowedRows -eq 11) "Grammar narrower count mismatch"
Assert-True ($widerRows -eq 2) "Grammar wider count mismatch"
Assert-True ($excludedRows -eq 3) "Grammar excluded count mismatch"
$ownershipDoc = Get-Content -Raw -Encoding UTF8 -LiteralPath "docs/curriculum/grammar-id-ownership.md"
$ownershipRows = [regex]::Matches($ownershipDoc, "(?m)^\| \d+ \|").Count
Assert-True ($ownershipRows -eq 13) "Grammar ownership document must contain 13 IDs"
$mappingDoc = Get-Content -Raw -Encoding UTF8 -LiteralPath "docs/curriculum/grammar-whitelist-mapping.md"
$mappingRows = [regex]::Matches($mappingDoc, "(?m)^\| \d+ \|").Count
Assert-True ($mappingRows -eq 15) "Grammar mapping must contain 15 whitelist rows"
$questionSchema = Read-Json "contracts/schemas/question.json"
$grammarEnum = @($questionSchema.properties.grammar_tags.items.enum)
Assert-True ($grammarEnum.Count -eq 21) "Question grammar enum must contain 21 IDs"
Assert-True ($grammarEnum -contains "infinitive_nonfinite") "Question grammar enum missing infinitive"
Write-Output "PASS grammar whitelistRows=15 grammarIds=21 unitRows=25"

$openapi = Get-Content -Raw -Encoding UTF8 -LiteralPath "contracts/openapi.yaml"
foreach ($path in @(
  "/practice/start:",
  "/practice/{session_id}/answer:",
  "/practice/{session_id}/submit:",
  "/reports/{session_id}:",
  "/reports/summary:",
  "/error-tags:",
  "/student-data:",
  "/admin/banks:",
  "/admin/banks/compare:",
  "/admin/banks/{bank_id}/generate:",
  "/admin/banks/{bank_id}/coverage:",
  "/admin/banks/{bank_id}/preview:",
  "/admin/banks/{bank_id}/activate:",
  "/admin/banks/{bank_id}/archive:",
  "/admin/banks/{bank_id}/job:",
  "/admin/questions:",
  "/admin/questions/review:"
)) {
  Assert-True ($openapi.Contains($path)) "OpenAPI missing path $path"
}
Assert-True (-not $openapi.Contains("approved_by_owner")) "Client-side owner approval must be removed"
Assert-True (-not [regex]::IsMatch($openapi, "(?m)^security:")) "Top-level global security must be absent"
Assert-True ([regex]::Matches($openapi, "(?m)^      security:\s*$").Count -eq 21) "Every operation must declare security"
Assert-True ([regex]::Matches($openapi, "- StudentId: \[\]").Count -eq 9) "Student security declaration mismatch"
Assert-True ([regex]::Matches($openapi, "- AdminToken: \[\]").Count -eq 12) "Admin security declaration mismatch"
Assert-True ($openapi.Contains("/approve-generation:")) "Generation approval path missing"
Assert-True ($openapi.Contains("Idempotency-Key")) "Submit idempotency contract missing"
Assert-True (-not $openapi.Contains("components_parameters_anchor")) "Invalid OpenAPI anchor remains"
Write-Output "PASS openapi-required-paths"

Write-Output "M0_CHECK=PASS"
