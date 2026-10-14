# 清理为加载插件而写入的 Chrome 注册表/策略项（作业截图完成后执行）
$ErrorActionPreference = 'SilentlyContinue'

$extKey = 'HKCU:\Software\Google\Chrome\Extensions\geloleknkedjngohffneoefbgbfhfgjp'
$polKey = 'HKCU:\Software\Policies\Google\Chrome'

if (Test-Path $extKey) {
    Remove-Item -Path $extKey -Recurse -Force
    Write-Host "已删除扩展注册表键: $extKey"
} else {
    Write-Host "扩展注册表键不存在，跳过"
}

if (Test-Path $polKey) {
    Remove-ItemProperty -Path $polKey -Name 'ExtensionInstallForcelist' -Force
    Remove-ItemProperty -Path $polKey -Name 'ExtensionInstallSources' -Force
    Write-Host "已删除策略值: ExtensionInstallForcelist / ExtensionInstallSources"
    # 若策略键下已无任何值，则连键一起删除
    $left = (Get-Item $polKey).Property.Count
    if ($left -eq 0) {
        Remove-Item -Path $polKey -Force
        Write-Host "已删除空策略键: $polKey"
    }
}

Write-Host "清理完成"
