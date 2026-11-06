$paths = @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall','HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall')
& { foreach ($path in $paths) {
    if (Test-Path -LiteralPath $path) {
        Get-ChildItem -LiteralPath $path | Get-ItemProperty | Where-Object { $_.DisplayName } | Select-Object -First 500 DisplayName,DisplayVersion,Publisher
    }
} } | Select-Object -First 500
