import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
import traceback

# 페이지 설정
st.set_page_config(page_title="현장 발주 시스템", layout="wide")

# ---------------------------------------------------------
# 🎨 표 내부의 모든 값을 중앙 정렬하기 위한 CSS 스타일 추가
# ---------------------------------------------------------
st.markdown("""

""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 1. 구글 스프레드시트 연결 설정
# ---------------------------------------------------------
# 🚨 본인의 구글 스프레드시트 URL 주소로 꼭 다시 변경하세요!
SHEET_URL = "https://docs.google.com/spreadsheets/d/1jvQNuEMI_8-Ff3wygskhrdHyz5Rkshouvn48wHkamk4/edit?gid=1314802059#gid=1314802059"

@st.cache_resource
def init_connection():
    return gspread.service_account(filename="secrets.json")

try:
    gc = init_connection()
    sh = gc.open_by_url(SHEET_URL)
except Exception as e:
    st.error("🚨 에러 상세 추적:")
    st.code(traceback.format_exc())
    st.stop()

# ---------------------------------------------------------
# 2. 데이터 로드 로직 (가격 열 콤마 및 이미지 처리)
# ---------------------------------------------------------
@st.cache_data(ttl=60)
def load_data(sheet_name):
    try:
        ws = sh.worksheet(sheet_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            target_indices = [1, 3, 4, 5, 6, 7, 10, 11, 20]
            valid_indices = [i for i in target_indices if i < len(df.columns)]
            cols_to_keep = [df.columns[i] for i in valid_indices]
            
            if '이미지' in df.columns:
                cols_to_keep.append('이미지')
                
            df = df[cols_to_keep]
            
            # '가'가 포함된 열(특약점가, 특판가, 단가 등)에 자동으로 콤마(,) 포맷 적용
            for col in df.columns:
                if '가' in str(col):
                    def format_price(val):
                        try:
                            return f"{int(float(val)):,}"
                        except (ValueError, TypeError):
                            return val
                    df[col] = df[col].apply(format_price)
            
            # 발주수량 열을 맨 뒤에 추가
            df['발주수량'] = 0
            
        return df
    except Exception as e:
        st.error(f"🚨 '{sheet_name}' 데이터를 읽는 중 에러 발생:")
        st.code(traceback.format_exc())
        return None

# ---------------------------------------------------------
# 3. 메인 화면 (영업사원 UI)
# ---------------------------------------------------------
st.title("📦 현장 발주 시스템 (구글 연동)")

col1, col2 = st.columns(2)
with col1:
    region = st.selectbox("🏢 지역 선택", ["👇 지역 선택", "서울", "대구", "부산"])

with col2:
    if region == "서울":
        names = ["이승엽 부장", "정재훈 차장", "남기원 차장", "남상협 차장", "김성진 차장", "송형섭 과장"]
    elif region == "대구":
        names = ["최재환 부장", "정재욱 차장", "김석주 과장", "변기훈 과장", "박갑열 과장"]
    elif region == "부산":
        names = ["박영진 과장", "이영진 과장", "이창문 과장"]
    else:
        names = ["👈 먼저 지역을 선택해주세요"]
        
    name = st.selectbox("👤 영업사원 성함", names)

if region != "👇 지역 선택" and name != "👈 먼저 지역을 선택해주세요":
    sales_person = f"{region} / {name}"
else:
    sales_person = ""

st.write("") 

view_mode = st.radio("📋 리스트 선택", ["⭐ 지정관리상품", "📦 전체상품"], horizontal=True)

sheet_name = "지정관리상품" if view_mode == "⭐ 지정관리상품" else "전체상품"
df = load_data(sheet_name)

if df is None or df.empty:
    st.info(f"'{sheet_name}' 시트에 데이터가 없거나 양식이 잘못되었습니다.")
    st.stop()

search_term = st.text_input("🔍 품목 또는 규격 검색", placeholder="검색어를 입력하세요...")

if search_term:
    mask = df.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
    filtered_df = df[mask]
else:
    filtered_df = df

st.write(f"### {view_mode} (총 {len(filtered_df)}건)")

disabled_cols = filtered_df.columns.tolist()
if '발주수량' in disabled_cols:
    disabled_cols.remove('발주수량')

# 표 안에 상품 사진 썸네일 표시 설정
col_config = {}
if '이미지' in df.columns:
    col_config['이미지'] = st.column_config.ImageColumn(
        "상품 사진",
        help="상품 이미지 미리보기"
    )

edited_df = st.data_editor(
    filtered_df,
    hide_index=True,
    use_container_width=True,
    disabled=disabled_cols,
    column_config=col_config
)

st.divider()

# ---------------------------------------------------------
# 4. 발주 실행 및 데이터 저장
# ---------------------------------------------------------
if st.button("🛒 주문서 서버로 전송하기", type="primary", use_container_width=True):
    if not sales_person:
        st.warning("⚠️ 발주를 진행하려면 상단에서 [지역]과 [영업사원 성함]을 모두 정확히 선택해주세요.")
        st.stop()

    order_items = edited_df[edited_df['발주수량'] > 0]
    
    if not order_items.empty:
        try:
            order_ws = sh.worksheet("주문내역")
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            rows_to_insert = []
            order_text = "[발주서]\n--------------------\n"
            
            col_b = df.columns[0]
            col_d = df.columns[1]
            col_e = df.columns[2]

            for _, row in order_items.iterrows():
                row_data = [now, sales_person, row[col_b], row[col_d], row[col_e], row['발주수량']]
                rows_to_insert.append(row_data)
                
                order_text += f"▪ {row[col_b]} / {row[col_d]} / {row[col_e]} 👉 {row['발주수량']}개\n"
            
            order_ws.append_rows(rows_to_insert)
            
            order_text += f"--------------------\n✅ 전송자: {sales_person}\n✅ 시스템 서버 접수 완료."

            st.success("✅ 주문이 성공적으로 접수되었으며, 관리자 구글 시트에 즉시 기록되었습니다!")
            st.text_area("메신저 복사용 텍스트", value=order_text, height=200)
            
        except Exception as e:
            st.error("🚨 주문 전송 중 서버 오류가 발생했습니다:")
            st.code(traceback.format_exc())
            
    else:
        st.warning("⚠️ 주문할 품목의 발주수량을 1개 이상 입력해주세요.")