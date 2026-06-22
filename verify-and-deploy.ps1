$log = "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\verify-deploy-log.txt"
"=== VERIFY GCLOUD $(Get-Date) ===" | Out-File $log

# Refresh PATH for this process from the registry (machine + user), since gcloud was
# just installed by a separate process and this PowerShell session started before that.
$machinePath = [System.Environment]::GetEnvironmentVariable("Path","Machine")
$userPath = [System.Environment]::GetEnvironmentVariable("Path","User")
$env:Path = "$machinePath;$userPath"

$gcloudCmd = Get-Command gcloud -ErrorAction SilentlyContinue
if ($gcloudCmd) {
    "FOUND gcloud at: $($gcloudCmd.Source)" | Out-File $log -Append
} else {
    "gcloud NOT on refreshed PATH, searching known install dirs..." | Out-File $log -Append
    $candidates = @(
        "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
        "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
        "C:\google-cloud-sdk\bin\gcloud.cmd"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            "EXISTS: $c" | Out-File $log -Append
        } else {
            "missing: $c" | Out-File $log -Append
        }
    }
}
"=== DONE $(Get-Date) ===" | Out-File $log -Append
