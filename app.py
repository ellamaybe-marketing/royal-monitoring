import time
import random
import re
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==========================================
# 1. 설정 및 함수 정의
# ==========================================

# 한글 폰트 설정 (그래프 깨짐 방지)
import platform
if platform.system() == 'Darwin': # Mac
    plt.rc('font', family='AppleGothic')
else: # Windows
    plt.rc('font', family='Malgun Gothic')

plt.rcParams['axes.unicode_minus'] = False # 마이너스 기호 깨짐 방지

def parse_relative_time(time_text):
    """
    네이버 카페의 시간 텍스트('방금 전', '5분 전', '13:40', '2024.02.12')를 
    현재 기준 datetime 객체로 변환합니다.
    """
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
            
        elif ':' in time_text and len(time_text) <= 5: # 13:40 형식 (오늘 작성된 글)
            hour, minute = map(int, time_text.split(':'))
            return now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
        elif '.' in time_text: # 2024.05.21 형식 (과거 글)
            # 날짜만 있는 경우 시간은 00:00으로 처리하거나 제외해야 함
            # 여기서는 그래프 분석을 위해 날짜가 있으면 오늘이 아니므로 None 반환하여 필터링
            # (만약 며칠 간의 추이를 보고 싶다면 datetime으로 변환 사용)
            return None 
            
    except Exception as e:
        return None
        
    return None

# ==========================================
# 2. 크롤러 실행
# ==========================================

# 검색할 키워드 및 카페 정보 설정
KEYWORD = "추천"  # 예시 키워드
CAFE_URL = "https://cafe.naver.com/dieselmania" # 예시: 디젤매니아 (원하는 카페 URL로 변경)

# 브라우저 열기
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized") # 창 최대화
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

try:
    print(f"[{KEYWORD}] 키워드로 검색을 시작합니다...")
    
    # 1. 카페 접속
    driver.get(CAFE_URL)
    time.sleep(2)
    
    # 2. 검색창 찾기 및 검색 (카페마다 상단 검색창 ID가 다를 수 있음, 일반적인 구조 사용)
    # 보통 상단 검색창 name='query' 혹은 id='topLayerQueryInput'
    try:
        search_box = driver.find_element(By.NAME, 'query')
        search_box.send_keys(KEYWORD)
        search_box.send_keys(Keys.RETURN)
    except:
        print("검색창을 찾을 수 없습니다. 수동으로 검색해주세요.")
        time.sleep(10) # 수동 조작 대기

    time.sleep(3)
    
    # 3. iframe 전환 (네이버 카페는 메인 컨텐츠가 iframe 안에 있음)
    driver.switch_to.frame("cafe_main")
    
    # ★★★ [핵심 수정] 최신순 정렬 클릭 ★★★
    # 검색 결과 상단에 '정확도' | '최신순' 탭이 있음.
    try:
        # '최신순' 텍스트를 가진 요소를 찾아 클릭
        sort_latest = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '최신순')]"))
        )
        sort_latest.click()
        print(">> '최신순' 정렬을 클릭했습니다.")
        time.sleep(2) # 로딩 대기
    except:
        print(">> '최신순' 버튼을 찾지 못했습니다 (이미 최신순이거나 구조가 다름)")

    # 4. 게시글 데이터 수집
    post_list = []
    
    # 게시글 목록 요소 가져오기 (카페 스킨에 따라 class 이름이 다를 수 있음)
    # 일반적인 리스트형 게시판 구조: tr 태그 반복
    rows = driver.find_elements(By.CSS_SELECTOR, "div.article-board > table > tbody > tr")
    
    if not rows: # 다른 스킨일 경우 (카드형 등)
         rows = driver.find_elements(By.XPATH, "//div[contains(@class, 'article-board')]//table//tr")

    print(f">> 총 {len(rows)}개의 글을 발견했습니다. 분석 중...")

    for row in rows:
        try:
            # 제목
            title_element = row.find_element(By.CSS_SELECTOR, "a.article")
            title = title_element.text.strip()
            link = title_element.get_attribute("href")
            
            # 작성 시간 (td.td_date)
            date_element = row.find_element(By.CSS_SELECTOR, "td.td_date")
            time_text = date_element.text.strip()
            
            # 작성자 (선택 사항)
            try:
                author = row.find_element(By.CSS_SELECTOR, "td.td_name a").text.strip()
            except:
                author = "Unknown"

            # 데이터 저장
            post_list.append({
                "title": title,
                "author": author,
                "time_text": time_text, # 원본 텍스트
                "link": link
            })
            
        except Exception as e:
            continue # 구분선이나 공지사항 등은 패스

    # ==========================================
    # 3. 데이터 처리 및 시각화
    # ==========================================
    
    if post_list:
        df = pd.DataFrame(post_list)
        
        # (1) 시간 데이터 변환 (방금 전 -> datetime)
        df['parsed_time'] = df['time_text'].apply(parse_relative_time)
        
        # (2) 오늘 작성된 글만 필터링 (그래프용)
        # parsed_time이 존재하고(None 아님), 날짜가 오늘인 경우
        today = datetime.now().date()
        df_today = df.dropna(subset=['parsed_time']) # 날짜 파싱 실패 제거
        df_today = df_today[df_today['parsed_time'].dt.date == today]
        
        print(f"\n>> 오늘 작성된 글: {len(df_today)}개 (전체 수집: {len(df)}개)")
        print(df[['title', 'time_text', 'parsed_time']].head()) # 확인용 출력

        # (3) 그래프 그리기
        if not df_today.empty:
            df_today['hour'] = df_today['parsed_time'].dt.hour
            
            plt.figure(figsize=(12, 6))
            
            # 시간대별 막대 그래프
            ax = sns.countplot(x='hour', data=df_today, palette='coolwarm', order=range(0, 24))
            
            # 그래프 꾸미기
            plt.title(f"'{KEYWORD}' 키워드 - 오늘 시간대별 새 글 현황", fontsize=15, pad=20)
            plt.xlabel("시간 (0시 ~ 23시)")
            plt.ylabel("게시글 수")
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            
            # 막대 위에 숫자 표시
            for p in ax.patches:
                if p.get_height() > 0:
                    ax.annotate(f'{int(p.get_height())}', 
                                (p.get_x() + p.get_width() / 2., p.get_height()), 
                                ha = 'center', va = 'center', 
                                xytext = (0, 9), 
                                textcoords = 'offset points')

            print(">> 그래프를 출력합니다...")
            plt.show() # 창이 뜹니다
            
        else:
            print(">> 오늘 작성된 글이 없어서 그래프를 그리지 못했습니다.")
            
    else:
        print(">> 수집된 데이터가 없습니다.")

except Exception as e:
    print(f"에러 발생: {e}")

finally:
    # 확인 후 브라우저 닫기 (원치 않으면 주석 처리)
    # driver.quit()
    pass
