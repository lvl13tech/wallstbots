$log = "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\deploy-backend-result.txt"

# Ensure gcloud's bin dir is on PATH for this process and for the cmd.exe child it spawns.
$gcloudBin = "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin"
if (Test-Path $gcloudBin) {
    $env:Path = "$gcloudBin;$env:Path"
}

# Also persist it to the User PATH permanently so future sessions (and the owner) have it,
# if it isn't already there.
$userPath = [System.Environment]::GetEnvironmentVariable("Path","User")
if ($userPath -notlike "*Cloud SDK*google-cloud-sdk\bin*") {
    [System.Environment]::SetEnvironmentVariable("Path", "$userPath;$gcloudBin", "User")
}

Set-Location "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"
cmd /c "DEPLOY-BACKEND.bat"
