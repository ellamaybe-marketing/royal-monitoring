import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import re
import time
import os

# Selenium 관련 임포트
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# ---------------------------------------------------------
# 1. 환경 설정 및 함수 정의
# ---------------------------------------------------------

# 한글 폰트 설정 (Streamlit Cloud의 Linux 환경 고려)
import matplotlib.font_manager as fm

def setup_korean_font():
    # 리눅스(Streamlit Cloud) 경로에 나눔폰트가 있는지 확인
    font_path = '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'
    if os.path.exists(font_path):
        plt.rc('font', family='NanumGothic')
        plt.rcParams['axes.unicode_minus'] = False
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

def parse_relative_time(time_text):
    """ '방금 전', '5분 전', '13:40' 등을 datetime으로 변환 """
    now = datetime.now()
    time_text = str(time_text).strip()
    
    try:
        if '방금' in time_text:
            return now
        elif '분 전' in time_text:
            minutes = int(re.search(r'(\d+)분', time_text).group(1))
            return now - timedelta(minutes=minutes)
        elif '시간 전' in time_text:
            hours = int(re.search(r'(\d+)시간', time_text).group(1))
            return now - timedelta(hours=hours)
        elif ':' in time_text and len(time_text) <= 5: # 13:40
            hour, minute = map(int, time_text.split(':'))
            return now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # 날짜(2023.01.01)는 오늘 데이터가 아니므로 None 반환
        return None
    except:
        return None

# ---------------------------------------------------------
# 2. 크롬 드라이버 설정 (핵심: Streamlit Cloud 대응)
# ---------------------------------------------------------
def get_driver():
    options = Options()
    options.add_argument("--headless")  # 창 없이 실행
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # Streamlit Cloud 환경인지 확인 (서버에는 /usr/bin/chromium이 있음)
    if os.path.exists("/usr/bin/chromium"):
        options.binary_location = "/usr/bin/chromium"
        service = Service("/usr/bin/chromedriver")
    else:
        # 로컬 컴퓨터에서 실행할 경우를 대비한 예외 처리 (자동 설치)
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
        except:
            service = Service() # 기본 경로 시도

    driver = webdriver.Chrome(service=service, options=options)
    return driver

# ---------------------------------------------------------
# 3. 메인 앱 UI
# ---------------------------------------------------------
st.title("📊 카페 키워드 골든타임 분석기")
st.markdown("특정 키워드에 대한 **최신 글**을 수집하여, 오늘 글이 언제 많이 올라왔는지 보여줍니다.")

with st.sidebar:
    st.header("설정")
    KEYWORD = st.text_input("검색 키워드", value="추천")
    CAFE_URL = st.text_input("카페 URL", value="https://cafe.naver.com/dieselmania")
    
    st.info("💡 팁: '최신순' 정렬을 위해 크롤링 시간이 조금 걸릴 수 있습니다.")
    run_btn = st.button("데이터 수집 시작 🚀")

