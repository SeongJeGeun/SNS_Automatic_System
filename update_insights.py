from google_sheet_manager import GoogleSheetManager
from instagram_metrics import get_instagram_metrics

def main():
    print("="*60)
    print(" Instagram Media Insights Syncer (Real-Time Sync) ")
    print("="*60)
    
    gsm = GoogleSheetManager()
    
    # 1. 시트 연동 검사 및 레코드 로드
    if not gsm.sheet:
        print("[Mock Info] 구글 시트 연동 키(google_creds.json)가 발견되지 않아 모의 수치 업데이트를 가동합니다.")
        # 모의 동작 시연 데이터 업데이트
        impressions, comments, saved = 2500, 85, 412
        print(f"-> 수집 결과 (모의) -> 조회수: {impressions}, 댓글수: {comments}, 저장수: {saved}")
        gsm.update_cell_value(2, 5, impressions)
        gsm.update_cell_value(2, 6, comments)
        gsm.update_cell_value(2, 7, saved)
        return
        
    records = gsm.sheet.get_all_records()
    print(f"[Info] 구글 시트에서 총 {len(records)}개의 기록을 탐색하여 최신 지표로 동기화합니다.")
    
    # 2행부터 루프 (헤더는 1행)
    for idx, record in enumerate(records, start=2):
        media_id = record.get("미디어ID")
        title = record.get("타이틀")
        
        if not media_id:
            continue
            
        print(f"\n-> 최신 지표 수집 중: {title} (ID: {media_id})")
        impressions, comments, saved = get_instagram_metrics(media_id)
        
        # API 오류 등으로 0이 찍히는 경우 갱신하지 않고 스킵 (기존 값 보존 목적)
        if impressions == 0 and comments == 0 and saved == 0:
            print("   [Warning] API 호출 결과가 모두 0이므로 기존 데이터를 보존하기 위해 건너뜁니다.")
            continue
            
        print(f"   수집 성공 -> 조회수: {impressions}, 댓글수: {comments}, 저장수: {saved}")
        
        # E열 = 5 (조회수), F열 = 6 (댓글수), G열 = 7 (저장수)
        try:
            gsm.update_cell_value(idx, 5, impressions)
            gsm.update_cell_value(idx, 6, comments)
            gsm.update_cell_value(idx, 7, saved)
            print(f"   행 {idx} 구글 시트 반영 완료.")
        except Exception as e:
            print(f"   [Error] 행 {idx} 구글 시트 업데이트 중 오류 발생: {e}")
            
    print("\n🎉 모든 활성 피드의 최신 인사이트 수치 동기화 완료!")

if __name__ == "__main__":
    main()
