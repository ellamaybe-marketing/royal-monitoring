import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import random

# --------------------------------------------------------------------------------
# 1. 페이지 설정: 위기 관리 모드 (Red Theme)
# --------------------------------------------------------------------------------
st.set_page_config(
    page_title="🚨 Crisis Monitor: Royal Canin",
    page_icon="🔥",
    layout="wide"
)

# --------------------------------------------------------------------------------
# 2. 데이터 수집 및 위기 시뮬레이션
# --------------------------------------------------------------------------------

# (1) 네이버 API 함수
def get_naver_data(keyword, client_id, client_secret):
    if not client_id or not client_secret:
        return None
    
    # 위기 관련 키워드를 포함해서 검색 (이물질, 벌레 등)
    search_query = f"{keyword} (구더기 OR 애벌레 OR 이물질 OR 벌레)"
    encText = urllib.parse.quote(search_query)
    url = f"https://openapi.naver.com/v1/search/blog?query={encText}&display=100&sort=date"
    
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)
    
    try:
        response = urllib.request.urlopen(request)
        if response.getcode() == 200:
            data = json.loads(response.read().decode('utf-8'))
            df = pd.DataFrame(data['items'])
            
            df['title'] = df['title'].apply(lambda x: x.replace('<b>', '').replace('</b>', '').replace('&quot;', '"'))
            df['description'] = df['description'].apply(lambda x: x.replace('<b>', '').replace('</b>', ''))
            df['postdate'] = pd.to_datetime(df['postdate'], format='%Y%m%d')
            
            # 위험도 분석 로직 (간이)
            df['risk_level'] = df['description'].apply(lambda x: '심각' if '식약처' in x or '뉴스' in x else '주의')
            df['channel'] = 'Naver Blog' # 실제론 다양하게 들어옴
            
            return df[['postdate', 'title', 'description', 'risk_level', 'channel', 'link']]
    except:
        return None
    return None

# (2) 위기 상황 시뮬레이션 데이터 (구더기/이물질 이슈 특화)
def generate_crisis_mock_data():
    # 문제의 제품군
    targets = ["에이징 11+", "에이징 15+", "12+ 그레이비", "인도어 7+"]
    
    # 위기 키워드 (실제 발생 가능한 컴플레인)
    issues = [
        "사료 봉투 안에서 구더기가 기어다닙니다 혐오스러워요",
        "흰색 애벌레 같은 게 꿈틀거려서 소름 돋았어요",
        "거미줄 같은 게 엉켜있는데 이거 곰팡이인가요?",
        "아이가 먹고 계속 구토해서 봤더니 벌레가 있네요",
        "본사에 전화했는데 상담원 연결이 안 됩니다",
        "고다(카페) 보고 확인했더니 저희 집 사료도 당첨이네요 ㅠ",
        "이거 식약처에 신고 가능한가요? 뉴스 제보합니다",
        "환불로 끝날 게 아니라 전량 리콜해야 하는 거 아닌가요?"
    ]
    
    sources = ["고양이라서 다행이야", "강사모", "냥이네", "Instagram", "Twitter(X)"]
    
    data = []
    end_date = datetime.datetime.now()
    
    # 최근 3일간 이슈가 폭증하는 시나리오
    for _ in range(40): 
        days_ago = random.choices([0, 1, 2, 3, 4, 5], weights=[40, 30, 15, 5, 5, 5])[0] # 최근 날짜에 가중치
        rand_date = end_date - datetime.timedelta(days=days_ago)
        
        target = random.choice(targets)
        issue = random.choice(issues)
        source = random.choice(sources)
        
        # 위험도(Risk Level) 판별 로직
        if "식약처" in issue or "뉴스" in issue or "리콜" in issue:
            risk = "🚨심각(High)"
        elif "구토" in issue or "소름" in issue:
            risk = "⚠️주의(Medium)"
        else:
            risk = "관찰(Low)"

        data.append({
            'postdate': rand_date.date(),
            'title': f"[{target}] {issue[:15]}... (충격)",
            'description': f"...{target} 급여 중인데 {issue} 사진 첨부합니다. 유통기한은 2025년까지인데...",
            'risk_level': risk,
            'channel': source,
            'link': '#'
        })
    
    return pd.DataFrame(data)

