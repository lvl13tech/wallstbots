$log = "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\gcloud-install-log.txt"
"START $(Get-Date)" | Out-File $log
try {
    $installer = "$env:TEMP\GoogleCloudSDKInstaller.exe"
    "Downloading installer to $installer" | Out-File $log -Append
    Invoke-WebRequest -Uri "https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe" -OutFile $installer
    "DOWNLOAD OK, size: $((Get-Item $installer).Length) bytes" | Out-File $log -Append
    "Running installer silently..." | Out-File $log -Append
    Start-Process -FilePath $installer -ArgumentList "/S","/allusers=0","/noreporting=1" -Wait
    "INSTALL DONE $(Get-Date)" | Out-File $log -Append
} catch {
    "ERROR: $($_.Exception.Message)" | Out-File $log -Append
}
"SCRIPT FINISHED $(Get-Date)" | Out-File $log -Append
