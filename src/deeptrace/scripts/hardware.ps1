Get-CimInstance Win32_Processor | ForEach-Object { [pscustomobject]@{Kind='CPU';Name=$_.Name;Manufacturer=$_.Manufacturer;Cores=$_.NumberOfCores;Threads=$_.NumberOfLogicalProcessors} }
Get-CimInstance Win32_PhysicalMemory | ForEach-Object { [pscustomobject]@{Kind='RAM';Manufacturer=$_.Manufacturer;Capacity=$_.Capacity;Speed=$_.Speed} }
Get-CimInstance Win32_VideoController | ForEach-Object { [pscustomobject]@{Kind='GPU';Name=$_.Name;DriverVersion=$_.DriverVersion} }
Get-CimInstance Win32_BaseBoard | ForEach-Object { [pscustomobject]@{Kind='Carte mère';Name=$_.Product;Manufacturer=$_.Manufacturer} }
Get-CimInstance Win32_BIOS | ForEach-Object { [pscustomobject]@{Kind='BIOS';Manufacturer=$_.Manufacturer;Version=$_.SMBIOSBIOSVersion} }
