"""实体提取器 - 使用LLM从文本中提取结构化信息"""
import asyncio
import re
from llm import get_llm
from llm.cache import get_cached, set_cached
from llm.json_utils import normalize_entity_result
from core.text_chunker import TextChunker
from core.llm_budget import truncate_for_llm, should_fallback
from logger import get_logger

log = get_logger("core.extractor")

EXTRACT_PROMPT = """你是一个专业的信息提取助手。请从给定文本中精确提取所有关键实体信息，以JSON格式返回。

## 实体类型定义
- person: 人名（中文姓名、英文姓名、职位+姓名）
- organization: 机构/公司/政府部门/学校/医院等组织名称
- date: 日期/时间（如2026年3月15日、2026-03-15、Q3等）
- amount: 金额/数量（如120万元、¥1,200,000、98000元/年）
- phone: 电话号码（手机号、座机号、400电话、内线号码）
- email: 邮箱地址
- address: 地址（省市区+详细地址）
- id_number: 证件号/编号/合同号/项目编号等标识符
- custom: 其他重要信息（产品名称、技术术语、百分比指标等）

## 提取规则
1. 只提取文本中明确出现的信息，不要推测或编造
2. 同一实体只提取一次，取最完整的表述
3. 置信度评分标准：明确出现=0.95，上下文推断=0.80，模糊信息=0.65
4. context字段填写实体所在的原文片段（15-30字），帮助定位来源

## 输出格式（严格JSON）
{
  "entities": [
    {"type": "实体类型", "value": "实体值", "context": "实体所在原文片段", "confidence": 0.95}
  ],
  "summary": "文档核心内容一句话摘要",
  "topic": "文档主题分类"
}

## 示例
输入文本："甲方：北京智远科技有限公司，联系人王建国，电话010-82567890，合同金额120万元，签订日期2026年3月15日。"

输出：
{
  "entities": [
    {"type": "organization", "value": "北京智远科技有限公司", "context": "甲方：北京智远科技有限公司", "confidence": 0.95},
    {"type": "person", "value": "王建国", "context": "联系人王建国", "confidence": 0.95},
    {"type": "phone", "value": "010-82567890", "context": "电话010-82567890", "confidence": 0.95},
    {"type": "amount", "value": "120万元", "context": "合同金额120万元", "confidence": 0.95},
    {"type": "date", "value": "2026年3月15日", "context": "签订日期2026年3月15日", "confidence": 0.95}
  ],
  "summary": "北京智远科技有限公司签订120万元合同",
  "topic": "商业合同"
}"""

VERIFY_PROMPT = """你是一个实体验证专家。请根据原文上下文，逐一验证以下实体信息的准确性。

## 验证标准
1. 实体值是否在原文中真实存在（非幻觉）
2. 实体类型分类是否正确（如人名不应归为机构）
3. 实体值是否完整（如地址是否截断、金额是否包含单位）
4. 如果实体有误，请修正为正确值；如果是幻觉实体，标记 verified=false

## 待验证的实体
{entities}

## 输出格式（严格JSON）
{{
  "entities": [
    {{"type": "类型", "value": "修正后的值", "context": "原文片段", "confidence": 置信度, "verified": true}}
  ]
}}

注意：verified=false 表示该实体应被删除，verified=true 表示验证通过。"""

# 低于此阈值的实体将进入二轮验证
CONFIDENCE_THRESHOLD = 0.75
EXTRACT_CACHE_PROMPT = "entity_extract:v2"
MAX_CHUNK_CANDIDATES = 8
REGEX_ENTITY_PATTERNS = {
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "phone": r"(?<!\d)(?:1[3-9]\d{9}|0\d{2,3}-?\d{7,8}|400-?\d{3}-?\d{4}|\+\d{1,3}[\s-]?\d{1,14})(?!\d)",
    "amount": (
        r"(?:￥|¥|USD|\$)?\d+(?:,\d{3})*(?:\.\d+)?\s*(?:万元|亿元|元|人民币|美元|万|亿|USD|dollars?)"
        r"|[壹贰叁肆伍陆柒捌玖拾佰仟万萬亿億零]+元(?:整|[角分壹贰叁肆伍陆柒捌玖拾零]+)*"
    ),
    "date": (
        r"\d{4}年\d{1,2}月\d{1,2}日"
        r"|\d{4}年\d{1,2}月"
        r"|\d{4}[-/.]\d{1,2}[-/.]\d{1,2}"
        r"|\d{1,2}/\d{1,2}/\d{2,4}"
        r"|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}"
        r"|[一二三四五六七八九十]+月[一二三四五六七八九十]+日"
    ),
    "id_number": r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)",
}
CHUNK_KEYWORDS = {
    "person": ("姓名", "联系人", "负责人", "经办人", "申请人", "代表"),
    "organization": ("公司", "单位", "机构", "企业", "甲方", "乙方"),
    "date": ("日期", "时间", "期限", "签订", "年月日"),
    "amount": ("金额", "费用", "预算", "价格", "报价", "总价", "元", "万"),
    "phone": ("电话", "手机", "联系方式", "联系电话", "座机"),
    "email": ("邮箱", "邮件", "@"),
    "address": ("地址", "住址", "所在地"),
    "id_number": ("编号", "证件号", "合同号", "统一社会信用代码", "身份证"),
}


