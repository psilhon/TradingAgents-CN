## ADDED Requirements

### Requirement: 数据健康审计脚本 MUST tracked 于 scripts/

数据正确性审计脚本 MUST 作为 tracked 文件存在于 `scripts/data_audit.js`，MUST NOT 是 `/tmp` 下的一次性产物。

脚本 MUST 能直连 MongoDB 检查关键集合（`stock_basic_info` 等）的字段完整率与数值合理性（neg / zero / null / NaN），用于迁移后验证与定期复核数据健康。

理由：data-audit 2026-05-17 的审计脚本是 `/tmp/data_audit.js` 一次性产物，重启即丢，无法定期复核数据健康，也无法作为 Phase 3 迁移后的验证工具。

#### Scenario: 审计脚本在版本库

- **WHEN** 在仓库扫描数据审计脚本
- **THEN** `scripts/data_audit.js` 是 tracked 文件
- **AND** 不依赖 `/tmp` 下的临时副本

#### Scenario: 运行数据健康检查

- **WHEN** 执行 `mongosh <连接串> --quiet --file scripts/data_audit.js`
- **THEN** 输出各关键集合的字段完整率 + 数值合理性报告
- **AND** 报告标记低覆盖率字段与数学异常值（负 `ps` / 量级失真 `pe` 等）
