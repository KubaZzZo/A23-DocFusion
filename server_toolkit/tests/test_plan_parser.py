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


def test_parse_instruction_builds_format_then_convert_l2_plan():
    plan = parse_instruction("format heading font SimHei 18 then convert to PDF", ["input/report.docx"])

    assert plan["level"] == "L2"
    assert plan["outputs"] == ["output/report.pdf"]
    assert [step["command"] for step in plan["steps"]] == ["format-docx", "convert"]
    assert plan["steps"][0]["args"]["heading_font"] == "SimHei"
    assert plan["steps"][0]["args"]["heading_size"] == 18
    assert plan["steps"][1]["args"]["input"] == "work/report_formatted.docx"


def test_parse_instruction_builds_single_format_plan_for_first_line():
    plan = parse_instruction("将第一行字体变粗,然后加下划线并改成红色", ["input/report.docx"])

    assert plan["level"] == "L1"
    assert plan["outputs"] == ["output/report_formatted.docx"]
    assert plan["steps"][0]["command"] == "format-docx"
    assert plan["steps"][0]["args"]["first_line_bold"] is True
    assert plan["steps"][0]["args"]["first_line_underline"] is True
    assert plan["steps"][0]["args"]["first_line_color"] == "#d93025"


def test_parse_instruction_converts_markdown_before_first_line_format():
    plan = parse_instruction("将第一行字体变粗,然后加下划线", ["input/notes.md"])

    assert plan["level"] == "L2"
    assert plan["outputs"] == ["output/notes_formatted.docx"]
    assert [step["command"] for step in plan["steps"]] == ["convert", "format-docx"]
    assert plan["steps"][1]["args"]["first_line_bold"] is True
    assert plan["steps"][1]["args"]["first_line_underline"] is True


def test_parse_instruction_builds_ocr_then_extract_l2_plan():
    plan = parse_instruction("ocr then extract amount date vendor", ["input/invoice.png"])

    assert plan["level"] == "L2"
    assert plan["outputs"] == ["output/entities.json"]
    assert [step["command"] for step in plan["steps"]] == ["ocr", "extract"]
    assert plan["steps"][1]["args"]["schema"] == "amount,date,vendor"


def test_parse_instruction_builds_merge_then_format_l2_plan():
    plan = parse_instruction("merge these Word files and format heading font SimHei 16", ["input/a.docx", "input/b.docx"])

    assert plan["level"] == "L2"
    assert plan["outputs"] == ["output/merged.docx"]
    assert [step["command"] for step in plan["steps"]] == ["merge", "format-docx"]


def test_parse_instruction_rejects_merge_format_for_non_docx_inputs():
    try:
        parse_instruction("merge these Word files and format heading font SimHei 16", ["input/a.txt", "input/b.txt"])
    except PlanUnresolvedError as exc:
        assert "docx" in str(exc)
    else:
        raise AssertionError("expected non-docx merge format rejection")
