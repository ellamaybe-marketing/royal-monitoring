import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

# 1. 페이지 설정
st.set_page_config(
    page_title="Royal Canin Deep Monitor",
    page_icon="📡",
    layout="wide"
)

# 2. HTML 태그 제거 함수
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

# 3. 데이터 수집 함수 (1000개까지 깊게 탐색 + 버리는 데이터 없음)
def get_data_deep_scan(keyword_string, exclude_string, client_id, client_secret):
    if not client_id or not client_secret:
        return None, []
    
    keywords = [k.strip() for k in keyword_string.split(',') if k.strip()]
    excludes = [e.strip() for e in exclude_string.split(',') if e.strip()]
    
    category = "cafearticle"
    all_data = []
    log_messages = []
    
    status_area = st.empty()
    progress_bar = st.progress(0)
    
    # 30일 유통기한
    now = datetime.datetime.now()
    cutoff_date = now - datetime.timedelta(days=30)
    
    # [설정] 최대 탐색 페이지 수 (10페이지 = 1000개)
    # 누락을 막기 위해 범위를 대폭 늘렸습니다.
    MAX_PAGES = 10 
    
    total_keywords = len(keywords)
    
    for k_idx, search_term in enumerate(keywords):
        for page in range(1, MAX_PAGES + 1):
            # 진행률 표시
            start_index = (page - 1) * 100 + 1
            progress = (k_idx * MAX_PAGES + page) / (total_keywords * MAX_PAGES)
            progress_bar.progress(min(progress, 1.0))
            
            try:
                status_area.info(f"📡 '{search_term}' {start_index}~{start_index+99}번째 글 스캔 중...")
                
                query_str = search_term
                if excludes:
                    for exc in excludes:
                        query_str += f" -{exc}"
                
                encText = urllib.parse.quote(query_str)
                # sort=date (최신순 요청)
                url = f"https://openapi.naver.com/v1/search/{category}?query={encText}&display=100&start={start_index}&sort=date"
                
                request = urllib.request.Request(url)
                request.add_header("X-Naver-Client-Id", client_id)
                request.add_header("X-Naver-Client-Secret", client_secret)
                
                response = urllib.request.urlopen(request)
                
                if response.getcode() == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    items = data['items']
                    
                    if not items: break # 더 이상 글이 없으면 다음 키워드로

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
                        
                        # 30일 지난 글 제외
                        if p_date.year > 2000 and p_date < cutoff_date:
                            continue 
                        
                        # 커뮤니티 분류 (4대장 + 기타)
                        raw_name = item.get('cafename', '')
                        is_target = False
                        
                        if "고양이라서 다행이야" in raw_name or "고다" in raw_name: 
                            source_label = "고양이라서 다행이야"
                            is_target = True
                        elif "강사모" in raw_name: 
                            source_label = "강사모"
                            is_target = True
                        elif "아반강고" in raw_name: 
                            source_label = "아반강고"
                            is_target = True
                        elif "냥이네" in raw_name: 
                            source_label = "냥이네"
                            is_target = True
                        else: 
                            # 누락 확인을 위해 '기타'도 일단 수집은 함 (화면에서 분리)
                            source_label = f"기타 ({raw_name})"
                            is_target = False

                        item['source'] = source_label
                        item['is_target'] = is_target # 4대 커뮤니티 여부 태그
                        item['clean_title'] = clean_html(item['title'])
                        item['clean_desc'] = clean_html(item['description'])
                        item['postdate_dt'] = p_date
                        item['search_keyword'] = "로얄캐닌"
                        
                        all_data.append(item)
                else:
                    break
            except Exception as e:
                log_messages.append(f"❌ 에러: {e}")
                break
    
    status_area.success(f"✅ 스캔 완료! 총 {len(all_data)}개 글을 확보했습니다.")
    progress_bar.empty()
    
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
    
    # [정렬] 날짜순 (1900년은 최신으로)
    df['sort_helper'] = df['postdate_dt'].apply(lambda x: now if x.year == 1900 else x)
    df = df.sort_values(by='sort_helper', ascending=False)
    
    # [중복 제거]
    df = df.drop_duplicates(['clean_title'], keep='first')
    
    return df[['postdate_dt', 'source', 'is_target', 'clean_title', 'clean_desc', 'risk_level', 'link', 'search_keyword', 'sort_helper']], log_messages

