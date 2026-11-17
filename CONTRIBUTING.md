# 贡献说明

感谢对进销存管理系统的改进建议和代码贡献。

## 开发流程

1. 从默认分支创建功能分支。
2. 保持改动范围清晰，避免提交数据库、构建产物和本地 IDE 配置。
3. 完成功能后运行编译检查和全部测试。
4. 提交 Pull Request，并说明改动内容、测试方式和可能的兼容性影响。

## 提交前检查

```powershell
python -m compileall -q app client run_server.py run_local.py
python -W error::ResourceWarning -m unittest discover -s tests -p "test_*.py" -v
```

## Commit 建议

建议使用清晰的动词开头，例如：

- `feat: add inventory report export`
- `fix: prevent duplicate document posting`
- `docs: update server deployment guide`
