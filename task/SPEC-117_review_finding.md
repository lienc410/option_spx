# SPEC-117/118/119 Quant 复核回执（2026-07-05）

**总体**: 三个 SPEC 验证通过，部署确认（oldair @6ab6939，21+ 任务，heartbeat 注册表设计良好——"新任务必须入表"断言尤其好）。settling 修复已部署（最新运行干净落 INFO，下一交易日见真章，heartbeat 会兜住）。**一个必须修的发现 + 一个注册项**：

## F-1 本机备份定时任务从未成功运行过（需修复）

- `com.spxstrat.local_backup_pull` launchctl exit code **126**；err log: `/bin/bash: .../scripts/backup_oldair_pull.sh: Operation not permitted`
- **根因 = macOS TCC**：launchd 环境无权读 `~/Documents` 下的文件（Documents 受 TCC 保护）。已有的 676MB 备份是手动终端运行的产物（terminal 有 FDA），定时路径从未走通
- 建议修复：脚本复制/移动到非 TCC 路径（如 `~/bin/backup_oldair_pull.sh`），plist 指向新路径；验收 = 下一个 05:00 周期自动成功 + oldair `data/.last_backup_pull` 标记出现（本次核查未见该标记，请一并确认 touch 逻辑在 launchd 路径下生效）
- 顺带：**本机任务不在 oldair heartbeat 覆盖内**——请把 local_backup_pull 的产出新鲜度（如 `~/backups/oldair/data` mtime < 26h）加进 heartbeat 注册表（oldair monitor 可通过反向检查约定文件实现，方案自定）

## R-1 注册项：moff 重述任务（~07-17）

AC-3 的 mid-implied 发现（vendor iv 比 mid-implied 低 1-2.5vp）意味着 Q085 P3 / Q087 A1 的旧 CALIB 绝对数字偏严苛（方向：真实 credit 比旧 CALIB 富）。*_moff 满 10 天（约 07-17）后：(a) calibration.py 出正式 offsets；(b) Quant 重述受影响 verdict 的绝对值段落；(c) SPEC-120 排期。相对比较类结论（分层无差、filter 无保护、门槛对比）不受影响。
