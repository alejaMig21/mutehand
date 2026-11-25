# Creates the "Workflow Factory" shortcut on the Desktop and in the Start Menu. It points at the project's own
# windowless Python (pythonw.exe), so a double click opens the editor with no console and needs no network.
# Safe to run twice: the shortcuts are simply rewritten. Writes nothing else.
param(
  [string]$DesktopDir = [Environment]::GetFolderPath('Desktop'),
  [string]$StartMenuDir = [Environment]::GetFolderPath('Programs'),
  [string]$Python = (Join-Path $PSScriptRoot '..\.venv\Scripts\pythonw.exe')
)
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not (Test-Path $Python)) {
  Write-Host "The project environment is missing ($Python). Run 'uv sync' in $root and then run this again."
  exit 1
}
$python = (Resolve-Path $Python).Path
$shell = New-Object -ComObject WScript.Shell
foreach ($folder in @($DesktopDir, $StartMenuDir)) {
  $link = $shell.CreateShortcut((Join-Path $folder 'Workflow Factory.lnk'))
  $link.TargetPath = $python
  $link.Arguments = '-m workflow_factory.app'
  $link.WorkingDirectory = $root
  $link.Description = 'Open Workflow Factory'
  $link.Save()
  Write-Host "Shortcut created in $folder"
}
