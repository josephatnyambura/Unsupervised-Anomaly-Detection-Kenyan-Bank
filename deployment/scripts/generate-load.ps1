# Generate API traffic so Prometheus collects metrics and Grafana shows data.
# Run from: deployment folder. Usage: .\scripts\generate-load.ps1
# To allow script execution once: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

$Api = "http://localhost:5000"
$Duration = 60  # seconds
$BatchSize = 10

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Generating load for Grafana dashboard" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Sending health + predict requests to $Api"
Write-Host " Running for $Duration seconds. Then open Grafana: http://localhost:3000"
Write-Host " Press Ctrl+C to stop early."
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$start = Get-Date
$sent = 0

while ((Get-Date) -lt $start.AddSeconds($Duration)) {
    try {
        Invoke-WebRequest -Uri "$Api/health" -UseBasicParsing -TimeoutSec 2 | Out-Null
        $body = '{"fund_name":"money_market_fund","transactions":[{"clientid":"LOAD","transactiondate":"2024-07-15","inflows":5000,"outflows":100,"balance":10000,"dailyincome":50,"cumulativeincome":500}]}'
        Invoke-WebRequest -Uri "$Api/predict" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing -TimeoutSec 5 | Out-Null
        $sent += 2
        if ($sent % 20 -eq 0) { Write-Host "  Sent $sent requests..." }
    } catch {
        Write-Host "  Warning: $($_.Exception.Message)" -ForegroundColor Yellow
    }
    Start-Sleep -Milliseconds 500
}

Write-Host ""
Write-Host "Done. Sent $sent requests. Open http://localhost:3000 and refresh the dashboard." -ForegroundColor Green
Write-Host ""
