try {
    Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2;StartTime=(Get-Date).AddDays(-7)} -MaxEvents 50 -ErrorAction Stop | Select-Object Id,ProviderName,Level,@{n='TimeCreated';e={$_.TimeCreated.ToUniversalTime().ToString('o')}}
} catch {
    if ($_.FullyQualifiedErrorId -notlike 'NoMatchingEventsFound*') { throw }
}
