"""实体提取准确率验证框架。

用于证明模块二(非结构化文档信息提取)满足竞赛要求的 >80% 准确率指标。

Usage:
    python -m core.accuracy_validator --test-data tests/fixtures/accuracy/
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AccuracyReport:
    """Per-type and overall accuracy metrics."""
    entity_type: str
    expected: int = 0
    extracted: int = 0
    matched: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0

    @property
    def is_pass(self) -> bool:
        return self.f1 >= 0.80


@dataclass
class OverallReport:
    reports: list[AccuracyReport] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)

    @property
    def total_expected(self) -> int:
        return sum(r.expected for r in self.reports)

    @property
    def total_matched(self) -> int:
        return sum(r.matched for r in self.reports)

    @property
    def total_extracted(self) -> int:
        return sum(r.extracted for r in self.reports)

    @property
    def overall_precision(self) -> float:
        if self.total_extracted == 0:
            return 0.0
        return self.total_matched / self.total_extracted

    @property
    def overall_recall(self) -> float:
        if self.total_expected == 0:
            return 0.0
        return self.total_matched / self.total_expected

    @property
    def overall_f1(self) -> float:
        p, r = self.overall_precision, self.overall_recall
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)

    @property
    def is_pass(self) -> bool:
        """竞赛要求: 准确率 > 80%"""
        return self.overall_f1 >= 0.80

    def summary_text(self) -> str:
        lines = [
            "=" * 60,
            "          实体提取准确率验证报告",
            "=" * 60,
            f"  预期实体总数: {self.total_expected}",
            f"  实际提取总数: {self.total_extracted}",
            f"  成功匹配数量: {self.total_matched}",
            "",
            f"  准确率 (Precision): {self.overall_precision:.1%}",
            f"  召回率 (Recall):    {self.overall_recall:.1%}",
            f"  F1 分数:           {self.overall_f1:.1%}",
            "",
            f"  是否达标 (>80%): {'YES' if self.is_pass else 'NO — 需要改进'}",
            "",
            "-" * 60,
            "  各类型明细:",
            "",
        ]
        for r in self.reports:
            flag = "[PASS]" if r.is_pass else "[FAIL]"
            lines.append(
                f"  {flag} {r.entity_type:20s}  "
                f"P={r.precision:.1%}  R={r.recall:.1%}  F1={r.f1:.1%}  "
                f"({r.matched}/{r.expected})"
            )
        if self.errors:
            lines.append("")
            lines.append(f"  错误/遗漏: {len(self.errors)} 条")
            for err in self.errors[:10]:
                lines.append(f"    - [{err['type']}] 预期={err.get('expected')} 实际={err.get('actual')}")
        lines.append("=" * 60)
        return "\n".join(lines)


class EntityAccuracyValidator:
    """Validate entity extraction accuracy against annotated golden data."""

    @staticmethod
    def load_annotations(file_path: str | Path) -> list[dict]:
        """Load annotated entities from a JSON file.

        Expected format:
        [
          {"text": "document text here...",
           "entities": [
             {"type": "person", "value": "张三"},
             {"type": "amount", "value": "100万元"}
           ]}
        ]
        """
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("Annotation file must contain a JSON array")
        return data

    @staticmethod
    def normalize_value(value: str) -> str:
        """Normalize entity value for fuzzy comparison."""
        return value.strip().rstrip(".,，。、：:；;!！?？")

    @classmethod
    def match_entity(cls, extracted: dict, expected: dict) -> bool:
        """Check if an extracted entity matches an expected (golden) entity."""
        if extracted.get("entity_type") != expected.get("type"):
            return False
        ext_val = cls.normalize_value(str(extracted.get("entity_value", "")))
        exp_val = cls.normalize_value(str(expected.get("value", "")))
        if ext_val == exp_val:
            return True
        # Fuzzy: one contains the other
        if len(exp_val) >= 3 and len(ext_val) >= 3:
            return exp_val in ext_val or ext_val in exp_val
        return False

    @classmethod
    async def validate(
        cls,
        annotation_file: str | Path,
        extract_fn,
        *,
        entity_types: list[str] | None = None,
    ) -> OverallReport:
        """Run full accuracy validation.

        Args:
            annotation_file: Path to annotated test data JSON.
            extract_fn: Async function (text: str) -> list[dict] that extracts entities.
            entity_types: Optional list of entity types to validate (default: all).
        """
        annotations = cls.load_annotations(annotation_file)
        if entity_types is None:
            entity_types = cls._collect_types(annotations)

        all_expected: dict[str, list[dict]] = {t: [] for t in entity_types}
        all_extracted: dict[str, list[dict]] = {t: [] for t in entity_types}
        errors: list[dict] = []

        # Run extraction on each annotated document
        for idx, doc in enumerate(annotations):
            text = doc.get("text", "")
            expected_entities = doc.get("entities", [])

            extracted_entities = await extract_fn(text)

            # Classify expected entities by type
            for ent in expected_entities:
                etype = ent.get("type", "")
                if etype in all_expected:
                    all_expected[etype].append({"doc": idx, **ent})

            # Classify extracted entities by type
            for ent in extracted_entities:
                etype = ent.get("entity_type", ent.get("type", ""))
                if etype in all_extracted:
                    all_extracted[etype].append({"doc": idx, **ent})

        # Compute per-type metrics
        reports = []
        for etype in entity_types:
            expected = all_expected[etype]
            extracted = all_extracted[etype]
            matched = 0
            type_errors = []

            # Greedy matching: for each expected, find best match in extracted
            remaining = list(extracted)
            for exp_ent in expected:
                found = False
                for i, ext_ent in enumerate(remaining):
                    if cls.match_entity(ext_ent, exp_ent):
                        matched += 1
                        remaining.pop(i)
                        found = True
                        break
                if not found:
                    type_errors.append({
                        "type": etype,
                        "expected": exp_ent.get("value"),
                        "actual": "NOT FOUND",
                        "doc": exp_ent.get("doc"),
                    })

            precision = matched / len(extracted) if extracted else 1.0
            recall = matched / len(expected) if expected else 1.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

            reports.append(AccuracyReport(
                entity_type=etype,
                expected=len(expected),
                extracted=len(extracted),
                matched=matched,
                precision=precision,
                recall=recall,
                f1=f1,
            ))
            errors.extend(type_errors)

        return OverallReport(reports=reports, errors=errors)

    @staticmethod
    def _collect_types(annotations: list[dict]) -> list[str]:
        types: set[str] = set()
        for doc in annotations:
            for ent in doc.get("entities", []):
                t = ent.get("type", "")
                if t:
                    types.add(t)
        return sorted(types)


def create_sample_annotations(output_dir: str | Path) -> Path:
    """Create a sample annotation file for testing the accuracy framework.

    This provides a template users can copy and fill with real data.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_path = output_dir / "sample_annotations.json"

    sample = [
        {
            "document": "sample_contract_001.docx",
            "text": (
                "采购合同\n"
                "甲方：北京科技有限公司\n"
                "乙方：上海信息技术有限公司\n"
                "合同金额：人民币伍拾万元整（500,000.00元）\n"
                "签订日期：2024年3月15日\n"
                "交付日期：2024年6月30日\n"
                "联系人：张三，电话：13800138000\n"
                "邮箱：zhangsan@example.com\n"
            ),
            "entities": [
                {"type": "person", "value": "张三"},
                {"type": "organization", "value": "北京科技有限公司"},
                {"type": "organization", "value": "上海信息技术有限公司"},
                {"type": "amount", "value": "500,000.00元"},
                {"type": "amount", "value": "伍拾万元整"},
                {"type": "date", "value": "2024年3月15日"},
                {"type": "date", "value": "2024年6月30日"},
                {"type": "phone", "value": "13800138000"},
                {"type": "email", "value": "zhangsan@example.com"},
            ],
        }
    ]

    sample_path.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
    return sample_path
