# QuickForge 模板部署脚本
# 将所有 HTML 和配置文件复制到 teach 目录

$sourceDir = "C:/Users/Administrator/.openclaw/workspace/templates"
$targetBase = "D:\测试\quickforge3.8\templates\teach"

# 创建主目录（如果不存在）
if (!(Test-Path $targetBase)) {
    New-Item -ItemType Directory -Path $targetBase -Force | Out-Null
    Write-Host "[+] Created target directory: $targetBase" -ForegroundColor Green
}

# 定义需要复制的文件列表
$fileList = @(
    "regular_001_single_choice.html",
    "regular_002_multi_choice.html",
    "regular_003_partial_choice.html",
    "regular_004_true_false.html",
    "regular_005_fill_blank.html",
    "regular_006_short_answer.html",
    "regular_007_programming.html",
    "interactive_sport_001_match.html",
    "interactive_special_004_category.html",
    "interactive_special_006_circuit.html",
    "interactive_special_009_mindmap.html",
    "interactive_special_013_chengyu.html",
    "data_13_attendance.html",
    "data_16_qwen_plus.html",
    "data_20_feedback_survey.html",
    "data_34_whiteboard.html",
    
    "deepseek_data34_whiteboard_v2.html",
    
    "regular_001_single_choice.task.json",
    "regular_002_multi_choice.task.json",
    "regular_003_partial_choice.task.json",
    "regular_004_true_false.task.json",
    "regular_005_fill_blank.task.json",
    "regular_006_short_answer.task.json",
    "regular_007_programming.task.json",
    "interactive_sport_001_match.task.json",
    "interactive_special_004_category.task.json",
    "interactive_special_006_circuit.task.json",
    "interactive_special_009_mindmap.task.json",
    "interactive_special_013_chengyu.task.json",
    "data_13_attendance.task.json",
    "data_16_qwen_plus.task.json",
    "data_20_feedback_survey.task.json",
    "data_34_whiteboard.task.json"
)

$copiedCount = 0
$failedCount = 0

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  QuickForge 模板部署脚本" -ForegroundColor Cyan
Write-Host "  目标目录：$targetBase" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

foreach ($filename in $fileList) {
    $sourceFile = Join-Path $sourceDir $filename
    
    if (Test-Path $sourceFile) {
        $destPath = Join-Path $targetBase $filename
        
        # 复制文件
        Copy-Item -Path $sourceFile -Destination $destPath -Force
        
        # 获取文件大小
        $fileSize = [math]::Round((Get-Item $sourceFile).Length / 1KB, 2)
        
        Write-Host "[OK] $filename`t($fileSize KB)" -ForegroundColor Green
        $copiedCount++
    } else {
        Write-Host "[X ] $filename - File not found in source" -ForegroundColor Yellow
        $failedCount++
    }
}

Write-Host "`n----------------------------------------" -ForegroundColor Cyan
Write-Host "  部署完成！" -ForegroundColor Green
Write-Host "  成功：$copiedCount / 失败：$failedCount" -ForegroundColor Cyan
Write-Host "  目标目录：$targetBase" -ForegroundColor Cyan
Write-Host "----------------------------------------`n" -ForegroundColor Cyan

if ($failedCount -eq 0) {
    Write-Host "  🎉 所有文件已成功部署！可以直接浏览使用了" -ForegroundColor Green
    Write-Host "  📁 可以在浏览器中打开这些 HTML 文件进行测试" -ForegroundColor Cyan
} else {
    Write-Host "  ⚠️ 有部分文件部署失败，请检查源文件是否存在" -ForegroundColor Yellow
}
