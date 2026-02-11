import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

# 1. 페이지 설정
st.set_page_config(
    page_title="Royal Canin Unified Monitor",
    page_icon="👑",
    layout="wide"
)

# 2. HTML 태그 제거 함수
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

# 3. 데이터 수집 함수 (키워드 통합 로직 추가)
def get_data_unified(keyword_string, exclude_string, client_id, client_secret):
    if not client_id or not client_secret:
        return None, []
    
    keywords = [k.strip() for k in keyword_string.split(',') if k.strip()]
    excludes = [e.strip() for e in exclude_string.split(',') if e.strip()]
    
    category = "cafearticle"
    all_data = []
    log_messages = []
    
    status_area = st.empty()
    
    # 30일 유통기한
    now = datetime.datetime.now()
    cutoff_date = now - datetime.timedelta(days=30)
    
    # 통합할 브랜드명 정의
    unified_brand_name = "로얄캐닌" 
    
    # [1] 데이터 수집
    for idx, search_term in enumerate(keywords):
        for start_index in range(1, 300, 100):
            try:
                status_area.info(f"🚀 ({idx+1}/{len(keywords)}) '{search_term}' 수집 중...")
                
                query_str = search_term
                if excludes:
                    for exc in excludes:
                        query_str += f" -{exc}"
                
                encText = urllib.parse.quote(query_str)
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
                        
                        # 30일 필터
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
                        
                        # [핵심 변경] 검색어(로캐, 로케 등)를 무조건 '로얄캐닌'으로 통일!
                        # 원래 검색어가 무엇이었는지는 괄호 안에 살짝 남겨둘 수도 있지만, 
                        # 요청하신 대로 깔끔하게 통합하려면 그냥 덮어쓰는 게 좋습니다.
                        item['search_keyword'] = unified_brand_name 
                        
                        all_data.append(item)
                else:
                    break
            except Exception as e:
                log_messages.append(f"❌ 에러: {e}")
                break
    
    status_area.success(f"✅ 수집 및 통합 완료! (총 {len(all_data)}건)")
    
    if not all_data:
        return pd.DataFrame(), log_messages

    df = pd.DataFrame(all_data)
    
    # [2] 위험 키워드
    risk_keywords = ['벌레', '이물', '구더기', '회수', '식약처', '신고', '환불', '토해', '설사', '혈변', '곰팡이', '충격', '실망', '배신', '리콜']
    
    def check_risk(text):
        for k in risk_keywords:
            if k in text:
                return f"🚨 발견: {k}"
        return "일반"

    df['risk_level'] = df['clean_desc'].apply(check_risk)
    
    # [3] 정렬 후 중복 제거 (최신 글 살리기)
    df['sort_helper'] = df['postdate_dt'].apply(lambda x: now if x.year == 1900 else x)
    df = df.sort_values(by='sort_helper', ascending=False)
    df = df.drop_duplicates(['clean_title'], keep='first')
    
    return df[['postdate_dt', 'source', 'clean_title', 'clean_desc', 'risk_level', 'link', 'search_keyword']], log_messages

# 4. UI 구성
with st.sidebar:
    st.header("👑 브랜드 통합 모니터링")
    
    default_keywords = "로얄캐닌, 로캐, 로케"
    keyword_input = st.text_input("검색어 (콤마 구분)", value=default_keywords)
    st.caption("※ 입력한 모든 단어는 결과에서 '로얄캐닌'으로 합쳐집니다.")
    
    st.caption("🚫 제외어")
    exclude_input = st.text_input("제외할 단어", value="ㄹㅇㅋㄴ, 광고, 분양, 팝니다")
    
    st.markdown("---")
    st.caption("카페 필터")
    all_options = ["고양이라서 다행이야", "냥이네", "아반강고", "강사모"]
    target_filter = st.multiselect("카페 선택", all_options, default=all_options)
    
    st.markdown("---")
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Secret", type="password")
    run_btn = st.button("통합 분석 시작")

st.title(f"👑 '로얄캐닌' 통합 타임라인")

if run_btn:
    if not client_id or not client_secret:
        st.error("⚠️ API 키를 입력해주세요.")
    else:
        df, logs = get_data_unified(keyword_input, exclude_input, client_id, client_secret)
        
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
            
            col1, col2, col3 = st.columns(3)
            risk_df = filtered_df[filtered_df['risk_level'] != "일반"]
            
            # 최신 글 날짜
            if not filtered_df.empty:
                latest_date = filtered_df.iloc[0]['postdate_dt']
                latest_str = "⚡ 방금 (날짜미상)" if latest_date.year == 1900 else latest_date.strftime('%Y-%m-%d')
            else:
                latest_str = "-"
                
            col1.metric("통합 수집량", f"{len(filtered_df)}건")
            col2.metric("🚨 이슈 글", f"{len(risk_df)}건", delta_color="inverse")
            col3.metric("가장 최신 글", latest_str)
            
            st.markdown("---")
            
            tab1, tab2, tab3 = st.tabs(["🔥 피드 (시간순)", "📊 통합 통계", "📝 리스트"])
            
            with tab1:
                for i, row in filtered_df.iterrows():
                    with st.container():
                        if row['postdate_dt'].year == 1900:
                            date_str = "⚡ 최신 (날짜미상)"
                            date_color = "red"
                        else:
                            date_str = row['postdate_dt'].strftime('%Y-%m-%d')
                            date_color = "gray"
                        
                        if "🚨" in row['risk_level']:
                            title_prefix = "🚨 "
                        else:
                            title_prefix = ""

                        # [확인 포인트] 이제 검색어 부분이 모두 '로얄캐닌'으로 보일 겁니다.
                        st.markdown(f"**☕ [{row['source']}]** <span style='color:{date_color}'>{date_str}</span>", unsafe_allow_html=True)
                        st.markdown(f"**{title_prefix}{row['clean_title']}**")
                        
                        if "🚨" in row['risk_level']:
                             st.write(f"⚠️ **{row['risk_level']}**")
                        
                        st.caption(row['clean_desc'])
                        st.markdown(f"[원문 이동]({row['link']})")
                        st.divider()
            
            with tab2:
                if not filtered_df.empty:
                    st.write("📈 **일별 언급량 추이** (통합 기준)")
                    chart_df = filtered_df[filtered_df['postdate_dt'].dt.year > 2000]
                    if not chart_df.empty:
                        trend_data = chart_df['postdate_dt'].dt.date.value_counts().sort_index()
                        st.area_chart(trend_data, color="#ff4b4b")
                    
                    st.write("🔎 **키워드 통계**")
                    st.write("모든 키워드가 '로얄캐닌'으로 통합되었습니다.")
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
                label="📥 통합 엑셀 다운로드",
                data=csv,
                file_name=f"unified_monitoring.csv",
                mime="text/csv",
            )
        else:
            st.warning("조건에 맞는 데이터가 없습니다.")
