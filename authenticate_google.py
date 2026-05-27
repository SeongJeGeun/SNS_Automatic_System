import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# 스프레드시트 및 드라이브 접근 권한 범위 설정
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def main():
    creds = None
    # token.json 파일이 이미 존재하면 로드
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
    # 유효한 인증 자격이 없으면 인증 처리
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[Info] 만료된 토큰 리프레시 중...")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"[Warning] 토큰 리프레시 실패: {e}, 새로 로그인을 시도합니다.")
                creds = None
                
        if not creds:
            print("[Info] OAuth 2.0 사용자 인증 흐름을 시작합니다...")
            if not os.path.exists('client_secrets.json'):
                print("[Error] 'client_secrets.json' 파일이 존재하지 않습니다.")
                return
                
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secrets.json', SCOPES)
            
            # 로컬 서버를 구동해 브라우저 인증 대기
            # (브라우저가 자동으로 열립니다. 안 열릴 경우 터미널 주소를 복사해 열어주세요.)
            creds = flow.run_local_server(port=0)
            
        # 획득한 크레덴셜 저장
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    print("\n🎉 구글 계정 인증에 최종 성공했습니다! 'token.json' 파일이 발급되었습니다.")

if __name__ == '__main__':
    main()
