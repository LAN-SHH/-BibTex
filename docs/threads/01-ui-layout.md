任务目标
只处理主界面布局与缩放，不改业务逻辑。

边界
不改解析逻辑，不改候选确认规则，不改 API。

改动范围
允许
- bibtex_mvp/ui/main_window.py
- bibtex_mvp/ui/widgets.py
禁止
- bibtex_mvp/application/**
- bibtex_mvp/domain/**

验收标准
- 输入区、结果区、BibTeX 区、候选区在最小窗口可见
- 表格横向滚动条不被遮挡
- 左右和上下缩放时布局稳定

执行计划
1. 调整分区结构与 splitter 比例
2. 调整最小宽高和关键控件高度
3. 运行 py_compile 与 pytest

完成定义
- 代码提交
- 测试通过
