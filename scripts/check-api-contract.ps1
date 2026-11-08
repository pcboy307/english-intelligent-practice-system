$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

$client = Get-Content -Raw -Encoding UTF8 -LiteralPath "apps/mobile/src/api/client.ts"
$matches = [regex]::Matches(
  $client,
  'request<[^>]+>\(\s*[`"]([^`"]+)[`"]',
  [System.Text.RegularExpressions.RegexOptions]::Singleline
)

$replacementPatterns = @(
  @{ Pattern = '${sessionId}'; Replacement = '{session_id}' },
  @{ Pattern = '${passageId}'; Replacement = '{passage_id}' },
  @{
    Pattern = '${encodeURIComponent(passageId)}'
    Replacement = '{passage_id}'
  }
)

$openapi = Get-Content -Raw -Encoding UTF8 -LiteralPath "contracts/openapi.yaml"
$rows = foreach ($match in $matches) {
  $rawPath = $match.Groups[1].Value
  $contractPath = $rawPath.Split("?")[0]
  foreach ($replacement in $replacementPatterns) {
    $contractPath = $contractPath.Replace(
      $replacement.Pattern,
      $replacement.Replacement
    )
  }
  $present = [regex]::IsMatch(
    $openapi,
    "(?m)^  " + [regex]::Escape($contractPath) + ":\s*$"
  )
  [pscustomobject]@{
    FrontendCall = $rawPath
    OpenAPIPath = $contractPath
    Present = $present
  }
}

$rows | Format-Table -AutoSize
if (@($rows | Where-Object { -not $_.Present }).Count -gt 0) {
  throw "API_CONTRACT_MISMATCH"
}
Write-Output "API_CONTRACT_CHECK=PASS calls=$($rows.Count)"
