import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import re
import time

# Selenium 관련
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ---------------------------------------------------------
# 1. 설정 및 함수
# ---------------------------------------------------------
# 한글 폰트 설정 (리눅스 서버인 Streamlit Cloud 환경 고려)
import platform
if platform.system() == 'Darwin': # Mac
    plt.rc('font', family='AppleGothic')
elif platform.system() == 'Windows': # Windows
    plt.rc('font', family='Malgun Gothic')
else: # Streamlit Cloud (Linux)
    # 리눅스에서는 한글 폰트 설치가 복잡하므로 일단 영문으로 나오게 하거나
    # 나눔고딕 등을 별도로 설치해야 함. 깨짐 방지를 위해 임시로 영문 설정 추천
    plt.rc('font', family='DejaVu Sans') 

plt.rcParams['axes.unicode_minus'] = False 

def parse_relative_time(time_text):
    now = datetime.now()
    time_text = time_text.strip()
    try:
        if '방금' in time_text:
            return now
        elif '분 전' in time_text:
            minutes = int(re.search(r'(\d+)분', time_text).group(1))
            return now - timedelta(minutes=minutes)
        elif '시간 전' in time_text:
            hours = int(re.search(r'(\d+)시간', time_text).group(1))
            return now - timedelta(hours=hours)
        elif ':' in time_text and len(time_text) <= 5: 
            hour, minute = map(int, time_text.split(':'))
            return now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return None
    except:
        return None

# ---------------------------------------------------------
# 2. 메인 앱 화면 구성
# ---------------------------------------------------------
st.title("📊 카페 키워드 모니터링 대시보드")

# 사이드바에서 입력 받기
with st.sidebar:
    st.header("설정")
    KEYWORD = st.text_input("검색 키워드", value="추천")
    CAFE_URL = st.text_input("카페 URL", value="https://cafe.naver.com/dieselmania")
    run_btn = st.button("데이터 수집 시작")

# ---------------------------------------------------------
# 3. 크롤링 로직
# ---------------------------------------------------------
if run_btn:
    with st.spinner(f"'{KEYWORD}' 검색 결과를 수집 중입니다..."):
        try:
            # ★ Streamlit Cloud용 Headless 설정 (창 안띄우기) ★
            options = Options()
            options.add_argument("--headless")  # 화면 없이 실행
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            
            # 크롬 드라이버 설치 및 실행
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            
            driver.get(CAFE_URL)
            time.sleep(1)
            
            # (1) 검색
            try:
                search_box = driver.find_element(By.NAME, 'query')
                search_box.send_keys(KEYWORD)
                search_box.submit() # 엔터키 전송과 동일
            except:
                st.error("검색창을 찾을 수 없습니다.")
            
            time.sleep(2)
            driver.switch_to.frame("cafe_main")

            # (2) 최신순 정렬
            try:
                sort_latest = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '최신순')]"))
                )
                sort_latest.click()
                time.sleep(1)
            except:
                st.warning("최신순 버튼을 찾지 못해 기본 정렬로 수집합니다.")

            # (3) 데이터 수집
            rows = driver.find_elements(By.CSS_SELECTOR, "div.article-board > table > tbody > tr")
            if not rows:
                 rows = driver.find_elements(By.XPATH, "//div[contains(@class, 'article-board')]//table//tr")

            post_list = []
            for row in rows:
                try:
                    title = row.find_element(By.CSS_SELECTOR, "a.article").text.strip()
                    time_text = row.find_element(By.CSS_SELECTOR, "td.td_date").text.strip()
                    post_list.append({"title": title, "time_text": time_text})
                except:
                    continue
            
            driver.quit() # 브라우저 종료

            # ---------------------------------------------------------
            # 4. 결과 시각화
            # ---------------------------------------------------------
            if post_list:
                df = pd.DataFrame(post_list)
                df['parsed_time'] = df['time_text'].apply(parse_relative_time)
                
                # 오늘 작성된 글 필터링
                today = datetime.now().date()
                df_today = df.dropna(subset=['parsed_time'])
                df_today = df_today[df_today['parsed_time'].dt.date == today]

                # 결과 요약 표시
                st.success(f"수집 완료! 총 {len(df)}개 중 오늘 작성된 글은 {len(df_today)}개입니다.")

                if not df_today.empty:
                    # 그래프 그리기
                    df_today['hour'] = df_today['parsed_time'].dt.hour
                    
                    fig, ax = plt.subplots(figsize=(10, 5))
                    sns.countplot(x='hour', data=df_today, palette='viridis', order=range(0, 24), ax=ax)
                    ax.set_title(f"Today's Post Trend ({KEYWORD})") # 한글 깨짐 방지 영문 처리
                    ax.set_xlabel("Hour")
                    ax.set_ylabel("Count")
                    ax.grid(axis='y', linestyle='--', alpha=0.5)

                    # ★★★ Streamlit에 그래프 띄우기 (핵심) ★★★
                    st.pyplot(fig)
                    
                    # 데이터프레임 보여주기
                    st.subheader("상세 데이터")
                    st.dataframe(df_today[['title', 'time_text']])
                else:
                    st.info("오늘 작성된 관련 글이 없습니다.")
            else:
                st.warning("게시글을 찾지 못했습니다.")

        except Exception as e:
            st.error(f"에러가 발생했습니다: {e}")
