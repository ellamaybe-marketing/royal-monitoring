import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

# --------------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------------
st.set_page_config(
    page_title="Community Monitor (고다/냥이네/아반강고/강사모)",
    page_icon="🐾",
    layout="wide"
)

# --------------------------------------------------------------------------------
# 2. 데이터 수집 함수
# --------------------------------------------------------------------------------
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

def get_naver_data_communities(keyword, client_id, client_secret):
    if not client_id or not client_secret:
        return None
    
    categories = ["cafearticle", "blog"]
    all_data = []
    
    today = datetime.datetime.now()
    cutoff_date = today - datetime.timedelta(days=7) # 최근 7일
    
    status_text = st.empty() 
    
    for cat in categories:
        for start_index in range(1, 1000, 100):
            # [수정] try 구문 시작
            try:
                status_text.text(f"🔍 {cat} 데이터를 {start_index}번부터 긁어오는 중...")
                
                encText = urllib.parse.quote(keyword)
                url = f"https://openapi.naver.com/v1/search/{cat}?query={encText}&display=100&start={start_index}&sort=date"
                
                request = urllib.request.Request(url)
                request.add_header("X-Naver-Client-Id", client_id)
                request.add_header("X-Naver-Client-Secret", client_secret)
                
                response = urllib.request.urlopen(request)
                if response.getcode() == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    items = data['items']
                    
                    if not items: break

                    temp_list = []
                    stop_flag = False
                    
                    for item in items:
                        try:
                            p_date = pd.to_datetime(item['postdate'], format='%Y%m%d')
                        except:
                            continue
                            
                        if p_date < cutoff_date:
                            stop_flag = True
                            continue
