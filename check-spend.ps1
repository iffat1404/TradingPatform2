param(
  [string]$Key = $env:mm62c-oE1qSH2LACidn-Eg
)

if (-not $Key) {
  Write-Error "No key provided. Pass as argument or set ANTHROPIC_API_KEY" -ErrorAction Stop
}

$headers = @{
  "Authorization" = "Bearer $Key"
}

$response = Invoke-WebRequest -Headers $headers -Uri https://keys.echios.tech/user/spend
$json = ConvertFrom-Json $response.Content
$json | ConvertTo-Json -Depth 10
