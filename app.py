import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

# 1. 페이지 설정
st.set_page_config(
    page_title="Royal Canin Final Monitor",
    page_icon="📅",
    layout="wide"
)

# 2. HTML 태그 제거 함수
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

# 3. 데이터 수집 함수
def get_naver_data_final(keyword, client_id, client_secret):
    if not client_id or not client_secret:
        return None, []
    
    categories = ["blog", "cafearticle"]
    all_data = []
    log_messages = []
    
    status_area = st.empty()
    
    for cat in categories:
        cat_name = "블로그" if cat == "blog" else "카페"
        
        # 5페이지(500개) 탐색
        for start_index in range(1, 500, 100):
            try:
                status_area.info(f"🏃‍♂️ {cat_name} {start_index}번째 글 분석 중...")
                
                encText = urllib.parse.quote(keyword)
                # 날짜순 정렬
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

                    for item in items:
                        # 날짜 처리 (원본 우선)
                        raw_date = item.get('postdate', '')
                        try:
                            if raw_date:
                                p_date = pd.to_datetime(raw_date, format='%Y%m%d')
                            else:
                                p_date = pd.to_datetime('1900-01-01')
                        except:
                            p_date = pd.to_datetime('1900-01-01')
                        
                        # 카페 이름 처리
                        raw_name = item.get('cafename', '')
                        
                        if cat == "blog":
                            source_label = "네이버 블로그"
                        else:
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
                    # [에러 해결] 이 부분이 줄바꿈되지 않도록 한 줄로 작성
                    code = response.getcode()
                    log_messages.append(f"❌ {cat_name} API 호출 실패 (Code: {code})")
                    break
            except Exception as e:
                log_messages.append(f"❌ {cat_name} 에러 발생: {e}")
                break
                
    status_area.success("✅ 수집 완료!")
    
    if not all_data:
        return pd.DataFrame(), log_messages

    df = pd.DataFrame(all_data)
    
    # 위험 키워드
    risk_keywords = ['구더기', '벌레', '이물질', '식약처', '신고', '환불', '토해', '설사', '혈변', '곰팡이', '리콜']
    df['risk_level'] = df['clean_desc'].apply(lambda x: "🚨 심각/주의" if any(k in x for k in risk_keywords) else "일반")
    
    # 중복 제거 및 정렬
    df = df.drop_duplicates(['clean_title'])
    df = df.sort_values(by='postdate_dt', ascending=False)
    
    return df[['postdate_dt', 'source', 'clean_title', 'clean_desc', 'risk_level', 'link']], log_messages

# 4. 메인 화면 UI
with st.sidebar:
    st.header("⚙️ 모니터링 설정")
    keyword = st.text_input("검색어", value="로얄캐닌")
    
    st.markdown("---")
    st.caption("채널 필터")
    all_options = ["네이버 블로그", "고양이라서 다행이야", "냥이네", "아반강고", "강사모"]
    target_filter = st.multiselect("채널 선택", all_options, default=all_options)
    
    st.markdown("---")
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Secret", type="password")
    run_btn = st.button("데이터 수집 시작")

st.title(f"🔍 '{keyword}' 정밀 분석 (오류 해결판)")

if run_btn:
    if not client_id or not client_secret:
        st.error("⚠️ API 키를 입력해주세요.")
    else:
        df, logs = get_naver_data_final(keyword, client_id, client_secret)
        
        with st.expander("📜 수집 로그 확인", expanded=False):
            if logs:
                for log in logs: st.write(log)
            else:
                st.write("깨끗하게 수집되었습니다.")

        if df is not None and not df.empty:
            if target_filter:
                filtered_df = df[df['source'].isin(target_filter)]
            else:
                filtered_df = df
            
            # 날짜 오류(1900년) 데이터 제외
            filtered_df = filtered_df[filtered_df['postdate_dt'].dt.year > 2000]

            col1, col2, col3 = st.columns(3)
            risk_count = len(filtered_df[filtered_df['risk_level'] == "🚨 심각/주의"])
            top_src = filtered_df['source'].mode()[0] if not filtered_df.empty else "-"
                
            col1.metric("수집된 글", f"{len(filtered_df)}건")
            col2.metric("이슈 글", f"{risk_count}건", delta_color="inverse")
            col3.metric("최다 출처", top_src)
            
            st.markdown("---")
            
            tab1, tab2, tab3 = st.tabs(["🔥 리스크 피드", "📊 차트", "📝 리스트"])
            
            with tab1:
                risk_df = filtered_df[filtered_df['risk_level'] == "🚨 심각/주의"]
                if risk_df.empty:
                    st.success("발견된 위험 글이 없습니다.")
                else:
                    for i, row in risk_df.iterrows():
                        with st.container():
                            icon = "🅱️" if "블로그" in row['source'] else "☕"
                            date_str = row['postdate_dt'].strftime('%Y-%m-%d')
                            st.error(f"**{icon} [{row['source']}] {date_str}** | {row['clean_title']}")
                            st.caption(row['clean_desc'])
                            st.markdown(f"[원문 이동]({row['link']})")
                            st.divider()
            
            with tab2:
                if not filtered_df.empty:
                    st.bar_chart(filtered_df['source'].value_counts())

            with tab3:
                display = filtered_df.copy()
                display['날짜'] = display['postdate_dt'].dt.date
                st.dataframe(
                    display[['날짜', 'source', 'clean_title', 'risk_level', 'link']],
                    column_config={"link": st.column_config.LinkColumn("링크")},
                    use_container_width=True
                )
            
            st.markdown("---")
            csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 엑셀(CSV)로 저장하기",
                data=csv,
                file_name=f"{keyword}_monitoring.csv",
                mime="text/csv",
            )
        else:
            st.error("수집된 데이터가 없습니다.")
