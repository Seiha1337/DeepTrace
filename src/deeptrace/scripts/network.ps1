Get-NetAdapter | Select-Object InterfaceDescription,@{n='Status';e={[string]$_.Status}},LinkSpeed