# 4. UI 구성
with st.sidebar:
    st.header("📡 딥 스캔 모니터링")
    st.caption("누락 방지를 위해 더 깊게(10페이지) 검색합니다.")
    
    default_keywords = "로얄캐닌, 로캐, 로케"
    keyword_input = st.text_input("검색어", value=default_keywords)
    
    exclude_input = st.text_input("제외어", value="ㄹㅇㅋㄴ, 광고, 분양, 팝니다")
    
    st.markdown("---")
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Secret", type="password")
    run_btn = st.button("정밀 분석 시작")

st.title(f"📡 '{keyword_input}' 정밀 타임라인")

# 피드 렌더링 함수 (무조건 재정렬)
def render_feed(dataframe):
    if dataframe.empty:
        st.warning("표시할 데이터가 없습니다.")
        return

    # 화면에 그리기 직전에 다시 한번 정렬 (탭 간 이동 시 꼬임 방지)
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
        df, logs = get_data_deep_scan(keyword_input, exclude_input, client_id, client_secret)
        
        with st.expander("ℹ️ 로그 확인"):
            if logs:
                for log in logs: st.write(log)

        if df is not None and not df.empty:
            
            # 4대 커뮤니티 데이터만 필터링
            target_df = df[df['is_target'] == True]
            # 기타 데이터 (누락 확인용)
            other_df = df[df['is_target'] == False]
            
            col1, col2, col3 = st.columns(3)
            risk_count = len(target_df[target_df['risk_level'] != "일반"])
            
            if not target_df.empty:
                latest_date = target_df.iloc[0]['postdate_dt']
                latest_str = "⚡ 방금" if latest_date.year == 1900 else latest_date.strftime('%Y-%m-%d')
            else:
                latest_str = "-"
                
            col1.metric("4대 커뮤니티 글", f"{len(target_df)}건")
            col2.metric("🚨 이슈 발견", f"{risk_count}건", delta_color="inverse")
            col3.metric("가장 최신 글", latest_str)
            
            st.markdown("---")
            
            # 탭 구성 (기타 탭 추가됨!)
            tabs = st.tabs([
                "🔥 전체 (4대장)", 
                "😺 고다", 
                "😺 냥이네", 
                "🐶 강사모", 
                "🐶 아반강고",
                "🗑️ 기타/제외된 글 (누락확인)" 
            ])
            
            # 1. 전체 (4대 커뮤니티만)
            with tabs[0]:
                render_feed(target_df)
            
            # 2. 고다
            with tabs[1]:
                render_feed(target_df[target_df['source'] == "고양이라서 다행이야"])
            
            # 3. 냥이네
            with tabs[2]:
                render_feed(target_df[target_df['source'] == "냥이네"])
            
            # 4. 강사모
            with tabs[3]:
                render_feed(target_df[target_df['source'] == "강사모"])

            # 5. 아반강고
            with tabs[4]:
                render_feed(target_df[target_df['source'] == "아반강고"])
            
            # 6. 기타 (누락된 게 여기 있나 확인용)
            with tabs[5]:
                st.warning("👇 여기는 4대 커뮤니티가 아니라서 메인 화면에서 제외된 글들입니다.")
                st.info("만약 '고다' 글인데 여기에 와있다면, 카페 이름 인식이 잘못된 것입니다.")
                render_feed(other_df)

        else:
            st.warning("수집된 데이터가 없습니다.")
