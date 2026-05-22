from server_toolkit.plan_parser import PlanUnresolvedError, parse_instruction


def test_parse_instruction_builds_convert_plan():
    plan = parse_instruction("把这个 Word 转成 PDF", ["input/report.docx"])

    assert plan["level"] == "L1"
    assert plan["outputs"] == ["output/report.pdf"]
    assert plan["steps"][0]["command"] == "convert"
    assert plan["steps"][0]["args"]["to"] == "pdf"


def test_parse_instruction_builds_merge_plan_for_pdfs():
    plan = parse_instruction("合并这两个 PDF", ["input/a.pdf", "input/b.pdf"])

    assert plan["outputs"] == ["output/merged.pdf"]
    assert plan["steps"][0]["command"] == "merge"
    assert plan["steps"][0]["args"]["inputs"] == ["input/a.pdf", "input/b.pdf"]


def test_parse_instruction_builds_extract_schema_plan():
    plan = parse_instruction("提取甲方和金额", ["input/contract.txt"])

    assert plan["steps"][0]["command"] == "extract"
    assert plan["steps"][0]["args"]["schema"] == "party_a,amount"


def test_parse_instruction_rejects_unresolved_request():
    try:
        parse_instruction("帮我优化一下这些材料", ["input/a.docx"])
    except PlanUnresolvedError as exc:
        assert "PLAN_UNRESOLVED" in str(exc)
    else:
        raise AssertionError("expected unresolved error")
