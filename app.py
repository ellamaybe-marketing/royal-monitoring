import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

# 1. 페이지 설정
st.set_page_config(
    page_title="Royal Canin Monitor (Clean)",
    page_icon="✨",
    layout="wide"
)

# 2. HTML 태그 제거 함수
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

# 3. 데이터 수집 함수 (30일 지난 글은 자동 폐기)
def get_naver_data_clean_sorted(keyword_string, client_id, client_secret):
    if not client_id or not client_secret:
        return None, []
    
    keywords = [k.strip() for k in keyword_string.split(',') if k.strip()]
    category = "cafearticle"
    all_data = []
    log_messages = []
    
    status_area = st.empty()
    
    # [핵심] 오늘 날짜와 30일 전 날짜 계산
    now = datetime.datetime.now()
    cutoff_date = now - datetime.timedelta(days=30) # 유통기한 30일
    
    for idx, search_term in enumerate(keywords):
        # 키워드당 3페이지씩 수집
        for start_index in range(1, 300, 100):
            try:
                status_area.info(f"🧹 ({idx+1}/{len(keywords)}) '{search_term}' 최신글 수집 중... (오래된 글은 버림)")
                
                encText = urllib.parse.quote(search_term)
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
                        # 날짜 변환
                        raw_date = item.get('postdate', '')
                        try:
                            if raw_date:
                                p_date = pd.to_datetime(raw_date, format='%Y%m%d')
                            else:
                                # 날짜 없으면 1900년 (얘는 최신글로 쳐줌)
                                p_date = pd.to_datetime('1900-01-01')
                        except:
                            p_date = pd.to_datetime('1900-01-01')
                        
                        # -----------------------------------------------------------
                        # [핵심 필터] 30일보다 오래된 글이면 -> 저장 안 하고 건너뜀!
                        # (단, 날짜가 1900년인 건 '날짜미상 최신글'일 수 있으니 살려둠)
                        # -----------------------------------------------------------
                        if p_date.year > 2000 and p_date < cutoff_date:
                            continue 
                        
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
                        item['search_keyword'] = search_term 
                        all_data.append(item)
                else:
                    break
            except Exception as e:
                log_messages.append(f"❌ 에러: {e}")
                break
            
    status_area.success(f"✅ 최근 30일 데이터만 {len(all_data)}건 확보 완료!")
    
    if not all_data:
        return pd.DataFrame(), log_messages

    df = pd.DataFrame(all_data)
    
    # 위험 키워드
    risk_keywords = ['벌레', '이물', '구더기', '회수', '식약처', '신고', '환불', '토해', '설사', '혈변', '곰팡이', '충격', '실망', '배신', '리콜']
    
    def check_risk(text):
        for k in risk_keywords:
            if k in text:
                return f"🚨 발견: {k}"
        return "일반"

    df['risk_level'] = df['clean_desc'].apply(check_risk)
    
    # 중복 제거
    df = df.drop_duplicates(['clean_title'])
    
    # [정렬] 날짜순 (1900년은 '현재'로 취급해서 맨 위로)
    df['sort_helper'] = df['postdate_dt'].apply(lambda x: now if x.year == 1900 else x)
    df = df.sort_values(by='sort_helper', ascending=False)
    
    return df[['postdate_dt', 'source', 'clean_title', 'clean_desc', 'risk_level', 'link', 'search_keyword']], log_messages

# 4. UI 구성
with st.sidebar:
    st.header("✨ 최근 30일 모니터링")
    
    default_keywords = "로얄캐닌, 로캐, 로케, ㄹㅇㅋㄴ"
    keyword_input = st.text_input("검색어 (콤마 구분)", value=default_keywords)
    
    st.markdown("---")
    st.caption("카페 필터")
    all_options = ["고양이라서 다행이야", "냥이네", "아반강고", "강사모"]
    target_filter = st.multiselect("카페 선택", all_options, default=all_options)
    
    st.markdown("---")
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Secret", type="password")
    run_btn = st.button("최신 데이터만 가져오기")

st.title(f"✨ '{keyword_input}' 클린 타임라인 (30일 이내)")

if run_btn:
    if not client_id or not client_secret:
        st.error("⚠️ API 키를 입력해주세요.")
    else:
        df, logs = get_naver_data_clean_sorted(keyword_input, client_id, client_secret)
        
        with st.expander("ℹ️ 로그 확인"):
            if logs:
                for log in logs: st.write(log)
            else:
                st.write("이상 무.")

        if df is not None and not df.empty:
            if target_filter:
                filtered_df = df[df['source'].isin(target_filter)]
            else:
                filtered_df = df
            
            # 요약
            col1, col2, col3 = st.columns(3)
            risk_df = filtered_df[filtered_df['risk_level'] != "일반"]
            risk_count = len(risk_df)
            top_src = filtered_df['source'].mode()[0] if not filtered_df.empty else "-"
                
            col1.metric("최근 30일 글", f"{len(filtered_df)}건")
            col2.metric("🚨 이슈 글", f"{risk_count}건", delta_color="inverse")
            col3.metric("최다 출처", top_src)
            
            st.markdown("---")
            
            # 차트
            st.subheader("📊 일별 언급량 (최근 30일)")
            chart_df = filtered_df[filtered_df['postdate_dt'].dt.year > 2000]
            if not chart_df.empty:
                trend_data = chart_df['postdate_dt'].dt.date.value_counts().sort_index()
                st.area_chart(trend_data, color="#ff4b4b")
            
            st.markdown("---")

            # 탭
            tab1, tab2, tab3 = st.tabs(["🔥 리스크 피드", "📊 키워드 통계", "📝 전체 리스트"])
            
            with tab1:
                if risk_df.empty:
                    st.success("✅ 최근 30일 내 위험 단어가 포함된 글이 없습니다.")
                else:
                    for i, row in risk_df.iterrows():
                        with st.container():
                            if row['postdate_dt'].year == 1900:
                                date_str = "⚡ 최신 (날짜미상)"
                                date_color = "red"
                            else:
                                date_str = row['postdate_dt'].strftime('%Y-%m-%d')
                                date_color = "gray"
                            
                            st.markdown(f"**☕ [{row['source']}]** <span style='color:{date_color}'>{date_str}</span>", unsafe_allow_html=True)
                            st.error(f"{row['clean_title']}")
                            st.write(f"⚠️ {row['risk_level']} (검색어: {row['search_keyword']})")
                            st.caption(row['clean_desc'])
                            st.markdown(f"[원문 이동]({row['link']})")
                            st.divider()
            
            with tab2:
                if not filtered_df.empty:
                    st.bar_chart(filtered_df['search_keyword'].value_counts())

            with tab3:
                display = filtered_df.copy()
                display['날짜'] = display['postdate_dt'].apply(lambda x: "⚡최신" if x.year == 1900 else x.strftime('%Y-%m-%d'))
                
                st.dataframe(
                    display[['날짜', 'source', 'clean_title', 'risk_level', 'search_keyword', 'link']],
                    column_config={"link": st.column_config.LinkColumn("링크")},
                    use_container_width=True
                )
            
            st.markdown("---")
            csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 엑셀 다운로드",
                data=csv,
                file_name=f"clean_monitoring.csv",
                mime="text/csv",
            )
        else:
            st.warning("최근 30일 내에 작성된 글이 없습니다.")
