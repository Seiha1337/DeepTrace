Get-CimInstance Win32_PnPSignedDriver | Select-Object -First 300 DeviceName,Manufacturer,DriverVersion,IsSigned
