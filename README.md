# 参考文献转 BibTeX

当前版本  
`v1.1.2`

## 主要功能

- 单条输入  
  支持 DOI、标题、完整参考文献字符串
- 批量输入  
  支持自动分条、歧义分条确认、逐条输出
- 候选确认  
  支持待确认候选列表与 Scholar 辅助确认
- BibTeX key 规则切换  
  支持预设规则并自动更新 BibTeX key
- 离线许可证门禁  
  启动先校验本地许可证  
  本地有效直接进入主程序  
  本地无效进入许可证验证页

## 离线许可证规则

- 许可证外层格式  
  `version` `payload` `signature`
- 签名对象仅为 `payload`
- 验签算法  
  Ed25519
- `payload` 序列化  
  固定确定性 JSON 规则加 UTF-8 编码
- 设备绑定  
  `bind_to_device=false` 时忽略 `device_id`  
  `bind_to_device=true` 且 `device_id` 为空时  
  客户端在激活时自动读取本机机器码并写入本地许可证绑定字段

## 许可证发证工具

路径  
`tools/license_issuer`

图形界面命令

```powershell
.\.venv\Scripts\python tools\license_issuer\issuer_ui.py
```

当前界面行为

- 只显示许可证参数和生成按钮
- 生成许可证时自动处理密钥
- 本地无密钥会自动生成私钥和公钥
- 生成时自动同步客户端固定公钥

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

- 变更记录见 `CHANGELOG.md`
- 发布流程见 `VERSIONING.md`
- 提交流程见 `CONTRIBUTING.md`
