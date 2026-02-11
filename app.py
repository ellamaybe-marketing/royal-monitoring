import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

st.set_page_config(page_title="Debug Mode", layout="wide")

def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

def get_debug_data(keyword, client_id, client_secret):
    if not client_id or not client_secret: return None
    
    # 이번에는 '카페'만 집중적으로 긁어봅니다.
    cat = "cafearticle"
    all_data = []
    
    status_text = st.empty()
    
    # 1페이지(100개)만 긁어서 테스트
    try:
        status_text.text(f"🔍 카페 데이터를 날것으로 가져오는 중...")
        encText = urllib.parse.quote(keyword)
        url = f"https://openapi.naver.com/v1/search/{cat}?query={encText}&display=100&sort=date"
        
        request = urllib.request.Request(url)
        request.add_header("X-Naver-Client-Id", client_id)
        request.add_header("X-Naver-Client-Secret", client_secret)
        
        response = urllib.request.urlopen(request)
        if response.getcode() == 200:
            data = json.loads(response.read().decode('utf-8'))
            items = data['items']
            
            for item in items:
                # 필터링 없이 무조건 다 담기
                item['real_cafe_name'] = item.get('cafename', '이름없음')
                item['clean_title'] = clean_html(item['title'])
                item['clean_desc'] = clean_html(item['description'])
                item['link'] = item['link']
                all_data.append(item)
    except Exception as e:
        st.error(f"Error: {e}")

    status_text.empty()
    return pd.DataFrame(all_data)

# UI
st.title("🔍 카페 데이터 정밀 진단")
st.warning("필터링을 끄고 네이버가 주는 카페 글을 전부 보여줍니다.")

with st.sidebar:
    keyword = st.text_input("검색어", value="로얄캐닌")
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Secret", type="password")
    run_btn = st.button("진단 시작")

if run_btn:
    df = get_debug_data(keyword, client_id, client_secret)
    
    if df is not None and not df.empty:
        st.success(f"총 {len(df)}개의 카페 글이 검색되었습니다!")
        
        # 카페 이름 순위 보여주기
        st.subheader("실제로 검색된 카페 이름들 (Top 10)")
        st.write(df['real_cafe_name'].value_counts().head(10))
        
        st.markdown("---")
        st.subheader("전체 데이터 리스트")
        st.dataframe(df[['real_cafe_name', 'clean_title', 'link']])
    else:
        st.error("검색 결과가 0건입니다. 네이버 '전체 공개' 카페 글이 없는 것 같습니다.")