class EntityExtractor:
    def __init__(self, provider: str = None, enable_verify: bool = True, llm_client=None):
        self.llm = llm_client or get_llm(provider)
        self.chunker = TextChunker()
        self.enable_verify = enable_verify

    async def extract(self, text: str, force: bool = False) -> dict:
        """从文本中提取实体，支持长文本自动分块 + 多轮验证"""
        if not text or not text.strip():
            log.warning("输入文本为空，跳过提取")
            return {"entities": [], "summary": "", "topic": ""}

        cache_key_prefix = self._cache_key_prefix()
        cached = None if force else get_cached(cache_key_prefix, text)
        if cached and not cached.get("parse_error"):
            log.info("命中文档级实体提取缓存，跳过LLM抽取")
            return cached

        chunks = self.chunker.chunk(text)
        chunks = self._select_relevant_chunks(chunks)
        chunks = [truncate_for_llm(chunk) for chunk in chunks]

        if len(chunks) == 1:
            result = await self._extract_with_fallback(chunks[0])
        else:
            tasks = [self._extract_with_fallback(chunk) for chunk in chunks]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            result = self._merge_results(results)

        if result.get("parse_error"):
            return result

        result = normalize_entity_result(result)
        result["entities"] = self._merge_entities(result.get("entities", []), self._extract_regex_entities(text))

        # 二轮验证：对低置信度实体进行精确验证
        if self.enable_verify:
            result = await self._verify_low_confidence(result, text)
            result["entities"] = self._merge_entities(result.get("entities", []), [])

        set_cached(cache_key_prefix, text, result)
        return result

    def _cache_key_prefix(self) -> str:
        profile = getattr(self.llm, "profile", None)
        vendor = getattr(profile, "vendor", "")
        base_url = getattr(profile, "base_url", "") or getattr(self.llm, "base_url", "")
        model = getattr(self.llm, "model", "")
        verify = bool(getattr(self, "enable_verify", True))
        return (
            f"{EXTRACT_CACHE_PROMPT}:verify={verify}:"
            f"llm={type(self.llm).__name__}:vendor={vendor}:base_url={base_url}:model={model}"
        )

    async def _verify_low_confidence(self, result: dict, original_text: str) -> dict:
        """对低置信度实体进行二轮验证"""
        entities = result.get("entities", [])
        low_conf = [e for e in entities if (e.get("confidence") or 0) < CONFIDENCE_THRESHOLD]
        high_conf = [e for e in entities if (e.get("confidence") or 0) >= CONFIDENCE_THRESHOLD]

        if not low_conf:
            log.info(f"所有 {len(entities)} 个实体置信度均达标，跳过二轮验证")
            return result

        log.info(f"发现 {len(low_conf)} 个低置信度实体，启动二轮验证")

        # 构建验证prompt
        entities_str = "\n".join(
            f"- [{e.get('type')}] {e.get('value')} (上下文: {e.get('context', '')}, 置信度: {e.get('confidence', 'N/A')})"
            for e in low_conf
        )
        # 使用完整原文作为验证上下文（LLM会自动处理长文本）
        context_text = original_text
        verify_result = await self.llm.extract_json(VERIFY_PROMPT.format(entities=entities_str), context_text)

        if verify_result.get("parse_error"):
            log.warning("二轮验证解析失败，保留原始结果")
            return result
        verify_result = normalize_entity_result(verify_result)

        # 合并验证结果
        verified = verify_result.get("entities", [])
        verified_entities = []
        for e in verified:
            if e.get("verified", True):
                # 验证通过的实体提升置信度
                e["confidence"] = max(e.get("confidence", 0), CONFIDENCE_THRESHOLD)
                verified_entities.append(e)
            else:
                log.info(f"实体被二轮验证排除: [{e.get('type')}] {e.get('value')}")

        result["entities"] = high_conf + verified_entities
        log.info(f"二轮验证完成: {len(high_conf)} 高置信 + {len(verified_entities)} 验证通过 = {len(result['entities'])} 个实体")
        return result

    @staticmethod
    def _select_relevant_chunks(chunks: list[str]) -> list[str]:
        if len(chunks) <= MAX_CHUNK_CANDIDATES:
            return chunks

        ranked = sorted(
            ((EntityExtractor._score_chunk(chunk), idx, chunk) for idx, chunk in enumerate(chunks)),
            key=lambda item: (-item[0], item[1]),
        )
        selected = [chunk for score, _, chunk in ranked[:MAX_CHUNK_CANDIDATES] if score > 0]
        if selected:
            return selected
        return chunks[:MAX_CHUNK_CANDIDATES]

    @staticmethod
    def _score_chunk(chunk: str) -> int:
        text = str(chunk)
        score = 0
        for keywords in CHUNK_KEYWORDS.values():
            for keyword in keywords:
                if keyword in text:
                    score += 1
        score += len(re.findall(r"\d", text)) // 8
        return score

    @staticmethod
    def _extract_regex_entities(text: str) -> list[dict]:
        entities = []
        seen = set()
        for entity_type, pattern in REGEX_ENTITY_PATTERNS.items():
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                value = match.group(0).strip().rstrip("，,。；;")
                key = (entity_type, value)
                if not value or key in seen:
                    continue
                seen.add(key)
                entities.append(
                    {
                        "type": entity_type,
                        "value": value,
                        "context": EntityExtractor._context_window(text, match.start(), match.end()),
                        "confidence": 0.95,
                    }
                )
        return entities

    @staticmethod
    def _context_window(text: str, start: int, end: int, radius: int = 20) -> str:
        return text[max(0, start - radius): min(len(text), end + radius)].strip()

    @staticmethod
    def _merge_entities(primary: list[dict], secondary: list[dict]) -> list[dict]:
        merged = []
        by_key = {}
        for entity in primary + secondary:
            key = (entity.get("type"), entity.get("value"))
            if not key[0] or not key[1]:
                continue
            existing_index = by_key.get(key)
            if existing_index is None:
                by_key[key] = len(merged)
                merged.append(entity)
                continue
            existing = merged[existing_index]
            if (entity.get("confidence") or 0) > (existing.get("confidence") or 0):
                merged[existing_index] = entity
        return merged

    def _merge_results(self, results: list) -> dict:
        """合并多个chunk的提取结果，去重"""
        all_entities = []
        summaries = []
        seen = set()

        for r in results:
            if isinstance(r, Exception) or r.get("parse_error"):
                continue
            for entity in r.get("entities", []):
                key = (entity.get("type"), entity.get("value"))
                if key not in seen:
                    seen.add(key)
                    all_entities.append(entity)
                else:
                    # 重复实体取更高置信度
                    for existing in all_entities:
                        if (existing.get("type"), existing.get("value")) == key:
                            existing["confidence"] = max(
                                existing.get("confidence", 0),
                                entity.get("confidence", 0)
                            )
                            break
            if r.get("summary"):
                summaries.append(r["summary"])

        return {
            "entities": all_entities,
            "summary": " ".join(summaries) if summaries else "",
            "topic": next((r.get("topic", "") for r in results if isinstance(r, dict) and not r.get("parse_error")), ""),
        }

    async def _extract_with_fallback(self, chunk: str) -> dict:
        """Extract entities with fallback to regex-only on LLM failure."""
        try:
            return await self.llm.extract_json(EXTRACT_PROMPT, chunk)
        except Exception as e:
            if should_fallback(e):
                log.warning(f"LLM调用失败，降级为正则提取: {e}")
                entities = self._extract_regex_entities(chunk)
                return {"entities": entities, "summary": "", "topic": "", "fallback": True}
            raise
