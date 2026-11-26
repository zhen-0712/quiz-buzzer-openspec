"""Google Sheets API implementation with no import-time auth or network access."""

import re
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlparse

from quiz_buzzer.sheets.models import (
    CellUpdate,
    MergedRange,
    SheetsAdapterError,
    SpreadsheetStructure,
    WorksheetGrid,
)


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
GRID_FIELDS = (
    "spreadsheetId,sheets(properties(sheetId,title),merges,"
    "data(startRow,startColumn,rowData(values(formattedValue))))"
)
SHEET_METADATA_FIELDS = "spreadsheetId,sheets(properties(sheetId,title))"


class GoogleSheetsAdapter:
    def __init__(self, service):
        self._service = service

    @classmethod
    def from_user_credentials(
        cls,
        instance_path: str | Path,
        credentials_filename: str = "client_secret.json",
        token_filename: str = "token.json",
    ):
        """Build a service from user-created desktop OAuth files on explicit use."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as error:
            raise SheetsAdapterError(
                "缺少 Google API 依賴，請依 README 安裝 requirements.txt"
            ) from error

        instance_dir = Path(instance_path)
        credentials_path = instance_dir / credentials_filename
        token_path = instance_dir / token_filename
        if not credentials_path.is_file():
            raise SheetsAdapterError(
                f"找不到使用者 OAuth 憑證：{credentials_path}；下載後必須將 JSON 重新命名為 "
                "client_secret.json，再放入 instance/。"
            )

        credentials = None
        if token_path.is_file():
            credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if credentials is None or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
                credentials = flow.run_local_server(port=0)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(credentials.to_json(), encoding="utf-8")

        service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        return cls(service)

    def read_structure(
        self, sheet_url: str, worksheet_id: str | None = None
    ) -> SpreadsheetStructure:
        spreadsheet_id = self._parse_url(sheet_url)
        selected_worksheet_id = str(worksheet_id) if worksheet_id is not None else None
        if selected_worksheet_id is None:
            response = self._get_structure(spreadsheet_id)
        else:
            metadata = self._get_sheet_metadata(spreadsheet_id)
            selected_title = next(
                (
                    str(sheet.get("properties", {}).get("title", ""))
                    for sheet in metadata.get("sheets", [])
                    if str(sheet.get("properties", {}).get("sheetId"))
                    == selected_worksheet_id
                ),
                None,
            )
            if selected_title is None:
                raise SheetsAdapterError(
                    f"找不到匯入時記錄的工作表 worksheet_id={selected_worksheet_id}"
                )
            response = self._get_structure(
                spreadsheet_id,
                ranges=[self._quote_sheet_name(selected_title)],
            )

        worksheets = []
        for sheet in response.get("sheets", []):
            properties = sheet.get("properties", {})
            sheet_id = properties.get("sheetId")
            if selected_worksheet_id is not None and str(sheet_id) != selected_worksheet_id:
                continue
            worksheets.append(
                WorksheetGrid(
                    worksheet_id=str(sheet_id),
                    title=str(properties.get("title", "")),
                    values=self._grid_values(sheet.get("data", [])),
                    merged_ranges=[
                        MergedRange(
                            start_row_index=merge["startRowIndex"],
                            end_row_index=merge["endRowIndex"],
                            start_column_index=merge["startColumnIndex"],
                            end_column_index=merge["endColumnIndex"],
                        )
                        for merge in sheet.get("merges", [])
                    ],
                )
            )

        if selected_worksheet_id is not None and not worksheets:
            raise SheetsAdapterError(
                f"Google Sheet 回應中找不到已選工作表 worksheet_id={selected_worksheet_id}"
            )
        return SpreadsheetStructure(
            spreadsheet_id=str(response.get("spreadsheetId", spreadsheet_id)),
            worksheets=worksheets,
        )

    def write_answers(self, spreadsheet_id: str, updates: Sequence[CellUpdate]) -> None:
        requests = []
        for update in updates:
            try:
                worksheet_id = int(update.worksheet_id)
            except (TypeError, ValueError) as error:
                raise SheetsAdapterError(
                    f"工作表識別碼不是 Google Sheets 數字 ID：{update.worksheet_id}"
                ) from error
            requests.append(
                {
                    "updateCells": {
                        "range": {
                            "sheetId": worksheet_id,
                            "startRowIndex": update.row_index,
                            "endRowIndex": update.row_index + 1,
                            "startColumnIndex": update.column_index,
                            "endColumnIndex": update.column_index + 1,
                        },
                        "rows": [
                            {
                                "values": [
                                    {"userEnteredValue": {"stringValue": str(update.value)}}
                                ]
                            }
                        ],
                        "fields": "userEnteredValue",
                    }
                }
            )
        if not requests:
            return
        try:
            (
                self._service.spreadsheets()
                .batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={"requests": requests},
                )
                .execute()
            )
        except Exception as error:
            raise SheetsAdapterError(f"Google Sheet 寫入失敗：{error}") from error

    @staticmethod
    def _parse_url(sheet_url: str) -> str:
        if not isinstance(sheet_url, str):
            raise SheetsAdapterError("Google Sheet 連結必須是文字")
        parsed = urlparse(sheet_url.strip())
        match = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)(?:/|$)", parsed.path)
        if parsed.scheme not in {"http", "https"} or not match:
            raise SheetsAdapterError("無法從連結識別 Google Sheet ID")
        return match.group(1)

    @staticmethod
    def _grid_values(grid_data: list[dict]) -> list[list[str | None]]:
        rows: list[list[str | None]] = []
        for block in grid_data:
            start_row = int(block.get("startRow", 0))
            start_column = int(block.get("startColumn", 0))
            for row_offset, row_data in enumerate(block.get("rowData", [])):
                row_index = start_row + row_offset
                while len(rows) <= row_index:
                    rows.append([])
                row = rows[row_index]
                for column_offset, cell_data in enumerate(row_data.get("values", [])):
                    column_index = start_column + column_offset
                    while len(row) <= column_index:
                        row.append(None)
                    row[column_index] = cell_data.get("formattedValue")
        return rows

    def _get_sheet_metadata(self, spreadsheet_id: str) -> dict:
        try:
            return (
                self._service.spreadsheets()
                .get(
                    spreadsheetId=spreadsheet_id,
                    includeGridData=False,
                    fields=SHEET_METADATA_FIELDS,
                )
                .execute()
            )
        except Exception as error:
            raise SheetsAdapterError(f"Google Sheet 工作表清單讀取失敗：{error}") from error

    def _get_structure(self, spreadsheet_id: str, ranges: list[str] | None = None) -> dict:
        try:
            arguments = {
                "spreadsheetId": spreadsheet_id,
                "includeGridData": True,
                "fields": GRID_FIELDS,
            }
            if ranges is not None:
                arguments["ranges"] = ranges
            return self._service.spreadsheets().get(**arguments).execute()
        except Exception as error:
            raise SheetsAdapterError(f"Google Sheet 讀取失敗：{error}") from error

    @staticmethod
    def _quote_sheet_name(title: str) -> str:
        return "'" + title.replace("'", "''") + "'"
