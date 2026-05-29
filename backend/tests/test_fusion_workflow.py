import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.fusion_workflow import FusionWorkflow
from openpyxl import load_workbook
from db.database import DocumentDAO, EntityDAO
from db import models
from db.models import Base, configure_database, init_db, reset_database


def test_fusion_workflow_clusters_variants_and_exports_report(tmp_path):
    configure_database(f"sqlite:///{tmp_path / 'fusion.db'}")
    Base.metadata.drop_all(models.engine)
    init_db()
    try:
        docs = [
            DocumentDAO.create("校园采购合同A.txt", "txt", str(tmp_path / "a.txt")),
            DocumentDAO.create("供应商报价B.txt", "txt", str(tmp_path / "b.txt")),
            DocumentDAO.create("验收纪要C.txt", "txt", str(tmp_path / "c.txt")),
        ]
        EntityDAO.create_batch(
            docs[0].id,
            [
                {"type": "organization", "value": "北京智远科技有限公司", "confidence": 0.95},
                {"type": "amount", "value": "128,000.00元", "confidence": 0.96},
            ],
        )
        EntityDAO.create_batch(
            docs[1].id,
            [
                {"type": "organization", "value": "北京智远科技", "confidence": 0.90},
                {"type": "amount", "value": "128,000.00元", "confidence": 0.95},
            ],
        )
        EntityDAO.create_batch(
            docs[2].id,
            [
                {"type": "organization", "value": "智远科技有限公司", "confidence": 0.91},
                {"type": "amount", "value": "128,000.00元", "confidence": 0.93},
            ],
        )

        rows = FusionWorkflow().list_cross_document_entities()

        org = next(row for row in rows if row["type"] == "organization")
        assert org["doc_count"] == 3
        assert set(org["variants"]) == {"北京智远科技有限公司", "北京智远科技", "智远科技有限公司"}

        export = FusionWorkflow().export_report(rows)
        assert export.filename.endswith(".xlsx")
        assert export.content.startswith(b"PK")
    finally:
        reset_database()


def test_fusion_report_does_not_export_question_mark_garbage(tmp_path):
    rows = [
        {
            "type": "organization",
            "value": "????????",
            "doc_count": 3,
            "count": 3,
            "avg_confidence": 0.95,
            "documents": ["fusion_test.docx"],
            "variants": ["????????", "Acme Trading Co."],
        },
        {
            "type": "amount",
            "value": "128,000.00?",
            "doc_count": 2,
            "count": 2,
            "avg_confidence": 0.96,
            "documents": ["fusion_test.docx"],
            "variants": ["128,000.00?"],
        },
    ]

    export = FusionWorkflow().export_report(rows)
    target = tmp_path / "fusion.xlsx"
    target.write_bytes(export.content)
    workbook = load_workbook(target)
    sheet = workbook.active

    assert sheet["B2"].value == "Acme Trading Co."
    assert sheet["G2"].value == "Acme Trading Co."
    assert sheet["B3"].value == "128,000.00?"
