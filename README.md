# 参考文献转 BibTeX（单条输入 MVP）

当前版本：`v0.1.2`

## 功能概览
- 支持三种输入  
  DOI  
  文献标题  
  完整参考文献字符串
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

## 当前开发改动（未发布）
- 新增检索进度条和阶段文案
- 检索与候选确认改为后台线程执行
- 新增检索超时配置 `search_timeout_sec`，默认 `6.0` 秒

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
