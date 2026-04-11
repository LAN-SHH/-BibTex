# 参考文献转 BibTeX（单条输入 MVP）

当前版本：`v0.1.1`

## 核心能力
- 支持三种输入  
DOI  
文献标题  
完整参考文献字符串
- 支持 Crossref 和 OpenAlex 检索
- 支持状态展示  
成功  
待确认  
失败
- 支持候选确认  
确认当前候选  
确认全部候选
- 支持 Google Scholar 辅助确认
- 支持 BibTeX key 规则切换和复制

## BibTeX key 规则
- 作者姓 + 年份  
例 `Zhou2007`
- 作者姓 + 年份 + 标题首词  
例 `Zhou2007Functional`
- 标题首词 + 年份  
例 `Functional2007`

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

