import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

# 1. 페이지 설정
st.set_page_config(
    page_title="Royal Canin Monitor (Fixed)",
    page_icon="🛠️",
    layout="wide"
)

# 2. HTML 태그 제거 함수
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

# 3. 데이터 수집 함수 (날짜 에러가 나도 절대 버리지 않음!)
def get_naver_data_robust(keyword, client_id, client_secret):
    if not client_id or not client_secret:
        return None, []
    
    categories = ["blog", "cafearticle"]
    all_data = []
    log_messages = [] # 화면에 띄울 로그
    
    # ---------------------------------------------------------
    # 진행 상황을 보여줄 공간 (Progress Bar 느낌)
    # ---------------------------------------------------------
    status_area = st.empty()
    
    for cat in categories:
        cat_name = "블로그" if cat == "blog" else "카페"
        
        # 5페이지(500개) 탐색
        for start_index in range(1, 500, 100):
            try:
                status_area.info(f"🏃‍♂️ {cat_name} {start_index}번째 글 긁어오는 중...")
                
                encText = urllib.parse.quote(keyword)
                url = f"https://openapi.naver.com/v1/search/{cat}?query={encText}&display=100&start={start_index}&sort=date"
                
                request = urllib.request.Request(url)
                request.add_header("X-Naver-Client-Id", client_id)
                request.add_header("X-Naver-Client-Secret", client_secret)
                
                response = urllib.request.urlopen(request)
                
                if response.getcode() == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    items = data['items']
                    
                    if not items:
                        log_messages.append(f"⚠️ {cat_name}: 더 이상 데이터가 없어서 멈춤 (Page {start_index})")
                        break

                    for item in items:
                        # [핵심 수정] 날짜 변환 실패해도 글을 버리지 않음!
                        try:
                            # postdate가 없으면 오늘 날짜로 대체
                            raw_date = item.get('postdate', '')
                            if raw_date:
                                p_date = pd.to_datetime(raw_date, format='%Y%m%d')
                            else:
                                p_date = datetime.datetime.now() # 날짜 없으면 현재 시간
                        except:
                            p_date = datetime.datetime.now() # 에러 나도 현재 시간으로 땜빵
                        
                        # 카페 이름 처리
                        raw_name = item.get('cafename', '')
                        
                        if cat == "blog":
                            source_label = "네이버 블로그"
                        else:
                            # 이름 매칭
                            if "고양이라서 다행이야" in raw_name or "고다" in raw_name: source_label = "고양이라서 다행이야"
                            elif "강사모" in raw_name: source_label = "강사모"
                            elif "아반강고" in raw_name: source_label = "아반강고"
                            elif "냥이네" in raw_name: source_label = "냥이네"
                            else: source_label = f"기타 카페 ({raw_name})"
                        
                        item['source'] = source_label
                        item['clean_title'] = clean_html(item['title'])
                        item['clean_desc'] = clean_html(item['description'])
                        item['postdate_dt'] = p_date
                        all_data.append(item)
                else:
                    log_messages.append(f"❌ {cat_name} API 호출 실패 (Code: {response.getcode()})")
                    break
            except Exception as e:
                log_messages.append(f"❌ {cat_name} 에러 발생: {e}")
                break
                
    status_area.success("✅ 수집 끝!")
    
    if not all_data:
        return pd.DataFrame(), log_messages

    df = pd.DataFrame(all_data)
    
    # 위험 키워드
    risk_keywords = ['구더기', '벌레', '이물질', '식약처', '신고', '환불', '토해', '설사', '혈변', '곰팡이', '리콜']
    df['risk_level'] = df['clean_desc'].apply(lambda x: "🚨 심각/주의" if any(k in x for k in risk_keywords) else "일반")
    
    # 중복 제거 (제목 기준)
    df = df.drop_duplicates(['clean_title'])
    # 날짜순 정렬
    df = df.sort_values(by='postdate_dt', ascending=False)
    
    return df[['postdate_dt', 'source', 'clean_title', 'clean_desc', 'risk_level', 'link']], log_messages

# 4. 메인 화면 UI
with st.sidebar:
    st.header("⚙️ 튼튼한 모니터링")
    # [중요] 기본 검색어를 짧게 설정 (길면 결과 0개일 확률 높음)
    keyword = st.text_input("검색어", value="로얄캐닌")
    
    st.markdown("---")
    st.caption("보고 싶은 채널")
    all_options = ["네이버 블로그", "고양이라서 다행이야", "냥이네", "아반강고", "강사모"]
    target_filter = st.multiselect("채널 선택", all_options, default=all_options)
    
    st.markdown("---")
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Secret", type="password")
    run_btn = st.button("데이터 수집 시작")

st.title(f"🔍 '{keyword}' 정밀 분석기")

if run_btn:
    if not client_id or not client_secret:
        st.error("⚠️ API 키를 입력해주세요.")
    else:
        # 데이터 수집
        df, logs = get_naver_data_robust(keyword, client_id, client_secret)
        
        # 1. 수집 로그 보여주기 (문제가 있으면 여기서 보임)
        with st.expander("📜 수집 로그 (여기를 눌러 확인하세요)", expanded=False):
            for log in logs:
                st.write(log)
            if not logs:
                st.write("특이사항 없이 깔끔하게 수집되었습니다.")

        # 2. 결과 표시
        if df is not None and not df.empty:
            # 필터링
            if target_filter:
                filtered_df = df[df['source'].isin(target_filter)]
            else:
                filtered_df = df
            
            # 요약
            col1, col2, col3 = st.columns(3)
            risk_count = len(filtered_df[filtered_df['risk_level'] == "🚨 심각/주의"])
            if not filtered_df.empty:
                top_src = filtered_df['source'].mode()[0]
            else:
                top_src = "-"
                
            col1.metric("표시된 글", f"{len(filtered_df)}건")
            col2.metric("이슈 글", f"{risk_count}건", delta_color="inverse")
            col3.metric("최다 출처", top_src)
            
            st.markdown("---")
            
            # 탭
            tab1, tab2, tab3 = st.tabs(["🔥 리스크 피드", "📊 채널 차트", "📝 전체 리스트"])
            
            with tab1:
                risk_df = filtered_df[filtered_df['risk_level'] == "🚨 심각/주의"]
                if risk_df.empty:
                    st.success("발견된 위험 글이 없습니다.")
                else:
                    for i, row in risk_df.iterrows():
                        with st.container():
                            icon = "🅱️" if "블로그" in row['source'] else "☕"
                            st.error(f"**{icon} [{row['source']}] {row['postdate_dt'].date()}** | {row['clean_title']}")
                            st.caption(row['clean_desc'])
                            st.markdown(f"[원문 이동]({row['link']})")
                            st.divider()
            
            with tab2:
                if not filtered_df.empty:
                    st.bar_chart(filtered_df['source'].value_counts())
                else:
                    st.write("표시할 데이터가 없습니다.")

            with tab3:
                display = filtered_df.copy()
                display['날짜'] = display['postdate_dt'].dt.date
                st.dataframe(
                    display[['날짜', 'source', 'clean_title', 'risk_level', 'link']],
                    column_config={"link": st.column_config.LinkColumn("링크")},
                    use_container_width=True
                )
        else:
            st.error("수집된 데이터가 0건입니다. (검색어를 '로얄캐닌'으로 짧게 줄여보세요)")
