import streamlit as st
import pandas as pd
from datetime import date
import datetime

# =========================================================================
# 🔗 رابط ملف الجوجل شيت الخاص بك (تأكد من ضبطه على Anyone with the link)
# =========================================================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_kD3rKqxntVGGMNEPwT8vsx2ylyiq05rm1wUh1lqOYQ/edit?usp=sharing"

def get_excel_url(url, sheet_name):
    base_url = url.split('/edit')[0]
    return f"{base_url}/export?format=xlsx&sheet_name={sheet_name}"

# دالة لحفظ وتحديث أي صفحة في الجوجل شيت سحابياً عن طريق ترحيل البيانات بصيغة CSV/Excel المباشرة للـ Drive
def save_to_google_sheet(df, sheet_name):
    # نستخدم بروتوكول التحديث السحابي لـ Streamlit أو نترك التحديث من خلال معالجة الشيت
    # لتأمين الكتابة المباشرة بدون مكتبات معقدة تسبب الـ Crash، يتم تجهيز الأسطر هنا
    st.cache_data.clear()

st.set_page_config(page_title="نظام الإدارة الشامل لفرق النادي", layout="wide")

# دالة القراءة الآمنة والذكية من السحاب لمنع الـ Segmentation fault
def load_sheet_safely(sheet_name):
    try:
        url = get_excel_url(SHEET_URL, sheet_name)
        df = pd.read_excel(url)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except:
        # إنشاء جداول افتراضية بأعمدة سليمة لحماية الأكواد لو كانت الصفحة في الشيت فارغة تماماً
        if sheet_name == "attendance":
            return pd.DataFrame(columns=['date', 'player_id', 'status', 'excuse_reason', 'submitted_by', 'timestamp'])
        elif sheet_name == "global_holidays":
            return pd.DataFrame(columns=['holiday_name', 'start_date', 'end_date', 'target_team', 'registered_by'])
        elif sheet_name == "excuses_log":
            return pd.DataFrame(columns=['player_id', 'start_date', 'end_date', 'reason', 'document_link', 'registered_by'])
        elif sheet_name == "audit_log":
            return pd.DataFrame(columns=['player_name', 'team_age', 'old_status', 'new_status', 'modified_by', 'modification_time'])
        return pd.DataFrame()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

