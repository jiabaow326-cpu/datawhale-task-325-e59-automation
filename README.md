# E59 重复电脑操作自动化：安全批处理实操包

本包面向需要重复复制文件、规范命名并汇总 CSV 的职场新手。所有姓名、组织、门店、商品、日期与数字均为虚构练习数据。

## 交付结构

- `tutorial/重复电脑操作自动化实操教程.md`：五步教程；每步包含目的、材料、AI 提示词、完成标志，并把前一步产物带到下一步。
- `materials/`：样例 CSV 与版本冲突、重复、缺失素材。
- `scripts/safe_batch.py`：Python 标准库脚本。默认只预演；只有显式给出 `--apply` 才复制到新输出目录；不改、不删来源。
- `reference/`：验收答案、陷阱逐条核验、回滚说明及真实运行核验记录。
- `templates/`：流程采集卡与可复用 AI 提示词模板。
- `results/demo-run-001/`：虚构样例运行结果、汇总表和哈希清单。
- `references.md`：Python 官方文档来源。

## 快速体验

需要 Python 3.10 或更新版本，无需安装第三方套件。以下命令从本包根目录运行。

先运行故意埋坑的 v2 清单：它会报告重复目标名与不存在的源文件，并拒绝执行：

```powershell
python scripts/safe_batch.py --source-dir materials/source --manifest materials/manifests/处理清单_v2_待核验.csv --output-dir results/blocked-demo
```

再用验收答案中的独立、已核准演练清单预演：

```powershell
python scripts/safe_batch.py --source-dir materials/source --manifest materials/manifests/演练已核准清单.csv --output-dir results/demo-run-001
```

看完逐条计划后，明确确认只操作虚构样例，再加 `--apply`：

```powershell
python scripts/safe_batch.py --source-dir materials/source --manifest materials/manifests/演练已核准清单.csv --output-dir results/new-run --apply
```

输出目录必须不存在；若目录已存在，脚本拒绝覆盖。再次运行时使用新的目录名。回滚方式是按 `reference/验收答案与回滚说明.md` 将生成目录移到隔离目录；来源保持原样。

## 安全边界

不要把个人、客户、员工、财务或公司机密数据上传给 AI。使用真实材料前先确认权限与组织规则。先在一次性副本中核对预演、数量、金额和输出文件，再决定是否用于正式流程。AI 草稿不是授权；正式数据、删除、覆盖、付款、邮件发送等动作须由有权人员按组织流程批准。
