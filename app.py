import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

# 1. 페이지 설정
st.set_page_config(
    page_title="Total Monitor (Blog + Cafe)",
    page_icon="👀",
    layout="wide"
)

# 2. HTML 태그 제거 함수
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

# 3. 데이터 수집 함수
def get_naver_data_integrated(keyword, client_id, client_secret):
    if not client_id or not client_secret:
        return None
    
    # [수정] 블로그(blog)와 카페(cafearticle) 모두 검색
    categories = ["blog", "cafearticle"]
    all_data = []
    
    today = datetime.datetime.now()
    cutoff_date = today - datetime.timedelta(days=7) # 최근 7일
    
    status_text = st.empty() 
    
    for cat in categories:
        # 최대 10페이지(1000개)까지 수집
        for start_index in range(1, 1000, 100):
            try:
                cat_name_kr = "블로그" if cat == "blog" else "카페"
                status_text.text(f"🔍 {cat_name_kr} 데이터를 {start_index}번부터 가져오는 중...")
                
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
                        break 

                    temp_list = []
                    stop_flag = False
                    
                    for item in items:
                        # 날짜 변환
                        try:
                            p_date = pd.to_datetime(item['postdate'], format='%Y%m%d')
                        except:
                            continue
                            
                        if p_date < cutoff_date:
                            stop_flag = True
                            continue 
                        
                        # [핵심] 출처 분류 로직 (블로그 vs 카페 이름)
                        if cat == "blog":
                            source_label = "네이버 블로그"
                        else:
                            # 카페 이름 매칭
                            raw_name = item.get('cafename', '')
                            if "고양이라서 다행이야" in raw_name: source_label = "고양이라서 다행이야"
                            elif "강사모" in raw_name: source_label = "강사모"
                            elif "아반강고" in raw_name: source_label = "아반강고"
                            elif "냥이네" in raw_name: source_label = "냥이네"
                            else: source_label = f"기타 카페 ({raw_name})"
                        
                        item['source'] = source_label
                        item['clean_title'] = clean_html(item['title'])
                        item['clean_desc'] = clean_html(item['description'])
                        item['postdate_dt'] = p_date
                        temp_list.append(item)
                    
                    all_data.extend(temp_list)
                    
                    if stop_flag or len(items) < 100:
                        break
                else:
                    break
            
            except Exception as e:
                print(f"Error: {e}")
                break
                
    status_text.empty()
    
    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data)
    
    # 위험 키워드 분석
    risk_keywords = ['구더기', '벌레', '이물질', '식약처', '신고', '환불', '토해', '설사', '혈변', '곰팡이', '리콜', '배신']
    df['risk_level'] = df['clean_desc'].apply(lambda x: "🚨 심각/주의" if any(k in x for k in risk_keywords) else "일반")
    
    # 중복 제거 및 정렬
    df = df.drop_duplicates(['clean_title'])
    df = df.sort_values(by='postdate_dt', ascending=False)
    
    return df[['postdate_dt', 'source', 'clean_title', 'clean_desc', 'risk_level', 'link']]

# 4. 메인 화면 UI
with st.sidebar:
    st.header("⚙️ 통합 모니터링 설정")
    keyword = st.text_input("검색어", value="로얄캐닌")
    
    st.markdown("---")
    st.caption("필터 (기본값: 블로그+4대카페 전체)")
    
    # [수정] 기본 선택값(default)에 '네이버 블로그'를 포함시켰습니다!
    all_options = ["네이버 블로그", "고양이라서 다행이야", "냥이네", "아반강고", "강사모"]
    target_filter = st.multiselect(
        "보고 싶은 채널 선택",
        all_options,
        default=all_options 
    )
    
    st.markdown("---")
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Secret", type="password")
    run_btn = st.button("데이터 수집 시작")

st.title(f"👀 '{keyword}' 블로그 & 카페 통합 분석")

if run_btn:
    if not client_id or not client_secret:
        st.error("⚠️ 왼쪽 사이드바에 API 키를 입력해주세요!")
    else:
        with st.spinner("블로그와 커뮤니티를 모두 훑어보는 중..."):
            df = get_naver_data_integrated(keyword, client_id, client_secret)

        if df is not None and not df.empty:
            # 필터링 적용
            if target_filter:
                # 선택한 채널이거나, 선택한 채널 목록에 없는 '기타' 카페인 경우 (옵션)
                # 여기서는 명확하게 선택한 것만 보여줍니다.
                filtered_df = df[df['source'].isin(target_filter)]
            else:
                filtered_df = df
            
            if filtered_df.empty:
                 st.warning("조건에 맞는 글이 없습니다.")
            else:
                # 요약 지표
                col1, col2, col3 = st.columns(3)
                risk_count = len(filtered_df[filtered_df['risk_level'] == "🚨 심각/주의"])
                top_source = filtered_df['source'].mode()[0]
                
                col1.metric("수집된 글", f"{len(filtered_df)}건")
                col2.metric("위험(이슈) 글", f"{risk_count}건", delta_color="inverse")
                col3.metric("최다 언급", top_source)
                
                st.markdown("---")

                # 탭 구성
                tab1, tab2, tab3 = st.tabs(["🔥 위험글(Risk)", "📊 채널별 비중", "📝 전체 리스트"])
                
                with tab1:
                    risk_df = filtered_df[filtered_df['risk_level'] == "🚨 심각/주의"]
                    if risk_df.empty:
                        st.success("✅ 감지된 위험 이슈가 없습니다.")
                    else:
                        for i, row in risk_df.iterrows():
                            with st.container():
                                # 블로그는 파란색, 카페는 붉은색 계열 느낌으로 구분 (여기선 아이콘으로 구분)
                                icon = "🅱️" if "블로그" in row['source'] else "☕"
                                st.error(f"**{icon} [{row['source']}] {row['postdate_dt'].date()}** | {row['clean_title']}")
                                st.write(row['clean_desc'])
                                st.markdown(f"[원문 보러가기]({row['link']})")
                                st.divider()

                with tab2:
                    st.bar_chart(filtered_df['source'].value_counts())

                with tab3:
                    display_df = filtered_df.copy()
                    display_df['날짜'] = display_df['postdate_dt'].dt.date
                    st.dataframe(
                        display_df[['날짜', 'source', 'clean_title', 'risk_level', 'link']],
                        column_config={"link": st.column_config.LinkColumn("링크")},
                        use_container_width=True
                    )
        else:
            st.warning("검색 결과가 없습니다. API 설정을 확인해주세요.")
else:
    st.info("👈 API 키 입력 후 버튼을 눌러주세요.")
