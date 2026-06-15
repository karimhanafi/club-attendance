import streamlit as st
import sqlite3
from datetime import date
import datetime
import pandas as pd
import os
import shutil

DB_FILE = "club_attendance.db"
BACKUP_DIR = "backups"

# --- 1. نظام النسخ الاحتياطي التلقائي ---
def create_backup():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    if os.path.exists(DB_FILE):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_file = os.path.join(BACKUP_DIR, f"backup_{timestamp}.db")
        shutil.copy2(DB_FILE, backup_file)
        # الاحتفاظ بآخر 10 نسخ احتياطية فقط لعدم امتلاء المساحة
        all_backups = sorted([os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR)])
        if len(all_backups) > 10:
            os.remove(all_backups[0])

# تشغيل الباك أب تلقائياً مع كل تحديث للصفحة لحماية الداتا
create_backup()

# --- 2. تهيئة وتحديث قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # جدول المستخدمين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            User_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Username TEXT UNIQUE NOT NULL,
            Password TEXT NOT NULL,
            Full_Name TEXT NOT NULL,
            Role TEXT CHECK(Role IN ('Coach', 'Admin', 'SuperAdmin')) NOT NULL,
            Assigned_Teams TEXT -- أسماء الفرق مفصولة بفاصلة مثل (تحت 14 سنة,تحت 12 سنة)
        )
    ''')
    
    # جدول اللاعبين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Players (
            Player_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Player_Name TEXT NOT NULL,
            Team_Age TEXT NOT NULL,
            Gender TEXT CHECK(Gender IN ('ناشئين', 'ناشئات')) NOT NULL
        )
    ''')
    
    # جدول الحضور والغياب
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
    
    # جدول الإجازات
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
    
    # جدول الرقابة
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
    
    # حساب الأدمن الرئيسي الافتراضي لو الجداول فاضية
    if cursor.execute("SELECT COUNT(*) FROM Users").fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO Users (Username, Password, Full_Name, Role, Assigned_Teams)
            VALUES ('super_admin', '789', 'مدير النظام الرئيسي', 'SuperAdmin', 'الكل')
        ''')
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# --- إعدادات واجهة Streamlit ---
st.set_page_config(page_title="نظام الإدارة الشامل لفرق النادي", layout="wide")

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
else:
    user = st.session_state.user
    st.sidebar.title(f"👋 {user['Full_Name']}")
    st.sidebar.info(f"المنصب: {user['Role']}")
    
    if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()

    today_str = str(date.today())

    # --- 1. شاشة المدرب (Coach) ---
    if user['Role'] == 'Coach':
        st.header("📋 شاشة المدرب لتسجيل الحضور اليومي")
        st.info(f"📅 تاريخ اليوم التلقائي: {today_str}")
        
        # استخراج الفرق المربوطة بالمدرب ده
        teams_allowed = [t.strip() for t in user['Assigned_Teams'].split(",") if t.strip()]
        
        if not teams_allowed:
            st.warning("لم يتم ربط أي فرق بحسابك حالياً. راجع مدير النظام.")
        else:
            selected_team = st.selectbox("اختر الفريق المراد تسجيل حضوره الآن:", teams_allowed)
            
            conn = get_db_connection()
            players = conn.execute("SELECT * FROM Players WHERE Team_Age = ?", (selected_team,)).fetchall()
            
            # فحص التكرار
            player_ids = [p['Player_ID'] for p in players]
            already_submitted = False
            if player_ids:
                placeholders = ','.join('?' for _ in player_ids)
                check_exist = conn.execute(f"SELECT COUNT(*) FROM Attendance WHERE Date = ? AND Player_ID IN ({placeholders})", [today_str] + player_ids).fetchone()[0]
                if check_exist > 0:
                    already_submitted = True
            
            if already_submitted:
                st.error("⚠️ تم تسجيل حضور هذا الفريق اليوم بالفعل! لمنع التكرار لا يمكنك الإدخال مجدداً. راجع الإداري للتعديل.")
                conn.close()
            else:
                st.write("علّم على اللاعبين الحاضرين في تمرين اليوم:")
                attendance_dict = {}
                
                for p in players:
                    col_name, col_status = st.columns([3, 1])
                    with col_name:
                        excuse = conn.execute('SELECT Reason FROM Excuses_Log WHERE Player_ID = ? AND ? BETWEEN Start_Date AND End_Date', (p['Player_ID'], today_str)).fetchone()
                        if excuse:
                            st.write(f"🔹 {p['Player_Name']} *(⚠️ إجازة رسمية: {excuse['Reason']} )*")
                        else:
                            st.write(f"🔹 {p['Player_Name']}")
                    with col_status:
                        is_present = st.checkbox("حاضر", key=f"p_{p['Player_ID']}")
                        attendance_dict[p['Player_ID']] = "Present" if is_present else "Absent"
                
                if st.button("💾 حفظ وإرسال التقرير للإدارة", type="primary"):
                    now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    try:
                        for p_id, status in attendance_dict.items():
                            final_status = status
                            reason_str = None
                            if status == "Absent":
                                excuse = conn.execute('SELECT Reason FROM Excuses_Log WHERE Player_ID = ? AND ? BETWEEN Start_Date AND End_Date', (p_id, today_str)).fetchone()
                                if excuse:
                                    final_status = "Excused"
                                    reason_str = f"إجازة: {excuse['Reason']}"
                            
                            conn.execute('INSERT INTO Attendance (Date, Player_ID, Status, Excuse_Reason, Submitted_By, Timestamp) VALUES (?, ?, ?, ?, ?, ?)', (today_str, p_id, final_status, reason_str, user['Username'], now_ts))
                        conn.commit()
                        st.success("✔️ تم حفظ وإرسال حضور الفريق بنجاح!")
                        st.balloons()
                        st.rerun()
                    except Exception as e:
                        st.error(f"خطأ أثناء الحفظ: {e}")
                    finally:
                        conn.close()

    # --- 2. شاشة الإداري (Admin) ---
    elif user['Role'] == 'Admin':
        st.header("🛡️ لوحة تحكم ومراقبة الإداريين")
        tab1, tab2, tab3, tab4 = st.tabs(["📁 تسجيل إجازة رسمية", "🔄 مراجعة وتصحيح أخطاء الغياب", "📝 إدخال غياب يدوي (بديل للمدرب)", "📊 كشف التزام المدربين"])
        
        conn = get_db_connection()
        
        # تبويب 1: تسجيل الإجازات
        with tab1:
            st.subheader("تسجيل إجازة معتمدة بمستندات")
            all_players = [dict(row) for row in conn.execute("SELECT * FROM Players").fetchall()]
            if all_players:
                selected_p = st.selectbox("اختر اللاعب:", all_players, format_func=lambda x: f"{x['Team_Age']} - {x['Player_Name']}")
                col_s, col_e = st.columns(2)
                start_d = col_s.date_input("بداية الإجازة", date.today(), key="admin_s")
                end_d = col_e.date_input("نهاية الإجازة", date.today(), key="admin_e")
                exc_reason = st.selectbox("السبب:", ["إصابة", "سفر", "امتحانات"])
                if st.button("اعتماد الإجازة"):
                    conn.execute('INSERT INTO Excuses_Log (Player_ID, Start_Date, End_Date, Reason, Registered_By) VALUES (?, ?, ?, ?, ?)', (selected_p['Player_ID'], str(start_d), str(end_d), exc_reason, user['Username']))
                    conn.commit()
                    st.success("✔️ تم الحفظ بنجاح.")
                    st.rerun()
                    
        # تبويب 2: تعديل غياب
        with tab2:
            st.subheader("تعديل غياب أخطأ فيه مدرب")
            t_date = st.date_input("اختر التاريخ", date.today())
            records = conn.execute('SELECT a.Record_ID, a.Status, a.Submitted_By, p.Player_Name, p.Team_Age FROM Attendance a JOIN Players p ON a.Player_ID = p.Player_ID WHERE a.Date = ?', (str(t_date),)).fetchall()
            if records:
                r_list = [dict(r) for r in records]
                st.dataframe(pd.DataFrame(r_list)[['Team_Age', 'Player_Name', 'Status', 'Submitted_By']], use_container_width=True)
                to_edit = st.selectbox("اختر السجل للتعديل:", r_list, format_func=lambda x: f"{x['Team_Age']} - {x['Player_Name']} ({x['Status']})")
                new_st = st.selectbox("الحالة الجديدة:", ["Present", "Absent", "Excused"])
                if st.button("تحديث وتوثيق في الرقابة"):
                    now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    conn.execute("UPDATE Attendance SET Status = ?, Excuse_Reason = NULL WHERE Record_ID = ?", (new_st, to_edit['Record_ID']))
                    conn.execute('INSERT INTO Audit_Log (Attendance_Record_ID, Old_Status, New_Status, Modified_By, Modification_Time) VALUES (?, ?, ?, ?, ?)', (to_edit['Record_ID'], to_edit['Status'], new_st, user['Username'], now_ts))
                    conn.commit()
                    st.success("✔️ تم التعديل وتوثيقه.")
                    st.rerun()
            else:
                st.warning("لا توجد بيانات مسجلة في هذا التاريخ.")
                
        # تبويب 3: إدخال ورقي بديل للمدرب
        with tab3:
            st.subheader("تسجيل غياب وحضور نيابة عن المدرب (استلام ورقي)")
            teams_list = [r['Team_Age'] for r in conn.execute("SELECT DISTINCT Team_Age FROM Players").fetchall()]
            if teams_list:
                sel_team = st.selectbox("اختر الفريق المراد الإدخال له:", teams_list)
                p_date = st.date_input("تاريخ الحصة التدريبية", date.today(), key="admin_p_date")
                players_team = conn.execute("SELECT * FROM Players WHERE Team_Age = ?", (sel_team,)).fetchall()
                
                # فحص التكرار
                p_ids = [p['Player_ID'] for p in players_team]
                already_has_data = False
                if p_ids:
                    ph = ','.join('?' for _ in p_ids)
                    if conn.execute(f"SELECT COUNT(*) FROM Attendance WHERE Date = ? AND Player_ID IN ({ph})", [str(p_date)] + p_ids).fetchone()[0] > 0:
                        already_has_data = True
                        
                if already_has_data:
                    st.error("هذا الفريق لديه غياب مسجل بالفعل في هذا التاريخ.")
                else:
                    st.write("حدد اللاعبين الحاضرين بناءً على الكشف الورقي:")
                    manual_dict = {}
                    for p in players_team:
                        is_p = st.checkbox(p['Player_Name'], key=f"man_{p['Player_ID']}")
                        manual_dict[p['Player_ID']] = "Present" if is_p else "Absent"
                    if st.button("حفظ الكشف الإداري البديل"):
                        now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        for p_id, st_val in manual_dict.items():
                            conn.execute('INSERT INTO Attendance (Date, Player_ID, Status, Submitted_By, Timestamp) VALUES (?, ?, ?, ?, ?)', (str(p_date), p_id, st_val, f"الإداري نيابة عن المدرب ({user['Username']})", now_ts))
                        conn.commit()
                        st.success("✔️ تم حفظ الكشف بنجاح.")
                        st.rerun()
                        
        # تبويب 4: كشف الالتزام
        with tab4:
            st.subheader("👀 من من المدربين لم يسجل الحضور اليوم؟")
            check_d = st.date_input("اختر تاريخ المتابعة", date.today(), key="admin_check_d")
            all_teams = [r['Team_Age'] for r in conn.execute("SELECT DISTINCT Team_Age FROM Players").fetchall()]
            submitted = [r['Team_Age'] for r in conn.execute('SELECT DISTINCT p.Team_Age FROM Attendance a JOIN Players p ON a.Player_ID = p.Player_ID WHERE a.Date = ?', (str(check_d),)).fetchall()]
            
            st.write(f"📊 **وضعية الفرق بتاريخ {check_d}:**")
            for t in all_teams:
                if t in submitted:
                    details = conn.execute('SELECT DISTINCT a.Submitted_By, a.Timestamp FROM Attendance a JOIN Players p ON a.Player_ID = p.Player_ID WHERE a.Date = ? AND p.Team_Age = ?', (str(check_d), t)).fetchone()
                    st.success(f"✅ **فريق {t}**: تم التسجيل بواسطة ({details['Submitted_By']}) في الساعة {details['Timestamp']}")
                else:
                    st.error(f"❌ **فريق {t}**: ⚠️ لم يتم تسجيل الحضور حتى الآن!")
        conn.close()

    # --- 3. شاشة السوبر أدمن المطلقة (SuperAdmin / مدير النظام) ---
    elif user['Role'] == 'SuperAdmin':
        st.header("🏆 لوحة التحكم المطلقة لمدير النظام ورئيس الجهاز")
        
        # القائمة العلوية للتحكم الفوري في كل النظام
        menu = st.sidebar.radio("🗂️ اختر قسم التحكم الإداري:", [
            "📊 التقارير الختامية والأكسيل", 
            "👥 إدارة حسابات المستخدمين والكلمات السرية", 
            "🏃 إدارة قوائم اللاعبين والفرق",
            "🛡️ التحكم الشامل وحذف/تعديل الداتا"
        ])
        
        conn = get_db_connection()
        
        # القسم 1: التقارير والأكسيل
        if menu == "📊 التقارير الختامية والأكسيل":
            st.subheader("إحصائيات ونسب الحضور التراكمية للموسم")
            teams_list = ['الكل'] + [r['Team_Age'] for r in conn.execute("SELECT DISTINCT Team_Age FROM Players").fetchall()]
            sel_t = st.selectbox("تصفية التقرير حسب الفريق:", teams_list)
            
            query = 'SELECT p.Player_ID, p.Player_Name, p.Team_Age, COUNT(a.Record_ID) as total_sessions, SUM(CASE WHEN a.Status = "Present" THEN 1 ELSE 0 END) as present_days, SUM(CASE WHEN a.Status = "Absent" THEN 1 ELSE 0 END) as absent_days, SUM(CASE WHEN a.Status = "Excused" THEN 1 ELSE 0 END) as excused_days FROM Players p LEFT JOIN Attendance a ON p.Player_ID = a.Player_ID'
            if sel_t != 'الكل':
                query += f" WHERE p.Team_Age = '{sel_t}'"
            query += " GROUP BY p.Player_ID"
            
            rep = conn.execute(query).fetchall()
            if rep:
                df = pd.DataFrame([dict(r) for r in rep])
                df['نسبة الحضور (%)'] = df.apply(lambda r: round((r['present_days'] / r['total_sessions'] * 100), 1) if r['total_sessions'] > 0 else 0.0, axis=1)
                df.columns = ['ID اللاعب', 'اسم اللاعب', 'المرحلة السنية', 'إجمالي الحصص', 'أيام الحضور', 'أيام الغياب', 'أيام الغياب بعذر', 'نسبة الحضور (%)']
                st.dataframe(df, use_container_width=True)
                st.download_button("📥 تحميل التقرير الشامل كملف Excel/CSV", df.to_csv(index=False).encode('utf-8-sig'), "Full_Club_Report.csv", "text/csv", use_container_width=True)
            else:
                st.info("لا توجد بيانات حضور مسجلة حتى الآن.")
                
        # القسم 2: إدارة المستخدمين والفرق وباسورداتهم
        elif menu == "👥 إدارة حسابات المستخدمين والكلمات السرية":
            st.subheader("إضافة وتعديل حسابات المدربين والإداريين وباسورداتهم")
            
            # عرض المستخدمين الحاليين في جدول
            current_users = conn.execute("SELECT User_ID, Username, Password, Full_Name, Role, Assigned_Teams FROM Users").fetchall()
            st.write("👥 **المستخدمين الحاليين بالنظام:**")
            st.dataframe(pd.DataFrame([dict(u) for u in current_users]), use_container_width=True)
            
            st.write("---")
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.markdown("### ➕ إضافة مستخدم/مدرب جديد")
                new_user = st.text_input("اسم المستخدم (Username بالإنجليزية)")
                new_pass = st.text_input("كلمة المرور (Password)")
                new_name = st.text_input("الاسم بالكامل الثلاثي")
                new_role = st.selectbox("الصلاحية:", ["Coach", "Admin", "SuperAdmin"])
                new_teams = st.text_input("الفرق المسؤول عنها (افصل بينها بفاصلة لو أكتر من فرقة مثلاً: تحت 14 سنة, تحت 12 سنة)")
                
                if st.button("➕ إنشاء الحساب فوراً"):
                    if new_user and new_pass and new_name:
                        try:
                            conn.execute('INSERT INTO Users (Username, Password, Full_Name, Role, Assigned_Teams) VALUES (?, ?, ?, ?, ?)', (new_user, new_pass, new_name, new_role, new_teams))
                            conn.commit()
                            st.success("تم إنشاء حساب المستخدم بنجاح ومتاح له الدخول من موبايله حالياً!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"خطأ: اسم المستخدم موجود بالفعل أو {e}")
                            
            with col_b:
                st.markdown("### ✏️ تعديل / حذف حساب حالي")
                user_to_mod = st.selectbox("اختر الحساب المراد تعديله أو حذفه:", [dict(u) for u in current_users], format_func=lambda x: f"{x['Full_Name']} ({x['Username']})")
                mod_pass = st.text_input("تعديل كلمة المرور:", value=user_to_mod['Password'])
                mod_name = st.text_input("تعديل الاسم بالكامل:", value=user_to_mod['Full_Name'])
                mod_teams = st.text_input("تعديل الفرق المشرف عليها:", value=user_to_mod['Assigned_Teams'] if user_to_mod['Assigned_Teams'] else "")
                
                col_b1, col_b2 = st.columns(2)
                if col_b1.button("💾 حفظ التعديلات الإدارية", use_container_width=True):
                    conn.execute("UPDATE Users SET Password = ?, Full_Name = ?, Assigned_Teams = ? WHERE User_ID = ?", (mod_pass, mod_name, mod_teams, user_to_mod['User_ID']))
                    conn.commit()
                    st.success("تم التحديث!")
                    st.rerun()
                if col_b2.button("❌ حذف الحساب نهائياً", use_container_width=True):
                    if user_to_mod['Username'] == 'super_admin':
                        st.error("لا يمكنك حذف الحساب الرئيسي للنظام!")
                    else:
                        conn.execute("DELETE FROM Users WHERE User_ID = ?", (user_to_mod['User_ID'],))
                        conn.commit()
                        st.success("تم حذف المستخدم.")
                        st.rerun()

        # القسم 3: إدارة قوائم اللاعبين والتعديل الفوري للأسماء
        elif menu == "🏃 إدارة قوائم اللاعبين والفرق":
            st.subheader("إضافة وتعديل وحذف أسماء اللاعبين والمراحل السنية")
            
            all_p = conn.execute("SELECT * FROM Players").fetchall()
            if all_p:
                st.write("🏃 **قائمة اللاعبين المسجلين بالنظام حالياً:**")
                st.dataframe(pd.DataFrame([dict(i) for i in all_p]), use_container_width=True)
                
            st.write("---")
            col_p1, col_p2 = st.columns(2)
            
            with col_p1:
                st.markdown("### ➕ إضافة لاعب جديد للقائمة")
                p_name = st.text_input("اسم اللاعب بالكامل")
                p_team = st.text_input("المرحلة السنية (مثل: تحت 14 سنة)")
                p_gender = st.selectbox("النوع:", ["ناشئين", "ناشئات"])
                if st.button("➕ تسجيل اللاعب"):
                    if p_name and p_team:
                        conn.execute('INSERT INTO Players (Player_Name, Team_Age, Gender) VALUES (?, ?, ?)', (p_name, p_team, p_gender))
                        conn.commit()
                        st.success("تم إضافة اللاعب بنجاح!")
                        st.rerun()
                        
            with col_p2:
                st.markdown("### ✏️ تعديل اسم لاعب أو حذفه")
                if all_p:
                    p_to_mod = st.selectbox("اختر اللاعب المراد تعديله:", [dict(i) for i in all_p], format_func=lambda x: f"{x['Team_Age']} - {x['Player_Name']}")
                    mod_p_name = st.text_input("تعديل الاسم:", value=p_to_mod['Player_Name'])
                    mod_p_team = st.text_input("تعديل المرحلة السنية:", value=p_to_mod['Team_Age'])
                    
                    col_p_b1, col_p_b2 = st.columns(2)
                    if col_p_b1.button("💾 حفظ تعديل اسم اللاعب", use_container_width=True):
                        conn.execute("UPDATE Players SET Player_Name = ?, Team_Age = ? WHERE Player_ID = ?", (mod_p_name, mod_p_team, p_to_mod['Player_ID']))
                        conn.commit()
                        st.success("تم تعديل بيانات اللاعب بنجاح!")
                        st.rerun()
                    if col_p_b2.button("❌ حذف اللاعب نهائياً من النادي", use_container_width=True):
                        conn.execute("DELETE FROM Players WHERE Player_ID = ?", (p_to_mod['Player_ID'],))
                        conn.commit()
                        st.success("تم حذف اللاعب بنجاح.")
                        st.rerun()

        # القسم 4: التحكم المطلق في حركة الغياب (حذف وإلغاء أي داتا)
        elif menu == "🛡️ التحكم الشامل وحذف/تعديل الداتا":
            st.subheader("❌ شاشة إلغاء وحذف أي حصة تدريبية أو حركة حضور مسجلة بالخطأ")
            st.warning("تحذير: الحذف من هذه الشاشة نهائي ويمسح السجلات من قاعدة البيانات!")
            
            all_attendance = conn.execute('SELECT a.Record_ID, a.Date, a.Status, p.Player_Name, p.Team_Age FROM Attendance a JOIN Players p ON a.Player_ID = p.Player_ID ORDER BY a.Date DESC').fetchall()
            if all_attendance:
                att_list = [dict(r) for r in all_attendance]
                to_delete = st.selectbox("اختر حركة الحضور المراد حذفها وإلغائها تماماً:", att_list, format_func=lambda x: f"تاريخ {x['Date']} | {x['Team_Age']} - {x['Player_Name']} ({x['Status']})")
                if st.button("❌ حذف وإلغاء هذه الحركة نهائياً"):
                    conn.execute("DELETE FROM Attendance WHERE Record_ID = ?", (to_delete['Record_ID'],))
                    conn.commit()
                    st.success("تم حذف وإلغاء حركة الحضور بنجاح من قاعدة البيانات!")
                    st.rerun()
            else:
                st.info("لا توجد سجلات حضور بالنظام حالياً لحذفها.")
                
        conn.close()
