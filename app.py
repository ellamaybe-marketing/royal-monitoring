import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="Community Monitor",
    page_icon="🐾",
    layout="wide"
)

# 2. HTML 태그 제거 함수
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

# 3. 데이터 수집 함수 (에러 방지 로직 강화)
def get_naver_data_communities(keyword, client_id, client_secret):
    if not client_id or not client_secret:
        return None
    
    # 검색 대상: 카페(cafearticle), 블로그(blog)
    categories = ["cafearticle", "blog"]
    all_data = []
    
    today = datetime.datetime.now()
    cutoff_date = today - datetime.timedelta(days=7) # 최근 7일치
    
    # 진행 상황 표시
    status_text = st.empty() 
    
    for cat in categories:
        # 최대 10페이지(1000개)까지만 수집
        for start_index in range(1, 1000, 100):
            
            # [중요] try-except 구문을 가장 안전하게 배치
            try:
                status_text.text(f"🔍 {cat} 데이터를 {start_index}번부터 가져오는 중...")
                
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
                        break # 데이터 없으면 다음 카테고리로

                    temp_list = []
                    stop_flag = False
                    
                    for item in items:
                        # 날짜 변환 시도
                        try:
                            p_date = pd.to_datetime(item['postdate'], format='%Y%m%d')
                        except:
                            continue # 날짜 형식이 이상하면 건너뜀 (여기 except는 필수)
                            
                        # 7일 지난 데이터면 그만 수집
                        if p_date < cutoff_date:
                            stop_flag = True
                            continue 
                        
                        # 커뮤니티 이름 정리
                        raw_name = item.get('cafename', '')
                        source_label = "기타"
                        
                        if cat == "blog":
                            source_label = "블로그"
                        else:
                            if "고양이라서 다행이야" in raw_name: source_label = "고다 (고양이라서 다행이야)"
                            elif "냥이네" in raw_name: source_label = "냥이네"
                            elif "아반강고" in raw_name or "아픈 반려" in raw_name: source_label = "아반강고"
                            elif "강사모" in raw_name or "강아지를 사랑하는 모임" in raw_name: source_label = "강사모"
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
                # 에러가 나면 화면에 보여주고 멈춤 (여기가 있어야 SyntaxError가 안 남)
                print(f"Error: {e}")
                break
                
    status_text.empty() # 로딩 문구 삭제
    
    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data)
    
    # 위험 키워드 분석
    risk_keywords = ['구더기', '벌레', '이물질', '식약처', '신고', '환불', '토해', '설사', '혈변', '곰팡이']
    df['risk_level'] = df['clean_desc'].apply(lambda x: "🚨 심각/주의" if any(k in x for k in risk_keywords) else "일반")
    
    # 중복 제거 및 정렬
    df = df.drop_duplicates(['clean_title'])
    df = df.sort_values(by='postdate_dt', ascending=False)
    
    return df[['postdate_dt', 'source', 'clean_title', 'clean_desc', 'risk_level', 'link']]

# 4. 메인 화면 UI
with st.sidebar:
    st.header("⚙️ 모니터링 설정")
    keyword = st.text_input("검색어", value="로얄캐닌")
    
    st.markdown("---")
    st.caption("보고 싶은 커뮤니티 필터")
    target_filter = st.multiselect(
        "선택 (비워두면 전체 보기)",
        ["고다 (고양이라서 다행이야)", "냥이네", "아반강고", "강사모", "블로그"],
        default=["고다 (고양이라서 다행이야)", "냥이네", "아반강고", "강사모"]
    )
    
    st.markdown("---")
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Secret", type="password")
    run_btn = st.button("데이터 수집 시작")

st.title(f"🐾 '{keyword}' 커뮤니티 여론 분석")

if run_btn:
    if not client_id or not client_secret:
        st.error("⚠️ 왼쪽 사이드바에 API 키를 입력해주세요!")
    else:
        with st.spinner("데이터를 수집하고 분석 중입니다..."):
            df = get_naver_data_communities(keyword, client_id, client_secret)

        if df is not None and not df.empty:
            # 필터링 적용
            if target_filter:
                # 사용자가 선택한 커뮤니티만 남기기 (기타 포함 로직은 복잡하니 단순화)
                filtered_df = df[df['source'].isin(target_filter)]
                # 만약 필터 결과가 너무 적으면 '기타'도 보여줄지 고민해봐야 함
            else:
                filtered_df = df
            
            # 요약 지표
            col1, col2, col3 = st.columns(3)
            risk_count = len(filtered_df[filtered_df['risk_level'] == "🚨 심각/주의"])
            top_source = filtered_df['source'].mode()[0] if not filtered_df.empty else "-"
            
            col1.metric("조회된 게시글", f"{len(filtered_df)}건")
            col2.metric("위험(이슈) 글", f"{risk_count}건", delta_color="inverse")
            col3.metric("최다 언급", top_source)
            
            st.markdown("---")

            # 탭 구성
            tab1, tab2, tab3 = st.tabs(["🔥 위험글(Risk)", "📊 커뮤니티 비중", "📝 전체 리스트"])
            
            with tab1:
                risk_df = filtered_df[filtered_df['risk_level'] == "🚨 심각/주의"]
                if risk_df.empty:
                    st.success("✅ 선택하신 커뮤니티에서 발견된 위험 이슈가 없습니다.")
                else:
                    for i, row in risk_df.iterrows():
                        with st.container():
                            st.error(f"**[{row['source']}] {row['postdate_dt'].date()}** | {row['clean_title']}")
                            st.write(row['clean_desc'])
                            st.markdown(f"[원문 보러가기]({row['link']})")
                            st.divider()

            with tab2:
                if not filtered_df.empty:
                    st.bar_chart(filtered_df['source'].value_counts())
                else:
                    st.info("데이터가 없습니다.")

            with tab3:
                # 날짜 포맷 예쁘게 변경해서 출력
                display_df = filtered_df.copy()
                display_df['날짜'] = display_df['postdate_dt'].dt.date
                st.dataframe(
                    display_df[['날짜', 'source', 'clean_title', 'risk_level', 'link']],
                    column_config={"link": st.column_config.LinkColumn("링크")},
                    use_container_width=True
                )
        else:
            st.warning("검색 결과가 없습니다. (API 설정 '검색' 체크 여부를 꼭 확인하세요!)")
else:
    st.info("👈 API 키 입력 후 버튼을 눌러주세요.")
