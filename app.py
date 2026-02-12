import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import urllib.request
import json
import datetime
import os
import re

# ---------------------------------------------------------
# 1. 한글 폰트 설정
# ---------------------------------------------------------
import matplotlib.font_manager as fm

def setup_korean_font():
    # 리눅스(Streamlit Cloud)
    font_path = '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'
    if os.path.exists(font_path):
        plt.rc('font', family='NanumGothic')
    else:
        # 윈도우/맥
        import platform
        system_name = platform.system()
        if system_name == 'Windows':
            plt.rc('font', family='Malgun Gothic')
        elif system_name == 'Darwin':
            plt.rc('font', family='AppleGothic')
    plt.rcParams['axes.unicode_minus'] = False

setup_korean_font()

# ---------------------------------------------------------
# 2. 네이버 API 호출 함수 (카페/블로그/뉴스 통합)
# ---------------------------------------------------------
def get_naver_search_result(client_id, client_secret, keyword, category, display=50):
    encText = urllib.parse.quote(keyword)
    
    # 카테고리에 따라 URL 변경
    if category == "카페":
        base_url = "https://openapi.naver.com/v1/search/cafearticle.json"
    elif category == "블로그":
        base_url = "https://openapi.naver.com/v1/search/blog.json"
    elif category == "뉴스":
        base_url = "https://openapi.naver.com/v1/search/news.json"
    
    url = f"{base_url}?query={encText}&display={display}&sort=date"
    
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)
    
    try:
        response = urllib.request.urlopen(request)
        if response.getcode() == 200:
            return json.loads(response.read().decode('utf-8'))
        else:
            return None
    except Exception as e:
        return None

# ---------------------------------------------------------
# 3. 메인 화면
# ---------------------------------------------------------
st.set_page_config(page_title="로얄캐닌 모니터링", page_icon="🐶", layout="wide")

st.title("🐶 로얄캐닌 바이럴 모니터링 (API 버전)")
st.markdown("네이버 **카페, 블로그, 뉴스**에서 키워드를 실시간으로 추적합니다.")

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 설정 (Developers API)")
    CLIENT_ID = st.text_input("Client ID", type="default", placeholder="API 아이디")
    CLIENT_SECRET = st.text_input("Client Secret", type="password", placeholder="비밀번호")
    
    st.markdown("---")
    st.header("🔍 검색 옵션")
    # 검색 대상 선택 (핵심 기능)
    CATEGORY = st.radio("검색 대상 선택", ["블로그", "뉴스", "카페"])
    
    keywords = st.text_area("키워드 (쉼표 구분)", value="로얄캐닌, 강아지 사료, 고양이 사료")
    run_btn = st.button("모니터링 시작 🚀")
    
    if CATEGORY == "카페":
        st.warning("⚠️ '카페' API는 네이버 정책상 '작성 날짜'를 제공하지 않아 그래프가 표시되지 않습니다.")

