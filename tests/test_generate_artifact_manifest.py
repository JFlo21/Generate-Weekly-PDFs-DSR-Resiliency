import json

from scripts.generate_artifact_manifest import generate_manifest


def test_manifest_includes_nested_excel_files(tmp_path):
    docs_folder = tmp_path / "generated_docs"
    nested_week = docs_folder / "2025-01-05"
    docs_folder.mkdir()
    nested_week.mkdir()

    top_file = docs_folder / "WR_111_WeekEnding_010525_000000_aaaaaaaaaaaaaaaa.xlsx"
    nested_file = nested_week / "WR_222_WeekEnding_011225_000000_bbbbbbbbbbbbbbbb.xlsx"

    top_file.write_bytes(b"top")
    nested_file.write_bytes(b"nested")

    manifest = generate_manifest(str(docs_folder), "artifact_manifest.json")

    assert manifest["summary"]["total_files"] == 2
    assert set(manifest["summary"]["work_requests"]) == {"111", "222"}
    assert set(manifest["summary"]["week_endings"]) == {"010525", "011225"}

    filepaths = {entry["filepath"] for entry in manifest["artifacts"]}
    assert str(top_file) in filepaths
    assert str(nested_file) in filepaths

    # Ensure manifest file was written inside docs_folder
    manifest_path = docs_folder / "artifact_manifest.json"
    assert manifest_path.exists()
    manifest_disk = json.loads(manifest_path.read_text())
    assert manifest_disk["summary"]["total_files"] == 2