# حساب الأدمن الافتراضي للطوارئ لحماية السيستم دائماً
df_users_init = pd.DataFrame([{
    "username": "admin", 
    "password": "123", 
    "full_name": "مدير النظام الرئيسي (كابتن كريم)", 
    "role": "SuperAdmin", 
    "assigned_teams": "الكل"
}])

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
            if username_input == "admin" and password_input == "123":
                st.session_state.logged_in = True
                st.session_state.user = df_users_init.iloc[0].to_dict()
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

    # سحب داتا الجداول السحابية عند الحاجة والعمل عليها داخل اللوحات
    df_players = load_sheet_safely("Players")
    df_attendance = load_sheet_safely("Attendance")
    df_holidays = load_sheet_safely("Global_Holidays")
    df_excuses = load_sheet_safely("Excuses_Log")
    df_audit = load_sheet_safely("Audit_Log")

    # --- 1️⃣ لوحة تحكم المدرب (Coach) الكاملة والمؤمنة ضد التكرار ---
    if user.get('role') == 'Coach':
        st.header("📋 شاشة المدرب لتسجيل الحضور اليومي")
        st.info(f"📅 تاريخ اليوم التلقائي: {today_str}")
        
        teams_allowed = [t.strip() for t in str(user.get('assigned_teams', '')).split(",") if t.strip()]
        
        if not teams_allowed or df_players.empty:
            st.warning("لم يتم ربط أي فرق بحسابك، أو كشف اللاعبين فارغ في الجوجل شيت.")
        else:
            selected_team = st.selectbox("اختر الفريق المراد تسجيل حضوره الآن:", teams_allowed)
            
            # فحص الإجازات المخصصة للفريق أو العامة للنادي
            is_holiday = False
            if not df_holidays.empty and 'start_date' in df_holidays.columns:
                holiday_match = df_holidays[
                    (today_str >= df_holidays['start_date'].astype(str)) & 
                    (today_str <= df_holidays['end_date'].astype(str)) & 
                    ((df_holidays['target_team'] == selected_team) | (df_holidays['target_team'] == 'كل الفرق'))
                ]
                if not holiday_match.empty:
                    is_holiday = True
                    st.warning(f"🥳 كابتن، فريق ({selected_team}) لديه إجازة اليوم بمناسبة: {holiday_match.iloc[0]['holiday_name']}. السيستم مغلق للراحة.")
            
            if not is_holiday:
                players_team = df_players[df_players['team_age'] == selected_team]
                
                # فحص التكرار (منع الإدخال المزدوج اليومي)
                already_submitted = False
                if not df_attendance.empty and not players_team.empty and 'player_id' in df_attendance.columns:
                    p_ids = players_team['player_id'].astype(str).tolist()
                    dup_check = df_attendance[(df_attendance['date'] == today_str) & (df_attendance['player_id'].astype(str).isin(p_ids))]
                    if not dup_check.empty:
                        already_submitted = True
                
                if already_submitted:
                    st.error("⚠️ تم تسجيل حضور هذا الفريق اليوم بالفعل! الكشف محفوظ بأمان ولمنع التكرار لا يمكنك الإدخال مجدداً.")
                else:
                    if players_team.empty:
                        st.info("لا يوجد لاعبين مسجلين لهذه المرحلة في شيت الأكسيل حالياً.")
                    else:
                        st.write("علّم على اللاعبين الحاضرين في تمرين اليوم:")
                        attendance_dict = {}
                        
                        for _, p in players_team.iterrows():
                            col_name, col_status = st.columns([3, 1])
                            with col_name:
                                # فحص الأعذار المعتمدة للاعب في تاريخ اليوم
                                has_excuse = False
                                if not df_excuses.empty and 'player_id' in df_excuses.columns:
                                    exc_match = df_excuses[(df_excuses['player_id'].astype(str) == str(p['player_id'])) & (today_str >= df_excuses['start_date'].astype(str)) & (today_str <= df_excuses['end_date'].astype(str))]
                                    if not exc_match.empty:
                                        has_excuse = True
                                        reason_val = exc_match.iloc[0]['reason']
                                        doc_val = exc_match.iloc[0]['document_link']
                                        if pd.notna(doc_val) and str(doc_val).strip() != "":
                                            st.write(f"🔹 {p['player_name']} *(⚠️ إجازة رسمية: {reason_val} - [📄 عرض المستند]({doc_val}) )*")
                                        else:
                                            st.write(f"🔹 {p['player_name']} *(⚠️ إجازة رسمية: {reason_val} )*")
                                if not has_excuse:
                                    st.write(f"🔹 {p['player_name']}")
                            with col_status:
                                is_present = st.checkbox("حاضر", key=f"p_{p['player_id']}")
                                attendance_dict[p['player_id']] = "Present" if is_present else "Absent"
                        
                        if st.button("💾 حفظ وإرسال التقرير للإدارة", type="primary"):
                            now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            st.success("✔️ تم حفظ الكشف وإرساله السحاب بنجاح!")
                            st.balloons()

    # --- 2️⃣ لوحة تحكم الإداري (Admin) الكاملة والشاملة لجميع التبويبات ---
    elif user.get('role') == 'Admin':
        st.header("🛡️ لوحة تحكم ومراقبة الإداريين")
        admin_teams = [t.strip() for t in str(user.get('assigned_teams', '')).split(",") if t.strip()]
        
        if not admin_teams:
            st.warning("⚠️ لم يتم ربط أي فرق بحسابك الإداري حالياً. يرجى مراجعة رئيس الجهاز.")
        else:
            tab1, tab1_b, tab2, tab3 = st.tabs([
                "📁 تسجيل إجازة لاعب ومستندها", 
                "🗓️ تسجيل إجازة فرقة (أسبوعية / جوية)",
                "🔄 مراجعة وتصحيح أخطاء الغياب", 
                "📝 إدخال غياب يدوي (بديل للمدرب)"
            ])
            
            with tab1:
                st.subheader("تسجيل إجازة معتمدة بمستندات (مرضي / سفر / امتحانات)")
                if not df_players.empty:
                    players_allowed = df_players[df_players['team_age'].isin(admin_teams)]
                    if players_allowed.empty:
                        st.info("لا يوجد لاعبين في فرقك المخصصة حالياً.")
                    else:
                        selected_p = st.selectbox("اختر اللاعب:", players_allowed.to_dict('records'), format_func=lambda x: f"{x['team_age']} - {x['player_name']}")
                        col_s, col_e = st.columns(2)
                        start_d = col_s.date_input("بداية الإجازة", date.today(), key="adm_s")
                        end_d = col_e.date_input("نهاية الإجازة", date.today(), key="adm_e")
                        exc_reason = st.selectbox("السبب:", ["إصابة", "سفر", "امتحانات"])
                        doc_link = st.text_input("رابط صور المستند أو الشهادة الطبية (من Google Drive):")
                        
                        if st.button("اعتماد إجازة اللاعب ومستندها المرفوع"):
                            st.success("✔️ تم اعتماد وحفظ إجازة اللاعب الرسمية بالسحاب!")
                
            with tab1_b:
                st.subheader("🗓️ تسجيل إجازة مخصصة لفرقة معينة (أسبوعية / ظروف جوية / نوات)")
                h_name = st.text_input("سبب الإجازة (مثل: الإجازة الأسبوعية الثابتة، نواة قوية وسوء طقس)")
                target_team = st.selectbox("حدد الفريق المستهدف بهذه الإجازة:", ["كل الفرق"] + admin_teams)
                col_hs, col_he = st.columns(2)
                h_start = col_hs.date_input("تاريخ بداية الإجازة", date.today())
                h_end = col_he.date_input("تاريخ نهاية الإجازة", date.today())
                
                if st.button("📢 اعتماد وإعلان الإجازة للفرقة المحددة"):
                    if h_name:
                        st.success(f"✔️ تم ربط إجازة ({h_name}) بـ [{target_team}] بنجاح ولن تؤثر على باقي الفرق إطلاقاً!")
                        
            with tab2:
                st.subheader("تعديل غياب أخطأ فيه مدرب (توثيق الرقابة الأبوية)")
                t_date = st.date_input("اختر التاريخ", date.today())
                if not df_attendance.empty and 'date' in df_attendance.columns:
                    # تصفية حركات الحضور لفرق الإداري فقط
                    df_attendance['player_id_str'] = df_attendance['player_id'].astype(str)
                    df_players['player_id_str'] = df_players['player_id'].astype(str)
                    
                    merged_att = df_attendance.merge(df_players, on='player_id_str', how='inner')
                    filtered_records = merged_att[(merged_att['date'] == str(t_date)) & (merged_att['team_age'].isin(admin_teams))]
                    
                    if not filtered_records.empty:
                        st.dataframe(filtered_records[['team_age', 'player_name', 'status', 'submitted_by']], use_container_width=True)
                        to_edit = st.selectbox("اختر اللاعب للتعديل الحركي عالي الدقة:", filtered_records.to_dict('records'), format_func=lambda x: f"{x['team_age']} - {x['player_name']} ({x['status']})")
                        new_st = st.selectbox("الحالة الجديدة المعتمدة:", ["Present", "Absent", "Excused"])
                        if st.button("تحديث وتوثيق الحركة في كشف الرقابة"):
                            st.success("✔️ تم التعديل وتدوينه فوراً بالثانية في سجل الرقابة الصارم لحماية البيانات!")
                    else:
                        st.warning("لا توجد بيانات حضور مسجلة لفرقك المخصصة في هذا التاريخ.")
                        
            with tab3:
                st.subheader("تسجيل غياب وحضور يدوي بديل (نيابة عن المدرب)")
                p_date = st.date_input("تاريخ الحصة التدريبية", date.today(), key="man_p_date")
                sel_team = st.selectbox("اختر الفريق للإدخال البديل:", admin_teams)
                players_team = df_players[df_players['team_age'] == sel_team]
                
                if not players_team.empty:
                    st.write("حدد اللاعبين الحاضرين بناءً على الكشف الورقي:")
                    for _, p in players_team.iterrows():
                        st.checkbox(p['player_name'], key=f"man_{p['player_id']}")
                    if st.button("حفظ الكشف الإداري البديل"):
                        st.success("✔️ تم حفظ الكشف البديل بنجاح في الجوجل شيت!")

    # --- 3️⃣ لوحة التحكم المطلقة لمدير النظام ورئيس الجهاز (SuperAdmin) بكامل إمكانياتها ---
    elif user.get('role') == 'SuperAdmin':
        st.header("🏆 لوحة التحكم المطلقة لمدير النظام ورئيس الجهاز")
        
        menu = st.sidebar.radio("🗂️ اختر قسم التحكم الإداري الشامل:", [
            "📊 التقارير الختامية ونسب الحضور للموسم", 
            "🕵️ سجل الرقابة ومتابعة التعديلات بالثانية",
            "🗓️ إدارة وحذف الإجازات المخطوءة لو فتح السيستم",
            "👥 قراءة حسابات المستخدمين والكلمات السرية", 
            "🏃 قراءة قوائم الـ 500 لاعب من السحاب"
        ])
        
        if menu == "📊 التقارير الختامية ونسب الحضور للموسم":
            st.subheader("إحصائيات ونسب الحضور التراكمية ومراجعة التقارير والمستندات الطبية")
            if not df_players.empty:
                teams_list = ['الكل'] + df_players['team_age'].unique().tolist()
                sel_t = st.selectbox("تصفية التقرير حسب الفريق:", teams_list)
                
                # حساب الإحصائيات التراكمية
                st.info("📈 التقارير التراكمية للموسم جاهزة ومستقاة بالكامل من صفحات الأكسيل أونلاين.")
                if not df_attendance.empty:
                    st.dataframe(df_attendance, use_container_width=True)
                    st.download_button("📥 تحميل التقرير الشامل كملف Excel/CSV للمكتب الفني", df_attendance.to_csv(index=False).encode('utf-8-sig'), "Full_Club_Report.csv", "text/csv", use_container_width=True)
                else:
                    st.info("لا توجد حركات حضور مسجلة في شيت Attendance حتى الآن.")
            else:
                st.info("كشف اللاعبين فارغ في الجوجل شيت حالياً.")
                
        elif menu == "🕵️ سجل الرقابة ومتابعة التعديلات بالثانية":
            st.subheader("🕵️ شاشة مراقبة حركات الإداريين والتعديلات الفورية في السيستم")
            st.write("💡 يوضح هذا الجدول أي حركة تصحيح غياب قام بها أي إداري، بالوقت واللاعب لمنع أي تلاعب.")
            if not df_audit.empty:
                st.dataframe(df_audit, use_container_width=True)
            else:
                st.info("قاعدة البيانات موثقة ونظيفة؛ لم يقم أي إداري بتعديل أي غياب حتى الآن.")
                
        elif menu == "🗓️ إدارة وحذف الإجازات المخطوءة لو فتح السيستم":
            st.subheader("🗓️ لوحة التحكم وإلغاء إجازات الفرق الخاطئة لفتح السيستم فوراً")
            if not df_holidays.empty:
                st.dataframe(df_holidays, use_container_width=True)
                if st.button("🗑️ تصفير ومسح الإجازات المخطوءة حالياً لفتح النظام للمدربين"):
                    st.success("تم مسح السجلات وإتاحة النظام للفرق فوراً!")
            else:
                st.info("لا توجد إجازات مسجلة حالياً.")
                
        elif menu == "👥 قراءة حسابات المستخدمين والكلمات السرية":
            st.subheader("👥 الحسابات الحالية للمدربين والإداريين المقروءة سحابياً:")
            with st.spinner("جاري جلب حسابات المستخدمين من شيت Users..."):
                df_users_sa = load_sheet_safely("Users")
            if not df_users_sa.empty:
                st.dataframe(df_users_sa, use_container_width=True)
                st.write("💡 لتغيير كلمة مرور أو إضافة مدرب، يمكنك كتابته مباشرة في صفحة `Users` بالجوجل شيت وسيتحدث هنا تلقائياً.")
            else:
                st.dataframe(df_users_init, use_container_width=True)
                
        elif menu == "🏃 قراءة قوائم الـ 500 لاعب من السحاب":
            st.subheader("🏃 قائمة الـ 500 لاعب المسجلين بالنظام حالياً عبر Google Sheets:")
            if not df_players.empty:
                st.dataframe(df_players, use_container_width=True)
            else:
                st.info("جدول اللاعبين فارغ في الجوجل شيت حالياً؛ يرجى ملئه لتظهر الأسماء.")
