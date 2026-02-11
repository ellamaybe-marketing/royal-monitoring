import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

# --------------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------------
st.set_page_config(
    page_title="Royal Canin 7-Day Monitor",
    page_icon="📈",
    layout="wide"
)

# --------------------------------------------------------------------------------
# 2. 데이터 수집 함수 (7일치 반복 수집)
# --------------------------------------------------------------------------------
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

def get_naver_data_7days(keyword, client_id, client_secret):
    if not client_id or not client_secret:
        return None
    
    categories = ["blog", "cafearticle"]
    all_data = []
    
    # 7일 전 날짜 계산
    today = datetime.datetime.now()
    cutoff_date = today - datetime.timedelta(days=7)
    
    # 진행상황 표시용 텍스트 박스
    status_text = st.empty() 
    
    for cat in categories:
        # 카테고리별로 최대 10페이지(1000개)까지만 탐색 (무한 루프 방지)
        # start=1, 101, 201, ... 식으로 페이지를 넘김
        for start_index in range(1, 1000, 100):
            try:
                status_text.text(f"🔍 {cat} 데이터를 {start_index}번부터 긁어오는 중...")
                
                encText = urllib.parse.quote(keyword)
                # display=100 (최대치), start=페이지 시작 위치
                url = f"https://openapi.naver.com/v1/search/{cat}?query={encText}&display=100&start={start_index}&sort=date"
                
                request = urllib.request.Request(url)
                request.add_header("X-Naver-Client-Id", client_id)
                request.add_header("X-Naver-Client-Secret", client_secret)
                
                response = urllib.request.urlopen(request)
                if response.getcode() == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    items = data['items']
                    
                    if not items:
                        break # 데이터가 없으면 중단

                    # 날짜 확인 및 저장
                    temp_list = []
                    stop_flag = False
                    
                    for item in items:
                        # 날짜 변환 (블로그/카페 형식 처리)
                        try:
                            p_date = pd.to_datetime(item['postdate'], format='%Y%m%d')
                        except:
                            continue
                            
                        # 7일보다 오래된 글이면 멈춤 신호
                        if p_date < cutoff_date:
                            stop_flag = True
                            continue # 저장 안 함
                        
                        # 데이터 정제
                        item['source'] = "블로그" if cat == "blog" else "카페"
                        item['clean_title'] = clean_html(item['title'])
                        item['clean_desc'] = clean_html(item['description'])
                        item['postdate_dt'] = p_date
                        temp_list.append(item)
                    
                    all_data.extend(temp_list)
                    
                    # 7일 지난 데이터가 나오기 시작했거나, 결과가 100개 미만이면 다음 페이지 안 감
                    if stop_flag or len(items) < 100:
                        break
                else:
                    break
            except Exception as e:
                print(f"Error: {e}")
                break
                
    status_text.empty() # 로딩 문구 삭제
    
    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data)
    
    # 위험도 분석
    risk_keywords = ['구더기', '벌레', '이물질', '식약처', '신고', '환불', '배신', '실망', '토해', '설사', '혈변']
    def check_risk(text):
        for k in risk_keywords:
            if k in text:
                return "🚨 심각/주의"
        return "일반"
        
    df['risk_level'] = df['clean_desc'].apply(check_risk)
    
    # 중복 제거 (제목 기준)
    df = df.drop_duplicates(['clean_title'])
    
    # 날짜 기준 내림차순 정렬
    df = df.sort_values(by='postdate_dt', ascending=False)
    
    return df[['postdate_dt', 'source', 'clean_title', 'clean_desc', 'risk_level', 'link']]

# --------------------------------------------------------------------------------
# 3. 메인 UI
# --------------------------------------------------------------------------------

# 사이드바
with st.sidebar:
    st.header("⚙️ 설정")
    keyword = st.text_input("검색어", value="로얄캐닌")
    st.markdown("---")
    st.caption("네이버 API 키 입력")
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Secret", type="password")
    
    run_btn = st.button("7일치 데이터 분석 시작")

st.title(f"📊 '{keyword}' 주간 트렌드 분석 (Last 7 Days)")

if run_btn:
    if not client_id or not client_secret:
        st.error("⚠️ 왼쪽 사이드바에 API 키를 입력해주세요!")
    else:
        with st.spinner("최근 7일간의 블로그/카페 글을 모두 수집 중입니다... (최대 20페이지)"):
            df = get_naver_data_7days(keyword, client_id, client_secret)

        if df is not None and not df.empty:
            # 1. 상단 요약 (Metric)
            col1, col2, col3 = st.columns(3)
            risk_count = len(df[df['risk_level'] == "🚨 심각/주의"])
            
            # 최다 출처 계산
            top_source = df['source'].mode()[0] if not df.empty else "-"

            col1.metric("총 수집 문서 (7일)", f"{len(df)}건")
            col2.metric("🚨 이슈(위험) 글", f"{risk_count}건", delta_color="inverse")
            col3.metric("주요 출처", top_source)

            st.markdown("---")

            # 2. [그래프 복구] 일별 언급량 추이
            st.subheader("📈 일별 언급량 추이")
            
            # 날짜별로 그룹핑해서 카운트 (Index를 날짜로 변환)
            trend_df = df.copy()
            trend_df['date_only'] = trend_df['postdate_dt'].dt.date
            trend_data = trend_df.groupby('date_only').size()
            
            # 꺾은선 그래프 (빨간색으로 강조)
            st.area_chart(trend_data, color="#ff4b4b")

            # 3. 상세 데이터 탭
            st.markdown("---")
            tab1, tab2 = st.tabs(["🔥 위험글 모아보기", "📋 전체 리스트"])
            
            with tab1:
                risk_df = df[df['risk_level'] == "🚨 심각/주의"]
                if risk_df.empty:
                    st.success("✅ 다행히 최근 7일간 감지된 위험 키워드가 없습니다.")
                else:
                    for i, row in risk_df.iterrows():
                        with st.container():
                            st.error(f"**[{row['source']}] {row['postdate_dt'].date()}** | {row['clean_title']}")
                            st.write(row['clean_desc'])
                            st.markdown(f"[원문 보러가기]({row['link']})")
                            st.divider()
            
            with tab2:
                # 보기 좋게 날짜 포맷 변경해서 출력
                display_df = df.copy()
                display_df['날짜'] = display_df['postdate_dt'].dt.date
                st.dataframe(
                    display_df[['날짜', 'source', 'clean_title', 'risk_level', 'link']],
                    column_config={
                        "link": st.column_config.LinkColumn("링크"),
                    },
                    use_container_width=True
                )
                
        else:
            st.warning("데이터가 없거나 API 호출에 실패했습니다. (검색 결과가 없거나 키 오류)")
else:
    st.info("👈 왼쪽 사이드바에 API 키를 넣고 버튼을 눌러주세요.")
