# configure_openclaw_models.ps1 - 配置 OpenClaw 模型

$modelsFile = "$env:USERPROFILE\.openclaw\agents\main\agent\models.json"
$backupFile = "$env:USERPROFILE\.openclaw\agents\main\agent\models.json.bak"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "OpenClaw Model Configuration" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 备份当前配置
if (Test-Path $modelsFile) {
    Write-Host "[1/4] Backing up current models.json..." -ForegroundColor Yellow
    Copy-Item $modelsFile $backupFile -Force
    Write-Host "      Backup saved to: $backupFile" -ForegroundColor Green
} else {
    Write-Host "[ERROR] models.json not found!" -ForegroundColor Red
    exit 1
}

# 读取当前配置
Write-Host "[2/4] Reading current configuration..." -ForegroundColor Yellow
$config = Get-Content $modelsFile -Raw | ConvertFrom-Json

# 添加新的 provider
Write-Host "[3/4] Adding dashscope-custom provider..." -ForegroundColor Yellow

$newProvider = @{
    "baseUrl" = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    "apiKey" = "sk-676611e12c9549c08125cd1c0d3733b9"
    "models" = @(
        @{
            "id" = "kimi-k2.5"
            "name" = "Kimi K2.5"
            "api" = "openai-completions"
            "reasoning" = $false
            "input" = @("text")
            "cost" = @{
                "input" = 0
                "output" = 0
                "cacheRead" = 0
                "cacheWrite" = 0
            }
            "contextWindow" = 200000
            "maxTokens" = 8192
        },
        @{
            "id" = "glm-5"
            "name" = "GLM-5"
            "api" = "openai-completions"
            "reasoning" = $false
            "input" = @("text")
            "cost" = @{
                "input" = 0
                "output" = 0
                "cacheRead" = 0
                "cacheWrite" = 0
            }
            "contextWindow" = 200000
            "maxTokens" = 8192
        },
        @{
            "id" = "qwen3.5-plus"
            "name" = "Qwen3.5-Plus"
            "api" = "openai-completions"
            "reasoning" = $false
            "input" = @("text")
            "cost" = @{
                "input" = 0
                "output" = 0
                "cacheRead" = 0
                "cacheWrite" = 0
            }
            "contextWindow" = 200000
            "maxTokens" = 8192
        },
        @{
            "id" = "qwen3-max-2026-01-23"
            "name" = "Qwen3-Max"
            "api" = "openai-completions"
            "reasoning" = $false
            "input" = @("text")
            "cost" = @{
                "input" = 0
                "output" = 0
                "cacheRead" = 0
                "cacheWrite" = 0
            }
            "contextWindow" = 200000
            "maxTokens" = 8192
        },
        @{
            "id" = "qwen3.5-flash"
            "name" = "Qwen3.5-Flash"
            "api" = "openai-completions"
            "reasoning" = $false
            "input" = @("text")
            "cost" = @{
                "input" = 0
                "output" = 0
                "cacheRead" = 0
                "cacheWrite" = 0
            }
            "contextWindow" = 200000
            "maxTokens" = 8192
        }
    )
}

# 检查是否已存在 dashscope-custom provider
if ($config.providers."dashscope-custom") {
    Write-Host "      Updating existing dashscope-custom provider..." -ForegroundColor Yellow
    $config.providers."dashscope-custom" = $newProvider
} else {
    Write-Host "      Adding new dashscope-custom provider..." -ForegroundColor Yellow
    $config.providers | Add-Member -NotePropertyName "dashscope-custom" -NotePropertyValue $newProvider
}

# 保存配置
Write-Host "[4/4] Saving configuration..." -ForegroundColor Yellow
$config | ConvertTo-Json -Depth 10 | Set-Content $modelsFile -Encoding UTF8

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Configuration Complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Restart OpenClaw gateway:" -ForegroundColor White
Write-Host "     openclaw gateway restart" -ForegroundColor Cyan
Write-Host ""
Write-Host "  2. Verify models are loaded:" -ForegroundColor White
Write-Host "     openclaw agents list" -ForegroundColor Cyan
Write-Host ""
Write-Host "  3. (Optional) Change default model:" -ForegroundColor White
Write-Host "     Edit ~/.openclaw/workspace/MEMORY.md or use session settings" -ForegroundColor Cyan
Write-Host ""
Write-Host "Available models:" -ForegroundColor Yellow
Write-Host "  - dashscope-custom/kimi-k2.5" -ForegroundColor White
Write-Host "  - dashscope-custom/glm-5" -ForegroundColor White
Write-Host "  - dashscope-custom/qwen3.5-plus" -ForegroundColor White
Write-Host "  - dashscope-custom/qwen3-max-2026-01-23" -ForegroundColor White
Write-Host "  - dashscope-custom/qwen3.5-flash" -ForegroundColor White
Write-Host ""
