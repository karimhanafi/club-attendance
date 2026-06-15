import streamlit as st
import sqlite3
from datetime import date
import datetime
import pandas as pd

DB_FILE = "club_attendance.db"

# دالة للاتصال بقاعدة البيانات وإنشاء الجداول تلقائياً من الصفر
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # 1. جدول المستخدمين (المدربين والإداريين)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            User_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Username TEXT UNIQUE NOT NULL,
            Password TEXT NOT NULL,
            Full_Name TEXT NOT NULL,
            Role TEXT CHECK(Role IN ('Coach', 'Admin', 'SuperAdmin')) NOT NULL,
            Assigned_Team TEXT
        )
    ''')
    
    # 2. جدول اللاعبين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Players (
            Player_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Player_Name TEXT NOT NULL,
            Team_Age TEXT NOT NULL,
            Gender TEXT CHECK(Gender IN ('ناشئين', 'ناشئات')) NOT NULL
        )
    ''')
    
    # 3. جدول الحضور والغياب اليومي
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Attendance (
            Record_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Date TEXT NOT NULL,
            Player_ID INTEGER,
            Status TEXT CHECK(Status IN ('Present', 'Absent', 'Excused')) NOT NULL,
            Excuse_Reason TEXT,
            Submitted_By TEXT NOT NULL,
            Timestamp TEXT NOT NULL,
            FOREIGN KEY (Player_ID) REFERENCES Players(Player_ID),
            UNIQUE(Date, Player_ID)
        )
    ''')
    
    # 4. جدول الإجازات الرسمية المسجلة بالأوراق
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Excuses_Log (
            Excuse_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Player_ID INTEGER,
            Start_Date TEXT NOT NULL,
            End_Date TEXT NOT NULL,
            Reason TEXT CHECK(Reason IN ('إصابة', 'سفر', 'امتحانات')) NOT NULL,
            Registered_By TEXT NOT NULL,
            FOREIGN KEY (Player_ID) REFERENCES Players(Player_ID)
        )
    ''')
    
    # 5. جدول سجل التعديلات الإدارية (الرقابة)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Audit_Log (
            Log_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Attendance_Record_ID INTEGER,
            Old_Status TEXT,
            New_Status TEXT,
            Modified_By TEXT,
            Modification_Time TEXT,
            FOREIGN KEY (Attendance_Record_ID) REFERENCES Attendance(Record_ID)
        )
    ''')
    
    # إضافة حسابات تجريبية للمرة الأولى فقط لتتمكن من الدخول
    users_count = cursor.execute("SELECT COUNT(*) FROM Users").fetchone()[0]
    if users_count == 0:
        users = [
            ('cap_karim', '123', 'كابتن كريم', 'Coach', 'تحت 14 سنة'),
            ('cap_ahmed', '123', 'كابتن أحمد', 'Coach', 'تحت 12 سنة'),
            ('admin_safaa', '456', 'أستاذة صفاء (إداري)', 'Admin', 'الكل'),
            ('super_admin', '789', 'مدير النظام (رئيس الجهاز)', 'SuperAdmin', 'الكل')
        ]
        cursor.executemany('''
            INSERT INTO Users (Username, Password, Full_Name, Role, Assigned_Team)
            VALUES (?, ?, ?, ?, ?)
        ''', users)
        
        # إضافة لاعبين تجريبيين للمرة الأولى
        players = [
            ('أحمد محمد البدري', 'تحت 14 سنة', 'ناشئين'),
            ('يوسف عمر حلمي', 'تحت 14 سنة', 'ناشئين'),
            ('زياد كريم ممدوح', 'تحت 14 سنة', 'ناشئين'),
            ('خديجة كريم أحمد', 'تحت 14 سنة', 'ناشئات'),
            ('مروان حازم شديد', 'تحت 12 سنة', 'ناشئين'),
            ('مصطفى محمود عبد العال', 'تحت 12 سنة', 'ناشئين')
        ]
        cursor.executemany('''
            INSERT INTO Players (Player_Name, Team_Age, Gender)
            VALUES (?, ?, ?)
        ''', players)
        
    conn.commit()
    conn.close()

# تشغيل تهيئة قاعدة البيانات تلقائياً عند تشغيل السيرفر
init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# إعداد واجهة Streamlit
st.set_page_config(page_title="نظام إدارة حضور فرق النادي", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

# --- شاشة تسجيل الدخول ---
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center; color: #1E3A8A;'>⚽ نظام إدارة ومتابعة حضور فرق النادي</h2>", unsafe_allow_html=True)
    st.write("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("تسجيل الدخول")
        username = st.text_input("اسم المستخدم")
        password = st.text_input("كلمة المرور", type="password")
        if st.button("دخول", use_container_width=True):
            conn = get_db_connection()
            user = conn.execute("SELECT * FROM Users WHERE Username = ? AND Password = ?", (username, password)).fetchone()
            conn.close()
            if user:
                st.session_state.logged_in = True
                st.session_state.user = dict(user)
                st.rerun()
            else:
                st.error("اسم المستخدم أو كلمة المرور غير صحيحة")

# --- الشاشات بعد تسجيل الدخول ---
else:
    user = st.session_state.user
    
    st.sidebar.title(f"👋 {user['Full_Name']}")
    st.sidebar.info(f"الصلاحية: {user['Role']}")
    if user['Assigned_Team'] and user['Assigned_Team'] != 'الكل':
        st.sidebar.write(f"الفريق: {user['Assigned_Team']}")
        
    if st.sidebar.button("تسجيل الخروج", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()

    today_str = str(date.today())

    # --- 1. شاشة المدرب ---
    if user['Role'] == 'Coach':
        st.header(f"📋 تسجيل حضور فريق: {user['Assigned_Team']}")
        st.info(f"📅 تاريخ اليوم التلقائي: {today_str}")
        
        conn = get_db_connection()
        players = conn.execute("SELECT * FROM Players WHERE Team_Age = ?", (user['Assigned_Team'],)).fetchall()
        
        # فحص هل قام بالتسجيل اليوم مسبقاً لمنع التكرار؟
        player_ids = [p['Player_ID'] for p in players]
        already_submitted = False
        if player_ids:
            placeholders = ','.join('?' for _ in player_ids)
            check_exist = conn.execute(f"SELECT COUNT(*) FROM Attendance WHERE Date = ? AND Player_ID IN ({placeholders})", [today_str] + player_ids).fetchone()[0]
            if check_exist > 0:
                already_submitted = True
        
        if already_submitted:
            st.error("⚠️ تم تسجيل حضور هذا اليوم بالفعل لهذا الفريق! لا يمكنك الإدخال مجدداً لمنع التكرار. يرجى مراجعة الإداري للتعديل.")
            conn.close()
        else:
            st.write("الرجاء تحديد اللاعبين الحاضرين في تمرين اليوم:")
            attendance_dict = {}
            
            for p in players:
                col_name, col_status = st.columns([3, 1])
                with col_name:
                    # فحص هل للاعب إجازة رسمية مسجلة اليوم؟
                    excuse = conn.execute('''
                        SELECT Reason FROM Excuses_Log 
                        WHERE Player_ID = ? AND ? BETWEEN Start_Date AND End_Date
                    ''', (p['Player_ID'], today_str)).fetchone()
                    
                    if excuse:
                        st.write(f"🔹 {p['Player_Name']} *(⚠️ لديه إجازة رسمية: {excuse['Reason']} )*")
                    else:
                        st.write(f"🔹 {p['Player_Name']}")
                        
                with col_status:
                    is_present = st.checkbox("حاضر", key=f"p_{p['Player_ID']}")
                    attendance_dict[p['Player_ID']] = "Present" if is_present else "Absent"
            
            if st.button("حفظ وإرسال تقرير اليوم", type="primary"):
                now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                try:
                    for p_id, status in attendance_dict.items():
                        final_status = status
                        reason_str = None
                        
                        # إذا كان غائباً، نتحقق تلقائياً من جدول الإجازات
                        if status == "Absent":
                            excuse = conn.execute('''
                                SELECT Reason FROM Excuses_Log 
                                WHERE Player_ID = ? AND ? BETWEEN Start_Date AND End_Date
                            ''', (p_id, today_str)).fetchone()
                            if excuse:
                                final_status = "Excused"
                                reason_str = f"إجازة: {excuse['Reason']}"
                        
                        conn.execute('''
                            INSERT INTO Attendance (Date, Player_ID, Status, Excuse_Reason, Submitted_By, Timestamp)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (today_str, p_id, final_status, reason_str, user['Username'], now_ts))
                    conn.commit()
                    st.success("✔️ تم حفظ وإرسال تقرير الحضور بنجاح اليوم!")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"حدث خطأ أثناء الحفظ: {e}")
                finally:
                    conn.close()

    # --- 2. شاشة الإداري ---
    elif user['Role'] == 'Admin':
        st.header("🛡️ لوحة تحكم ومراقبة الإداريين")
        
        tab1, tab2, tab3 = st.tabs(["📁 تسجيل الإجازات الرسمية", "🔄 مراجعة وتعديل غياب يوم سابق", "📊 التزام المدربين"])
        
        conn = get_db_connection()
        
        with tab1:
            st.subheader("تسجيل إجازة/عذر رسمي للاعب بناءً على مستندات")
            all_players = [dict(row) for row in conn.execute("SELECT * FROM Players").fetchall()]
            
            if not all_players:
                st.warning("لا يوجد لاعبين مسجلين في النظام حالياً.")
            else:
                selected_p = st.selectbox(
                    "اختر اللاعب:", 
                    all_players, 
                    format_func=lambda x: f"{x['Team_Age']} - {x['Player_Name']}"
                )
            
                col_s, col_e = st.columns(2)
                with col_s:
                    start_d = st.date_input("بداية الإجازة", date.today(), key="exc_start")
                with col_e:
                    end_d = st.date_input("نهاية الإجازة", date.today(), key="exc_end")
                    
                exc_reason = st.selectbox("سبب الإجازة القانوني:", ["إصابة", "سفر", "امتحانات"])
                
                if st.button("تسجيل واعتماد الإجازة رسمياً"):
                    if start_d > end_d:
                        st.error("تاريخ البداية لا يمكن أن يكون بعد تاريخ النهاية!")
                    else:
                        conn.execute('''
                            INSERT INTO Excuses_Log (Player_ID, Start_Date, End_Date, Reason, Registered_By)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (selected_p['Player_ID'], str(start_d), str(end_d), exc_reason, user['Username']))
                        conn.commit()
                        st.success(f"✔️ تم اعتماد إجازة اللاعب بنجاح!")
                        st.rerun()
                    
        with tab2:
            st.subheader("تعديل وتصحيح أخطاء المدربين")
            target_date = st.date_input("اختر التاريخ للتعديل", date.today())
            
            records_raw = conn.execute('''
                SELECT a.Record_ID, a.Date, a.Status, a.Submitted_By, p.Player_Name, p.Team_Age 
                FROM Attendance a
                JOIN Players p ON a.Player_ID = p.Player_ID
                WHERE a.Date = ?
            ''', (str(target_date),)).fetchall()
            
            if not records_raw:
                st.warning("لا توجد بيانات مسجلة في هذا التاريخ حتى الآن.")
            else:
                records_list = [dict(r) for r in records_raw]
                
                df_records = pd.DataFrame(records_list)
                st.dataframe(df_records[['Team_Age', 'Player_Name', 'Status', 'Submitted_By']], use_container_width=True)
                
                record_to_edit = st.selectbox(
                    "اختر السجل المراد تعديله:", 
                    records_list, 
                    format_func=lambda x: f"{x['Team_Age']} - {x['Player_Name']} (الحالي: {x['Status']})"
                )
                
                new_status = st.selectbox("الحالة الجديدة المعدلة:", ["Present", "Absent", "Excused"])
                
                if st.button("تحديث السجل وتوثيقه في الرقابة"):
                    if new_status == record_to_edit['Status']:
                        st.info("لم تقم بتغيير الحالة.")
                    else:
                        now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        conn.execute("UPDATE Attendance SET Status = ?, Excuse_Reason = NULL WHERE Record_ID = ?", (new_status, record_to_edit['Record_ID']))
                        conn.execute('''
                            INSERT INTO Audit_Log (Attendance_Record_ID, Old_Status, New_Status, Modified_By, Modification_Time)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (record_to_edit['Record_ID'], record_to_edit['Status'], new_status, user['Username'], now_ts))
                        conn.commit()
                        st.success("✔️ تم التعديل وتوثيق الحركة.")
                        st.rerun()
                        
        with tab3:
            st.subheader("كشف التزام المدربين باليوم")
            check_date = st.date_input("اختر تاريخ المتابعة", date.today())
            submitted_teams = conn.execute('''
                SELECT DISTINCT p.Team_Age, a.Submitted_By, a.Timestamp 
                FROM Attendance a
                JOIN Players p ON a.Player_ID = p.Player_ID
                WHERE a.Date = ?
            ''', (str(check_date),)).fetchall()
            
            if submitted_teams:
                for t in submitted_teams:
                    st.write(f"✅ **فريق {t['Team_Age']}** | سجل بواسطة: {t['Submitted_By']} | في تمام الساعة: {t['Timestamp']}")
            else:
                st.error("⚠️ لم يقم أي مدرب بتسجيل الحضور في هذا التاريخ حتى الآن!")
                
        conn.close()

    # --- 3. شاشة رئيس الجهاز (Super Admin) ---
    elif user['Role'] == 'SuperAdmin':
        st.header("🏆 لوحة التحكم العليا (رئيس الجهاز والمشرف العام)")
        
        conn = get_db_connection()
        total_players = conn.execute("SELECT COUNT(*) FROM Players").fetchone()[0]
        total_coaches = conn.execute("SELECT COUNT(*) FROM Users WHERE Role = 'Coach'").fetchone()[0]
        
        col1, col2 = st.columns(2)
        col1.metric("إجمالي اللاعبين بالنظام", total_players)
        col2.metric("عدد المدربين المسجلين", total_coaches)
        
        st.write("---")
        st.subheader("📊 التقارير الختامية ونسب الحضور التراكمية للموسم كامل")
        
        teams_list = ['الكل'] + [r['Team_Age'] for r in conn.execute("SELECT DISTINCT Team_Age FROM Players").fetchall()]
        selected_team_report = st.selectbox("تصفية التقارير حسب الفريق:", teams_list)
        
        query = '''
            SELECT p.Player_Name, p.Team_Age,
                   COUNT(a.Record_ID) as total_sessions,
                   SUM(CASE WHEN a.Status = 'Present' THEN 1 ELSE 0 END) as present_days,
                   SUM(CASE WHEN a.Status = 'Absent' THEN 1 ELSE 0 END) as absent_days,
                   SUM(CASE WHEN a.Status = 'Excused' THEN 1 ELSE 0 END) as excused_days,
                   GROUP_CONCAT(DISTINCT a.Excuse_Reason) as excuse_details
            FROM Players p
            LEFT JOIN Attendance a ON p.Player_ID = a.Player_ID
            '''
        if selected_team_report != 'الكل':
            query += f" WHERE p.Team_Age = '{selected_team_report}'"
        query += " GROUP BY p.Player_ID"
        
        report_data = conn.execute(query).fetchall()
        conn.close()
        
        if report_data:
            df_report = pd.DataFrame([dict(r) for r in report_data])
            df_report['نسبة الحضور (%)'] = df_report.apply(
                lambda row: round((row['present_days'] / row['total_sessions'] * 100), 1) if row['total_sessions'] > 0 else 0.0, axis=1
            )
            
            df_report.columns = ['اسم اللاعب', 'المرحلة السنية', 'إجمالي الحصص', 'أيام الحضور', 'أيام الغياب', 'أيام الغياب بعذر', 'تفاصيل الأعذار المسجلة', 'نسبة الحضور (%)']
            st.dataframe(df_report, use_container_width=True)
            
            csv = df_report.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 تحميل التقرير الختامي والموسمي كملف Excel/CSV", csv, "Final_Attendance_Report.csv", "text/csv", use_container_width=True)
        else:
            st.info("لا توجد بيانات حضور مسجلة لحساب النسب حتى الآن.")
