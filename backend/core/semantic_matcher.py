"""语义匹配器 - 将模板字段与提取的实体进行智能匹配"""
from llm import get_llm

LOCAL_FIELD_RULES = {
    "person": ("姓名", "联系人", "负责人", "经办人", "申请人", "代表"),
    "organization": ("公司", "单位", "机构", "企业", "甲方", "乙方"),
    "date": ("日期", "时间", "期限", "年月日"),
    "amount": ("金额", "费用", "预算", "价格", "报价", "总价"),
    "phone": ("电话", "手机", "联系方式", "联系电话"),
    "email": ("邮箱", "邮件", "email", "e-mail"),
    "address": ("地址", "住址", "所在地"),
    "id_number": ("编号", "证件号", "合同号", "统一社会信用代码", "身份证"),
}

MATCH_PROMPT = """你是一个语义匹配专家。请将模板表格的字段名与已提取的实体数据进行智能匹配。

## 模板字段
{fields}

## 已提取的实体数据
{entities}

## 匹配规则
1. 语义匹配：字段名和实体类型/值语义相近即可匹配
   - "姓名"/"联系人"/"负责人" → person 类型
   - "公司"/"单位"/"机构" → organization 类型
   - "日期"/"时间"/"签订日期" → date 类型
   - "金额"/"费用"/"预算" → amount 类型
   - "电话"/"手机"/"联系方式" → phone 类型
   - "邮箱"/"邮件" → email 类型
   - "地址"/"住址" → address 类型
   - "编号"/"证件号"/"合同号" → id_number 类型
2. 如果同一类型有多个候选实体，选择置信度最高的
3. 一个实体可以匹配多个字段（如同一个人名可填"联系人"和"负责人"）
4. 无法匹配的字段放入 unmatched_fields，不要强行匹配

## 输出格式（严格JSON）
{{
  "matches": [
    {{"field": "字段名", "value": "匹配的实体值", "confidence": 0.95, "source_entity_type": "实体类型"}}
  ],
  "unmatched_fields": ["未能匹配的字段名"]
}}

## 示例
字段：["姓名", "公司名称", "联系电话", "合同金额"]
实体：[person]王建国(0.95), [organization]北京智远科技(0.90), [phone]010-82567890(0.95), [amount]120万元(0.95)

输出：
{{
  "matches": [
    {{"field": "姓名", "value": "王建国", "confidence": 0.95, "source_entity_type": "person"}},
    {{"field": "公司名称", "value": "北京智远科技", "confidence": 0.90, "source_entity_type": "organization"}},
    {{"field": "联系电话", "value": "010-82567890", "confidence": 0.95, "source_entity_type": "phone"}},
    {{"field": "合同金额", "value": "120万元", "confidence": 0.95, "source_entity_type": "amount"}}
  ],
  "unmatched_fields": []
}}"""


class SemanticMatcher:
    def __init__(self, provider: str = None):
        self.llm = get_llm(provider)

    async def match(self, fields: list[str], entities: list[dict]) -> dict:
        """将字段列表与实体列表进行语义匹配"""
        local_result = self._match_local(fields, entities)
        if not local_result["unmatched_fields"]:
            return local_result

        fields_str = "\n".join(f"- {f}" for f in fields)
        entities_str = "\n".join(
            f"- [{e.get('type')}] {e.get('value')} (置信度: {e.get('confidence', 'N/A')})"
            for e in entities
        )
        user_input = f"fields:\n{fields_str}\n\nentities:\n{entities_str}"
        llm_result = await self.llm.extract_json(MATCH_PROMPT.format(fields=fields_str, entities=entities_str), user_input)
        return self._merge_results(local_result, llm_result)

    @staticmethod
    def _match_local(fields: list[str], entities: list[dict]) -> dict:
        matches = []
        unmatched_fields = []
        entities_by_type = SemanticMatcher._best_entities_by_type(entities)

        for field in fields:
            entity_type = SemanticMatcher._infer_entity_type(field)
            entity = entities_by_type.get(entity_type)
            if entity:
                matches.append(
                    {
                        "field": field,
                        "value": entity.get("value"),
                        "confidence": entity.get("confidence", 0.8),
                        "source_entity_type": entity.get("type"),
                    }
                )
            else:
                unmatched_fields.append(field)

        return {"matches": matches, "unmatched_fields": unmatched_fields}

    @staticmethod
    def _best_entities_by_type(entities: list[dict]) -> dict[str, dict]:
        best = {}
        for entity in entities:
            entity_type = entity.get("type")
            if not entity_type or not entity.get("value"):
                continue
            current = best.get(entity_type)
            confidence = entity.get("confidence") or 0
            current_confidence = (current or {}).get("confidence") or 0
            if current is None or confidence > current_confidence:
                best[entity_type] = entity
        return best

    @staticmethod
    def _infer_entity_type(field: str) -> str | None:
        normalized = str(field).strip().lower()
        for entity_type, keywords in LOCAL_FIELD_RULES.items():
            if any(keyword.lower() in normalized for keyword in keywords):
                return entity_type
        return None

    @staticmethod
    def _merge_results(local_result: dict, llm_result: dict) -> dict:
        matches = list(local_result.get("matches", []))
        matched_fields = {m.get("field") for m in matches}

        for match in llm_result.get("matches", []):
            if match.get("field") not in matched_fields:
                matches.append(match)
                matched_fields.add(match.get("field"))

        unmatched_fields = [
            field
            for field in llm_result.get("unmatched_fields", local_result.get("unmatched_fields", []))
            if field not in matched_fields
        ]
        return {"matches": matches, "unmatched_fields": unmatched_fields}
