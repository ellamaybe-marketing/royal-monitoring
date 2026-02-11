import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

# 1. 페이지 설정
st.set_page_config(
    page_title="Community Split Monitor",
    page_icon="🏘️",
    layout="wide"
)

# 2. HTML 태그 제거 함수
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

# 3. 데이터 수집 함수
def get_data_split_community(keyword_string, exclude_string, client_id, client_secret):
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
    
    # 통합 브랜드명
    unified_brand_name = "로얄캐닌" 
    
    # [1] 데이터 수집
    for idx, search_term in enumerate(keywords):
        # 각 키워드별 3페이지(300개) 수집
        for start_index in range(1, 300, 100):
            try:
                status_area.info(f"🚚 ({idx+1}/{len(keywords)}) '{search_term}' 배달 중...")
                
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
                        
                        # -----------------------------------------------------------
                        # [핵심] 커뮤니티 이름표 정확하게 붙이기
                        # -----------------------------------------------------------
                        raw_name = item.get('cafename', '')
                        if "고양이라서 다행이야" in raw_name or "고다" in raw_name: 
                            source_label = "고양이라서 다행이야"
                        elif "강사모" in raw_name: 
                            source_label = "강사모"
                        elif "아반강고" in raw_name: 
                            source_label = "아반강고"
                        elif "냥이네" in raw_name: 
                            source_label = "냥이네"
                        else: 
                            source_label = "기타"
                        
                        item['source'] = source_label
                        item['clean_title'] = clean_html(item['title'])
                        item['clean_desc'] = clean_html(item['description'])
                        item['postdate_dt'] = p_date
                        item['search_keyword'] = unified_brand_name # 키워드 통합
                        
                        all_data.append(item)
                else:
                    break
            except Exception as e:
                log_messages.append(f"❌ 에러: {e}")
                break
    
    status_area.success(f"✅ 분류 완료! (총 {len(all_data)}건)")
    
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
    
    # [3] 통합 정렬 및 중복 제거
    # 1900년(날짜없음)을 '현재'로 치환해서 맨 위로 올림
    df['sort_helper'] = df['postdate_dt'].apply(lambda x: now if x.year == 1900 else x)
    df = df.sort_values(by='sort_helper', ascending=False)
    
    # 최신 글 남기고 중복 제거
    df = df.drop_duplicates(['clean_title'], keep='first')
    
    return df[['postdate_dt', 'source', 'clean_title', 'clean_desc', 'risk_level', 'link', 'search_keyword']], log_messages

# 4. UI 구성
with st.sidebar:
    st.header("🏘️ 커뮤니티별 모니터링")
    
    default_keywords = "로얄캐닌, 로캐, 로케"
    keyword_input = st.text_input("검색어", value=default_keywords)
    
    st.caption("🚫 제외어")
    exclude_input = st.text_input("제외할 단어", value="ㄹㅇㅋㄴ, 광고, 분양, 팝니다")
    
    st.markdown("---")
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Secret", type="password")
    run_btn = st.button("데이터 가져오기")

st.title(f"🏘️ '{keyword_input}' 커뮤니티 상황실")

# 게시글 리스트를 예쁘게 보여주는 함수 (반복 사용을 위해 함수로 뺌)
def render_feed(dataframe):
    if dataframe.empty:
        st.info("이 커뮤니티에는 최근 30일간 올라온 글이 없습니다.")
        return

    for i, row in dataframe.iterrows():
        with st.container():
            if row['postdate_dt'].year == 1900:
                date_str = "⚡ 최신 (날짜미상)"
                date_color = "red"
            else:
                date_str = row['postdate_dt'].strftime('%Y-%m-%d')
                date_color = "gray"
            
            # 위험 글 강조
            if "🚨" in row['risk_level']:
                title_prefix = "🚨 "
                border_color = "2px solid red"
            else:
                title_prefix = ""
                border_color = "1px solid #ddd"

            # 카드 형태로 출력
            st.markdown(f"**[{row['source']}]** <span style='color:{date_color}'>{date_str}</span>", unsafe_allow_html=True)
            st.markdown(f"##### {title_prefix}{row['clean_title']}")
            
            if "🚨" in row['risk_level']:
                    st.write(f"⚠️ **{row['risk_level']}**")
            
            st.caption(row['clean_desc'])
            st.markdown(f"[원문 보러가기]({row['link']})")
            st.divider()

