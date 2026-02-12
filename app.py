import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import re
import time
import os

# Selenium 관련
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# ---------------------------------------------------------
# 1. 폰트 및 함수 설정
# ---------------------------------------------------------
import matplotlib.font_manager as fm

def setup_korean_font():
    font_path = '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'
    if os.path.exists(font_path):
        plt.rc('font', family='NanumGothic')
    else:
        plt.rc('font', family='Malgun Gothic') # 윈도우용
    plt.rcParams['axes.unicode_minus'] = False

setup_korean_font()

def parse_relative_time(time_text):
    now = datetime.now()
    time_text = str(time_text).strip()
    try:
        if '방금' in time_text: return now
        elif '분 전' in time_text:
            minutes = int(re.search(r'(\d+)분', time_text).group(1))
            return now - timedelta(minutes=minutes)
        elif '시간 전' in time_text:
            hours = int(re.search(r'(\d+)시간', time_text).group(1))
            return now - timedelta(hours=hours)
        elif ':' in time_text:
            hour, minute = map(int, time_text.split(':'))
            return now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return None
    except: return None

# ---------------------------------------------------------
# 2. 크롬 드라이버 설정
# ---------------------------------------------------------
def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # 서버 환경 vs 로컬 환경 자동 구분
    if os.path.exists("/usr/bin/chromium"):
        options.binary_location = "/usr/bin/chromium"
        service = Service("/usr/bin/chromedriver")
    else:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())

    return webdriver.Chrome(service=service, options=options)

# ---------------------------------------------------------
# 3. 사이드바 UI (로그인 정보 입력)
# ---------------------------------------------------------
st.title("🔐 네이버 카페 모니터링 (로그인 버전)")

with st.sidebar:
    st.header("1. 로그인 정보")
    NAVER_ID = st.text_input("네이버 아이디")
    NAVER_PW = st.text_input("네이버 비밀번호", type="password")
    
    st.header("2. 검색 설정")
    KEYWORD = st.text_input("검색 키워드", value="추천")
    CAFE_URL = st.text_input("카페 URL", value="https://cafe.naver.com/dieselmania")
    
    run_btn = st.button("로그인 및 수집 시작 🚀")

# ---------------------------------------------------------
# 4. 실행 로직
# ---------------------------------------------------------
if run_btn:
    if not NAVER_ID or not NAVER_PW:
        st.error("아이디와 비밀번호를 입력해주세요!")
        st.stop()

    status = st.empty()
    status.info("브라우저를 실행 중입니다...")
    
    driver = None
    try:
        driver = get_driver()
        
        # [Step 1] 네이버 로그인 페이지 접속
        status.info("네이버 로그인 페이지 접속 중...")
        driver.get("https://nid.naver.com/nidlogin.login")
        time.sleep(2)
        
        # [Step 2] 아이디/비번 입력 (자바스크립트 사용 - 캡차 우회 시도)
        # 일반 send_keys를 쓰면 캡차가 바로 뜹니다. JS로 값만 넣습니다.
        script = f"document.getElementById('id').value='{NAVER_ID}'; document.getElementById('pw').value='{NAVER_PW}';"
        driver.execute_script(script)
        time.sleep(1)
        
        # 로그인 버튼 클릭
        login_btn = driver.find_element(By.ID, "log.login")
        login_btn.click()
        time.sleep(3) # 로그인 대기
        
        # 로그인 성공 여부 체크 (대략적으로)
        current_url = driver.current_url
        if "nidlogin" in current_url:
            st.error("로그인 실패! (보안 문자가 떴거나 아이디/비번 오류)")
            st.warning("서버 IP가 차단되었거나 캡차가 떴을 수 있습니다. 잠시 후 다시 시도하거나 로컬에서 실행하세요.")
            # 화면 캡쳐해서 보여주기 (디버깅용)
            st.image(driver.get_screenshot_as_png(), caption="현재 화면(로그인 실패 원인 확인)")
            driver.quit()
            st.stop()
        
        status.success("로그인 성공 추정! 카페로 이동합니다...")
        
        # [Step 3] 카페 이동 및 검색
        driver.get(CAFE_URL)
        time.sleep(2)
        
        try:
            # 검색창 찾기
            search_box = driver.find_element(By.NAME, 'query')
            search_box.send_keys(KEYWORD)
            search_box.send_keys(Keys.RETURN)
            time.sleep(2)
        except:
            st.error("카페 접속 후 검색창을 찾지 못했습니다. (URL 확인 필요)")
            st.image(driver.get_screenshot_as_png())
            driver.quit()
            st.stop()

        # [Step 4] iframe 전환 (여기가 문제였던 부분)
        try:
            driver.switch_to.frame("cafe_main")
        except:
            st.error("'cafe_main' 프레임을 찾을 수 없습니다.")
            st.write("원인: 로그인이 풀렸거나, 카페 멤버만 볼 수 있는 페이지일 수 있습니다.")
            st.image(driver.get_screenshot_as_png()) # 화면 보여주기
            driver.quit()
            st.stop()

        # [Step 5] 최신순 정렬
        try:
            status.info("최신순 정렬 버튼을 찾고 있습니다...")
            sort_latest = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '최신순')]"))
            )
            sort_latest.click()
            time.sleep(1)
        except:
            st.warning("최신순 버튼을 못 찾았습니다. (이미 최신순이거나 구조가 다름)")

        # [Step 6] 데이터 수집
        rows = driver.find_elements(By.CSS_SELECTOR, "div.article-board > table > tbody > tr")
        if not rows:
             rows = driver.find_elements(By.XPATH, "//div[contains(@class, 'article-board')]//table//tr")

        post_list = []
        for row in rows:
            try:
                title = row.find_element(By.CSS_SELECTOR, "a.article").text.strip()
                time_text = row.find_element(By.CSS_SELECTOR, "td.td_date").text.strip()
                post_list.append({"제목": title, "시간": time_text})
            except: continue
            
        driver.quit()
        
        # [Step 7] 결과 출력
        if post_list:
            df = pd.DataFrame(post_list)
            df['parsed_time'] = df['시간'].apply(parse_relative_time)
            
            # 오늘 글 필터링
            today = datetime.now().date()
            df_today = df.dropna(subset=['parsed_time'])
            df_today = df_today[df_today['parsed_time'].dt.date == today]
            
            st.success(f"수집 완료! 총 {len(df)}개 / 오늘 {len(df_today)}개")
            
            # 그래프
            if not df_today.empty:
                df_today['hour'] = df_today['parsed_time'].dt.hour
                hourly_counts = df_today['hour'].value_counts().reindex(range(24), fill_value=0).sort_index()
                
                fig, ax = plt.subplots(figsize=(10, 5))
                sns.barplot(x=hourly_counts.index, y=hourly_counts.values, palette='viridis', ax=ax)
                ax.set_title(f"Today's Trend: {KEYWORD}")
                st.pyplot(fig)
                
                st.dataframe(df_today[['제목', '시간']])
            else:
                st.info("오늘 작성된 글이 없습니다.")
                st.dataframe(df)
        else:
            st.warning("게시글을 찾지 못했습니다.")

    except Exception as e:
        st.error(f"에러 발생: {e}")
        if driver: driver.quit()
