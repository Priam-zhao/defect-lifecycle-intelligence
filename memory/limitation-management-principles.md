# Limitation Management Principles

## From User (2026-06-12)

### Principle 1: Limitation Creation Flow

When a defect is approved as limitation:
1. The original defect is **deferred** to the next project
2. A **limitation defect** is created in the current project as a record
3. All limitation defects have the **original defect ID in the description**

Example description:
```
This is the temporary limitation record for defect OBMC-17994.
```

### Principle 2: Limitation Tracking via Issue Links

Limitation defects can be identified through:
1. **Issue Links** - Related issues linked via `issuelinks`
2. **Summary Pattern** - All limitation defects share the same summary format
3. **Issue Key Ordering** - Limitation sequence can be determined by the number in the issue key

### Implication for LimitationTool

Need to add method to:
1. Search for limitation records linked to original defect
2. Find limitation records by summary pattern matching
3. Order limitations by issue key number (lower number = earlier)
4. Calculate duration for each limitation period

## Implementation Completed (2026-06-15)

### Method: `get_limitation_records(defect_id)`

Added to `mcp-server/tools/limitation_tool.py`:

```python
def get_limitation_records(self, defect_id: str) -> Dict[str, Any]:
    """
    获取缺陷的所有 limitation 记录（追溯 limitation 历史）
    
    原则1: 原 defect defer 到下一项目，当前项目生成 limitation defect 记录
    原则2: 通过 Issue Links 和 Description 模式识别 limitation records
    原则3: limitation 先后顺序按 issue key 数字大小排序
    """
```

### Implementation Details

1. **_get_linked_limitation_defects**: 从 Issue Links 获取关联的 limitation defect
2. **_get_similar_limitation_defects**: 通过 JQL 搜索 description 包含 "temporary/permanent limitation record for {defect_id}"
3. **_is_limitation_defect**: 判断 issue 是否是 limitation defect
4. **_merge_and_sort_records**: 合并并按 key_number 排序
5. **_calculate_duration**: 计算每个 limitation 的持续天数

### Test Result: OBMC-17994

```
Total Limitation Records: 3

#1: OBMC-18143 (Key: 18143) - Duration: 440.0 days
#2: OBMC-19321 (Key: 19321) - Duration: 369.0 days
#3: OBMC-23117 (Key: 23117) - Duration: 181.0 days
```

### Bug Fixed

`LIMITATION_STATUSES` 常量未定义，导致 JQL 搜索失败。已添加定义。

---

**Created**: 2026-06-12
**Updated**: 2026-06-15
**Related**: [[limitation-data-integration]]