# ---------------------------------------------------------
# 4. 실행 로직
# ---------------------------------------------------------
if run_btn:
    status_text = st.empty() # 진행상황 표시용 텍스트
    status_text.info(f"Step 1: '{KEYWORD}' 검색을 위해 브라우저를 켭니다...")
    
    driver = None
    try:
        driver = get_driver()
        
        # 1. 카페 접속
        driver.get(CAFE_URL)
        time.sleep(1)
        
        # 2. 검색
        try:
            search_box = driver.find_element(By.NAME, 'query')
            search_box.send_keys(KEYWORD)
            search_box.send_keys(Keys.RETURN)
            time.sleep(2)
        except:
            st.error("검색창을 찾을 수 없습니다.")
            driver.quit()
            st.stop()
            
        # 3. iframe 전환
        driver.switch_to.frame("cafe_main")
        status_text.info("Step 2: '최신순' 정렬을 시도합니다...")
        
        # 4. 최신순 클릭 (핵심)
        try:
            sort_latest = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '최신순')]"))
            )
            sort_latest.click()
            time.sleep(2) # 로딩 대기
        except:
            st.warning("⚠️ '최신순' 버튼을 못 찾았습니다. 기본 정렬로 진행합니다.")

        # 5. 데이터 수집
        status_text.info("Step 3: 데이터를 수집하고 있습니다...")
        
        rows = driver.find_elements(By.CSS_SELECTOR, "div.article-board > table > tbody > tr")
        if not rows:
             rows = driver.find_elements(By.XPATH, "//div[contains(@class, 'article-board')]//table//tr")

        post_list = []
        for row in rows:
            try:
                title = row.find_element(By.CSS_SELECTOR, "a.article").text.strip()
                time_text = row.find_element(By.CSS_SELECTOR, "td.td_date").text.strip()
                
                # 작성자 (선택)
                try:
                    author = row.find_element(By.CSS_SELECTOR, "td.td_name a").text.strip()
                except:
                    author = "Unknown"

                post_list.append({
                    "제목": title,
                    "작성자": author,
                    "작성시간(Raw)": time_text
                })
            except:
                continue
        
        driver.quit() # 브라우저 종료
        
        # ---------------------------------------------------------
        # 5. 데이터 가공 및 시각화
        # ---------------------------------------------------------
        if post_list:
            df = pd.DataFrame(post_list)
            
            # 시간 파싱
            df['추정시간'] = df['작성시간(Raw)'].apply(parse_relative_time)
            
            # 오늘 날짜만 필터링
            today = datetime.now().date()
            df_today = df.dropna(subset=['추정시간']) # 날짜 파싱 실패 제거
            df_today = df_today[df_today['추정시간'].dt.date == today]
            
            status_text.success("분석 완료!")
            
            # 상단 지표 (Metrics)
            col1, col2 = st.columns(2)
            col1.metric("총 수집된 글", f"{len(df)}개")
            col2.metric("오늘 작성된 글 (골든타임)", f"{len(df_today)}개")
            
            st.markdown("---")

            # 그래프 그리기 (오늘 데이터가 있을 때만)
            if not df_today.empty:
                df_today['시(Hour)'] = df_today['추정시간'].dt.hour
                
                # 시간대별 카운트 (빈 시간대도 0으로 채우기 위해 로직 추가)
                hourly_counts = df_today['시(Hour)'].value_counts().reindex(range(24), fill_value=0).sort_index()
                
                # Matplotlib 그래프
                fig, ax = plt.subplots(figsize=(10, 5))
                sns.barplot(x=hourly_counts.index, y=hourly_counts.values, palette='viridis', ax=ax)
                
                ax.set_title(f"오늘 '{KEYWORD}' 관련 글 발생 시간대", fontsize=15)
                ax.set_xlabel("시간 (0시 ~ 23시)")
                ax.set_ylabel("게시글 수")
                ax.grid(axis='y', linestyle='--', alpha=0.5)
                
                # 막대 위에 숫자 표시
                for i, v in enumerate(hourly_counts.values):
                    if v > 0:
                        ax.text(i, v, str(v), ha='center', va='bottom', fontsize=10)

                st.pyplot(fig) # 화면에 그래프 출력
                
                st.subheader("📋 오늘 작성된 글 목록")
                st.dataframe(df_today[['추정시간', '제목', '작성자']].sort_values(by='추정시간', ascending=False))
                
            else:
                st.warning("오늘 작성된 글이 아직 없습니다. (과거 글만 수집됨)")
                st.subheader("수집된 전체 목록")
                st.dataframe(df)
                
        else:
            status_text.error("게시글을 하나도 찾지 못했습니다. 카페 URL이나 구조를 확인해주세요.")

    except Exception as e:
        if driver:
            driver.quit()
        st.error(f"오류가 발생했습니다: {e}")
        st.code(str(e)) # 에러 메시지 자세히 보기
