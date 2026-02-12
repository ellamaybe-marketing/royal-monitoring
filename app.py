import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import urllib.request
import json
import datetime
import os

# ---------------------------------------------------------
# 1. 한글 폰트 설정 (그래프 깨짐 방지)
# ---------------------------------------------------------
import matplotlib.font_manager as fm

def setup_korean_font():
    # 리눅스(Streamlit Cloud) 경로에 나눔폰트가 있는지 확인
    font_path = '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'
    if os.path.exists(font_path):
        plt.rc('font', family='NanumGothic')
    else:
        # 로컬(Windows/Mac) 환경일 경우
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
def get_naver_search_result(client_id, client_secret, keyword, display=100):
    encText = urllib.parse.quote(keyword)
    # 카페 글 검색 (cafearticle) / 블로그 검색을 원하면 blog로 변경 가능
    url = f"https://openapi.naver.com/v1/search/cafearticle.json?query={encText}&display={display}&sort=date"
    
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)
    
    try:
        response = urllib.request.urlopen(request)
        rescode = response.getcode()
        
        if rescode == 200:
            response_body = response.read()
            return json.loads(response_body.decode('utf-8'))
        else:
            return None
    except Exception as e:
        st.error(f"API 호출 중 오류 발생: {e}")
        return None

# ---------------------------------------------------------
# 3. 메인 화면 구성
# ---------------------------------------------------------
st.set_page_config(page_title="로얄캐닌 모니터링", page_icon="🐶", layout="wide")

st.title("🐶 로얄캐닌(Royal Canin) 바이럴 모니터링")
st.markdown("네이버 카페에서 **'로얄캐닌'** 및 관련 키워드에 대한 최신 글을 실시간으로 추적합니다.")

# 사이드바: API 키 입력
with st.sidebar:
    st.header("⚙️ 설정 (Developers API)")
    
    # 비밀번호처럼 가려서 입력받기
    CLIENT_ID = st.text_input("Client ID", type="default", placeholder="API 아이디 입력")
    CLIENT_SECRET = st.text_input("Client Secret", type="password", placeholder="비밀번호 입력")
    
    st.markdown("---")
    st.markdown("**모니터링 키워드**")
    # 기본값으로 로얄캐닌 설정
    keywords = st.text_area("키워드 (쉼표로 구분)", value="로얄캐닌, 강아지 사료, 고양이 사료")
    
    run_btn = st.button("모니터링 시작 🔍")
    
    st.info("※ API 방식은 정확한 '작성 시간(초)' 대신 '작성 날짜'를 제공합니다.")

# ---------------------------------------------------------
# 4. 실행 로직
# ---------------------------------------------------------
if run_btn:
    if not CLIENT_ID or not CLIENT_SECRET:
        st.error("⚠️ 사이드바에 Client ID와 Secret을 먼저 입력해주세요!")
        st.stop()

    keyword_list = [k.strip() for k in keywords.split(',')]
    all_posts = []

    # 진행바
    progress_bar = st.progress(0)
    
    for i, key in enumerate(keyword_list):
        data = get_naver_search_result(CLIENT_ID, CLIENT_SECRET, key, display=50)
        
        if data and 'items' in data:
            for item in data['items']:
                # HTML 태그 제거
                title = item['title'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"')
                desc = item['description'].replace('<b>', '').replace('</b>', '')
                
                # 날짜 변환 (API는 YYYYMMDD 형식을 줌)
                post_date_str = item['postdate']
                post_date = datetime.datetime.strptime(post_date_str, "%Y%m%d").date()
                
                all_posts.append({
                    "검색어": key,
                    "제목": title,
                    "날짜": post_date,
                    "링크": item['link'],
                    "내용요약": desc
                })
        
        # 진행률 업데이트
        progress_bar.progress((i + 1) / len(keyword_list))
    
    progress_bar.empty()

    # ---------------------------------------------------------
    # 5. 결과 시각화
    # ---------------------------------------------------------
    if all_posts:
        df = pd.DataFrame(all_posts)
        
        # 최신순 정렬
        df = df.sort_values(by="날짜", ascending=False)
        
        # (1) 요약 지표
        today = datetime.datetime.now().date()
        today_posts = df[df['날짜'] == today]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("총 수집된 글", f"{len(df)}건")
        c2.metric("오늘 올라온 글", f"{len(today_posts)}건")
        c3.metric("모니터링 키워드", f"{len(keyword_list)}개")

        st.markdown("---")

        # (2) 그래프: 일자별 언급량 추이 (최근 7일)
        st.subheader("📈 일자별 게시글 추이")
        
        # 날짜별 그룹화
        daily_counts = df['날짜'].value_counts().sort_index()
        
        # 그래프 그리기
        if not daily_counts.empty:
            fig, ax = plt.subplots(figsize=(10, 4))
            sns.barplot(x=daily_counts.index, y=daily_counts.values, palette="Blues_d", ax=ax)
            
            # 그래프 디자인
            ax.set_xticklabels([d.strftime('%m-%d') for d in daily_counts.index]) # 날짜 포맷 MM-DD
            ax.set_ylabel("게시글 수")
            ax.set_title("최근 로얄캐닌 관련 글 발생 현황")
            ax.grid(axis='y', linestyle='--', alpha=0.3)
            
            # 숫자 표시
            for p in ax.patches:
                if p.get_height() > 0:
                    ax.annotate(f'{int(p.get_height())}', 
                                (p.get_x() + p.get_width() / 2., p.get_height()), 
                                ha = 'center', va = 'center', 
                                xytext = (0, 9), 
                                textcoords = 'offset points')
            
            st.pyplot(fig)
        
        # (3) 상세 테이블 (링크 클릭 가능하게 만들기)
        st.subheader("📋 상세 게시글 목록")
        
        # 링크 컬럼을 클릭 가능한 HTML로 변환
        def make_clickable(link):
            return f'<a target="_blank" href="{link}">이동</a>'
        
        df['바로가기'] = df['링크'].apply(make_clickable)
        
        # 화면에 테이블 출력 (HTML 허용)
        st.write(df[['날짜', '검색어', '제목', '내용요약', '바로가기']].to_html(escape=False), unsafe_allow_html=True)
        
    else:
        st.warning("데이터를 가져오지 못했습니다. Client ID/Secret을 확인하거나 검색 결과가 없는지 확인해주세요.")
