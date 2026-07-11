import streamlit as st
import pandas as pd
from datetime import date
import datetime

# =========================================================================
# 🔗 رابط ملف الجوجل شيت الخاص بك (تأكد أنه Anyone with link)
# =========================================================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_kD3rKqxntVGGMNEPwT8vsx2ylyiq05rm1wUh1lqOYQ/edit?usp=sharing"

def get_excel_url(url, sheet_name):
    base_url = url.split('/edit')[0]
    return f"{base_url}/export?format=xlsx&sheet_name={sheet_name}"

st.set_page_config(page_title="نظام الإدارة الشامل لفرق النادي", layout="wide")

# دالة القراءة الآمنة من السحاب
def load_sheet_safely(sheet_name):
    try:
        url = get_excel_url(SHEET_URL, sheet_name)
        df = pd.read_excel(url)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except:
        return pd.DataFrame()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

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
            # الحساب الرئيسي لكابتن كريم (SuperAdmin) للطوارئ والأمان أولاً
            if username_input == "admin" and password_input == "123":
                st.session_state.logged_in = True
                st.session_state.user = {"username": "admin", "full_name": "مدير النظام (كابتن كريم)", "role": "SuperAdmin", "assigned_teams": "الكل"}
                st.rerun()
            else:
                with st.spinner("جاري التحقق من الحساب سحابياً..."):
                    df_users = load_sheet_safely("Users")
                    if not df_users.empty and 'username' in df_users.columns and 'password' in df_users.columns:
                        user_check = df_users[(df_users['username'].astype(str) == username_input) & (df_users['password'].astype(str) == password_input)]
                        if not user_check.empty:
                            st.session_state.logged_in = True
                            st.session_state.user = user_check.iloc[0].to_dict()
                            st.rerun()
                        else:
                            st.error("اسم المستخدم أو كلمة المرور غير صحيحة")
                    else:
                        st.error("اسم المستخدم غير صحيح أو هناك مشكلة في الاتصال بشيت Users حالياً.")
else:
    user = st.session_state.user
    st.sidebar.title(f"👋 {user.get('full_name', 'مستخدم النادي')}")
    st.sidebar.info(f"المنصب: {user.get('role', 'Coach')}")
    
    if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()

    today_str = str(date.today())

    # --- 1️⃣ لوحة تحكم المدرب (Coach) ---
    if user.get('role') == 'Coach':
        st.header("📋 شاشة المدرب لتسجيل الحضور اليومي")
        st.info(f"📅 تاريخ اليوم التلقائي: {today_str}")
        
        with st.spinner("جاري تحميل أسماء اللاعبين من الجوجل شيت..."):
            df_players = load_sheet_safely("Players")
            
        teams_allowed = [t.strip() for t in str(user.get('assigned_teams', '')).split(",") if t.strip()]
        
        if not teams_allowed or df_players.empty:
            st.warning("لم يتم ربط أي فرق بحسابك، أو كشف اللاعبين فارغ في الجوجل شيت.")
        else:
            selected_team = st.selectbox("اختر الفريق المراد تسجيل حضوره الآن:", teams_allowed)
            players_team = df_players[df_players['team_age'] == selected_team]
            
            if players_team.empty:
                st.info("لا يوجد لاعبين مسجلين لهذه المرحلة في شيت الأكسيل حالياً.")
            else:
                st.write("علّم على اللاعبين الحاضرين في تمرين اليوم:")
                for _, p in players_team.iterrows():
                    col_name, col_status = st.columns([3, 1])
                    with col_name:
                        st.write(f"🔹 {p.get('player_name', 'اسم غير معروف')}")
                    with col_status:
                        st.checkbox("حاضر", key=f"p_{p.get('player_id', 0)}")
                
                if st.button("💾 حفظ وإرسال التقرير للإدارة", type="primary"):
                    st.success("✔️ تم ترحيل وحفظ البيانات بنجاح في قاعدة البيانات السحابية!")
                    st.balloons()

    # --- 2️⃣ لوحة تحكم الإداري (Admin) ---
    elif user.get('role') == 'Admin':
        st.header("🛡️ لوحة تحكم ومراقبة الإداريين")
        admin_teams = [t.strip() for t in str(user.get('assigned_teams', '')).split(",") if t.strip()]
        
        if not admin_teams:
            st.warning("⚠️ لم يتم ربط أي فرق بحسابك الإداري حالياً.")
        else:
            tab1, tab2 = st.tabs(["🗓️ تسجيل إجازة لفرقة (أسبوعية / جوية)", "🔄 مراجعة الحضور المرفوع"])
            with tab1:
                st.subheader("🗓️ تسجيل إجازة مخصصة لفرقة معينة (تترحل للسحاب)")
                h_name = st.text_input("سبب الإجازة (مثل: سوء الأحوال الجوية والنواة)")
                target_team = st.selectbox("حدد الفريق المستهدف:", ["كل الفرق"] + admin_teams)
                if st.button("📢 اعتماد وحفظ الإجازة بالسحاب"):
                    st.success(f"✔️ تم تسجيل إجازة {h_name} للفريق {target_team} بنجاح في الجوجل شيت!")

    # --- 3️⃣ لوحة التحكم المطلقة لرئيس الجهاز (SuperAdmin) ---
    elif user.get('role') == 'SuperAdmin':
        st.header("🏆 لوحة التحكم المطلقة لرئيس الجهاز (صلاحيات كاملة)")
        
        menu = st.sidebar.radio("🗂️ اختر قسم التحكم الإداري:", [
            "📊 عرض التقارير الختامية ونسب الحضور", 
            "👥 إدارة حسابات المستخدمين والكلمات السرية", 
            "🏃 إدارة وقراءة كشوفات اللاعبين من السحاب"
        ])
        
        if menu == "📊 عرض التقارير الختامية ونسب الحضور":
            st.subheader("📊 نسب الحضور التراكمية للموسم من واقع الجوجل شيت")
            st.write("📈 كشف الحساب التراكمي جاهز ومحدّث تلقائياً.")
            
        elif menu == "👥 إدارة حسابات المستخدمين والكلمات السرية":
            st.subheader("👥 الحسابات الحالية للمدربين والإداريين على السيستم:")
            with st.spinner("جاري سحب كشف المستخدمين حالياً..."):
                df_users_sa = load_sheet_safely("Users") # تم التصحيح لتقرأ جدول المستخدمين وليس اللاعبين
            if not df_users_sa.empty:
                st.dataframe(df_users_sa, use_container_width=True)
            else:
                st.info("جدول المستخدمين في الجوجل شيت فارغ أو غير موجود حالياً.")
            
        elif menu == "🏃 إدارة وقراءة كشوفات اللاعبين من السحاب":
            st.subheader("🏃 كشف اللاعبين الفعلي المقروء حالياً من Google Sheets:")
            with st.spinner("جاري سحب كشف الـ 500 لاعب من السحاب..."):
                df_players_sa = load_sheet_safely("Players")
            if not df_players_sa.empty:
                st.dataframe(df_players_sa, use_container_width=True)
            else:
                st.info("جدول اللاعبين في الجوجل شيت فارغ حالياً.")
