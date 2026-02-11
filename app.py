import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

# 1. 페이지 설정
st.set_page_config(
    page_title="Total Monitor (Blog + Cafe)",
    page_icon="🔎",
    layout="wide"
)

# 2. HTML 태그 제거 함수
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

# 3. 데이터 수집 함수 (긴 이름 매핑 로직 강화)
def get_naver_data_integrated(keyword, client_id, client_secret):
    if not client_id or not client_secret:
        return None, 0, 0
    
    categories = ["blog", "cafearticle"]
    all_data = []
    
    # 최근 30일 데이터 조회 (카페 글 확보를 위해 넉넉하게)
    today = datetime.datetime.now()
    cutoff_date = today - datetime.timedelta(days=30)
    
    count_blog = 0
    count_cafe = 0
    
    status_text = st.empty() 
    
    for cat in categories:
        # 5페이지(500개)까지 탐색
        for start_index in range(1, 500, 100):
            try:
                cat_name_kr = "블로그" if cat == "blog" else "카페"
                status_text.text(f"🔍 {cat_name_kr} 데이터를 {start_index}번부터 찾는 중...")
                
                encText = urllib.parse.quote(keyword)
                url = f"https://openapi.naver.com/v1/search/{cat}?query={encText}&display=100&start={start_index}&sort=date"
                
                request = urllib.request.Request(url)
                request.add_header("X-Naver-Client-Id", client_id)
                request.add_header("X-Naver-Client-Secret", client_secret)
                
                response = urllib.request.urlopen(request)
                
                if response.getcode() == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    items = data['items']
                    
                    if not items: break

                    for item in items:
                        # 날짜 체크
                        try:
                            p_date = pd.to_datetime(item['postdate'], format='%Y%m%d')
                        except:
                            continue
                        
                        if p_date < cutoff_date:
                            continue 
                        
                        # ---------------------------------------------------------
                        # [핵심] 긴 카페 이름을 깔끔하게 정리하는 부분
                        # ---------------------------------------------------------
                        raw_name = item.get('cafename', '') # API가 주는 원본 이름 (엄청 김)
                        
                        if cat == "blog":
                            source_label = "네이버 블로그"
                            count_blog += 1
                        else:
                            count_cafe += 1
                            # API 원본 이름에 특정 단어가 포함되어 있으면 짧은 이름으로 변경
                            
                            # 1. 강사모 (원본: 강사모-반려견 훈련 교육법, 강아지 종류...)
                            if "강사모" in raw_name: 
                                source_label = "강사모"
                            
                            # 2. 냥이네 (원본: 냥이네-고양이를 사랑하는 모임,길 고...)
                            elif "냥이네" in raw_name: 
                                source_label = "냥이네"
                            
                            # 3. 아반강고 (원본: 아반강고 힐링카페 아픈 반려 강아지와...)
                            elif "아반강고" in raw_name: 
                                source_label = "아반강고"
                            
                            # 4. 고다 (원본: 고양이라서 다행이야)
                            elif "고양이라서 다행이야" in raw_name: 
                                source_label = "고양이라서 다행이야"
                                
                            else: 
                                # 4대 카페가 아니면 '기타'로 표시하되, 괄호 안에 원본 이름 표시
                                source_label = f"기타 카페 ({raw_name})"
                        
                        item['source'] = source_label
                        item['clean_title'] = clean_html(item['title'])
                        item['clean_desc'] = clean_html(item['description'])
                        item['postdate_dt'] = p_date
                        all_data.append(item)
                else:
                    break
            except Exception as e:
                print(f"Error: {e}")
                break
                
    status_text.empty()
    
    if not all_data:
        return pd.DataFrame(), count_blog, count_cafe

    df = pd.DataFrame(all_data)
    
    # 위험 키워드
    risk_keywords = ['구더기', '벌레', '이물질', '식약처', '신고', '환불', '토해', '설사', '혈변', '곰팡이', '리콜', '배신', '실망']
    df['risk_level'] = df['clean_desc'].apply(lambda x: "🚨 심각/주의" if any(k in x for k in risk_keywords) else "일반")
    
    df = df.drop_duplicates(['clean_title'])
    df = df.sort_values(by='postdate_dt', ascending=False)
    
    return df[['postdate_dt', 'source', 'clean_title', 'clean_desc', 'risk_level', 'link']], count_blog, count_cafe

# 4. 메인 화면 UI
with st.sidebar:
    st.header("⚙️ 통합 모니터링")
    keyword = st.text_input("검색어", value="로얄캐닌")
    
    st.markdown("---")
    st.caption("보고 싶은 채널 필터")
    
    # 필터 옵션도 깔끔한 이름으로 통일
    all_options = ["네이버 블로그", "고양이라서 다행이야", "냥이네", "아반강고", "강사모"]
    target_filter = st.multiselect(
        "채널 선택 (기타 카페는 자동 제외됨)",
        all_options,
        default=all_options 
    )
    
    st.markdown("---")
    st.info("API 키 입력")
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Secret", type="password")
    
    run_btn = st.button("데이터 수집 시작")

st.title(f"👀 '{keyword}' 여론 분석 (최근 30일)")

if run_btn:
    if not client_id or not client_secret:
        st.error("⚠️ API 키를 입력해주세요.")
    else:
        with st.spinner("블로그와 카페를 정밀 분석 중..."):
            df, c_blog, c_cafe = get_naver_data_integrated(keyword, client_id, client_secret)

        # 진단 메시지
        if c_cafe == 0 and c_blog > 0:
             st.warning(f"⚠️ 블로그 글({c_blog}개)은 찾았으나, 카페 글은 0개입니다. (검색어 관련 최근 30일 카페 글 없음)")
        elif c_cafe == 0 and c_blog == 0:
             st.error("검색 결과가 없습니다. API 키와 검색어를 확인하세요.")
        else:
             st.success(f"✅ 분석 완료! (블로그: {c_blog}건 / 카페: {c_cafe}건)")

        if df is not None and not df.empty:
            # 필터링 적용 (사용자가 선택한 깔끔한 이름 기준)
            if target_filter:
                filtered_df = df[df['source'].isin(target_filter)]
            else:
                filtered_df = df
            
            if filtered_df.empty:
                st.warning("수집된 데이터는 있으나, 필터 설정 때문에 화면에 보이지 않습니다. 필터를 확인해주세요.")
            else:
                # 요약 지표
                col1, col2, col3 = st.columns(3)
                risk_count = len(filtered_df[filtered_df['risk_level'] == "🚨 심각/주의"])
                
                # 최빈값 에러 방지
                if not filtered_df.empty:
                    top_source = filtered_df['source'].mode()[0]
                else:
                    top_source = "-"
                
                col1.metric("표시된 게시글", f"{len(filtered_df)}건")
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
                    # 링크 컬럼 설정
                    st.dataframe(
                        display_df[['날짜', 'source', 'clean_title', 'risk_level', 'link']],
                        column_config={"link": st.column_config.LinkColumn("링크")},
                        use_container_width=True
                    )
