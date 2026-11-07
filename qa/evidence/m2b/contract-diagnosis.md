# M2.0b `EXPLANATION_NOT_OBJECT` 契约诊断

诊断时间：2026-11-07  
诊断成本：0 次生成请求，0 token，¥0

## 1. V11 原文

文件：`# 高二英语智能练习系统 · 需求提示词 V11（最终定稿）.txt`

第 154 行：

```text
| explanation | ≥3 句：为什么选它、干扰项为什么错、考点是什么；七选五须标注衔接逻辑类型 |
```

语义：`explanation` 是每题的一段纯文本解析，不是对象。

## 2. `question.json` 契约

文件：`contracts/schemas/question.json`

第 18 行把 `explanation` 列为必填字段；第 65 行定义：

```json
"explanation": {"type": "string", "minLength": 1}
```

契约要求：字符串，必填。

## 3. 失败校验器

文件：`backend/app/m2_deepseek_pipeline.py`

第 238–258 行中，失败位置为第 247–248 行：

```python
for item in explanations:
    if not isinstance(item, dict):
        raise ValueError("EXPLANATION_NOT_OBJECT")
    question_index = item.get("question_index")
    explanation = item.get("explanation")
    if not isinstance(question_index, int):
        raise ValueError("EXPLANATION_INDEX_INVALID")
```

校验器要求：每个数组元素必须是含 `question_index` 和 `explanation` 的对象。

## 4. 实际失败请求与原始响应

失败请求：

- `2a0ff97d-cc2e-4a6a-a474-b3999af848da`
- `3a6c7afb-ad92-406a-a6ea-ed1ed32e19fa`
- `308bcdd1-e740-45ae-90a3-d5ae801b582a`
- `46a6252f-7957-489f-95cf-120ae2957fc5`

四次日均返回 `finish_reason=stop`，但均在 `EXPLANATION_NOT_OBJECT` 处被拒收。

旧版 runner 没有落盘原始响应，且 DeepSeek 没有提供按 request ID 回取响应的接口，因此本轮无法诚实补出两条历史原文。该缺口已登记为可观测性缺陷，必须在再次请求前修复；不得用推测内容冒充原始响应。

修复可观测性后，单请求解析冒烟返回了可核对的原文：

- `qa/evidence/m2b/raw-responses/3f992ba4-3a1b-466e-8fe0-61ae586def93.txt`
- 结构形状实际为：

```json
{
  "explanations": [
    {"question_index": 1, "explanation": "第1空..."},
    {"question_index": 2, "explanation": "第2空..."}
  ]
}
```

这说明模型内容已经生成完整，但中间提示词对数组元素形状表达不够明确，模型自行包装成了对象。

## 单一结论

**校验器违背了契约：V11 和 `question.json` 都规定 `explanation` 为字符串，校验器却要求对象。**

因此本次只修校验器的中间批处理协议，不放宽七道闸门，也不修改 V11 或 `question.json` 的 explanation 类型。
