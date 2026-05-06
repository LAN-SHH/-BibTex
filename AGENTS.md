# Bib Agent Guide

## 1. 目标
本文件同时约束两类行为  
一是仓库协作规范  
二是子代理执行规则

项目目录  
`D:\Develop\Codex\bib`

默认语言  
中文

## 2. 文风规范
- 先给结论，再给必要说明
- 用短句，不写长复合句
- 少用生涩词，少用复杂比喻
- 多给可执行动作和真实路径
- 除非用户明确要求，不写大段铺垫

## 3. 改动边界
- 只做完成任务所需的最小修改
- 不修改与当前需求无关的文件
- 不顺手重构，不做风格性大清理
- 发现可疑问题先记录，再由 manager thread 决定是否开新任务

## 4. Karpathy Guidelines
在写代码、审查代码、重构代码时，默认遵循 `karpathy-guidelines`。

### 4.1 先想再写
- 明确假设，不要默默猜测
- 有歧义时先给选项再执行
- 发现更简单路径要主动指出
- 不清楚就先停下来确认

### 4.2 简单优先
- 只实现当前需求，不加额外功能
- 不为单次使用做抽象
- 不做未请求的可配置化
- 代码能短就不写长

### 4.3 手术式修改
- 只改必要代码
- 不顺手改相邻模块或格式
- 保持现有代码风格一致
- 仅清理本次修改引入的无用代码

### 4.4 目标驱动验证
- 先定义可验证目标，再改代码
- 每一步都要有检查项
- 默认用测试或可复现步骤证明完成

## 5. 协作规范

### 5.1 线程分工
- manager thread 负责任务拆分、优先级、验收、合并建议
- execution thread 负责单一目标改动
- 一个 execution thread 只做一件事
- manager thread 不做大改代码

### 5.2 命名规则
- manager thread  
  `[bib][area][manager]`
- execution thread  
  `[bib][YYYY-MM-DD][area] short-goal`
- 分支  
  `codex/<area>-<goal>-<yyyymmdd>`

### 5.3 回传格式
每个 execution thread 完成后必须回传
- 改动文件
- 测试结果
- commit hash

## 6. 环境规范

### 6.1 Python 解释器
固定使用  
`D:\Develop\Codex\bib\.venv\Scripts\python.exe`

### 6.2 执行约束
- 不新建 `.venv`
- Python 命令都用固定解释器
- 修改前先看 `git status -sb`

## 7. 执行流程

### 7.1 manager thread
1. 明确目标和边界
2. 指定 area
3. 生成 execution 任务单
4. 收集执行回传
5. 给出验收结论

### 7.2 execution thread
1. 切到目标分支或工作树
2. 只改任务允许范围
3. 运行测试
4. 提交并回传结果

## 8. 子代理角色规则

### 8.1 ui-layout
目标  
只做布局和缩放表现

允许改动
- `bibtex_mvp/ui/main_window.py`
- `bibtex_mvp/ui/widgets.py`

禁止改动
- `bibtex_mvp/application/**`
- `bibtex_mvp/domain/**`
- `bibtex_mvp/infra/**`

### 8.2 ui-interaction
目标  
只做按钮状态、选择联动、进度提示

允许改动
- `bibtex_mvp/ui/main_window.py`

禁止改动
- `bibtex_mvp/application/**`
- `bibtex_mvp/domain/**`
- `bibtex_mvp/infra/**`

### 8.3 candidate-flow
目标  
只做候选确认、分条弹窗、Scholar 跳转

允许改动
- `bibtex_mvp/ui/main_window.py`
- `bibtex_mvp/ui/batch_split_dialog.py`
- `bibtex_mvp/ui/widgets.py`

禁止改动
- `bibtex_mvp/license_gate/**`
- `bibtex_mvp/application/**`

### 8.4 api-backend
目标  
只做解析、检索、编排和基础设施

允许改动
- `bibtex_mvp/application/**`
- `bibtex_mvp/domain/**`
- `bibtex_mvp/infra/**`

禁止改动
- `bibtex_mvp/ui/**`

### 8.5 tests-regression
目标  
只做测试和回归覆盖

允许改动
- `bibtex_mvp/tests/**`
- 为可测性所需的最小生产代码

### 8.6 release
目标  
只做版本发布收尾

允许改动
- `README.md`
- `CHANGELOG.md`
- `VERSIONING.md`

输出要求
- commit
- tag
- push

## 9. 测试与提交

### 9.1 最低验证
- `D:\Develop\Codex\bib\.venv\Scripts\python.exe -m pytest -q`

### 9.2 提交规则
- 小步提交
- 提交信息清晰
- 不混入无关改动

## 10. 发布规范
发布版本必须同步
- `README.md` 版本号
- `CHANGELOG.md` 条目
- Git tag

## 11. 禁止事项
- 禁止 `git reset --hard`
- 禁止 `git checkout -- <file>`
- 禁止跨角色越界改动
- 禁止未验证就宣称完成
