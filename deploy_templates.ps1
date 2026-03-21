# 自动化部署脚本 - 将模板复制到项目目录

$sourceDir = "C:/Users/Administrator/.openclaw/workspace/templates"
$targetBase = "D:\测试\quickforge3.8\templates\teach"

# 定义模板映射 (文件名 -> 目标文件夹名)
$templateMappings = @(
    @{Name="regular_001_single_choice"; Type="regular"},
    @{Name="regular_002_multi_choice"; Type="regular"},
    @{Name="regular_003_partial_choice"; Type="regular"},
    @{Name="regular_004_true_false"; Type="regular"},
    @{Name="regular_005_fill_blank"; Type="regular"},
    @{Name="regular_006_short_answer"; Type="regular"},
    @{Name="regular_007_programming"; Type="regular"},
    @{Name="interactive_sport_001_match"; Type="interactive"},
    @{Name="interactive_special_004_category"; Type="interactive"},
    @{Name="interactive_special_006_circuit"; Type="interactive"},
    @{Name="interactive_special_009_mindmap"; Type="interactive"},
    @{Name="interactive_special_013_chengyu"; Type="interactive"},
    @{Name="data_13_attendance"; Type="data"},
    @{Name="data_16_qwen_plus"; Type="data", Note="qwen3.5-plus version"},
    @{Name="data_20_feedback_survey"; Type="data"},
    @{Name="data_34_whiteboard"; Type="data"}
)

foreach ($mapping in $templateMappings) {
    $sourceFile = Join-Path $sourceDir "$($mapping.Name).html"
    if (Test-Path $sourceFile) {
        # 创建目标文件夹
        $targetFolder = Join-Path $targetBase "$($mapping.Type)_$($mapping.Name)"
        New-Item -ItemType Directory -Path $targetFolder -Force | Out-Null
        
        # 复制 HTML 文件为 index.html
        Copy-Item $sourceFile (Join-Path $targetFolder "index.html") -Force
        Write-Host "✅ $($mapping.Name).html -> $targetFolder/index.html"
        
        # 检查并复制 task.json
        $taskJson = Join-Path $sourceDir "$($mapping.Name).task.json"
        if (Test-Path $taskJson) {
            Copy-Item $taskJson (Join-Path $targetFolder ".task.json") -Force
            Write-Host "   └─ .task.json copied"
        }
        
        # 如果是 whiteboard，也复制 v2 版本
        if ($mapping.Name -eq "data_34_whiteboard") {
            $v2Source = Join-Path $sourceDir "deepseek_data34_whiteboard_v2.html"
            if (Test-Path $v2Source) {
                Copy-Item $v2Source (Join-Path $targetFolder "whiteboard_v2.html") -Force
                Write-Host "   └─ whiteboard_v2.html (deepseek对比版) copied"
            }
        }
        
        Write-Host ""
    } else {
        Write-Host "❌ Source not found: $sourceFile" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "🎉 所有模板已部署完成！" -ForegroundColor Green
Write-Host "📁 目标目录：$targetBase" -ForegroundColor Cyan