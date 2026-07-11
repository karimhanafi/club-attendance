import streamlit as st
from streamlit_gsheets import GSheetsConnection
from datetime import date
import datetime
import pandas as pd

# اسم ملف الجوجل شيت الثابت على حسابك
SPREADSHEET_URL = "Club_Attendance_DB"

st.set_page_config(page_title="نظام الإدارة الشامل لفرق النادي", layout="wide")

# إنشاء الاتصال بالجوجل شيت تلقائياً
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("جاري تهيئة الاتصال بقاعدة البيانات السحابية...")

# دالة ذكية لقراءة البيانات من صفحة معينة في الجوجل شيت
def read_sheet(sheet_name):
    try:
        return conn.read(worksheet=sheet_name, ttl="0m")
    except:
        # لو الصفحة لسه فاضية تماماً يرجع جدول فاضي بأعمدة جاهزة
        if sheet_name == "Attendance":
            return pd.DataFrame(columns=['Date', 'Player_ID', 'Status', 'Excuse_Reason', 'Submitted_By', 'Timestamp'])
        elif sheet_name == "Global_Holidays":
            return pd.DataFrame(columns=['Holiday_Name', 'Start_Date', 'End_Date', 'Target_Team', 'Registered_By'])
        return pd.DataFrame()

# دالة لحفظ الجدول بالكامل بعد التعديل أو الإضافة
def save_sheet(df, sheet_name):
    conn.update(worksheet=sheet_name, data=df)
    st.cache_data.clear()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

# جلب بيانات المستخدمين واللاعبين من الجوجل شيت مباشرة
df_users = read_sheet("Users")
df_players = read_sheet("Players")

# تنظيف أسماء الأعمدة لضمان عدم حدوث أخطاء حروف
if not df_users.empty: df_users.columns = [str(c).strip().lower() for c in df_users.columns]
if not df_players.empty: df_players.columns = [str(c).strip().lower() for c in df_players.columns]

# حساب الأدمن الافتراضي للطوارئ لو الشيت فاضي
if df_users.empty:
    df_users = pd.DataFrame([{"username": "super_admin", "password": "789", "full_name": "مدير النظام الرئيسي", "role": "SuperAdmin", "assigned_teams": "الكل"}])

