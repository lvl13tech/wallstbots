$gcloudBin = "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin"
if (Test-Path $gcloudBin) {
    $env:Path = "$gcloudBin;$env:Path"
}
Write-Host "A browser window will open. Please sign in with the Google account that has access to the lvl13-tracker-496402 GCP project, then return here."
& gcloud auth login
Write-Host ""
Write-Host "If sign-in succeeded, you can now close this window and tell Claude to continue."
