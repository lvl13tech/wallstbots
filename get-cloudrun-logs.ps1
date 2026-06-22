$gcloudBin = "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin"
if (Test-Path $gcloudBin) {
    $env:Path = "$gcloudBin;$env:Path"
}

$log = "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\cloudrun-logs.txt"

& gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=wallstbots-backend AND resource.labels.revision_name=wallstbots-backend-00108-qgc" --project=lvl13-tracker-496402 --limit=100 --format="value(timestamp,severity,textPayload)" --freshness=1d *> $log

Write-Host "Logs written to $log"
