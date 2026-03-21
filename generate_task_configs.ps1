# 批量生成 task.json 配置文件的 PowerShell 脚本

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
    @{Name="data_16_qwen_plus"; Type="data"},
    @{Name="data_20_feedback_survey"; Type="data"},
    @{Name="data_34_whiteboard"; Type="data"}
)

foreach ($mapping in $templateMappings) {
    $config = @"
{
  "public": true,
  "allowOtherTeachers": false,
  "allowPrivateStudents": true,
  "allowGlobalStudents": false,
  "templateType": "$($mapping.Type)",
  "templateId": "$($mapping.Name)"
}
"@
    
    $targetFile = "C:/Users/Administrator/.openclaw/workspace/templates/$($mapping.Name).task.json"
    Set-Content -Path $targetFile -Value $config -Encoding UTF8
    
    Write-Host "✅ Created: $($mapping.Name).task.json"
}

Write-Host "`n🎉 All $($_TemplateMappings.Count) .task.json files created!" -ForegroundColor Green