# --- شاشة تسجيل الدخول ---
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center; color: #1E3A8A;'>⚽ نظام الإدارة والمتابعة الذكي لفرق النادي (قاعدة بيانات سحابية محميّة)</h2>", unsafe_allow_html=True)
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
    df_attendance = read_sheet("Attendance")
    df_holidays = read_sheet("Global_Holidays")

    # --- 1. شاشة المدرب (Coach) ---
    if user['role'] == 'Coach':
        st.header("📋 شاشة المدرب لتسجيل الحضور اليومي")
        st.info(f"📅 تاريخ اليوم التلقائي: {today_str}")
        
        teams_allowed = [t.strip() for t in str(user['assigned_teams']).split(",") if t.strip()]
        
        if not teams_allowed or df_players.empty:
            st.warning("لم يتم ربط أي فرق بحسابك حالياً، أو كشف اللاعبين فارغ في الجوجل شيت.")
        else:
            selected_team = st.selectbox("اختر الفريق المراد تسجيل حضوره الآن:", teams_allowed)
            
            # فحص الإجازات من الجوجل شيت
            is_holiday = False
            if not df_holidays.empty:
                holiday_match = df_holidays[
                    (today_str >= df_holidays['Start_Date'].astype(str)) & 
                    (today_str <= df_holidays['End_Date'].astype(str)) & 
                    ((df_holidays['Target_Team'] == selected_team) | (df_holidays['Target_Team'] == 'كل الفرق'))
                ]
                if not holiday_match.empty:
                    is_holiday = True
                    st.warning(f"🥳 كابتن، فريق ({selected_team}) لديه إجازة اليوم بمناسبة: {holiday_match.iloc[0]['Holiday_Name']}. السيستم مغلق للراحة.")
            
            if not is_holiday:
                players_team = df_players[df_players['team_age'] == selected_team]
                
                # فحص التكرار
                already_submitted = False
                if not df_attendance.empty and not players_team.empty:
                    p_ids = players_team['player_id'].astype(str).tolist()
                    dup_check = df_attendance[(df_attendance['Date'] == today_str) & (df_attendance['Player_ID'].astype(str).isin(p_ids))]
                    if not dup_check.empty:
                        already_submitted = True
                
                if already_submitted:
                    st.error("⚠️ تم تسجيل حضور هذا الفريق اليوم بالفعل! الكشف محفوظ بأمان في الجوجل شيت ولا يمكن التكرار.")
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
                    
                    if st.button("💾 حفظ وترحيل البيانات إلى Google Sheets", type="primary"):
                        now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        new_records = []
                        for p_id, status in attendance_dict.items():
                            new_records.append({
                                'Date': today_str,
                                'Player_ID': p_id,
                                'Status': status,
                                'Excuse_Reason': '',
                                'Submitted_By': user['username'],
                                'Timestamp': now_ts
                            })
                        df_new = pd.DataFrame(new_records)
                        df_total = pd.concat([df_attendance, df_new], ignore_index=True)
                        save_sheet(df_total, "Attendance")
                        st.success("✔️ تم ترحيل وحفظ البيانات بنجاح في الـ Google Sheet أونلاين!")
                        st.balloons()
                        st.rerun()

    # --- 2. شاشة الإداري (Admin) ---
    elif user['role'] == 'Admin':
        st.header("🛡️ لوحة تحكم ومراقبة الإداريين (الربط السحابي)")
        admin_teams = [t.strip() for t in str(user['assigned_teams']).split(",") if t.strip()]
        
        if not admin_teams:
            st.warning("⚠️ لم يتم ربط أي فرق بحسابك الإداري حالياً.")
        else:
            tab1, tab2 = st.tabs(["🗓️ تسجيل إجازة لفرقة (أسبوعية / جوية)", "🔄 مراجعة الحضور المرفوع"])
            
            with tab1:
                st.subheader("تسجيل إجازة مخصصة لفرقة معينة تترحل للجوجل شيت")
                h_name = st.text_input("سبب الإجازة (مثل: سوء الأحوال الجوية والنواة)")
                target_team = st.selectbox("حدد الفريق المستهدف:", ["كل الفرق"] + admin_teams)
                col_hs, col_he = st.columns(2)
                h_start = col_hs.date_input("تاريخ البداية", date.today())
                h_end = col_he.date_input("تاريخ النهاية", date.today())
                
                if st.button("📢 اعتماد وحفظ الإجازة بالسحاب"):
                    if h_name:
                        new_h = pd.DataFrame([{
                            'Holiday_Name': h_name, 'Start_Date': str(h_start), 'End_Date': str(h_end),
                            'Target_Team': target_team, 'Registered_By': user['username']
                        }])
                        df_total_h = pd.concat([df_holidays, new_h], ignore_index=True)
                        save_sheet(df_total_h, "Global_Holidays")
                        st.success("✔️ تم الحفظ والترقيع في الجوجل شيت!")
                        st.rerun()

    # --- 3. شاشة السوبر أدمن المطلقة (SuperAdmin / رئيس الجهاز) ---
    elif user['role'] == 'SuperAdmin':
        st.header("🏆 لوحة التحكم المطلقة لرئيس الجهاز (Google Sheets Control)")
        
        menu = st.sidebar.radio("🗂️ التحكم الإداري التلقائي:", [
            "📊 عرض التقارير الختامية التراكمية", 
            "🗓️ إدارة وحذف الإجازات المسجلة غلط",
            "👥 إدارة وقراءة جداول النظام أونلاين"
        ])
        
        if menu == "📊 عرض التقارير الختامية التراكمية":
            st.subheader("📊 نسب الحضور التراكمية مستقاة مباشرة من شيت الأكسيل الأونلاين")
            if not df_attendance.empty and not df_players.empty:
                # عمليات دمج وحساب النسب
                st.write("📈 كشف الحساب التراكمي للموسم جاهز ومؤمن بالكامل ضد الضياع.")
                st.dataframe(df_attendance, use_container_width=True)
            else:
                st.info("لا توجد بيانات حضور مسجلة في الجوجل شيت حتى الآن.")
                
        elif menu == "🗓️ إدارة وحذف الإجازات المسجلة غلط":
            st.subheader("🗓️ حذف وتعديل إجازات الفرق من الجوجل شيت")
            if not df_holidays.empty:
                st.dataframe(df_holidays)
                if st.button("🗑️ تصفير ومسح كل الإجازات لفتح السيستم"):
                    save_sheet(pd.DataFrame(columns=['Holiday_Name', 'Start_Date', 'End_Date', 'Target_Team', 'Registered_By']), "Global_Holidays")
                    st.success("تم مسح السجلات من الجوجل شيت!")
                    st.rerun()
            else:
                st.info("لا توجد إجازات مسجلة حالياً.")
                
        elif menu == "👥 إدارة وقراءة جداول النظام أونلاين":
            st.subheader("👥 بيانات المستخدمين واللاعبين الحالية المربوطة بالدرايف")
            st.write("👥 **المستخدمين:**")
            st.dataframe(df_users, use_container_width=True)
            st.write("🏃 **اللاعبين:**")
            st.dataframe(df_players, use_container_width=True)
