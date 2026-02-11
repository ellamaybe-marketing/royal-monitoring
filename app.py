import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

# 1. 페이지 설정
st.set_page_config(
    page_title="Royal Canin 4-Major Monitor",
    page_icon="🛡️",
    layout="wide"
)

# 2. HTML 태그 제거 함수
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

# 3. 데이터 수집 함수 (4대 커뮤니티 외에는 가차 없이 버림)
def get_data_strict_4_communities(keyword_string, exclude_string, client_id, client_secret):
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
    
    # [1] 데이터 수집
    for idx, search_term in enumerate(keywords):
        for start_index in range(1, 300, 100):
            try:
                status_area.info(f"🛡️ ({idx+1}/{len(keywords)}) '{search_term}' 정밀 탐색 중...")
                
                query_str = search_term
                if excludes:
                    for exc in excludes:
                        query_str += f" -{exc}"
                
                encText = urllib.parse.quote(query_str)
                # API에게 최신순 요청
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
                        
                        # -----------------------------------------------------------
                        # [핵심] 4대 커뮤니티 필터링 (여기에 없으면 데이터에 넣지도 않음)
                        # -----------------------------------------------------------
                        raw_name = item.get('cafename', '')
                        source_label = None
                        
                        # 포함 단어로 유연하게 매칭
                        if "고양이라서 다행이야" in raw_name or "고다" in raw_name: 
                            source_label = "고양이라서 다행이야"
                        elif "강사모" in raw_name: # 강사모-반려견... 등등 다 잡음
                            source_label = "강사모"
                        elif "아반강고" in raw_name: 
                            source_label = "아반강고"
                        elif "냥이네" in raw_name: 
                            source_label = "냥이네"
                        
                        # source_label이 None이면(4대장이 아니면) -> 저장 안 하고 넘어감 (Skip)
                        if source_label is None:
                            continue

                        item['source'] = source_label
                        item['clean_title'] = clean_html(item['title'])
                        item['clean_desc'] = clean_html(item['description'])
                        item['postdate_dt'] = p_date
                        item['search_keyword'] = "로얄캐닌" # 키워드 통합
                        
                        all_data.append(item)
                else:
                    break
            except Exception as e:
                log_messages.append(f"❌ 에러: {e}")
                break
    
    status_area.success(f"✅ 4대 커뮤니티 데이터 {len(all_data)}건 확보 완료!")
    
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
    # 1900년(날짜없음)을 '현재'로 치환해서 최상단으로 올림
    df['sort_helper'] = df['postdate_dt'].apply(lambda x: now if x.year == 1900 else x)
    
    # 1차 정렬 (최신순)
    df = df.sort_values(by='sort_helper', ascending=False)
    
    # 중복 제거 (가장 최신의 것을 남김)
    df = df.drop_duplicates(['clean_title'], keep='first')
    
    return df[['postdate_dt', 'source', 'clean_title', 'clean_desc', 'risk_level', 'link', 'search_keyword', 'sort_helper']], log_messages

# 4. UI 구성
with st.sidebar:
    st.header("🛡️ 4대 커뮤니티 전용")
    
    default_keywords = "로얄캐닌, 로캐, 로케"
    keyword_input = st.text_input("검색어", value=default_keywords)
    
    st.caption("🚫 제외어")
    exclude_input = st.text_input("제외할 단어", value="ㄹㅇㅋㄴ, 광고, 분양, 팝니다")
    
    st.markdown("---")
    st.info("⚠️ 이 모드는 '고다, 냥이네, 강사모, 아반강고' 글만 보여줍니다. 다른 잡다한 카페 글은 자동으로 삭제됩니다.")
    
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Secret", type="password")
    run_btn = st.button("분석 시작")

st.title(f"🛡️ '{keyword_input}' 커뮤니티 집중 분석")

# 게시글 리스트 함수 (정렬 강제 적용)
def render_feed_strictly_sorted(dataframe):
    if dataframe.empty:
        st.info("이 커뮤니티에는 조건에 맞는 글이 없습니다.")
        return

    # [핵심] 여기서 한 번 더 날짜순으로 줄을 세워버림 (절대 섞이지 않게)
    # sort_helper 기준 내림차순
    sorted_df = dataframe.sort_values(by='sort_helper', ascending=False)

    for i, row in sorted_df.iterrows():
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
        df, logs = get_data_strict_4_communities(keyword_input, exclude_input, client_id, client_secret)
        
        with st.expander("ℹ️ 로그 확인"):
            if logs:
                for log in logs: st.write(log)

        if df is not None and not df.empty:
            
            col1, col2, col3 = st.columns(3)
            risk_count = len(df[df['risk_level'] != "일반"])
            
            # 최신 글 날짜 (정렬 후 0번째)
            if not df.empty:
                latest_date = df.iloc[0]['postdate_dt']
                latest_str = "⚡ 방금" if latest_date.year == 1900 else latest_date.strftime('%Y-%m-%d')
            else:
                latest_str = "-"
                
            col1.metric("4대 커뮤니티 수집", f"{len(df)}건")
            col2.metric("🚨 이슈 글", f"{risk_count}건", delta_color="inverse")
            col3.metric("가장 최신 글", latest_str)
            
            st.markdown("---")
            
            # 탭 구성
            tab_all, tab_goda, tab_nyang, tab_kang, tab_aban, tab_stats = st.tabs([
                "🔥 전체 보기 (최신순)", 
                "😺 고다", 
                "😺 냥이네", 
                "🐶 강사모", 
                "🐶 아반강고",
                "📊 다운로드"
            ])
            
            # 1. 전체 보기
            with tab_all:
                st.caption("4대 커뮤니티의 모든 글을 시간순으로 보여줍니다.")
                render_feed_strictly_sorted(df)
            
            # 2. 고다
            with tab_goda:
                df_goda = df[df['source'] == "고양이라서 다행이야"]
                render_feed_strictly_sorted(df_goda)
            
            # 3. 냥이네
            with tab_nyang:
                df_nyang = df[df['source'] == "냥이네"]
                render_feed_strictly_sorted(df_nyang)
            
            # 4. 강사모
            with tab_kang:
                df_kang = df[df['source'] == "강사모"]
                render_feed_strictly_sorted(df_kang)

            # 5. 아반강고
            with tab_aban:
                df_aban = df[df['source'] == "아반강고"]
                render_feed_strictly_sorted(df_aban)
                
            # 6. 다운로드
            with tab_stats:
                st.subheader("📥 엑셀 다운로드")
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="통합 데이터 다운로드",
                    data=csv,
                    file_name="4_communities_monitoring.csv",
                    mime="text/csv",
                )
                
                st.markdown("---")
                st.subheader("📊 커뮤니티 비중")
                st.bar_chart(df['source'].value_counts())

        else:
            st.warning("조건에 맞는 4대 커뮤니티 글이 없습니다.")
