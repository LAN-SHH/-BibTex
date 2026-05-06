任务目标
只处理按钮显隐、启用状态、选择联动，不改布局。

边界
不改 API，不改解析结果数据结构，不改发布文档。

改动范围
允许
- bibtex_mvp/ui/main_window.py
禁止
- bibtex_mvp/application/**
- bibtex_mvp/domain/**

验收标准
- 开始处理按钮始终可见
- Scholar 按钮和候选确认按钮状态正确
- 结果选择与候选选择联动正确

执行计划
1. 清理按钮显隐逻辑
2. 修复 action bar 重排副作用
3. 增加或更新回归测试

完成定义
- 代码提交
- pytest 通过
