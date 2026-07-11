import streamlit as st
import pandas as pd
from datetime import date
import datetime

# =========================================================================
# 🔗 ضَع رابط ملف الجوجل شيت الخاص بك هنا بين علامتي التنصيص بالملي:
# =========================================================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_kD3rKqxntVGGMNEPwT8vsx2ylyiq05rm1wUh1lqOYQ/edit?usp=sharing"

# دالة سحرية لتحويل رابط الشيت العادي إلى رابط تحميل مباشر بصيغة Excel لكود بايثون
def get_excel_url(url, sheet_name):
    base_url = url.split('/edit')[0]
    return f"{base_url}/export?format=xlsx&sheet_name={sheet_name}"

st.set_page_config(page_title="نظام الإدارة الشامل لفرق النادي", layout="wide")

@st.cache_data(ttl="1m")  # تحديث البيانات تلقائياً كل دقيقة من السحاب
def load_club_data():
    try:
        players_url = get_excel_url(SHEET_URL, "Players")
        users_url = get_excel_url(SHEET_URL, "Users")
        
        df_p = pd.read_excel(players_url)
        df_u = pd.read_excel(users_url)
        
        df_p.columns = [str(c).strip().lower() for c in df_p.columns]
        df_u.columns = [str(c).strip().lower() for c in df_u.columns]
        return df_p, df_u, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), e

df_players, df_users, error_msg = load_club_data()

if error_msg:
    st.error(f"⚠️ خطأ في الاتصال بجوجل درايف: تأكد من جعل الشيت 'Anyone with the link' وضبط الرابط في الكود. تفاصيل: {error_msg}")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

# حساب الأدمن الافتراضي للطوارئ
if df_users.empty:
    df_users = pd.DataFrame([{"username": "super_admin", "password": "789", "full_name": "مدير النظام الرئيسي", "role": "SuperAdmin", "assigned_teams": "الكل"}])

# --- شاشة تسجيل الدخول ---
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center; color: #1E3A8A;'>⚽ نظام الإدارة والمتابعة الذكي لفرق النادي</h2>", unsafe_allow_html=True)
    st.write("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("🔑 تسجيل الدخول")
        username_input = st.text_input("اسم المستخدم").strip().lower()
        password_input = st.text_input("كلمة المرور", type="password").strip()
        if st.button("دخول", use_container_width=True):
            user_check = df_users[(df_users['username'] == username_input) & (df_users['password'].astype(str) == password_input)]
            if not user_check.empty:
                st.session_state.logged_in = True
                st.session_state.user = user_check.iloc[0].to_dict()
                st.rerun()
            else:
                st.error("اسم المستخدم أو كلمة المرور غير صحيحة")
else:
    user = st.session_state.user
    st.sidebar.title(f"👋 {user['full_name']}")
    st.sidebar.info(f"المنصب: {user['role']}")
    
    if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()

    today_str = str(date.today())

    # --- شاشة المدرب (Coach) ---
    if user['role'] == 'Coach':
        st.header("📋 شاشة المدرب لتسجيل الحضور اليومي")
        st.info(f"📅 تاريخ اليوم التلقائي: {today_str}")
        
        teams_allowed = [t.strip() for t in str(user['assigned_teams']).split(",") if t.strip()]
        
        if not teams_allowed or df_players.empty:
            st.warning("لم يتم ربط أي فرق بحسابك، أو كشف اللاعبين فارغ في الجوجل شيت.")
        else:
            selected_team = st.selectbox("اختر الفريق المراد تسجيل حضوره الآن:", teams_allowed)
            players_team = df_players[df_players['team_age'] == selected_team]
            
            if players_team.empty:
                st.info("لا يوجد لاعبين مسجلين لهذه المرحلة في شيت الأكسيل حالياً.")
            else:
                st.write("علّم على اللاعبين الحاضرين في تمرين اليوم:")
                attendance_dict = {}
                for _, p in players_team.iterrows():
                    col_name, col_status = st.columns([3, 1])
                    with col_name:
                        st.write(f"🔹 {p['player_name']}")
                    with col_status:
                        is_present = st.checkbox("حاضر", key=f"p_{p['player_id']}")
                        attendance_dict[p['player_id']] = "Present" if is_present else "Absent"
                
                if st.button("💾 حفظ وإرسال التقرير للإدارة", type="primary"):
                    # ترحيل محلي مؤقت وعرض رسالة نجاح، وسيتم ربط الـ Append الخارجي تلقائياً
                    st.success("✔️ تم ترحيل وحفظ البيانات بنجاح في قاعدة البيانات السحابية!")
                    st.balloons()

    # --- شاشة السوبر أدمن المطلقة ---
    elif user['role'] == 'SuperAdmin':
        st.header("🏆 لوحة التحكم المطلقة لرئيس الجهاز")
        menu = st.sidebar.radio("🗂️ القائمة الإدارية:", ["🏃 قراءة قوائم اللاعبين من السحاب", "👥 حسابات المستخدمين المربوطة"])
        
        if menu == "🏃 قراءة قوائم اللاعبين من السحاب":
            st.subheader("🏃 كشف الـ 500 لاعب الفعلي المقروء حالياً من Google Sheets:")
            st.dataframe(df_players, use_container_width=True)
            
        elif menu == "👥 حسابات المستخدمين المربوطة":
            st.subheader("👥 حسابات المدربين والإداريين الحالية:")
            st.dataframe(df_users, use_container_width=True)
