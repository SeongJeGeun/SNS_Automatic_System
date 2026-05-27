# 🧠 마인드팩토리 무인화 공장 시스템 운영 가이드

본 가이드는 마인드팩토리(MindFactory) SNS 자동 제작 및 업로드 파이프라인의 안전한 지속 실행과 예외 처리를 위한 시스템 인프라 관리 백서입니다.

---

## 📂 프로젝트 구조
- `insight_core.json`: 카드뉴스 생성 시 준수해야 할 전역 디자인 및 기획 규칙 정의
- `script.json`: 1단계 트렌드 분석 및 카피라이팅 결과 스크립트 (JSON)
- `page1.png` ~ `page5.png`: 최종 생성 및 텍스트 합성 완료된 인스타그램 카드뉴스 이미지 파일들 (1080x1080)
- `upload_carousel.py`: 인스타그램 공식 API 기반의 5장 슬라이드 게시물 자동 업로더
- `daily_report.json`: 일일 콘텐츠 발행 및 API 상태 로그 누적 보관 대시보드 데이터

---

## 1. 구글 드라이브 백업 연동 가이드

업로드가 완료된 로컬 카드뉴스 이미지 파일을 구글 드라이브 클라우드로 안전하게 이관하여 무제한 보관하는 시스템 연동 코드 및 가이드입니다.

### 🛠️ 준비사항
1. **Google Cloud Console**에서 프로젝트 생성 및 **Google Drive API** 활성화
2. **서비스 계정(Service Account)** 생성 및 JSON 키 파일 다운로드 (키 파일명: `google_creds.json`으로 워크스페이스에 저장)
3. 대상 구글 드라이브 폴더 생성 후, 서비스 계정 이메일 주소(`xxx@xxx.iam.gserviceaccount.com`)에 해당 폴더의 **편집자 권한** 부여

### 💻 설치 패키지
```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### 📝 자동 백업 파이썬 코드 예시 (`backup_to_drive.py`)
```python
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials

# 구글 드라이브 API 범위 설정
SCOPES = ['https://www.googleapis.com/auth/drive']
KEY_FILE_PATH = 'google_creds.json'  # 서비스 계정 키 파일 경로
PARENT_FOLDER_ID = 'YOUR_GOOGLE_DRIVE_FOLDER_ID'  # 백업 대상 드라이브 폴더 ID

def get_drive_service():
    creds = Credentials.from_service_account_file(KEY_FILE_PATH, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def upload_file_to_drive(file_path):
    if not os.path.exists(file_path):
        print(f"[Error] 백업 대상 파일이 존재하지 않습니다: {file_path}")
        return None

    service = get_drive_service()
    file_name = os.path.basename(file_path)
    
    file_metadata = {
        'name': file_name,
        'parents': [PARENT_FOLDER_ID]
    }
    media = MediaFileUpload(file_path, mimetype='image/png')
    
    try:
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        print(f"✅ 구글 드라이브 백업 완료: {file_name} (File ID: {file.get('id')})")
        return file.get('id')
    except Exception as e:
        print(f"❌ 구글 드라이브 업로드 실패 ({file_name}): {e}")
        return None

if __name__ == '__main__':
    # 업로드 성공 후 로컬 이미지 백업 예시
    for i in range(1, 6):
        upload_file_to_drive(f"page{i}.png")
```

---

## 2. 자기치유 시스템 백서 (Runbook)

무인 자동화 공장이 중단되지 않고 예외 발생 시 스스로 회복하거나 관리자에게 긴급 대응을 알리는 지침서입니다.

### 🚨 트러블슈팅 및 비상 대처 매뉴얼

#### 1) Meta API 토큰 만료 (OAuth Exception - Error 190)
*   **증상**: `Error 190: Access token has expired` 메시지와 함께 업로드 스크립트 중단.
*   **원인**: 단기 토큰(2시간) 또는 장기 토큰(60일) 만료.
*   **자가 치유 및 조치 방법**:
    1. **단기 토큰 리프레시**: 관리자가 직접 [Meta Graph API 탐색기](https://developers.facebook.com/tools/explorer/)에서 새로 발급받아야 합니다.
    2. **장기 토큰으로의 자동 전환**: 아래 엔드포인트를 통해 장기 토큰(60일 만료)을 생성해 등록해 둡니다.
       ```bash
       curl -X GET "https://graph.facebook.com/v19.0/oauth/access_token?grant_type=fb_exchange_token&client_id={app-id}&client_secret={app-secret}&fb_exchange_token={short-lived-token}"
       ```
    3. **자동화 알림**: 스크립트 실행 실패 감지 시 즉시 슬랙/디스코드 웹훅으로 경고를 발송합니다.

#### 2) 이미지 URL 오류 (Invalid URL / Download Failed - Error 100)
*   **증상**: `is_carousel_item` 생성 시 `Invalid URL` 혹은 `Failed to download image` 오류 발생.
*   **원인**: ngrok 주소 만료, Imgur 업로드 실패, 혹은 외부 이미지 호스팅 도메인의 일시적 에러.
*   **자가 치유 및 조치 방법**:
    1. **스마트 재시도 (Backoff)**: `upload_carousel.py` 내부에 `time.sleep` 대기 시간을 2배씩 늘리며 최대 3회 재시도(Exponential Backoff)하는 로직을 구동합니다.
    2. **ngrok 상태 체크**: 로컬 호스팅을 쓸 경우 `curl http://localhost:4040/api/tunnels` 명령을 쉘 스크립트에서 사전 가동하여 ngrok 터널이 유효한지 자동 검증하고, 만료되었을 시 ngrok 서비스를 자동 백그라운드 재시작합니다.

#### 3) 생성 지연 및 업로드 누락 (Timeout)
*   **증상**: 시스템 스케줄 크론은 돌았으나 안티그래비티 이미지 생성 완료가 늦어져 `page1.png` 등이 채 갖춰지기 전에 업로더가 실행됨.
*   **자가 치유 및 조치 방법**:
    1. **Pre-check 파일 검사**: `upload_carousel.py` 실행 직후 1~5장의 로컬 파일이 온전히 존재하는지 검사하고, 부재할 시 **최대 10분 동안 1분 주기로 대기**하며 완성을 기다리는 대기 루프를 활용합니다.

---

### 📲 관리자 긴급 알림 연동 (Slack Webhook)
스크립트 에러 발생 시 관리자 스마트폰으로 즉시 디버깅 정보를 전송하는 데코레이터 예시입니다:

```python
import requests

SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

def send_slack_alert(error_message):
    payload = {
        "text": f"🚨 [MindFactory Alert] 자동 업로드 파이프라인 장애 발생!\n*상세 정보*: `{error_message}`"
    }
    try:
        requests.post(SLACK_WEBHOOK_URL, json=payload)
    except Exception as e:
        print(f"슬랙 알림 발송 실패: {e}")
```
이 런북 및 백업 인프라를 상시 참조하여 24시간 안정적인 시스템 운영을 지속하시기 바랍니다.
