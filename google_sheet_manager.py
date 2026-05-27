import os
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials

class GoogleSheetManager:
    def __init__(self, credentials_path="google_creds.json", sheet_name="MindFactory_SNS_Dashboard", tab_name=None, gspread_client=None):
        self.credentials_path = credentials_path
        self.sheet_name = sheet_name
        self.tab_name = tab_name
        self.client = gspread_client if gspread_client else self._authenticate()
        self.sheet = self._get_or_create_sheet()

    def _authenticate(self):
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # 1. token.json (User Consent Token) 우선 시도
        if os.path.exists("token.json"):
            from google.oauth2.credentials import Credentials
            try:
                creds = Credentials.from_authorized_user_file("token.json", scope)
                return gspread.authorize(creds)
            except Exception as e:
                print(f"[Warning] token.json 기반 구글 시트 인증 실패: {e}")
                
        # 2. google_creds.json (Service Account) 차선 시도
        if os.path.exists(self.credentials_path):
            creds = ServiceAccountCredentials.from_json_keyfile_name(self.credentials_path, scope)
            return gspread.authorize(creds)
            
        print("[Warning] 구글 자격 증명 파일(token.json 또는 google_creds.json)이 존재하지 않아 시뮬레이션 모드로 동작합니다.")
        return None

    def _get_drive_service(self):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = None
        if os.path.exists("token.json"):
            from google.oauth2.credentials import Credentials as UserCredentials
            try:
                creds = UserCredentials.from_authorized_user_file("token.json", scopes)
            except Exception:
                pass
        if not creds and os.path.exists(self.credentials_path):
            from google.oauth2.service_account import Credentials as ServiceCredentials
            try:
                creds = ServiceCredentials.from_service_account_file(self.credentials_path, scopes)
            except Exception:
                pass
                
        if creds:
            from googleapiclient.discovery import build
            return build("drive", "v3", credentials=creds)
        return None

    def _get_or_create_drive_folder(self, drive_service, name, parent_id=None):
        query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
            
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])
        
        if files:
            return files[0]["id"]
            
        file_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder"
        }
        if parent_id:
            file_metadata["parents"] = [parent_id]
            
        folder = drive_service.files().create(body=file_metadata, fields="id").execute()
        return folder.get("id")

    def _get_or_create_sheet(self):
        if not self.client:
            return None
            
        drive_service = self._get_drive_service()
        sh = None
        sh_id = None
        
        if drive_service:
            try:
                system_folder_id = self._get_or_create_drive_folder(drive_service, "SNS_Automatic_System")
                
                # system_folder_id 폴더 내부에서 SHEET_NAME 스프레드시트가 있는지 먼저 검색
                query = f"name = '{self.sheet_name}' and mimeType = 'application/vnd.google-apps.spreadsheet' and '{system_folder_id}' in parents and trashed = false"
                results = drive_service.files().list(q=query, fields="files(id, name)").execute()
                files = results.get("files", [])
                
                if files:
                    sh_id = files[0]["id"]
                    print(f"📁 지정 폴더에서 기존 스프레드시트 로드 완료 (ID: {sh_id})")
                else:
                    # 없으면 system_folder_id 폴더 하위에 직접 생성
                    file_metadata = {
                        "name": self.sheet_name,
                        "mimeType": "application/vnd.google-apps.spreadsheet",
                        "parents": [system_folder_id]
                    }
                    sh_file = drive_service.files().create(body=file_metadata, fields="id").execute()
                    sh_id = sh_file.get("id")
                    print(f"📁 구글 드라이브 내 SNS_Automatic_System 폴더에 스프레드시트 직접 생성 완료 (ID: {sh_id})")
            except Exception as e:
                print(f"[Warning] 드라이브 폴더 내 시트 확인/생성 중 예외 발생: {e}")
                
        if sh_id:
            try:
                sh = self.client.open_by_key(sh_id)
            except Exception as e:
                print(f"[Warning] key를 통한 시트 열기 실패: {e}")
                
        if not sh:
            try:
                sh = self.client.open(self.sheet_name)
                # 만약 열었는데 parents에 system_folder_id가 없으면 이동시킨다.
                if drive_service:
                    try:
                        system_folder_id = self._get_or_create_drive_folder(drive_service, "SNS_Automatic_System")
                        file_info = drive_service.files().get(fileId=sh.id, fields="parents").execute()
                        parents = file_info.get("parents", [])
                        if system_folder_id not in parents:
                            print(f"[Info] 발견된 스프레드시트가 SNS_Automatic_System 폴더에 없습니다. 이동합니다.")
                            previous_parents = ",".join(parents)
                            drive_service.files().update(
                                fileId=sh.id,
                                addParents=system_folder_id,
                                removeParents=previous_parents,
                                fields='id, parents'
                            ).execute()
                    except Exception as e:
                        print(f"[Warning] 시트 이동 중 예외: {e}")
            except gspread.exceptions.SpreadsheetNotFound:
                print(f"[Info] '{self.sheet_name}' 스프레드시트가 존재하지 않아 신규 생성합니다.")
                sh = self.client.create(self.sheet_name)
                if drive_service:
                    try:
                        system_folder_id = self._get_or_create_drive_folder(drive_service, "SNS_Automatic_System")
                        file_info = drive_service.files().get(fileId=sh.id, fields="parents").execute()
                        parents = file_info.get("parents", [])
                        previous_parents = ",".join(parents)
                        drive_service.files().update(
                            fileId=sh.id,
                            addParents=system_folder_id,
                            removeParents=previous_parents,
                            fields='id, parents'
                        ).execute()
                    except Exception as e:
                        print(f"[Warning] 생성 후 시트 이동 실패: {e}")

        # tab_name 결정
        if not self.tab_name:
            start_file = "start_date.txt"
            if os.path.exists(start_file):
                with open(start_file, "r") as f:
                    date_str = f.read().strip()
                    start_date = datetime.strptime(date_str, "%Y-%m-%d")
            else:
                start_date = datetime.now()
                with open(start_file, "w") as f:
                    f.write(start_date.strftime("%Y-%m-%d"))
            days_elapsed = (datetime.now() - start_date).days
            month_num = (days_elapsed // 30) + 1
            self.tab_name = f"M{month_num}"
            
        try:
            worksheet = sh.worksheet(self.tab_name)
            print(f"[Info] 구글 시트 활성 탭: {self.tab_name}")
            return worksheet
        except gspread.exceptions.WorksheetNotFound:
            print(f"[Info] 월별 분할 탭 '{self.tab_name}'가 존재하지 않아 새로 추가합니다.")
            worksheet = sh.add_worksheet(title=self.tab_name, rows="1000", cols="20")
            headers = ["날짜", "미디어ID", "타이틀", "본문내용", "조회수", "댓글수", "저장수"]
            worksheet.append_row(headers)
            try:
                default_ws = sh.worksheet("시트1")
                sh.del_worksheet(default_ws)
            except Exception:
                pass
            return worksheet

    def append_upload_row(self, media_id, title, content_text):
        """업로드 성공 시 행 추가"""
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not self.sheet:
            print(f"[Mock Info] 구글 시트에 행 추가 (날짜: {date_str}, MediaID: {media_id}, 타이틀: {title})")
            return
            
        row = [date_str, str(media_id), title, content_text, 0, 0, 0]
        self.sheet.append_row(row)
        print(f"✅ 구글 시트에 업로드 성공 데이터 추가 완료 (MediaID: {media_id})")
        
        # 아카이빙 체크
        self.archive_if_full()

    def archive_if_full(self):
        if not self.sheet:
            return
            
        try:
            all_values = self.sheet.get_all_values()
            if len(all_values) >= 1000:
                active_title = self.sheet.title
                backup_title = f"{active_title}_Backup_{datetime.now().strftime('%Y%m')}"
                
                print(f"⚠️ [아카이빙] '{active_title}' 탭의 행 수가 {len(all_values)}개로 1,000개를 초과했습니다. 백업 탭 '{backup_title}'으로 데이터 이관을 시작합니다.")
                
                sh = self.sheet.spreadsheet
                try:
                    backup_ws = sh.worksheet(backup_title)
                except gspread.exceptions.WorksheetNotFound:
                    backup_ws = sh.add_worksheet(title=backup_title, rows=len(all_values) + 100, cols=len(all_values[0]))
                
                backup_ws.clear()
                backup_ws.update('A1', all_values)
                
                headers = all_values[0]
                self.sheet.clear()
                self.sheet.append_row(headers)
                
                print(f"✅ [아카이빙 완료] 데이터를 '{backup_title}'으로 백업하고, 활성 탭 '{active_title}'을 초기화했습니다.")
        except Exception as e:
            print(f"[Warning] 시트 아카이빙 중 예외 발생: {e}")

    def get_past_24h_media_ids(self):
        """24시간이 경과한 미디어ID와 해당 행 번호(1-based index) 리스트 반환"""
        if not self.sheet:
            # 인증 키가 없는 모의 동작 환경에서는 고정값 예시를 제공하여 실행 흐름 시연 가능하게 함
            print("[Mock Info] 24시간이 경과한 미디어를 탐색합니다 (모의 동작: 1개의 예시 미디어 ID 반환)")
            return [{
                "row_num": 2,
                "media_id": "17841436434753995",
                "title": "규율이 만드는 절대적 자유",
                "impressions": 0,
                "comments": 0,
                "saved": 0
            }]
            
        records = self.sheet.get_all_records()
        past_24h_items = []
        
        for idx, record in enumerate(records, start=2):
            date_val = record.get("날짜")
            media_id = record.get("미디어ID")
            
            if not date_val or not media_id:
                continue
                
            try:
                post_date = datetime.strptime(str(date_val), "%Y-%m-%d %H:%M:%S")
                if datetime.now() - post_date >= timedelta(hours=24):
                    past_24h_items.append({
                        "row_num": idx,
                        "media_id": str(media_id),
                        "title": record.get("타이틀"),
                        "impressions": record.get("조회수", 0),
                        "comments": record.get("댓글수", 0),
                        "saved": record.get("저장수", 0)
                    })
            except Exception as e:
                print(f"[Warning] 날짜 파싱 오류 (행 {idx}): {e}")
                
        return past_24h_items

    def update_cell_value(self, row, col, value):
        """특정 셀 값 업데이트"""
        if not self.sheet:
            print(f"[Mock Info] 구글 시트 업데이트 (행: {row}, 열: {col}, 값: {value})")
            return
        self.sheet.update_cell(row, col, value)

    def get_top_posts(self, limit=3):
        """조회수(impressions) 기준 상위 N개 게시물 반환"""
        if not self.sheet:
            # 모의 동작 환경을 위한 상위 리스트 모의 제공
            return [
                {"타이틀": "규율이 만드는 절대적 자유", "본문내용": "타협 없이 하루를 통제할 때 찾아오는 진짜 성장", "조회수": 1500, "댓글수": 45, "저장수": 320},
                {"타이틀": "동기부여라는 값싼 마약", "본문내용": "감정이 아닌 차가운 시스템으로 스스로를 움직여라", "조회수": 1200, "댓글수": 30, "저장수": 210},
                {"타이틀": "하루 2시간 압도적 몰입", "본문내용": "모든 디지털 소음을 차단하고 목표에만 집중하는 법", "조회수": 950, "댓글수": 12, "저장수": 150}
            ][:limit]
            
        records = self.sheet.get_all_records()
        valid_records = []
        for r in records:
            try:
                r["조회수"] = int(r.get("조회수", 0))
                r["댓글수"] = int(r.get("댓글수", 0))
                r["저장수"] = int(r.get("저장수", 0))
                valid_records.append(r)
            except ValueError:
                continue
                
        sorted_records = sorted(valid_records, key=lambda x: x["조회수"], reverse=True)
        return sorted_records[:limit]

    def get_bottom_posts(self, limit=3):
        """조회수(impressions) 기준 하위 N개 게시물 반환 (성공/실패 피드백용)"""
        if not self.sheet:
            return [
                {"타이틀": "지루한 시간 관리법", "본문내용": "시간을 체계적으로 쪼개서 분 단위로 일정을 관리하는 지루한 팁", "조회수": 100, "댓글수": 0, "저장수": 3},
                {"타이틀": "성공하는 방법 100가지", "본문내용": "남들이 다 아는 뻔한 성공 명언들 나열하기", "조회수": 120, "댓글수": 1, "저장수": 5},
                {"타이틀": "위로가 되는 한마디", "본문내용": "괜찮아 잘하고 있어 식의 가치 없는 무난한 위로글", "조회수": 150, "댓글수": 2, "저장수": 9}
            ][:limit]
            
        records = self.sheet.get_all_records()
        valid_records = []
        for r in records:
            try:
                # 조회수가 기입되어 있고 유효한 경우만
                if r.get("조회수") != "":
                    r["조회수"] = int(r.get("조회수", 0))
                    r["댓글수"] = int(r.get("댓글수", 0))
                    r["저장수"] = int(r.get("저장수", 0))
                    valid_records.append(r)
            except ValueError:
                continue
                
        # 조회수 기준 오름차순 정렬 (낮은 순)
        sorted_records = sorted(valid_records, key=lambda x: x["조회수"])
        return sorted_records[:limit]
