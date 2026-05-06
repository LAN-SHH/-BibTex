# UI Interaction Manager Board

## Scope
只管理 UI interaction 相关任务，不直接做大改代码。

## Rules
1. 每个执行任务新开一个 thread
2. 每个执行任务新建一个分支
3. 执行 thread 完成后回传改动文件、pytest 结果和 commit hash
4. manager thread 只做调度、验收、合并决策

## Backlog
- [ ] T1 清理按钮显隐逻辑，开始处理按钮始终可见
- [ ] T2 修复 action bar 重排副作用，Scholar 按钮状态正确
- [ ] T3 修复候选确认按钮状态，保证和处理阶段一致
- [ ] T4 修复结果选择与候选选择联动
- [ ] T5 增加或更新回归测试

## In Progress
- [ ] task:
  branch:
  thread:
  owner:
  started_at:
  scope:

## Review
- [ ] task:
  branch:
  changed_files:
  commit:
  pytest:
  risk:
  decision:

## Done
- [ ] task:
  merged_at:
  commit:
  notes:

## Naming
- manager thread:
  [bib][ui-interaction][manager]
- execution thread:
  [bib][YYYY-MM-DD][ui-interaction] short-goal
- branch:
  codex/ui-interaction-short-goal-YYYYMMDD
