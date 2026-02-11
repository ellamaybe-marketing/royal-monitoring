import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

# 1. 페이지 설정
st.set_page_config(
    page_title="Royal Canin Final Monitor",
    page_icon="📅",
    layout="wide"
)

# 2. HTML 태그 제거 함수
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

# 3. 데이터 수집 함수 (날짜 정확도 개선)
def get_naver_data_final(keyword, client_id, client_secret):
    if not client_id or not client_secret:
        return None, []
    
    categories = ["blog", "cafearticle"]
    all_data = []
    log_messages = []
    
    status_area = st.empty()
    
    for cat in categories:
        cat_name = "블로그" if cat == "blog" else "카페"
        
        # 5페이지(500개) 탐색
        for start_index in range(1, 500, 100):
            try:
                status_area.info(f"🏃‍♂️ {cat_name} {start_index}번째 글 분석 중...")
                
                encText = urllib.parse.quote(keyword)
                # 날짜순 정렬 (sort=date)
                url = f"https://openapi.naver.com/v1/search/{cat}?query={encText}&display=100&start={start_index}&sort=date"
                
                request = urllib.request.Request(url)
                request.add_header("X-Naver-Client-Id", client_id)
                request.add_header("X-Naver-Client-Secret", client_secret)
                
                response = urllib.request.urlopen(request)
                
                if response.getcode() == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    items = data['items']
                    
                    if not items:
                        break

                    for item in items:
                        # [핵심 수정] 날짜 땜빵 로직 삭제 -> 원본 날짜 우선 사용
                        raw_date = item.get('postdate', '') # YYYYMMDD 문자열
                        
                        try:
                            if raw_date:
                                p_date = pd.to_datetime(raw_date, format='%Y%m%d')
                            else:
                                # 날짜가 아예 없으면 맨 뒤로 보내기 위해 아주 옛날 날짜 부여 (절대 오늘 날짜 X)
                                p_date = pd.to_datetime('1900-01-01')
                        except:
                            # 변환 실패 시에도 오늘 날짜로 덮어쓰지 않음
                            p_date = pd.to_datetime('1900-01-01')
                        
                        # 카페 이름 처리
                        raw_name = item.get('cafename', '')
                        
                        if cat == "blog":
                            source_label = "네이버 블로그"
                        else:
                            # 이름 매칭 (요청하신 대로)
                            if "고양이라서 다행이야" in raw_name or "고다" in raw_name: source_label = "고양이라서 다행이야"
                            elif "강사모" in raw_name: source_label = "강사모"
                            elif "아반강고" in raw_name: source_label = "아반강고"
                            elif "냥이네" in raw_name: source_label = "냥이네"
                            else: source_label = f"기타 카페 ({raw_name})"
                        
                        item['source'] = source_label
                        item['clean_title'] = clean_html(item['title'])
                        item['clean_desc'] = clean_html(item['description'])
                        item['postdate_dt'] = p_date
                        all_data.append(item)
                else:
                    log_messages.append(f"❌ {cat_name} API 호출
