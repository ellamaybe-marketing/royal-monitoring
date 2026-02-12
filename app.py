import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import urllib.request
import json
import datetime
import os

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
# 2. 네이버 API 호출 함수
# ---------------------------------------------------------
def get_naver_search_result(client_id, client_secret, keyword, category, display=100):
    encText = urllib.parse.quote(keyword)
    
    # 카테고리별 URL
    if category == "카페":
        base_url = "https://openapi.naver.com/v1/search/cafearticle.json"
    elif category == "블로그":
        base_url = "https://openapi.naver.com/v1/search/blog.json"
    elif category == "뉴스":
        base_url = "https://openapi.naver.com/v1/search/news.json"
    
    # sort=date (최신순), display=100 (최대 건수)
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
# 3. 메인 화면 UI
# ---------------------------------------------------------
st.set_page_config(page_title="로얄캐닌 모니터링", page_icon="🐶", layout="wide")

st.title("🐶 로얄캐닌 타겟 모니터링 (API)")
st.markdown("특정 키워드에 대한 최신 글을 **최대 100건**까지 가져와서 분석합니다.")

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 기본 설정")
    CLIENT_ID = st.text_input("Client ID", type="default")
    CLIENT_SECRET = st.text_input("Client Secret", type="password")
    
    st.markdown("---")
    st.header("🔍 검색 필터")
    
    # 1. 카테고리 선택
    CATEGORY = st.radio("검색 대상", ["카페", "블로그", "뉴스"])
    
    # 2. 타겟 카페 설정 (핵심 기능)
    target_cafe_input = ""
    if CATEGORY == "카페":
        st.subheader("🎯 타겟 카페 지정 (중요)")
        st.info("여기에 적은 카페의 글만 걸러서 보여줍니다. 비워두면 모든 카페 글을 다 가져옵니다.")
        target_cafe_input = st.text_area(
            "카페 이름 입력 (쉼표로 구분)", 
            value="디젤매니아, 강아지를 사랑하는 모임, 고양이라서 다행이야, 냥이네",
            height=100
        )
    
    # 3. 키워드 설정
    st.markdown("---")
    st.subheader("🔑 키워드")
    keywords = st.text_area("검색어 입력", value="로얄캐닌, 강아지 사료, 고양이 사료")
    
    run_btn = st.button("모니터링 시작 🚀")

# ---------------------------------------------------------
# 4. 실행 로직
# ---------------------------------------------------------
if run_btn:
    if not CLIENT_ID or not CLIENT_SECRET:
        st.error("Client ID와 Secret을 입력해주세요!")
        st.stop()

    keyword_list = [k.strip() for k in keywords.split(',')]
    
    # 타겟 카페 리스트 정리
    target_cafes = []
    if CATEGORY == "카페" and target_cafe_input.strip():
        target_cafes = [c.strip() for c in target_cafe_input.split(',')]
        st.info(f"🎯 다음 {len(target_cafes)}개 카페의 글만 필터링합니다: {', '.join(target_cafes)}")

    all_posts = []
    progress_bar = st.progress(0)
    
    for i, key in enumerate(keyword_list):
        # display=100으로 설정하여 최대치 가져옴
        data = get_naver_search_result(CLIENT_ID, CLIENT_SECRET, key, CATEGORY, display=100)
        
        if data and 'items' in data:
            for item in data['items']:
                # 카페 필터링 로직 (핵심)
                # API 결과에 'cafename'이 있으면 그걸로 필터링
                cafe_name = item.get('cafename', '')
                
                if CATEGORY == "카페" and target_cafes:
                    # 타겟 카페 리스트에 포함되지 않은 카페면 건너뜀 (Pass)
                    # 부분 일치도 허용 (예: '디젤매니아' 입력 시 '디젤매니아 [대한민국...]' 통과)
                    is_target = False
                    for target in target_cafes:
                        if target in cafe_name:
                            is_target = True
                            break
                    if not is_target:
                        continue

                # 데이터 정제
                title = item['title'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"')
                desc = item['description'].replace('<b>', '').replace('</b>', '')
                link = item['link']
                
                # 날짜 처리
                post_date = None
                if 'postdate' in item: # 블로그
                    try: post_date = datetime.datetime.strptime(item['postdate'], "%Y%m%d").date()
                    except: pass
                elif 'pubDate' in item: # 뉴스
                    try: 
                        dt_obj = datetime.datetime.strptime(item['pubDate'], "%a, %d %b %Y %H:%M:%S %z")
                        post_date = dt_obj.date()
                    except: pass
                
                all_posts.append({
                    "날짜": post_date, 
                    "카페명": cafe_name if CATEGORY == "카페" else "-", # 카페명 컬럼 추가
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
        
        # 링크 클릭 가능하게
        def make_clickable(link):
            return f'<a target="_blank" href="{link}">이동</a>'
        df['바로가기'] = df['링크'].apply(make_clickable)

        # (1) 상단 요약
        st.success(f"총 {len(df)}개의 유의미한 글을 찾았습니다.")
        
        # (2) 그래프 (날짜가 있는 블로그/뉴스만)
        df_with_date = df.dropna(subset=['날짜'])
        if not df_with_date.empty:
            st.subheader(f"📈 {CATEGORY} 일자별 언급량 추이")
            daily_counts = df_with_date['날짜'].value_counts().sort_index()
            fig, ax = plt.subplots(figsize=(10, 4))
            sns.barplot(x=daily_counts.index, y=daily_counts.values, palette="Blues_d", ax=ax)
            ax.set_xticklabels([d.strftime('%m-%d') for d in daily_counts.index])
            st.pyplot(fig)
        elif CATEGORY == "카페":
            st.info("※ 카페 API는 날짜별 그래프를 제공하지 않습니다. 아래 목록을 확인하세요.")

        # (3) 상세 리스트 출력
        st.subheader(f"📋 {CATEGORY} 검색 결과 ({len(df)}건)")
        
        # 보여줄 컬럼 선택
        if CATEGORY == "카페":
            cols = ['카페명', '검색어', '제목', '내용요약', '바로가기']
        else:
            cols = ['날짜', '검색어', '제목', '내용요약', '바로가기']
            
        st.write(df[cols].to_html(escape=False), unsafe_allow_html=True)

    else:
        if CATEGORY == "카페" and target_cafes:
            st.warning(f"설정하신 4곳의 카페({', '.join(target_cafes)})에서 최근 100건 내 검색된 '{keywords}' 관련 글이 없습니다.")
            st.info("Tip: 타겟 카페 이름을 정확히 적었는지 확인하거나, 타겟 카페 입력칸을 비우고 전체 검색을 해보세요.")
        else:
            st.warning("검색 결과가 없습니다.")