# --------------------------------------------------------------------------------
# 3. UI 구성
# --------------------------------------------------------------------------------

# 사이드바
with st.sidebar:
    st.error("🚨 긴급 이슈 모니터링 모드")
    target_keyword = st.text_input("타겟 브랜드", value="로얄캐닌")
    issue_keywords = st.text_input("감지 키워드", value="구더기, 애벌레, 이물질, 벌레")
    
    st.markdown("---")
    st.caption("API Key (미입력 시 시뮬레이션)")
    api_id = st.text_input("Client ID", type="password")
    api_pw = st.text_input("Client Secret", type="password")
    
    if st.button("위기 현황 조회", type="primary"):
        st.session_state['run_crisis'] = True

st.title(f"🔥 '{target_keyword} 11+/15+' 이물질 이슈 현황판")
st.markdown("""
<style>
    .big-font { font-size:20px !important; color: #d32f2f; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

if st.session_state.get('run_crisis'):
    
    with st.spinner('커뮤니티/SNS 긴급 크롤링 중...'):
        df = get_naver_data(target_keyword, api_id, api_pw)
        if df is None:
            df = generate_crisis_mock_data()
            st.warning("⚠️ API 키가 없어 **'시뮬레이션 데이터'**가 표시됩니다. (실제 상황 가정)")

    # 1. 긴급 지표 (Dashboard)
    st.markdown("### 🛑 실시간 피해/제보 현황")
    
    total = len(df)
    high_risk = len(df[df['risk_level'] == '🚨심각(High)'])
    recent = len(df[df['postdate'] >= (datetime.datetime.now().date() - datetime.timedelta(days=1))])
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("총 제보 건수", f"{total}건", "확산 중")
    col2.metric("🚨 심각(보도/신고)", f"{high_risk}건", "즉시 대응 필요")
    col3.metric("오늘/어제 신규", f"{recent}건", "+240% (급증)")
    col4.metric("주요 키워드", "구더기, 환불", "전량 회수")

    st.markdown("---")

    # 2. 확산 추이 그래프
    st.subheader("📉 이슈 확산 속도 (Time-Series)")
    st.caption("최근 1주일간 이물질 관련 언급량 추이입니다. 그래프가 급격히 꺾이면 '바이럴'이 터진 것입니다.")
    
    trend = df.groupby('postdate').size()
    st.area_chart(trend, color="#ff4b4b") # 빨간색 차트

    # 3. 채널별 위험도 히트맵
    st.subheader("🔥 채널별/제품별 위험군")
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.write("**진원지(채널) 분석**")
        st.bar_chart(df['channel'].value_counts(), color="#ff4b4b")
        
    with col_chart2:
        st.write("**문제 제품 언급 비중**")
        # 텍스트 분석으로 제품명 추출 시뮬레이션
        product_counts = {"11+ (Aging)": 15, "15+ (Aging)": 12, "인도어": 8, "기타": 5}
        st.bar_chart(pd.DataFrame.from_dict(product_counts, orient='index'), color="#ffa726")

    # 4. 실시간 피드 (심각도별 필터링)
    st.markdown("---")
    st.subheader("📝 실시간 고객 반응 (Risk Feed)")
    
    tab1, tab2, tab3 = st.tabs(["🚨 심각 (High)", "⚠️ 주의 (Medium)", "전체 보기"])
    
    # 공통 출력 함수
    def render_feed(data_frame):
        if data_frame.empty:
            st.success("해당 등급의 이슈가 없습니다.")
        for i, row in data_frame.iterrows():
            with st.container():
                # 심각한 건은 빨간 박스로 강조
                if "심각" in row['risk_level']:
                    st.error(f"**[{row['channel']}]** {row['title']}")
                else:
                    st.warning(f"**[{row['channel']}]** {row['title']}")
                
                st.caption(f"📅 {row['postdate']} | 위험도: {row['risk_level']}")
                st.write(row['description'])
                st.markdown(f"[원문 확인]({row['link']})")

    with tab1:
        render_feed(df[df['risk_level'] == '🚨심각(High)'])
    with tab2:
        render_feed(df[df['risk_level'] == '⚠️주의(Medium)'])
    with tab3:
        render_feed(df)

else:
    st.info("👈 사이드바에서 **[위기 현황 조회]** 버튼을 눌러주세요.")