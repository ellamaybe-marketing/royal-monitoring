import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

# 1. 페이지 설정
st.set_page_config(
    page_title="Cafe Monitor with Graph",
    page_icon="📈",
    layout="wide"
)

# 2. HTML 태그 제거 함수
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

# 3. 데이터 수집 함수
def get_cafe_data_with_graph(keyword, client_id, client_secret):
    if not client_id or not client_secret:
        return None, []
    
    # 카페만 집중 공략
    category = "cafearticle"
    all_data = []
    log_messages = []
    
    status_area = st.empty()
    
    # 5페이지(500개) 탐색
    for start_index in range(1, 500, 100):
        try:
            status_area.info(f"☕ 카페 데이터 {start_index}개째 수집 중...")
            
            encText = urllib.parse.quote(keyword)
            # sort=date (최신순)
            url = f"https://openapi.naver.com/v1/search/{category}?query={encText}&display=100&start={start_index}&sort=date"
            
            request = urllib.request.Request(url)
            request.add_header("X-Naver-Client-Id", client_id)
            request.add_header("X-Naver-Client-Secret", client_secret)
            
            response = urllib.request.urlopen(request)
            
            if response.getcode() == 200:
                data = json.loads(response.read().decode('utf-8'))
                items = data['items']
                
                if not items: break

                for item in items:
                    # 날짜 처리
                    raw_date = item.get('postdate', '')
                    try:
                        if raw_date:
                            p_date = pd.to_datetime(raw_date, format='%Y%m%d')
                        else:
                            # 날짜 없으면 1900년 (리스트 상단 노출용)
                            p_date = pd.to_datetime('1900-01-01')
                    except:
                        p_date = pd.to_datetime('1900-01-01')
                    
                    # 카페 이름 매칭
                    raw_name = item.get('cafename', '')
                    
                    if "고양이라서 다행이야" in raw_name or "고다" in raw_name: source_label = "고양이라서 다행이야"
                    elif "강사모" in raw_name: source_label = "강사모"
                    elif "아반강고" in raw_name: source_label = "아반강고"
                    elif "냥이네" in raw_name: source_label = "냥이네"
                    else: source_label = f"기타 ({raw_name})"
                    
                    item['source'] = source_label
                    item['clean_title'] = clean_html(item['title'])
                    item['clean_desc'] = clean_html(item['description'])
                    item['postdate_dt'] = p_date
                    all_data.append(item)
            else:
                code = response.getcode()
                log_messages.append(f"❌ API 호출 실패 (Code: {code})")
                break
        except Exception as e:
            log_messages.append(f"❌ 에러 발생: {e}")
            break
            
    status_area.success("✅ 수집 완료!")
    
    if not all_data:
        return pd.DataFrame(), log_messages

    df = pd.DataFrame(all_data)
    
    # 위험도 분석
    risk_keywords = ['구더기', '벌레', '이물질', '식약처', '신고', '환불', '토해', '설사', '혈변', '곰팡이', '리콜', '배신', '실망']
    df['risk_level'] = df['clean_desc'].apply(lambda x: "🚨 심각/주의" if any(k in x for k in risk_keywords) else "일반")
    
    # 중복 제거
    df = df.drop_duplicates(['clean_title'])
    
    # [정렬 로직] 1900년(날짜없음)은 '현재'로 취급하여 맨 위로 정렬
    now = datetime.datetime.now()
    df['sort_date'] = df['postdate_dt'].apply(lambda x: now if x.year == 1900 else x)
    df = df.sort_values(by='sort_date', ascending=False)
    
    return df[['postdate_dt', 'source', 'clean_title', 'clean_desc', 'risk_level', 'link']], log_messages

# 4. UI 구성
with st.sidebar:
    st.header("☕ 카페 모니터링 (+그래프)")
    keyword = st.text_input("검색어", value="로얄캐닌")
    
    st.markdown("---")
    all_options = ["고양이라서 다행이야", "냥이네", "아반강고", "강사모"]
    target_filter = st.multiselect("카페 선택", all_options, default=all_options)
    
    st.markdown("---")
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Secret", type="password")
    run_btn = st.button("데이터 분석 시작")

