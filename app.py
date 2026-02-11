import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

# 1. 페이지 설정
st.set_page_config(
    page_title="Cafe Real-Time Feed",
    page_icon="⚡",
    layout="wide"
)

# 2. HTML 태그 제거 함수
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

# 3. 데이터 수집 함수 (네이버가 준 순서 절대 지킴!)
def get_cafe_realtime_raw(keyword, client_id, client_secret):
    if not client_id or not client_secret:
        return None, []
    
    category = "cafearticle"
    all_data = []
    log_messages = []
    
    status_area = st.empty()
    
    # 순서 보장을 위해 페이지 순차 탐색
    for start_index in range(1, 500, 100):
        try:
            status_area.info(f"⚡ 네이버가 주는 최신 데이터 {start_index}번부터 받는 중...")
            
            encText = urllib.parse.quote(keyword)
            # sort=date (최신순 요청)
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
                            # 날짜 없으면 1900년 (하지만 정렬은 안 할 거라 상관 없음)
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
            
    status_area.success("✅ 최신순 수집 완료!")
    
    if not all_data:
        return pd.DataFrame(), log_messages

    df = pd.DataFrame(all_data)
    
    # 위험 키워드
    risk_keywords = ['구더기', '벌레', '이물질', '식약처', '신고', '환불', '토해', '설사', '혈변', '곰팡이', '리콜', '배신', '실망', '충격']
    df['risk_level'] = df['clean_desc'].apply(lambda x: "🚨 심각/주의" if any(k in x for k in risk_keywords) else "일반")
    
    # 중복 제거 (제목 기준) - 중복 제거해도 순서는 유지됨
    df = df.drop_duplicates(['clean_title'])
    
    # [핵심] df.sort_values() 삭제함!
    # 네이버가 1페이지 맨 처음에 준 게 가장 최신이므로, 그 순서(Index) 그대로 유지.
    
    return df[['postdate_dt', 'source', 'clean_title', 'clean_desc', 'risk_level', 'link']], log_messages

# 4. UI 구성
with st.sidebar:
    st.header("⚡ 카페 최신순 피드")
    keyword = st.text_input("검색어", value="로얄캐닌")
    
    st.markdown("---")
    all_options = ["고양이라서 다행이야", "냥이네", "아반강고", "강사모"]
    target_filter = st.multiselect("카페 필터", all_options, default=all_options)
    
    st.markdown("---")
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Secret", type="password")
    run_btn = st.button("최신 데이터 가져오기")

st.title(f"⚡ '{keyword}' 실시간 도착 피드")

if run_btn:
    if not client_id or not client_secret:
        st.error("⚠️ API 키를 입력해주세요.")
    else:
        df, logs = get_cafe_realtime_raw(keyword, client_id, client_secret)
        
        with st.expander("ℹ️ 로그 확인"):
            if logs:
                for log in logs: st.write(log)
            else:
                st.write("정상.")

        if df is not None and not df.empty:
            if target_filter:
                filtered_df = df[df['source'].isin(target_filter)]
            else:
                filtered_df = df
            
            # 요약
            col1, col2, col3 = st.columns(3)
            risk_count = len(filtered_df[filtered_df['risk_level'] == "🚨 심각/주의"])
            top_src = filtered_df['source'].mode()[0] if not filtered_df.empty else "-"
                
            col1.metric("수집 글", f"{len(filtered_df)}건")
            col2.metric("이슈 글", f"{risk_count}건", delta_color="inverse")
            col3.metric("최다 출처", top_src)
            
            st.markdown("---")
            
            # 1. 일별 추이 그래프 (날짜 있는 것만 골라서 그림)
            st.subheader("📊 언급량 추이 (날짜 확인된 글 기준)")
            chart_df = filtered_df[filtered_df['postdate_dt'].dt.year > 2000]
            if not chart_df.empty:
                trend_data = chart_df['postdate_dt'].dt.date.value_counts().sort_index()
                st.area_chart(trend_data, color="#ff4b4b")
            else:
                st.caption("그래프를 그릴 날짜 데이터가 부족합니다.")
            
            st.markdown("---")

            # 2. 탭
            tab1, tab2, tab3 = st.tabs(["🔥 최신 피드 (순서대로)", "🥧 점유율", "📝 전체 리스트"])
            
            with tab1:
                risk_df = filtered_df[filtered_df['risk_level'] == "🚨 심각/주의"]
                if risk_df.empty:
                    st.success("위험 글 없음.")
                else:
                    st.caption("👇 위에서부터 네이버가 보낸 가장 최신 순서입니다.")
                    for i, row in risk_df.iterrows():
                        with st.container():
                            # 날짜 표시
                            if row['postdate_dt'].year == 1900:
                                # 이게 바로 그 '날짜 없는 최신글'입니다!
                                date_str = "⚡ 방금 수집 (날짜 정보 없음)" 
                                date_color = "red"
                            else:
                                date_str = row['postdate_dt'].strftime('%Y-%m-%d')
                                date_color = "gray"
                            
                            st.markdown(f"**☕ [{row['source']}]** <span style='color:{date_color}; font-weight:bold'>{date_str}</span>", unsafe_allow_html=True)
                            st.error(f"{row['clean_title']}")
                            st.caption(row['clean_desc'])
                            st.markdown(f"[원문 이동]({row['link']})")
                            st.divider()
            
            with tab2:
                if not filtered_df.empty:
                    st.bar_chart(filtered_df['source'].value_counts())

            with tab3:
                display = filtered_df.copy()
                display['날짜'] = display['postdate_dt'].apply(lambda x: "⚡최신(날짜없음)" if x.year == 1900 else x.strftime('%Y-%m-%d'))
                
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
                file_name=f"{keyword}_realtime_feed.csv",
                mime="text/csv",
            )
        else:
            st.warning("데이터가 없습니다.")
