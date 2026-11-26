import pytest

from quiz_buzzer.sheets.google_adapter import GRID_FIELDS, GoogleSheetsAdapter
from quiz_buzzer.sheets.models import CellUpdate, SheetsAdapterError


class Request:
    def __init__(self, result=None):
        self.result = result

    def execute(self):
        return self.result


class FakeSpreadsheetsResource:
    def __init__(self, metadata):
        self.metadata = metadata
        self.get_args = None
        self.get_calls = []
        self.batch_args = None

    def get(self, **kwargs):
        self.get_args = kwargs
        self.get_calls.append(kwargs)
        if not kwargs.get("includeGridData"):
            return Request(
                {
                    "spreadsheetId": self.metadata["spreadsheetId"],
                    "sheets": [
                        {"properties": sheet["properties"]}
                        for sheet in self.metadata.get("sheets", [])
                    ],
                }
            )
        ranges = kwargs.get("ranges")
        if ranges:
            title = ranges[0][1:-1].replace("''", "'")
            return Request(
                {
                    "spreadsheetId": self.metadata["spreadsheetId"],
                    "sheets": [
                        sheet
                        for sheet in self.metadata.get("sheets", [])
                        if sheet["properties"]["title"] == title
                    ],
                }
            )
        return Request(self.metadata)

    def batchUpdate(self, **kwargs):
        self.batch_args = kwargs
        return Request({"replies": []})


class FakeGoogleService:
    def __init__(self, metadata):
        self.resource = FakeSpreadsheetsResource(metadata)

    def spreadsheets(self):
        return self.resource


@pytest.fixture
def metadata():
    return {
        "spreadsheetId": "abc-123",
        "sheets": [
            {
                "properties": {"sheetId": 77, "title": "Guided Notes"},
                "merges": [
                    {
                        "startRowIndex": 4,
                        "endRowIndex": 6,
                        "startColumnIndex": 1,
                        "endColumnIndex": 2,
                    }
                ],
                "data": [
                    {
                        "startRow": 3,
                        "startColumn": 1,
                        "rowData": [
                            {"values": [{"formattedValue": "題號"}, {"formattedValue": "作答"}]},
                            {"values": [{"formattedValue": "1"}, {"formattedValue": ""}]},
                            {"values": [{}, {"formattedValue": ""}]},
                        ],
                    }
                ],
            },
            {
                "properties": {"sheetId": 88, "title": "Other"},
                "merges": [],
                "data": [],
            },
        ],
    }


def test_google_adapter_ignores_url_gid_and_reads_worksheets_in_sheet_order(metadata):
    service = FakeGoogleService(metadata)
    adapter = GoogleSheetsAdapter(service)

    structure = adapter.read_structure(
        "https://docs.google.com/spreadsheets/d/abc-123/edit#gid=999"
    )

    assert structure.spreadsheet_id == "abc-123"
    assert [sheet.worksheet_id for sheet in structure.worksheets] == ["77", "88"]
    worksheet = structure.worksheets[0]
    assert worksheet.worksheet_id == "77"
    assert worksheet.title == "Guided Notes"
    assert worksheet.values[3][1:3] == ["題號", "作答"]
    assert worksheet.values[4][1] == "1"
    assert worksheet.merged_ranges[0].end_row_index == 6
    assert service.resource.get_calls == [{
        "spreadsheetId": "abc-123", "includeGridData": True, "fields": GRID_FIELDS
    }]


def test_google_adapter_reads_all_worksheets_in_order_without_gid(metadata):
    service = FakeGoogleService(metadata)
    adapter = GoogleSheetsAdapter(service)

    structure = adapter.read_structure("https://docs.google.com/spreadsheets/d/abc-123/edit")

    assert [worksheet.worksheet_id for worksheet in structure.worksheets] == ["77", "88"]
    assert service.resource.get_calls == [
        {
            "spreadsheetId": "abc-123",
            "includeGridData": True,
            "fields": GRID_FIELDS,
        }
    ]


def test_google_adapter_contract_writes_text_to_requested_coordinates(metadata):
    service = FakeGoogleService(metadata)
    adapter = GoogleSheetsAdapter(service)
    update = CellUpdate("77", 5, 6, "=plain text")

    adapter.write_answers("abc-123", [update])

    request = service.resource.batch_args
    assert request["spreadsheetId"] == "abc-123"
    cell_request = request["body"]["requests"][0]["updateCells"]
    assert cell_request["range"] == {
        "sheetId": 77,
        "startRowIndex": 5,
        "endRowIndex": 6,
        "startColumnIndex": 6,
        "endColumnIndex": 7,
    }
    assert cell_request["rows"][0]["values"][0]["userEnteredValue"] == {
        "stringValue": "=plain text"
    }
    assert cell_request["fields"] == "userEnteredValue"


def test_google_adapter_rejects_invalid_urls_before_calling_service(metadata):
    service = FakeGoogleService(metadata)
    adapter = GoogleSheetsAdapter(service)

    with pytest.raises(SheetsAdapterError, match="無法從連結識別"):
        adapter.read_structure("https://example.com/not-a-sheet")
    assert service.resource.get_args is None


def test_google_adapter_can_read_only_the_recorded_worksheet(metadata):
    service = FakeGoogleService(metadata)
    adapter = GoogleSheetsAdapter(service)

    structure = adapter.read_structure(
        "https://docs.google.com/spreadsheets/d/abc-123/edit", worksheet_id="88"
    )

    assert [worksheet.worksheet_id for worksheet in structure.worksheets] == ["88"]
    assert service.resource.get_calls[-1]["ranges"] == ["'Other'"]


def test_google_adapter_rejects_missing_recorded_worksheet(metadata):
    adapter = GoogleSheetsAdapter(FakeGoogleService(metadata))

    with pytest.raises(SheetsAdapterError, match="找不到匯入時記錄的工作表 worksheet_id=999"):
        adapter.read_structure(
            "https://docs.google.com/spreadsheets/d/abc-123/edit", worksheet_id="999"
        )


def test_google_adapter_uses_recorded_worksheet_id_even_if_url_has_gid(metadata):
    service = FakeGoogleService(metadata)
    adapter = GoogleSheetsAdapter(service)

    structure = adapter.read_structure(
        "https://docs.google.com/spreadsheets/d/abc-123/edit#gid=77",
        worksheet_id="88",
    )
    assert [sheet.worksheet_id for sheet in structure.worksheets] == ["88"]
    assert service.resource.get_calls[-1]["ranges"] == ["'Other'"]
