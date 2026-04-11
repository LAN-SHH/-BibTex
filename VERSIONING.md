# 版本号与发布流程

## 版本号规则
采用语义化版本

`主版本.次版本.修订号`

说明
1. 主版本  
不兼容改动时递增  
如 `1.0.0`
2. 次版本  
兼容的新功能时递增  
如 `0.2.0`
3. 修订号  
兼容的缺陷修复时递增  
如 `0.1.1`

## 发布步骤
1. 确认代码在 `main`
2. 更新 `CHANGELOG.md` 的 `Unreleased`
3. 提交版本变更  
`git add .`  
`git commit -m "chore: release vX.Y.Z"`
4. 打标签  
`git tag vX.Y.Z`
5. 推送代码和标签  
`git push`  
`git push origin vX.Y.Z`

## 维护建议
1. 每次合并到 `main` 都更新 `Unreleased`
2. 每次发版将 `Unreleased` 内容搬到正式版本段
3. 保持每个版本的新增与修复清晰可查

