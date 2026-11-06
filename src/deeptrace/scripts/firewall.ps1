Get-NetFirewallProfile | Select-Object Name,@{n='Enabled';e={[bool]([int]$_.Enabled -eq 1)}}