if run_btn:
    if not client_id or not client_secret:
        st.error("⚠️ API 키를 입력해주세요.")
    else:
        df, logs = get_data_split_community(keyword_input, exclude_input, client_id, client_secret)
        
        with st.expander("ℹ️ 로그 확인"):
            if logs:
                for log in logs: st.write(log)

        if df is not None and not df.empty:
            
            # 요약 (전체 기준)
            col1, col2, col3 = st.columns(3)
            risk_count = len(df[df['risk_level'] != "일반"])
            
            # 최신 글 날짜
            latest_date = df.iloc[0]['postdate_dt']
            latest_str = "⚡ 방금 (날짜미상)" if latest_date.year == 1900 else latest_date.strftime('%Y-%m-%d')
                
            col1.metric("전체 수집 글", f"{len(df)}건")
            col2.metric("🚨 전체 이슈", f"{risk_count}건", delta_color="inverse")
            col3.metric("가장 최신 글", latest_str)
            
            st.markdown("---")
            
            # -----------------------------------------------------------
            # [핵심 기능] 탭으로 커뮤니티 나누기
            # -----------------------------------------------------------
            tab_all, tab_goda, tab_nyang, tab_kang, tab_aban, tab_stats = st.tabs([
                "🔥 전체 보기", 
                "😺 고양이라서 다행이야", 
                "😺 냥이네", 
                "🐶 강사모", 
                "🐶 아반강고",
                "📊 통계/다운로드"
            ])
            
            # 1. 전체 보기
            with tab_all:
                st.subheader("🔥 전체 커뮤니티 통합 (최신순)")
                render_feed(df)
            
            # 2. 고다
            with tab_goda:
                st.subheader("😺 고양이라서 다행이야 피드")
                df_goda = df[df['source'] == "고양이라서 다행이야"]
                render_feed(df_goda)
            
            # 3. 냥이네
            with tab_nyang:
                st.subheader("😺 냥이네 피드")
                df_nyang = df[df['source'] == "냥이네"]
                render_feed(df_nyang)
            
            # 4. 강사모
            with tab_kang:
                st.subheader("🐶 강사모 피드")
                df_kang = df[df['source'] == "강사모"]
                render_feed(df_kang)

            # 5. 아반강고
            with tab_aban:
                st.subheader("🐶 아반강고 피드")
                df_aban = df[df['source'] == "아반강고"]
                render_feed(df_aban)
                
            # 6. 통계 및 다운로드
            with tab_stats:
                st.subheader("📊 커뮤니티별 언급 비중")
                if not df.empty:
                    st.bar_chart(df['source'].value_counts())
                
                st.markdown("---")
                st.subheader("📥 데이터 다운로드")
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="통합 엑셀 다운로드 (전체)",
                    data=csv,
                    file_name="community_split_data.csv",
                    mime="text/csv",
                )
                
                st.markdown("---")
                st.subheader("📝 전체 데이터 표")
                
                display_df = df.copy()
                display_df['날짜'] = display_df['postdate_dt'].apply(lambda x: "⚡최신" if x.year == 1900 else x.strftime('%Y-%m-%d'))
                st.dataframe(
                    display_df[['날짜', 'source', 'clean_title', 'risk_level', 'link']],
                    column_config={"link": st.column_config.LinkColumn("링크")},
                    use_container_width=True
                )
        else:
            st.warning("조건에 맞는 데이터가 없습니다.")
