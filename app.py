import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

# 1. 페이지 설정
st.set_page_config(
    page_title="Royal Canin Real-Time",
    page_icon="⚡",
    layout="wide"
)

# 2. HTML 태그 제거 함수
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

# 3. 데이터 수집 함수 (API가 주는 순서 그대로 저장!)
def get_naver_data_realtime(keyword, client_id, client_secret):
    if not client_id or not client_secret:
        return None, []
    
    categories = ["blog", "cafearticle"]
    all_data = []
    log_messages = []
    
    status_area = st.empty()
    
    # 블로그와 카페를 번갈아가며 가져오면 순서가 섞이니, 각각 가져와서 합치되
    # 화면에서 볼 때는 '날짜'가 아닌 '수집 순서'를 존중해야 함.
    # 하지만 사용자 경험상 블로그/카페가 섞여있는 게 좋으므로,
    # 일단 다 가져온 뒤, '날짜 정보가 있으면 날짜순', '없으면 그냥 둠'이 아니라
    # ★ 핵심: 네이버가 준 순서를 믿는다.
    
    for cat in categories:
        cat_name = "블로그" if cat == "blog" else "카페"
        
        # 3페이지 정도만 빠르게 훑기 (실시간성 강조)
        for start_index in range(1, 300, 100):
            try:
                status_area.info(f"⚡ {cat_name} {start_index}번째 최신 글 가져오는 중...")
                
                encText = urllib.parse.quote(keyword)
                # sort=date (최신순) 요청
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
                        # 날짜 처리
                        raw_date = item.get('postdate', '')
                        try:
                            if raw_date:
                                p_date = pd.to_datetime(raw_date, format='%Y%m%d')
                            else:
                                # 날짜 없으면 '1900년'으로 기록하되, 정렬에 쓰지 않음
                                p_date = pd.to_datetime('1900-01-01')
                        except:
                            p_date = pd.to_datetime('1900-01-01')
                        
                        # 카페 이름
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
                    code = response.getcode()
                    log_messages.append(f"❌ {cat_name} 호출 실패 (Code: {code})")
                    break
            except Exception as e:
                log_messages.append(f"❌ {cat_name} 에러: {e}")
                break
                
    status_area.success("✅ 실시간 데이터 확보 완료!")
    
    if not all_data:
        return pd.DataFrame(), log_messages

    df = pd.DataFrame(all_data)
    
    # 위험 키워드
    risk_keywords = ['구더기', '벌레', '이물질', '식약처', '신고', '환불', '토해', '설사', '혈변', '곰팡이', '리콜', '배신']
    df['risk_level'] = df['clean_desc'].apply(lambda x: "🚨 심각/주의" if any(k in x for k in risk_keywords) else "일반")
    
    # 중복 제거
    df = df.drop_duplicates(['clean_title'])

    # [수정] 여기서 df.sort_values()를 삭제했습니다!
    # 대신, 블로그와 카페를 따로 모았으니, '날짜가 1900이 아닌 것들'을 기준으로 다시 섞어줄 필요는 있습니다.
    # 하지만 사용자가 '날짜 별로' 보고 싶다고 했으므로, 
    # 날짜가 있는 건 날짜순으로, 없는 건(1900) '수집된 순서(상단)'에 배치하는 하이브리드 정렬을 합니다.
    
    # 정렬 로직: 날짜 내림차순으로 하되, 1900년(날짜없음)은 맨 밑으로 보내지 말고 '오늘 날짜'처럼 취급해서 섞어버림
    # (주의: 이렇게 해야 "날짜 없는 최신글"이 위로 올라옵니다)
    
    now = datetime.datetime.now()
    df['sort_date'] = df['postdate_dt'].apply(lambda x: now if x.year == 1900 else x)
    
    # 이제 정렬! (날짜 없는 애들은 '방금 시간'으로 치환됐으니 맨 위로 뜸)
    df = df.sort_values(by='sort_date', ascending=False)
    
    return df[['postdate_dt', 'source', 'clean_title', 'clean_desc', 'risk_level', 'link']], log_messages

# 4. UI
with st.sidebar:
    st.header("⚙️ 실시간 모니터링")
    keyword = st.text_input("검색어", value="로얄캐닌")
    
    st.markdown("---")
    all_options = ["네이버 블로그", "고양이라서 다행이야", "냥이네", "아반강고", "강사모"]
    target_filter = st.multiselect("채널 필터", all_options, default=all_options)
    
    st.markdown("---")
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Secret", type="password")
    run_btn = st.button("실시간 수집 시작")

st.title(f"⚡ '{keyword}' 실시간 타임라인")

if run_btn:
    if not client_id or not client_secret:
        st.error("⚠️ API 키를 입력해주세요.")
    else:
        df, logs = get_naver_data_realtime(keyword, client_id, client_secret)
        
        with st.expander("📜 시스템 로그", expanded=False):
            if logs:
                for log in logs: st.write(log)
            else:
                st.write("모든 시스템 정상 가동 중.")

        if df is not None and not df.empty:
            if target_filter:
                filtered_df = df[df['source'].isin(target_filter)]
            else:
                filtered_df = df
            
            col1, col2, col3 = st.columns(3)
            risk_count = len(filtered_df[filtered_df['risk_level'] == "🚨 심각/주의"])
            top_src = filtered_df['source'].mode()[0] if not filtered_df.empty else "-"
                
            col1.metric("수집된 글", f"{len(filtered_df)}건")
            col2.metric("이슈 글", f"{risk_count}건", delta_color="inverse")
            col3.metric("최다 출처", top_src)
            
            st.markdown("---")
            
            tab1, tab2, tab3 = st.tabs(["🔥 타임라인 (Risk)", "📊 차트", "📝 전체 리스트"])
            
            with tab1:
                risk_df = filtered_df[filtered_df['risk_level'] == "🚨 심각/주의"]
                if risk_df.empty:
                    st.success("현재 감지된 위험 이슈가 없습니다.")
                else:
                    for i, row in risk_df.iterrows():
                        with st.container():
                            icon = "🅱️" if "블로그" in row['source'] else "☕"
                            
                            # 날짜 표시 로직 (핵심)
                            if row['postdate_dt'].year == 1900:
                                # 날짜가 없으면 '최신 수집'이라고 표시하고 빨간색 강조
                                date_str = "⚡ 최신 수집 (날짜 정보 없음)"
                                date_color = "red"
                            else:
                                date_str = row['postdate_dt'].strftime('%Y-%m-%d')
                                date_color = "black"
                            
                            st.markdown(f"**{icon} [{row['source']}]** <span style='color:{date_color}'>{date_str}</span>", unsafe_allow_html=True)
                            st.write(f"**{row['clean_title']}**")
                            st.caption(row['clean_desc'])
                            st.markdown(f"[원문 이동]({row['link']})")
                            st.divider()
            
            with tab2:
                if not filtered_df.empty:
                    st.bar_chart(filtered_df['source'].value_counts())

            with tab3:
                display = filtered_df.copy()
                # 표에서도 '날짜없음'을 명확히 표시
                display['날짜'] = display['postdate_dt'].apply(lambda x: "⚡최신(날짜없음)" if x.year == 1900 else x.strftime('%Y-%m-%d'))
                
                st.dataframe(
                    display[['날짜', 'source', 'clean_title', 'risk_level', 'link']],
                    column_config={"link": st.column_config.LinkColumn("링크")},
                    use_container_width=True
                )
            
            st.markdown("---")
            csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 결과 엑셀로 저장",
                data=csv,
                file_name=f"{keyword}_realtime.csv",
                mime="text/csv",
            )
        else:
            st.error("결과가 없습니다.")
