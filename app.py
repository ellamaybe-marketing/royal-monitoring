import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

# --------------------------------------------------------------------------------
# 설정 및 API 함수
# --------------------------------------------------------------------------------
st.set_page_config(page_title="🚨 Real-Time Monitor", page_icon="⚡", layout="wide")

def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

def get_real_naver_data(keyword, client_id, client_secret):
    if not client_id or not client_secret:
        return None
    
    # 검색할 카테고리: 블로그(blog) + 카페(cafearticle)
    categories = ["blog", "cafearticle"]
    all_data = []
    
    for cat in categories:
        try:
            encText = urllib.parse.quote(keyword)
            # display=50 (각 50개씩 총 100개), sort=date (최신순)
            url = f"https://openapi.naver.com/v1/search/{cat}?query={encText}&display=50&sort=date"
            
            request = urllib.request.Request(url)
            request.add_header("X-Naver-Client-Id", client_id)
            request.add_header("X-Naver-Client-Secret", client_secret)
            
            response = urllib.request.urlopen(request)
            if response.getcode() == 200:
                data = json.loads(response.read().decode('utf-8'))
                for item in data['items']:
                    item['source'] = "네이버 블로그" if cat == "blog" else "네이버 카페"
                    all_data.append(item)
        except Exception as e:
            st.error(f"Error fetching {cat}: {e}")
            
    if not all_data:
        return pd.DataFrame()

    # 데이터 프레임 변환 및 정제
    df = pd.DataFrame(all_data)
    df['title'] = df['title'].apply(clean_html)
    df['description'] = df['description'].apply(clean_html)
    
    # 날짜 처리 (블로그/카페 날짜 포맷 통일)
    df['postdate'] = pd.to_datetime(df['postdate'], format='%Y%m%d', errors='coerce')
    
    # 위험도 분석 (키워드 기반 자동 분류)
    risk_keywords = ['구더기', '벌레', '이물질', '식약처', '신고', '환불', '배신', '실망', '토해']
    
    def check_risk(text):
        for k in risk_keywords:
            if k in text:
                return "🚨 심각/주의"
        return "일반"
        
    df['risk_level'] = df['description'].apply(check_risk)
    
    # 최신순 정렬
    df = df.sort_values(by='postdate', ascending=False)
    
    return df[['postdate', 'source', 'title', 'description', 'risk_level', 'link']]

# --------------------------------------------------------------------------------
# 메인 화면 UI
# --------------------------------------------------------------------------------
with st.sidebar:
    st.header("설정 (Settings)")
    keyword = st.text_input("검색 키워드", value="로얄캐닌 이물질")
    
    st.markdown("---")
    st.info("👇 아까 발급받은 네이버 키를 여기에 넣으세요!")
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Client Secret", type="password")
    
    run_btn = st.button("실시간 데이터 가져오기")

st.title(f"⚡ '{keyword}' 실시간 검색 결과")

if run_btn:
    if not client_id or not client_secret:
        st.warning("⚠️ 사이드바에 'Client ID'와 'Secret'을 입력해야 실제 데이터를 가져올 수 있어요!")
        st.markdown("가짜 데이터(시뮬레이션)가 아닌 **실제 네이버 검색 결과**를 보려면 키가 필요합니다.")
    else:
        with st.spinner("네이버 블로그와 카페를 뒤지는 중입니다..."):
            df = get_real_naver_data(keyword, client_id, client_secret)
            
            if df is not None and not df.empty:
                st.success(f"총 {len(df)}건의 최신 데이터를 가져왔습니다.")
                
                # 1. 위험/일반 필터
                tab1, tab2 = st.tabs(["🚨 이슈 모니터링", "📝 전체 글 보기"])
                
                with tab1:
                    risk_df = df[df['risk_level'] == "🚨 심각/주의"]
                    if risk_df.empty:
                        st.success("현재 검색 결과 상위 100건 중 감지된 위험 키워드가 없습니다.")
                    else:
                        st.error(f"위험 키워드 포함 게시글: {len(risk_df)}건")
                        for i, row in risk_df.iterrows():
                            with st.container():
                                st.markdown(f"**[{row['source']}] {row['title']}**")
                                st.caption(f"{row['postdate'].date()} | {row['description']}")
                                st.markdown(f"[원문 보기]({row['link']})")
                                st.divider()
                
                with tab2:
                    st.dataframe(
                        df,
                        column_config={
                            "link": st.column_config.LinkColumn("링크"),
                            "postdate": st.column_config.DateColumn("날짜")
                        },
                        use_container_width=True
                    )
            else:
                st.write("검색 결과가 없습니다.")
else:
    st.info("👈 왼쪽 사이드바에 API 키를 넣고 버튼을 눌러주세요.")
