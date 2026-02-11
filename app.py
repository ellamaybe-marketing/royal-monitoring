import streamlit as st
import pandas as pd
import datetime
import urllib.request
import json
import re

# 1. 페이지 설정
st.set_page_config(
    page_title="Royal Canin Multi-Search",
    page_icon="🕵️",
    layout="wide"
)

# 2. HTML 태그 제거 함수
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

# 3. 데이터 수집 함수 (여러 키워드를 한 번에 검색!)
def get_naver_data_multi_keyword(keyword_string, client_id, client_secret):
    if not client_id or not client_secret:
        return None, []
    
    # 콤마(,)로 구분된 검색어를 리스트로 변환
    # 예: "로얄캐닌, 로캐, ㄹㅇㅋㄴ" -> ["로얄캐닌", "로캐", "ㄹㅇㅋㄴ"]
    keywords = [k.strip() for k in keyword_string.split(',') if k.strip()]
    
    category = "cafearticle"
    all_data = []
    log_messages = []
    
    status_area = st.empty()
    
    # 각 키워드별로 검색을 수행하고 합침
    for search_term in keywords:
        for start_index in range(1, 300, 100): # 키워드당 3페이지씩만 (속도 고려)
            try:
                status_area.info(f"🔍 키워드 '{search_term}' 검색 중... ({start_index}번째 글)")
                
                encText = urllib.parse.quote(search_term)
                # sort=date (최신순)
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
                        # 날짜 처리
                        raw_date = item.get('postdate', '')
                        try:
                            if raw_date:
                                p_date = pd.to_datetime(raw_date, format='%Y%m%d')
                            else:
                                p_date = pd.to_datetime('1900-01-01')
                        except:
                            p_date = pd.to_datetime('1900-01-01')
                        
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
                        item['search_keyword'] = search_term # 어떤 키워드로 걸렸는지 기록
                        all_data.append(item)
                else:
                    log_messages.append(f"❌ '{search_term}' 호출 실패")
                    break
            except Exception as e:
                log_messages.append(f"❌ 에러: {e}")
                break
            
    status_area.success(f"✅ 총 {len(keywords)}개 키워드 수집 완료!")
    
    if not all_data:
        return pd.DataFrame(), log_messages

    df = pd.DataFrame(all_data)
    
    # -----------------------------------------------------------------------
    # [핵심] 위험 키워드 정의 (요청하신 단어들 포함)
    # -----------------------------------------------------------------------
    risk_keywords = ['벌레', '이물', '구더기', '회수', '식약처', '신고', '환불', '토해', '설사', '혈변', '곰팡이', '충격', '실망']
    
    def check_risk(text):
        for k in risk_keywords:
            if k in text:
                return f"🚨 발견됨: {k}" # 어떤 단어가 걸렸는지 알려줌
        return "일반"

    df['risk_level'] = df['clean_desc'].apply(check_risk)
    
    # 중복 제거 (여러 키워드에 동시에 걸린 글 제거)
    df = df.drop_duplicates(['clean_title'])
    
    # 네이버 최신순 유지를 위해 정렬 로직 생략 (수집된 순서가 곧 최신순)
    # 단, 여러 키워드를 섞었으므로 날짜가 있다면 날짜순 정렬이 더 안전함
    # (1900년 날짜없음 데이터는 '현재'로 취급하여 상단 배치)
    now = datetime.datetime.now()
    df['sort_date'] = df['postdate_dt'].apply(lambda x: now if x.year == 1900 else x)
    df = df.sort_values(by='sort_date', ascending=False)
    
    return df[['postdate_dt', 'source', 'clean_title', 'clean_desc', 'risk_level', 'link', 'search_keyword']], log_messages

# 4. UI 구성
with st.sidebar:
    st.header("🕵️ 다중 키워드 모니터링")
    
    # [수정] 여러 검색어를 입력받도록 변경
    default_keywords = "로얄캐닌, 로캐, 로케, ㄹㅇㅋㄴ"
    keyword_input = st.text_input("검색어 입력 (콤마 , 로 구분)", value=default_keywords)
    
    st.markdown("---")
    st.caption("필터링할 카페")
    all_options = ["고양이라서 다행이야", "냥이네", "아반강고", "강사모"]
    target_filter = st.multiselect("카페 선택", all_options, default=all_options)
    
    st.markdown("---")
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Secret", type="password")
    run_btn = st.button("모니터링 시작")

st.title(f"🕵️ '{keyword_input}' 통합 분석")

if run_btn:
    if not client_id or not client_secret:
        st.error("⚠️ API 키를 입력해주세요.")
    else:
        df, logs = get_naver_data_multi_keyword(keyword_input, client_id, client_secret)
        
        with st.expander("ℹ️ 수집 로그"):
            if logs:
                for log in logs: st.write(log)
            else:
                st.write("모든 키워드 정상 수집됨.")

        if df is not None and not df.empty:
            if target_filter:
                filtered_df = df[df['source'].isin(target_filter)]
            else:
                filtered_df = df
            
            # 요약
            col1, col2, col3 = st.columns(3)
            # 위험 글 개수 (일반이 아닌 것들)
            risk_df = filtered_df[filtered_df['risk_level'] != "일반"]
            risk_count = len(risk_df)
            top_src = filtered_df['source'].mode()[0] if not filtered_df.empty else "-"
                
            col1.metric("총 수집 글", f"{len(filtered_df)}건")
            col2.metric("🚨 이슈 글", f"{risk_count}건", delta_color="inverse")
            col3.metric("최다 언급", top_src)
            
            st.markdown("---")
            
            # 1. 일별 추이 (날짜 있는 것만)
            st.subheader("📊 언급량 추이")
            chart_df = filtered_df[filtered_df['postdate_dt'].dt.year > 2000]
            if not chart_df.empty:
                trend_data = chart_df['postdate_dt'].dt.date.value_counts().sort_index()
                st.area_chart(trend_data, color="#ff4b4b")
            
            st.markdown("---")

            # 2. 탭
            tab1, tab2, tab3 = st.tabs(["🔥 리스크 피드", "📊 키워드별 차트", "📝 전체 리스트"])
            
            with tab1:
                if risk_df.empty:
                    st.success("✅ '벌레, 이물, 구더기' 등 위험 키워드가 포함된 글이 없습니다.")
                else:
                    st.caption("👇 지정하신 위험 단어가 포함된 글 목록입니다.")
                    for i, row in risk_df.iterrows():
                        with st.container():
                            if row['postdate_dt'].year == 1900:
                                date_str = "⚡ 최신 (날짜미상)"
                                date_color = "red"
                            else:
                                date_str = row['postdate_dt'].strftime('%Y-%m-%d')
                                date_color = "gray"
                            
                            st.markdown(f"**☕ [{row['source']}]** <span style='color:{date_color}'>{date_str}</span>", unsafe_allow_html=True)
                            
                            # 제목과 위험 키워드 강조
                            st.error(f"{row['clean_title']}")
                            st.write(f"⚠️ 감지된 이유: **{row['risk_level']}** (검색어: {row['search_keyword']})")
                            st.caption(row['clean_desc'])
                            st.markdown(f"[원문 이동]({row['link']})")
                            st.divider()
            
            with tab2:
                # 어떤 검색어(로얄캐닌 vs 로캐)로 많이 걸렸는지 확인
                if not filtered_df.empty:
                    st.write("🔎 어떤 검색어로 글이 많이 잡혔을까요?")
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
                label="📥 엑셀 다운로드",
                data=csv,
                file_name=f"{keyword_input}_monitoring.csv",
                mime="text/csv",
            )
        else:
            st.warning("결과가 없습니다.")
