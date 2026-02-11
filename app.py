import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

# 1. 페이지 설정
st.set_page_config(
    page_title="Royal Canin Global Sort",
    page_icon="🌪️",
    layout="wide"
)

# 2. HTML 태그 제거 함수
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

# 3. 데이터 수집 함수 (모두 모아서 마지막에 한 번에 정렬)
def get_data_global_sort(keyword_string, exclude_string, client_id, client_secret):
    if not client_id or not client_secret:
        return None, []
    
    keywords = [k.strip() for k in keyword_string.split(',') if k.strip()]
    excludes = [e.strip() for e in exclude_string.split(',') if e.strip()]
    
    category = "cafearticle"
    all_data = [] # 여기에 모든 검색어의 결과를 다 넣습니다.
    log_messages = []
    
    status_area = st.empty()
    
    # 30일 유통기한
    now = datetime.datetime.now()
    cutoff_date = now - datetime.timedelta(days=30)
    
    # [1] 데이터 수집 단계 (정렬 신경 쓰지 말고 무조건 모으기)
    total_found = 0
    for idx, search_term in enumerate(keywords):
        for start_index in range(1, 300, 100):
            try:
                status_area.info(f"🚜 ({idx+1}/{len(keywords)}) '{search_term}' 긁어모으는 중... (현재 {total_found}개 확보)")
                
                # 검색어 + 제외어 조합
                query_str = search_term
                if excludes:
                    for exc in excludes:
                        query_str += f" -{exc}"
                
                encText = urllib.parse.quote(query_str)
                # API에게 최신순으로 달라고 하긴 함
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
                                p_date = pd.to_datetime('1900-01-01')
                        except:
                            p_date = pd.to_datetime('1900-01-01')
                        
                        # 30일 지난 글 버리기 (1900년은 살림)
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
                        total_found += 1
                else:
                    break
            except Exception as e:
                log_messages.append(f"❌ 에러: {e}")
                break
            
    status_area.success(f"✅ 총 {len(all_data)}개 글 확보! 이제 최신순으로 섞습니다...")
    
    if not all_data:
        return pd.DataFrame(), log_messages

    df = pd.DataFrame(all_data)
    
    # [2] 위험 키워드 분석
    risk_keywords = ['벌레', '이물', '구더기', '회수', '식약처', '신고', '환불', '토해', '설사', '혈변', '곰팡이', '충격', '실망', '배신', '리콜']
    
    def check_risk(text):
        found = [k for k in risk_keywords if k in text]
        if found:
            return f"🚨 {found[0]}" # 첫 번째 발견된 키워드 표시
        return "일반"

    df['risk_level'] = df['clean_desc'].apply(check_risk)
    
    # [3] 중복 제거 (제목 기준)
    df = df.drop_duplicates(['clean_title'])
    
    # [4] ★ 여기가 핵심: 전체 통합 정렬 (Global Sort) ★
    # '로얄캐닌' 글이든 '로캐' 글이든 상관없이 날짜 하나만 보고 줄 세웁니다.
    # 1900년(날짜없음)은 '현재(now)'로 치환해서 맨 위로 보냄
    
    df['sort_helper'] = df['postdate_dt'].apply(lambda x: now if x.year == 1900 else x)
    df = df.sort_values(by='sort_helper', ascending=False)
    
    # 이제 df는 완벽하게 섞여서 최신순으로 정렬됨
    
    return df[['postdate_dt', 'source', 'clean_title', 'clean_desc', 'risk_level', 'link', 'search_keyword']], log_messages

# 4. UI 구성
with st.sidebar:
    st.header("🌪️ 통합 최신순 모니터링")
    
    default_keywords = "로얄캐닌, 로캐, 로케"
    keyword_input = st.text_input("검색어 (콤마 구분)", value=default_keywords)
    
    st.caption("🚫 제외어")
    exclude_input = st.text_input("제외할 단어", value="ㄹㅇㅋㄴ, 광고, 분양, 팝니다")
    
    st.markdown("---")
    st.caption("카페 필터")
    all_options = ["고양이라서 다행이야", "냥이네", "아반강고", "강사모"]
    target_filter = st.multiselect("카페 선택", all_options, default=all_options)
    
    st.markdown("---")
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Secret", type="password")
    run_btn = st.button("최신순 정렬 시작")

st.title(f"🌪️ '{keyword_input}' 통합 타임라인")

if run_btn:
    if not client_id or not client_secret:
        st.error("⚠️ API 키를 입력해주세요.")
    else:
        df, logs = get_data_global_sort(keyword_input, exclude_input, client_id, client_secret)
        
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
            
            # 최신 글 시간 확인 (정렬 잘 됐나 보려고)
            if not filtered_df.empty:
                latest_date = filtered_df.iloc[0]['postdate_dt']
                if latest_date.year == 1900:
                    latest_str = "방금 (날짜미상)"
                else:
                    latest_str = latest_date.strftime('%Y-%m-%d')
            else:
                latest_str = "-"
                
            col1.metric("수집된 글", f"{len(filtered_df)}건")
            col2.metric("🚨 이슈 글", f"{risk_count}건", delta_color="inverse")
            col3.metric("가장 최신 글", latest_str)
            
            st.markdown("---")
            
            # 탭
            tab1, tab2, tab3 = st.tabs(["🔥 통합 피드 (최신순)", "📊 통계", "📝 전체 리스트"])
            
            with tab1:
                # 통합 피드: 여기는 무조건 섞여서 최신순으로 나옴
                for i, row in filtered_df.iterrows():
                    with st.container():
                        if row['postdate_dt'].year == 1900:
                            date_str = "⚡ 최신 (날짜미상)"
                            date_color = "red"
                        else:
                            date_str = row['postdate_dt'].strftime('%Y-%m-%d')
                            date_color = "gray"
                        
                        # 위험 글이면 배경색 강조 느낌 (이모지)
                        if "🚨" in row['risk_level']:
                            title_prefix = "🚨 "
                        else:
                            title_prefix = ""

                        st.markdown(f"**☕ [{row['source']}]** <span style='color:{date_color}'>{date_str}</span>", unsafe_allow_html=True)
                        st.markdown(f"**{title_prefix}{row['clean_title']}**")
                        
                        if "🚨" in row['risk_level']:
                             st.write(f"⚠️ **{row['risk_level']}** (검색어: {row['search_keyword']})")
                        
                        st.caption(row['clean_desc'])
                        st.markdown(f"[원문 이동]({row['link']})")
                        st.divider()
            
            with tab2:
                if not filtered_df.empty:
                    st.write("🔎 **검색어별 비중**")
                    st.bar_chart(filtered_df['search_keyword'].value_counts())
                    
                    st.write("📈 **일별 추이** (날짜 확인된 글)")
                    chart_df = filtered_df[filtered_df['postdate_dt'].dt.year > 2000]
                    if not chart_df.empty:
                        trend_data = chart_df['postdate_dt'].dt.date.value_counts().sort_index()
                        st.area_chart(trend_data, color="#ff4b4b")

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
                file_name=f"global_sorted_monitoring.csv",
                mime="text/csv",
            )
        else:
            st.warning("조건에 맞는 데이터가 없습니다.")
