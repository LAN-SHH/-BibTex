任务目标
只处理后端 API 或解析编排逻辑，不改 UI 样式。

边界
不改界面布局，不改窗口样式，不改发布文档。

改动范围
允许
- bibtex_mvp/application/**
- bibtex_mvp/domain/**
- bibtex_mvp/infra/**
禁止
- bibtex_mvp/ui/**

验收标准
- 输入解析与检索行为符合预期
- 候选与成功失败状态输出正确
- 相关单元测试和集成测试通过

执行计划
1. 修改目标 API 或编排逻辑
2. 补充测试用例
3. 跑全量测试并检查回归

完成定义
- 代码提交
- pytest 通过
