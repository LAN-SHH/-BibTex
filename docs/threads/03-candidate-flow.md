任务目标
只处理候选确认流程与分条弹窗体验。

边界
不做整体布局重构，不改许可证流程，不改发布流程。

改动范围
允许
- bibtex_mvp/ui/main_window.py
- bibtex_mvp/ui/batch_split_dialog.py
- bibtex_mvp/ui/widgets.py
禁止
- bibtex_mvp/license_gate/**

验收标准
- 候选列表展示稳定
- 单条确认流程可用
- Scholar 跳转和文案提示正确
- 分条弹窗无编码问题

执行计划
1. 清理候选流程按钮与状态
2. 清理分条弹窗文案和输入校验
3. 回归测试

完成定义
- 代码提交
- pytest 通过
