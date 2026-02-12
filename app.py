import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import urllib.request
import json
import datetime
import os
import time

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
# 2. 네이버 API 호출 함수 (페이지네이션 추가)
# ---------------------------------------------------------
def get_naver_search_result(client_id, client_secret, keyword, category, display=100, start=1):
    encText = urllib.parse.quote(keyword)
    
    if category == "카페":
        base_url = "https://openapi.naver.com/v1/search/cafearticle.json"
    elif category == "블로그":
        base_url = "https://openapi.naver.com/v1/search/blog.json"
    elif category == "뉴스":
        base_url = "https://openapi.naver.com/v1/search/news.json"
    
    # display: 한 번에 가져올 개수 (최대 100)
    # start: 검색 시작 위치 (1, 101, 201...)
    url = f"{base_url}?query={encText}&display={display}&start={start}&sort=date"
    
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

st.title("🐶 로얄캐닌 심층 모니터링 (대량 수집)")
st.markdown("API 한계를 넘어, **더 많은 글(최대 1000개)**을 수집한 뒤 타겟 카페 글을 찾아냅니다.")

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 기본 설정")
    CLIENT_ID = st.text_input("Client ID", type="default")
    CLIENT_SECRET = st.text_input("Client Secret", type="password")
    
    st.markdown("---")
    st.header("🔍 검색 필터")
    
    CATEGORY = st.radio("검색 대상", ["카페", "블로그", "뉴스"])
    
    # [핵심] 수집량 조절 슬라이더
    st.subheader("📊 수집량 설정 (Deep Search)")
    search_depth = st.slider(
        "검색할 게시글 수 (많을수록 느림)", 
        min_value=100, 
        max_value=1000, 
        value=300, 
        step=100,
        help="API는 한 번에 100개까지만 줍니다. 300으로 설정하면 3번 호출해서 300개를 긁어온 뒤 필터링합니다."
    )

    target_cafes_list = []
    if CATEGORY == "카페":
        st.subheader("🎯 타겟 카페 지정")
        st.info("아래 입력한 카페의 글만 남기고 나머지는 숨깁니다.")
        
        # ★★★ 요청하신대로 카페 리스트 수정 완료 ★★★
        target_cafe_input = st.text_area(
            "카페 이름 (쉼표 구분)", 
            value="강아지를 사랑하는 모임, 냥이네, 고양이라서 다행이야, 아픈 반려 강아지와 고양이를 위한 힐링 카페"
        )
        if target_cafe_input.strip():
            target_cafes_list = [c.strip() for c in target_cafe_input.split(',')]

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
    
    all_posts = []
    
    # 진행바
    total_steps = len(keyword_list) * (search_depth // 100)
    progress_bar = st.progress(0)
    step_count = 0

    st.info(f"키워드당 최신 글 {search_depth}개를 수집하여 분석합니다...")

    for key in keyword_list:
        # 설정한 깊이만큼 반복 호출 (예: 300개면 3번 루프)
        for start_idx in range(1, search_depth + 1, 100):
            
            # API 호출 (한 번에 100개씩)
            data = get_naver_search_result(CLIENT_ID, CLIENT_SECRET, key, CATEGORY, display=100, start=start_idx)
            
            if data and 'items' in data:
                for item in data['items']:
                    cafe_name = item.get('cafename', '')
                    
                    # 카페 필터링
                    if CATEGORY == "카페" and target_cafes_list:
                        is_target = False
                        for target in target_cafes_list:
                            # 카페 이름에 포함되어 있으면 통과 (부분 일치 허용)
                            if target.strip() in cafe_name:
                                is_target = True
                                break
                        if not is_target:
                            continue # 타겟 아니면 버림

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
                        "카페명": cafe_name if CATEGORY == "카페" else "-",
                        "검색어": key,
                        "제목": title,
                        "내용요약": desc,
                        "링크": link
                    })
            
            # 진행률 업데이트
            step_count += 1
            progress_bar.progress(min(step_count / total_steps, 1.0))
            time.sleep(0.1) # API 과부하 방지

    progress_bar.empty()

    # ---------------------------------------------------------
    # 5. 결과 시각화
    # ---------------------------------------------------------
    if all_posts:
        df = pd.DataFrame(all_posts)
        
        # 중복 제거 (여러 페이지 긁다보면 중복될 수 있음)
        df = df.drop_duplicates(subset=['링크'])
        
        # 링크 클릭 처리
        def make_clickable(link):
            return f'<a target="_blank" href="{link}">이동</a>'
        df['바로가기'] = df['링크'].apply(make_clickable)

        # (1) 요약
        st.success(f"필터링 후 남은 게시글: 총 {len(df)}건")
        
        if CATEGORY == "카페" and target_cafes_list:
            st.caption(f"검색 범위: 키워드당 최근 {search_depth}개 글 분석 → '{', '.join(target_cafes_list)}' 카페 글만 추출")

        # (2) 그래프 (날짜 정보 있는 경우만)
        df_with_date = df.dropna(subset=['날짜'])
        if not df_with_date.empty:
            st.subheader(f"📈 {CATEGORY} 일자별 언급량 추이")
            daily_counts = df_with_date['날짜'].value_counts().sort_index()
            fig, ax = plt.subplots(figsize=(10, 4))
            sns.barplot(x=daily_counts.index, y=daily_counts.values, palette="Blues_d", ax=ax)
            ax.set_xticklabels([d.strftime('%m-%d') for d in daily_counts.index])
            st.pyplot(fig)
        
        # (3) 상세 리스트
        st.subheader(f"📋 {CATEGORY} 검색 결과")
        
        if CATEGORY == "카페":
            cols = ['카페명', '검색어', '제목', '내용요약', '바로가기']
        else:
            cols = ['날짜', '검색어', '제목', '내용요약', '바로가기']
            
        st.write(df[cols].to_html(escape=False), unsafe_allow_html=True)

    else:
        st.warning("조건에 맞는 게시글을 찾지 못했습니다.")
        if CATEGORY == "카페" and target_cafes_list:
             st.info(f"팁: '{search_depth}개'의 최신 글 중에는 타겟 카페 글이 없었습니다. 수집량 슬라이더를 더 늘려보세요.")
