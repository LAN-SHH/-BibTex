# 参考文献转 BibTeX 单条输入 MVP

## 功能范围
- 单条输入，不做批量
- 支持 DOI、标题、完整参考文献字符串
- 检索源使用 Crossref 和 OpenAlex
- 状态支持 成功、待确认、失败
- 支持候选确认与 Google Scholar 辅助确认
- 支持 BibTeX key 规则切换与复制

## 关键行为
- DOI 输入直接查并生成 BibTeX
- 标题输入先检索 DOI，再生成 BibTeX
- 参考文献字符串先提取标题作者年份，再检索 DOI
- 候选中存在完美匹配时直接成功  
  完美匹配为 标题一致 年份一致 作者完整列表逐一一致且顺序一致
- 只有一个高置信候选时直接成功
- 多候选待确认或检索失败时，才显示 Google Scholar 按钮

## 目录结构
```text
app.py
requirements.txt
bibtex_mvp/
  application/
  domain/
  infra/
  ui/
  tests/
```

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