st.title(f"📈 '{keyword}' 카페 여론 & 추이 분석")

if run_btn:
    if not client_id or not client_secret:
        st.error("⚠️ API 키를 입력해주세요.")
    else:
        df, logs = get_cafe_data_with_graph(keyword, client_id, client_secret)
        
        with st.expander("ℹ️ 로그 확인"):
            if logs:
                for log in logs: st.write(log)
            else:
                st.write("이상 무.")

        if df is not None and not df.empty:
            # 필터링
            if target_filter:
                filtered_df = df[df['source'].isin(target_filter)]
            else:
                filtered_df = df
            
            # 요약 지표
            col1, col2, col3 = st.columns(3)
            risk_count = len(filtered_df[filtered_df['risk_level'] == "🚨 심각/주의"])
            top_src = filtered_df['source'].mode()[0] if not filtered_df.empty else "-"
                
            col1.metric("수집 글", f"{len(filtered_df)}건")
            col2.metric("이슈 글", f"{risk_count}건", delta_color="inverse")
            col3.metric("최다 언급", top_src)
            
            st.markdown("---")
            
            # ----------------------------------------------------------------
            # [추가됨] 일별 추이 그래프 (Line/Area Chart)
            # ----------------------------------------------------------------
            st.subheader("📊 일별 언급량 추이")
            
            # 그래프용 데이터: 1900년(날짜없음) 데이터는 그래프 그릴 때만 제외! (그래프 왜곡 방지)
            chart_df = filtered_df[filtered_df['postdate_dt'].dt.year > 2000]
            
            if not chart_df.empty:
                # 날짜별 개수 세기
                trend_data = chart_df['postdate_dt'].dt.date.value_counts().sort_index()
                # 빨간색 영역 차트로 그리기
                st.area_chart(trend_data, color="#ff4b4b")
            else:
                st.info("📉 날짜 정보가 있는 글이 적어서 그래프를 그릴 수 없습니다. (아래 리스트를 확인하세요)")
            
            st.markdown("---")

            # 탭 구성
            tab1, tab2, tab3 = st.tabs(["🔥 타임라인", "🥧 카페 점유율", "📝 전체 리스트"])
            
            with tab1:
                risk_df = filtered_df[filtered_df['risk_level'] == "🚨 심각/주의"]
                if risk_df.empty:
                    st.success("감지된 위험 이슈가 없습니다.")
                else:
                    for i, row in risk_df.iterrows():
                        with st.container():
                            if row['postdate_dt'].year == 1900:
                                date_str = "⚡ 최신 (날짜미상)"
                                date_color = "red"
                            else:
                                date_str = row['postdate_dt'].strftime('%Y-%m-%d')
                                date_color = "black"
                            
                            st.markdown(f"**☕ [{row['source']}]** <span style='color:{date_color}'>{date_str}</span>", unsafe_allow_html=True)
                            st.error(f"{row['clean_title']}")
                            st.caption(row['clean_desc'])
                            st.markdown(f"[게시글 바로가기]({row['link']})")
                            st.divider()
            
            with tab2:
                if not filtered_df.empty:
                    st.bar_chart(filtered_df['source'].value_counts())

            with tab3:
                display = filtered_df.copy()
                display['날짜'] = display['postdate_dt'].apply(lambda x: "⚡최신(확인중)" if x.year == 1900 else x.strftime('%Y-%m-%d'))
                
                st.dataframe(
                    display[['날짜', 'source', 'clean_title', 'risk_level', 'link']],
                    column_config={"link": st.column_config.LinkColumn("링크")},
                    use_container_width=True
                )
            
            st.markdown("---")
            csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 엑셀 다운로드",
                data=csv,
                file_name=f"{keyword}_cafe_trend.csv",
                mime="text/csv",
            )
        else:
            st.warning("데이터가 없습니다.")
