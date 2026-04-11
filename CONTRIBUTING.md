# 贡献与版本管理

## 分支规范
1. `main` 只保留可发布代码
2. 新功能使用 `feature/<简短功能名>`
3. 问题修复使用 `fix/<简短问题名>`
4. 紧急修复使用 `hotfix/<简短问题名>`
5. 文档改动使用 `docs/<简短主题名>`

示例
- `feature/scholar-candidate-link`
- `fix/title-search-score`
- `hotfix/doi-fetch-timeout`

## 提交规范
提交信息格式

`<type>: <简短说明>`

常用 `type`
- `feat` 新功能
- `fix` 修复问题
- `refactor` 重构
- `test` 测试
- `docs` 文档
- `chore` 构建或工具调整

示例
- `feat: 支持候选结果逐条确认`
- `fix: 修复仅标题输入时误判失败`
- `docs: 补充版本发布流程`

## 日常开发流程
1. 切换到主分支并拉取最新代码  
`git checkout main`  
`git pull`
2. 创建开发分支  
`git checkout -b feature/<name>`
3. 开发并提交  
`git add .`  
`git commit -m "feat: ..."`
4. 推送分支  
`git push -u origin feature/<name>`
5. 合并后删除分支  
`git branch -d feature/<name>`

## 合并前检查
1. 本地测试通过
2. 关键功能手动验证通过
3. `CHANGELOG.md` 已补充本次改动