# ---------------------------------------------------------
# 4. 실행 로직
# ---------------------------------------------------------
if run_btn:
    if not CLIENT_ID or not CLIENT_SECRET:
        st.error("사이드바에 Client ID와 Secret을 입력해주세요!")
        st.stop()

    keyword_list = [k.strip() for k in keywords.split(',')]
    all_posts = []

    progress_bar = st.progress(0)
    
    for i, key in enumerate(keyword_list):
        data = get_naver_search_result(CLIENT_ID, CLIENT_SECRET, key, CATEGORY, display=30)
        
        if data and 'items' in data:
            for item in data['items']:
                # 제목/내용 태그 제거
                title = item['title'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"')
                desc = item['description'].replace('<b>', '').replace('</b>', '')
                link = item['link']
                
                # 날짜 처리 (핵심 수정 파트)
                post_date = None
                
                # 1) 블로그: 'postdate' (YYYYMMDD)
                if 'postdate' in item:
                    try:
                        post_date = datetime.datetime.strptime(item['postdate'], "%Y%m%d").date()
                    except: pass
                
                # 2) 뉴스: 'pubDate' (Mon, 12 Feb 2024...)
                elif 'pubDate' in item:
                    try:
                        # 영어 날짜 포맷 변환
                        # 예: "Mon, 12 Feb 2024 16:21:00 +0900"
                        dt_obj = datetime.datetime.strptime(item['pubDate'], "%a, %d %b %Y %H:%M:%S %z")
                        post_date = dt_obj.date()
                    except: pass
                
                # 3) 카페: 날짜 정보 없음 (None 유지) -> 오늘 날짜로 가정하거나 비워둠
                
                all_posts.append({
                    "날짜": post_date, # 카페는 None이 됨
                    "검색어": key,
                    "제목": title,
                    "내용요약": desc,
                    "링크": link
                })
        
        progress_bar.progress((i + 1) / len(keyword_list))
    progress_bar.empty()

    # ---------------------------------------------------------
    # 5. 결과 시각화
    # ---------------------------------------------------------
    if all_posts:
        df = pd.DataFrame(all_posts)
        
        # 날짜가 있는 데이터만 분리 (블로그/뉴스용)
        df_with_date = df.dropna(subset=['날짜'])
        
        # (1) 요약 정보
        c1, c2, c3 = st.columns(3)
        c1.metric("총 검색 결과", f"{len(df)}건")
        
        if not df_with_date.empty:
            today = datetime.datetime.now().date()
            today_count = len(df_with_date[df_with_date['날짜'] == today])
            c2.metric("오늘 작성된 글", f"{today_count}건")
        else:
            c2.metric("오늘 작성된 글", "집계 불가 (카페)")
            
        c3.metric("검색 키워드", f"{len(keyword_list)}개")

        st.markdown("---")

        # (2) 그래프 (날짜 데이터가 있을 때만 그림)
        if not df_with_date.empty:
            st.subheader(f"📈 {CATEGORY} 일자별 언급량 추이")
            
            # 날짜별 카운트
            daily_counts = df_with_date['날짜'].value_counts().sort_index()
            
            fig, ax = plt.subplots(figsize=(10, 4))
            sns.barplot(x=daily_counts.index, y=daily_counts.values, palette="Blues_d", ax=ax)
            
            # X축 날짜 포맷
            ax.set_xticklabels([d.strftime('%m-%d') for d in daily_counts.index])
            ax.set_title(f"최근 '{keywords}' 관련 글 발생 현황")
            ax.grid(axis='y', linestyle='--', alpha=0.3)
            
            # 숫자 표시
            for p in ax.patches:
                if p.get_height() > 0:
                    ax.annotate(f'{int(p.get_height())}', 
                                (p.get_x() + p.get_width() / 2., p.get_height()), 
                                ha = 'center', va = 'center', xytext=(0, 5), textcoords='offset points')
            st.pyplot(fig)
        
        elif CATEGORY == "카페":
            st.info("ℹ️ **카페 검색 결과는 네이버 정책상 '날짜 그래프'를 그릴 수 없습니다.** 아래 목록을 확인해주세요.")

        # (3) 상세 리스트
        st.subheader(f"📋 {CATEGORY} 검색 결과 목록")
        
        # 링크 클릭 가능하게 만들기
        def make_clickable(link):
            return f'<a target="_blank" href="{link}">이동</a>'
        df['바로가기'] = df['링크'].apply(make_clickable)
        
        # 날짜가 없으면(카페) 날짜 컬럼 제외하고 보여주기
        if CATEGORY == "카페":
            display_cols = ['검색어', '제목', '내용요약', '바로가기']
        else:
            display_cols = ['날짜', '검색어', '제목', '내용요약', '바로가기']

        st.write(df[display_cols].to_html(escape=False), unsafe_allow_html=True)

    else:
        st.warning("검색 결과가 없습니다. 키워드나 API 키를 확인해주세요.")
