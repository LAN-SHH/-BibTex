# Changelog

## [Unreleased]

## [1.1.1] - 2026-05-06
### Changed
- Compressed action bar height and vertical spacing for a denser top section
- Kept action controls and key-rule selector in one row at cold start

## [1.1.0] - 2026-05-01
### Changed
- Main UI layout adjusted for responsive resizing behavior
- Input area kept above action bar
- Progress bar height reduced for a denser top section
- Result section height allocation increased
- Removed "Confirm all candidates" action and related workflow branch

### Fixed
- Stabilized action bar relayout to avoid hiding the resolve button
- Improved bottom panel sizing to reduce scrollbar clipping during resize

## [1.0.1] - 2026-05-01
### 修复
- 删除主界面中的选中条目详情区
- 删除开发调试面板，改为在 `app.py` 中配置自动通过阈值和候选展示阈值
- 修复 Scholar 相关按钮显示逻辑
- 固定成功、待确认、失败和候选列表的表头与列宽，避免切换命名规则时表头位置跳动

## [1.0.0] - 2026-04-28
### 新增
- 新增离线许可证门禁流程  
  启动优先校验本地许可证  
  本地无效时进入许可证验证页
- 新增许可证错误码体系  
  `LICENSE_NOT_FOUND`  
  `INVALID_JSON`  
  `CORRUPTED_LICENSE`  
  `UNSUPPORTED_VERSION`  
  `INVALID_SIGNATURE`  
  `EXPIRED`  
  `DEVICE_ID_UNAVAILABLE`  
  `DEVICE_MISMATCH`
- 新增离线发证工具 `tools/license_issuer`  
  支持图形界面一键生成许可证

### 变更
- 许可证外层结构固定为 `version` `payload` `signature`
- 签名对象固定为 `payload`
- 验签算法固定为 Ed25519
- `payload` 序列化固定为确定性 JSON 规则加 UTF-8 编码
- 设备绑定逻辑调整  
  `bind_to_device=true` 且 `device_id` 为空时  
  客户端在激活时自动读取机器码并写入本地绑定字段
- 发证工具界面简化  
  仅保留许可证生成入口  
  生成时自动处理私钥和公钥同步

### 测试
- 新增许可证模块单元测试覆盖
- 全量测试通过

## [0.2.0] - 2026-04-23
### 新增
- 新增输入框批量处理流程
- 新增批量进度事件 `BatchProgressEvent`
- 新增批量取消机制
- 新增分条结构化结果 `reason_code`

### 优化
- 检索和候选确认改为后台线程执行
- Scholar 入口去重与候选交互优化
- 失败项展示补全标题、作者、年份、DOI

### 修复
- 修复部分 DOI 查询异常导致整条失败的问题
- 修复 BibTeX key 切换后内容不更新的问题
- 修复中文 `J/OL` 风格参考文献解析不稳定的问题

## [0.1.3] - 2026-04-21
### 修复
- 新增检索进度条和阶段提示文案
- 修复检索期间界面无响应问题
- 增加单路超时控制

## [0.1.2] - 2026-04-20
### 修复
- 优化 Vancouver 风格参考文献识别与解析
- 修复年份末尾解析和无 DOI 候选兜底
- 修复 Crossref 异常中断与 BibTeX 单行输出问题

## [0.1.1] - 2026-04-12
### 修复
- 修复 `作者姓+年份+标题首词` 规则中标题首词大小写问题

## [0.1.0] - 2026-04-11
### 新增
- 单条输入 MVP
- 支持 DOI、标题、完整参考文献字符串输入
- 支持 Crossref + OpenAlex 检索
- 支持 BibTeX 生成、复制和 key 规则切换

