Get-CimInstance Win32_Processor | ForEach-Object { [pscustomobject]@{Kind='CPU';Name=$_.Name;LoadPercentage=$_.LoadPercentage} }
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 5 | ForEach-Object { [pscustomobject]@{Kind='Processus';Name=$_.ProcessName;WorkingSetBytes=$_.WorkingSet64} }
