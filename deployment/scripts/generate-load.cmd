@echo off
REM Generate API traffic so Prometheus collects metrics and Grafana shows data.
REM Run from: deployment folder (or run from project root and adjust path).
REM Usage: generate-load.cmd   OR   scripts\generate-load.cmd

set API=http://localhost:5000
set /a count=0

echo.
echo ========================================
echo  Generating load for Grafana dashboard
echo ========================================
echo  Sending health checks and predictions to %API%
echo  Run for at least 30-60 seconds, then open Grafana.
echo  Press Ctrl+C to stop early.
echo ========================================
echo.

:loop
curl -s -o nul %API%/health
curl -s -o nul -X POST %API%/predict -H "Content-Type: application/json" -d "{\"fund_name\": \"money_market_fund\", \"transactions\": [{\"clientid\": \"LOAD\", \"transactiondate\": \"2024-07-15\", \"inflows\": 5000, \"outflows\": 100, \"balance\": 10000, \"dailyincome\": 50, \"cumulativeincome\": 500}]}"
set /a count+=1
if %count%==50 (
  echo Sent %count% batches. Keep running or press Ctrl+C. Open http://localhost:3000
  set /a count=0
)
timeout /t 1 /nobreak > nul
goto loop
