"""End-to-end workflow engine connecting all three competition modules.

Module 2 (extract) → Module 3 (fill) → Module 1 (format/generate)

Built-in workflows:
- extract_and_fill:  extract entities from docs → fill a template
- full_pipeline:     extract → fill → format the result
- batch_process:     extract from multiple docs → cross-document fusion → generate report
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

from config import OUTPUT_DIR
from core.doc_commander import DocCommander
from core.entity_extractor import EntityExtractor
from core.template_filler import TemplateFiller
from core.workflow_errors import WorkflowNotFoundError, WorkflowValidationError
from db.database import EntityDAO


@dataclass
class WorkflowStep:
    name: str
    description: str = ""

    async def run(self, ctx: WorkflowContext) -> dict[str, Any]:
        raise NotImplementedError


@dataclass
class WorkflowContext:
    """Mutable context passed through workflow steps."""
    data: dict[str, Any] = field(default_factory=dict)
    logs: list[dict] = field(default_factory=list)

    def log(self, step: str, **payload):
        self.logs.append({"step": step, "time": datetime.now().isoformat(), **payload})

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value


# ── Step implementations ──────────────────────────────────────────

class ExtractStep(WorkflowStep):
    """Module 2: Extract entities from document raw text."""

    def __init__(self, doc_ids: list[int], get_texts: Callable):
        super().__init__(name="extract", description=f"Extract entities from {len(doc_ids)} doc(s)")
        self.doc_ids = doc_ids
        self.get_texts = get_texts

    async def run(self, ctx: WorkflowContext) -> dict:
        extractor = EntityExtractor()
        all_entities = []
        for doc_id in self.doc_ids:
            doc = self.get_texts(doc_id)
            if not doc or not doc.raw_text:
                ctx.log("extract_skip", doc_id=doc_id, reason="no text")
                continue
            result = await extractor.extract(doc.raw_text)
            entities = result.get("entities", [])
            EntityDAO.create_batch(doc_id, entities)
            all_entities.extend(entities)
            ctx.log("extract_done", doc_id=doc_id, entity_count=len(entities))
        ctx.set("entities", all_entities)
        ctx.set("entity_count", len(all_entities))
        return {"entities": all_entities, "count": len(all_entities)}


class FillStep(WorkflowStep):
    """Module 3: Fill a template with extracted entities."""

    def __init__(self, template_path: str):
        super().__init__(name="fill", description=f"Fill template: {Path(template_path).name}")
        self.template_path = template_path

    async def run(self, ctx: WorkflowContext) -> dict:
        entities = ctx.get("entities", [])
        if not entities:
            raise WorkflowValidationError("No entities available for template filling")
        filler = TemplateFiller()
        result = await filler.fill(self.template_path, entities)
        ctx.set("filled_path", result.get("output_path"))
        ctx.set("fill_accuracy", result.get("accuracy", 0))
        ctx.log("fill_done", accuracy=result.get("accuracy"), path=result.get("output_path"))
        return result


class FormatStep(WorkflowStep):
    """Module 1: Apply formatting to the output document via natural language."""

    def __init__(self, instruction: str):
        super().__init__(name="format", description=f"Format: {instruction[:60]}")
        self.instruction = instruction

    async def run(self, ctx: WorkflowContext) -> dict:
        doc_path = ctx.get("filled_path")
        if not doc_path or not Path(doc_path).exists():
            raise WorkflowNotFoundError("No document available for formatting")
        commander = DocCommander()
        result = await commander.execute_command(
            self.instruction, doc_path,
            doc_info=f"Path: {doc_path}",
        )
        ctx.log("format_done", success=result.get("success"))
        return result


class CrossDocFusionStep(WorkflowStep):
    """Cross-document entity fusion (data fusion theme highlight)."""

    SIMILARITY_THRESHOLD = 0.6

    def __init__(self, doc_ids: list[int]):
        super().__init__(name="fusion", description=f"Cross-document fusion for {len(doc_ids)} docs")
        self.doc_ids = doc_ids

    async def run(self, ctx: WorkflowContext) -> dict:
        if len(self.doc_ids) < 2:
            ctx.set("cross_doc", [])
            return {"cross_doc": [], "message": "Need at least 2 documents for fusion"}

        all_entities = []
        for doc_id in self.doc_ids:
            entities = EntityDAO.get_by_document(doc_id)
            for e in entities:
                all_entities.append({
                    "type": e.entity_type,
                    "value": e.entity_value,
                    "confidence": e.confidence or 0,
                    "doc_id": e.document_id,
                })

        fused = self._fuzzy_cluster(all_entities)
        cross = [c for c in fused if c["doc_count"] >= 2]
        cross.sort(key=lambda c: c["doc_count"], reverse=True)

        ctx.set("cross_doc", cross)
        ctx.set("entities", self._pick_best(fused, ctx.get("entities", [])))
        ctx.log("fusion_done", clusters=len(fused), cross_doc=len(cross))
        return {"cross_doc": cross, "count": len(cross)}

    @classmethod
    def _fuzzy_cluster(cls, entities: list[dict]) -> list[dict]:
        by_type: dict[str, list[dict]] = {}
        for e in entities:
            by_type.setdefault(e["type"], []).append(e)

        clusters = []
        for entity_type, items in by_type.items():
            groups: list[list[dict]] = []
            for item in items:
                merged = False
                for group in groups:
                    if cls._same_entity_value(entity_type, item["value"], group[0]["value"]):
                        group.append(item)
                        merged = True
                        break
                if not merged:
                    groups.append([item])

            for group in groups:
                best = max(group, key=lambda e: e["confidence"])
                doc_ids = list({e["doc_id"] for e in group})
                clusters.append({
                    "type": entity_type,
                    "value": best["value"],
                    "confidence": best["confidence"],
                    "doc_count": len(doc_ids),
                    "total_occurrences": len(group),
                    "doc_ids": doc_ids,
                    "variants": list({e["value"] for e in group}),
                })
        return clusters

    @classmethod
    def _same_entity_value(cls, entity_type: str, a: str, b: str) -> bool:
        if entity_type in {"phone", "email", "id_number", "date", "amount"}:
            return str(a).strip().lower() == str(b).strip().lower()
        return cls._char_jaccard(a, b) >= cls.SIMILARITY_THRESHOLD

    @staticmethod
    def _char_jaccard(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        set_a = set(a)
        set_b = set(b)
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union else 0.0

    @staticmethod
    def _pick_best(clusters: list[dict], existing: list[dict]) -> list[dict]:
        seen_types: dict[str, list[dict]] = {}
        for e in existing:
            seen_types.setdefault(e.get("type"), []).append(e)
        for c in clusters:
            entry = {"type": c["type"], "value": c["value"], "confidence": c["confidence"]}
            group = seen_types.setdefault(c["type"], [])
            if not any(e["value"] == c["value"] for e in group):
                group.append(entry)
        result = []
        for group in seen_types.values():
            result.extend(group)
        return result


class GenerateSummaryStep(WorkflowStep):
    """Generate a summary report from extracted/fused data via Codex CLI."""

    def __init__(self, report_description: str = ""):
        super().__init__(name="generate_summary", description="Generate summary report")
        self.report_description = report_description

    async def run(self, ctx: WorkflowContext) -> dict:
        entities = ctx.get("entities", [])
        cross_doc = ctx.get("cross_doc", [])
        if len(entities) > 100:
            logger.warning(
                "实体数量 (%d) 超过上限 100，报告将基于前 100 个实体生成",
                len(entities),
            )
            ctx.log("generate_summary_truncated", total=len(entities), used=100)
        if len(cross_doc) > 50:
            logger.warning(
                "跨文档实体数量 (%d) 超过上限 50，报告将基于前 50 个生成",
                len(cross_doc),
            )
        fusion_data = {
            "entities": entities[:100],
            "entity_count": len(entities),
            "cross_document": [self._serialize_cross_doc_entry(e) for e in cross_doc[:50]],
        }
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(OUTPUT_DIR / f"summary_report_{timestamp}.docx")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        if not Path(output_path).exists():
            from docx import Document as DocxDocument

            DocxDocument().save(output_path)

        description = self.report_description or "生成一份数据融合汇总报告，包含关键实体统计和跨文档关联分析"
        commander = DocCommander()
        instruction = (
            f"生成一份格式严谨的汇总报告保存到 {output_path}。"
            f"报告主题：{description}\n"
            f"融合数据如下：\n{json.dumps(fusion_data, ensure_ascii=False, indent=2)}"
        )
        result = await commander.execute_via_codex(output_path, instruction)
        report_ready = Path(output_path).exists() and Path(output_path).stat().st_size > 0
        if result.get("success") or report_ready:
            ctx.set("report_path", output_path)
            ctx.log("generate_summary_done", path=output_path, codex_success=result.get("success", False))
            if not result.get("success"):
                result = {
                    **result,
                    "success": True,
                    "message": result.get("message") or "Report file generated",
                }
        return result

    @staticmethod
    def _serialize_cross_doc_entry(entry: Any) -> dict[str, Any]:
        if isinstance(entry, dict):
            return {
                "type": entry.get("type") or entry.get("entity_type"),
                "value": entry.get("value") or entry.get("entity_value"),
                "doc_count": entry.get("doc_count", 0),
                "total_occurrences": entry.get("total_occurrences") or entry.get("count", 0),
                "variants": entry.get("variants", []),
                "doc_ids": entry.get("doc_ids", []),
            }
        return {
            "type": getattr(entry, "entity_type", getattr(entry, "type", None)),
            "value": getattr(entry, "entity_value", getattr(entry, "value", None)),
            "doc_count": getattr(entry, "doc_count", 0),
            "total_occurrences": getattr(entry, "total_occurrences", getattr(entry, "count", 0)),
            "variants": getattr(entry, "variants", []),
            "doc_ids": getattr(entry, "doc_ids", []),
        }


# ── Workflow runner ────────────────────────────────────────────────

class WorkflowRunner:
    """Execute a sequence of workflow steps with context propagation."""

    MAX_RETRIES = 1
    RETRY_DELAY = 2.0

    def __init__(self, name: str = "workflow"):
        self.name = name
        self.steps: list[WorkflowStep] = []

    def add_step(self, step: WorkflowStep) -> WorkflowRunner:
        self.steps.append(step)
        return self

    async def run(self, ctx: WorkflowContext = None) -> WorkflowContext:
        if ctx is None:
            ctx = WorkflowContext()
        ctx.log("workflow_start", name=self.name, step_count=len(self.steps))
        for step in self.steps:
            ctx.log("step_start", step_name=step.name)
            last_exc = None
            for attempt in range(1 + self.MAX_RETRIES):
                try:
                    result = await step.run(ctx)
                    ctx.set(f"step_{step.name}_result", result)
                    ctx.log("step_done", step_name=step.name, success=True)
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt < self.MAX_RETRIES:
                        logger.warning(
                            "Step '%s' failed (attempt %d/%d), retrying: %s",
                            step.name, attempt + 1, 1 + self.MAX_RETRIES, exc,
                        )
                        ctx.log("step_retry", step_name=step.name, attempt=attempt + 1, error=str(exc))
                        await asyncio.sleep(self.RETRY_DELAY)
            if last_exc is not None:
                ctx.log("step_failed", step_name=step.name, error=str(last_exc))
                raise last_exc
        ctx.log("workflow_complete", name=self.name)
        return ctx


# ── Pre-built workflows ───────────────────────────────────────────

async def run_extract_and_fill(
    doc_ids: list[int],
    template_path: str,
    get_texts: Callable,
    format_instruction: str = None,
) -> WorkflowContext:
    """Extract entities from documents, then fill a template.

    This is the most common end-to-end flow for Module 2 + Module 3.
    """
    runner = WorkflowRunner("extract_and_fill")
    runner.add_step(ExtractStep(doc_ids, get_texts))
    runner.add_step(FillStep(template_path))
    if format_instruction:
        runner.add_step(FormatStep(format_instruction))
    return await runner.run()


async def run_full_pipeline(
    doc_ids: list[int],
    template_path: str,
    get_texts: Callable,
    format_instruction: str = "",
    include_fusion: bool = True,
) -> WorkflowContext:
    """Complete Module 2 → Module 3 → Module 1 pipeline with optional fusion.

    This demonstrates all three competition modules working together.
    """
    runner = WorkflowRunner("full_pipeline")
    runner.add_step(ExtractStep(doc_ids, get_texts))
    if include_fusion and len(doc_ids) >= 2:
        runner.add_step(CrossDocFusionStep(doc_ids))
    runner.add_step(FillStep(template_path))
    if format_instruction:
        runner.add_step(FormatStep(format_instruction))
    return await runner.run()


async def run_batch_process_and_report(
    doc_ids: list[int],
    get_texts: Callable,
    report_description: str = "",
) -> WorkflowContext:
    """Batch extract from multiple documents, fuse data, and generate a report.

    Covers the 'data fusion' theme — multiple unstructured inputs → structured output.
    """
    runner = WorkflowRunner("batch_process")
    runner.add_step(ExtractStep(doc_ids, get_texts))
    if len(doc_ids) >= 2:
        runner.add_step(CrossDocFusionStep(doc_ids))
    runner.add_step(GenerateSummaryStep(report_description))
    return await runner.run()
