# Git 自动版本管理

本项目已配置以下 Git 约定：

- 本地身份固定为 `r <18479259773@168.com>`。
- `main` 分支跟踪 `origin/main`，远程使用 SSH。
- `git add` 会遵守项目级 `.gitignore`，不提交缓存、虚拟环境和临时文件。
- 提交前自动运行 `git diff --cached --check`，阻止空白错误进入提交。
- `scripts/git_auto_snapshot.sh` 会添加当前改动、创建提交并推送到远程。

## 手动触发自动保存

在项目根目录执行：

```bash
./scripts/git_auto_snapshot.sh
```

也可以指定提交信息：

```bash
./scripts/git_auto_snapshot.sh "Update research data"
```

脚本没有改动时不会创建空提交。当前默认不安装后台定时任务，避免研究过程中的中间文件被立即推送；如需定时自动运行，应另外配置 macOS `launchd` 的运行频率。
