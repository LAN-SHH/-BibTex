# 参考文献转 BibTeX（单条 + 批量输入）

当前版本：`v0.2.0`

## 功能概览
- 支持三种输入  
  DOI  
  文献标题  
  完整参考文献字符串
- 支持输入框内批量输入  
  自动分条  
  歧义分条确认  
  手动分条编辑
- 支持 Crossref 和 OpenAlex 双源检索
- 支持检索进度条和阶段提示
- 支持后台检索与后台确认  
  检索和确认时界面不再无响应
- 支持单路检索超时保护  
  某个数据源超时不会拖慢整体返回
- 支持三种状态  
  成功  
  待确认  
  失败
- 支持候选确认  
  确认当前候选  
  确认全部候选
- 支持 Google Scholar 辅助确认
- 支持 BibTeX 生成与复制
- 支持 BibTeX key 规则切换
- 支持取消批量任务  
  保留已完成条目结果  
  未完成条目标记为已取消

## 批量处理说明
- 程序会先自动分条，再进入批量检索
- 如果分条有歧义且条目数大于等于 2，会弹分条确认窗  
  只要求用户确认有歧义的条目
- 如果分条有歧义且条目数等于 1，会给三选一  
  按单条处理  
  打开手动分条编辑  
  取消
- 分条确认完成后会统一重编号为 `1..N`  
  后续进度和结果都用这个编号
- 结果区按三块显示  
  成功  
  待确认  
  失败
- 取消条目不会在结果区显示内容

## Scholar 与确认按钮
- 待确认且有候选时，只显示一个 Scholar 入口  
  `在 Scholar 打开当前候选`
- `在 Scholar 打开选中文献` 仅在无候选时显示
- 确认当前候选按钮和 Scholar 按钮都采用选中制  
  必须先选中条目或候选才能点击

## 0.2.0 本次更新
- 新增输入框批量处理完整流程
- 新增批量进度事件 `BatchProgressEvent`
- 新增批量取消机制 `cancel_token`
- 新增分条结构化结果 `reason_code`
- 新增 DOI 路径容错与回退检索
- 修复失败条目只显示编号的问题
- 修复切换 BibTeX key 规则后内容不变化的问题  
  切换时优先解析 BibTeX，再回退到 selected

## BibTeX key 规则
- 作者姓 + 年份  
  例 `Zhou2007`
- 作者姓 + 年份 + 标题首词  
  例 `Zhou2007Functional`
- 标题首词 + 年份  
  例 `Functional2007`

## 0.1.2 本次更新
- 修复 Vancouver 风格参考文献识别问题  
  例如 `Barch DM, Ceaser A. ... 2012.`
- 修复年份在句尾时的字段提取问题  
  现在可正确提取作者 标题 年份
- 优化参考文献检索失败时的兜底流程  
  无 DOI 时提供可确认候选，不再直接失败
- 优化候选自动确认策略  
  对明显领先的 DOI 候选可直接成功
- 修复部分返回 BibTeX 为单行的问题  
  对 `month=june` 这类字段做规范化后统一输出多行
- 增强 Crossref 异常容错  
  请求异常时不会中断主流程

## 运行方式
```powershell
cd D:\Develop\Codex\bib
.\.venv\Scripts\activate
python app.py
```

## 测试
```powershell
cd D:\Develop\Codex\bib
.\.venv\Scripts\activate
python -m pytest -q
```

## 版本管理
- 贡献规范见 `CONTRIBUTING.md`
- 版本记录见 `CHANGELOG.md`
- 发版流程见 `VERSIONING.md`
