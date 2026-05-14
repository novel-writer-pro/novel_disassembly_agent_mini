# 后续行动

在此记录本次评估会话的后续任务与决策。

## 下一步

1. 建立 baseline 产物（Loom 最小化/关闭）
2. 建立 Loom 对照产物（至少 `ab` 或 `enabled`）
3. 运行：
   - `loom-collect-pairs`
   - `loom-pairs-stats`
   - `loom-ab-compare`
4. 对复杂 case 做人工判定
5. 人工完成后回到 resume / recovery 链继续

## 恢复入口

- `writer-imitate-execution-resume.*`
- `resume-run`
- `/api/recovery`
