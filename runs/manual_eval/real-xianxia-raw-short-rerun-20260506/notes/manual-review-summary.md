# Raw Xianxia Short Rerun Summary

## Final status
run_id=51499b32-cdd0-475f-bbc7-2ac27ea0f529
branch_id=23685de0-a53e-4229-a946-14d53d5b026d
branch_name=main
branch_status=active
manifest_chapter_count=5
completed_chapters=5
failed_jobs=0
running_jobs=0
next_chapter=None
fact_count=51
window_count=1
graph_node_count=64
graph_edge_count=524


## Chapter rows
chapter_row_count=5
chapter=1|title=青华|job=validated|artifact=True|retrieval=True|hook=4.5|review=False
chapter=2|title=厌物丽人同行|job=validated|artifact=True|retrieval=True|hook=4.0|review=False
chapter=3|title=狡舌|job=validated|artifact=True|retrieval=True|hook=4.0|review=False
chapter=4|title=仙道无凭|job=validated|artifact=True|retrieval=True|hook=4.0|review=True
chapter=5|title=世界|job=validated|artifact=True|retrieval=True|hook=4.0|review=False


## Key conclusions
- 原始 `第X节` 修仙文本已可直接 ingest。
- chapter 2 不再出现 dialogue_candidates schema fail。
- chapter 3 不再出现 normalized_title 缺失导致的 fallback。
- 本次短复跑用于验证前 3 章兼容性修复，随后补完 chapter 4/5 以验证主链完整度。
