from quiz_buzzer.sheets.adapter import SheetsAdapter
from quiz_buzzer.sheets.models import CellUpdate, MergedRange, SpreadsheetStructure, WorksheetGrid
from tests.fakes import MemorySheetsAdapter


def test_memory_adapter_implements_transport_neutral_read_write_contract():
    url = "fake://course/notes"
    structure = SpreadsheetStructure(
        spreadsheet_id="sheet-test",
        worksheets=[
            WorksheetGrid(
                worksheet_id="tab-1",
                title="Notes",
                values=[["題號", "作答"], [1, None]],
                merged_ranges=[MergedRange(1, 2, 0, 1)],
            )
        ],
    )
    adapter: SheetsAdapter = MemorySheetsAdapter({url: structure})

    read_back = adapter.read_structure(url)
    update = CellUpdate("tab-1", 1, 1, "answer")
    adapter.write_answers("sheet-test", [update])

    assert read_back is structure
    assert read_back.worksheets[0].merged_ranges[0] == MergedRange(1, 2, 0, 1)
    assert adapter.write_calls == [("sheet-test", [update])]
