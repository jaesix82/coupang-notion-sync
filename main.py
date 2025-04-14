import os
import dropbox
import pandas as pd
from dotenv import load_dotenv
from io import BytesIO
import re
import requests
import time

load_dotenv()

DROPBOX_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN")
DROPBOX_FOLDER = os.getenv("DROPBOX_FOLDER_PATH")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
ADS_DB_ID = os.getenv("ADS_DB_ID")
SALES_DB_ID = os.getenv("SALES_DB_ID")

dbx = dropbox.Dropbox(DROPBOX_TOKEN)
headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def get_latest_file():
    entries = dbx.files_list_folder(DROPBOX_FOLDER).entries
    excel_files = [f for f in entries if f.name.endswith(".xlsx")]
    if not excel_files:
        return None
    latest = sorted(excel_files, key=lambda x: x.server_modified, reverse=True)[0]
    return latest.name

def load_excel_from_dropbox(filename):
    _, res = dbx.files_download(f"{DROPBOX_FOLDER}/{filename}")
    df = pd.read_excel(BytesIO(res.content))
    date_match = re.search(r"(\\d{8})", filename)
    if date_match:
        df["날짜"] = date_match.group(1)
    return df

def send_to_notion(df, db_type="ads"):
    db_id = ADS_DB_ID if db_type == "ads" else SALES_DB_ID
    for _, row in df.iterrows():
        props = {
            "옵션 ID": {"rich_text": [{"text": {"content": str(row.get("옵션 ID", ""))}}]},
            "날짜": {"date": {"start": str(row.get("날짜", ""))}}
        }

        if db_type == "ads":
            props["광고비"] = {"number": float(row.get("총 광고비용", 0))}
            props["클릭수"] = {"number": int(row.get("클릭수", 0))}
            props["노출수"] = {"number": int(row.get("노출수", 0))}
        else:
            props["순 판매 금액"] = {"number": float(row.get("순 판매 금액(전체 거래 금액 - 취소 금액)", 0))}

        r = requests.post("https://api.notion.com/v1/pages", headers=headers, json={
            "parent": {"database_id": db_id},
            "properties": props
        })
        if r.status_code != 200:
            print("❌", r.text)
        else:
            print("✅ 업로드:", row.get("옵션 ID"))

def main():
    filename = get_latest_file()
    if not filename:
        print("📂 새 엑셀 파일 없음.")
        return
    df = load_excel_from_dropbox(filename)
    if "총 광고비용" in df.columns:
        send_to_notion(df, db_type="ads")
    else:
        send_to_notion(df, db_type="sales")

# Render용 루프 (10분마다 실행)
if __name__ == "__main__":
    while True:
        main()
        time.sleep(600)
