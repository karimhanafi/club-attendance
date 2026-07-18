import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import date
import datetime

# =========================================================================
# 🔗 إعدادات الاتصال بالجوجل شيت
# =========================================================================
# ID الشيت (الجزء اللي بين d/ و /edit في رابط الشيت بتاعك)
SHEET_ID = "https://docs.google.com/spreadsheets/d/1_kD3rKqxntVGGMNEPwT8vsx2ylyiq05rm1wUh1lqOYQ/edit?usp=drivesdk"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

DEFAULT_COLUMNS = {
    "attendance": ["date", "player_id", "status", "excuse_reason", "submitted_by", "timestamp"],
    "global_holidays": ["holiday_name", "start_date", "end_date", "target_team", "registered_by"],
    "excuses_log": ["player_id", "start_date", "end_date", "reason", "document_link", "registered_by"],
    "audit_log": ["player_name", "team_age", "old_status", "new_status", "modified_by", "modification_time"],
    "users": ["username", "password", "full_name", "role", "assigned_teams"],
    "players": ["player_id", "player_name", "team_age"],
}

st.set_page_config(page_title="نظام الإدارة الشامل لفرق النادي", layout="wide")


# =========================================================================
# 🔌 طبقة الاتصال بجوجل شيت (gspread + Service Account) — القراءة والكتابة الحقيقية
# =========================================================================
@st.cache_resource(show_spinner=False)
def get_gspread_client():
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    client = get_gspread_client()
    return client.open_by_key(SHEET_ID)


@st.cache_data(ttl=15, show_spinner=False)
def load_sheet_safely(sheet_name):
    """قراءة صفحة معينة بالاسم فعليًا (مش أول صفحة في الملف زي قبل)."""
    try:
        sh = get_spreadsheet()
        worksheet = sh.worksheet(sheet_name)
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"⚠️ الصفحة '{sheet_name}' مش موجودة في الشيت بنفس الاسم ده بالظبط (تأكد من اسم الـ Tab).")
        return pd.DataFrame(columns=DEFAULT_COLUMNS.get(sheet_name.lower(), []))
    except Exception as e:
        st.error(f"⚠️ فشل الاتصال بصفحة '{sheet_name}': {e}")
        return pd.DataFrame(columns=DEFAULT_COLUMNS.get(sheet_name.lower(), []))


def append_row_to_sheet(sheet_name, row_dict):
    """إضافة صف جديد فعليًا في الشيت، مع مطابقة القيم لترتيب الأعمدة الحقيقي."""
    try:
        sh = get_spreadsheet()
        worksheet = sh.worksheet(sheet_name)
        headers = worksheet.row_values(1)
        if not headers:
            st.error(f"⚠️ صفحة '{sheet_name}' لا تحتوي على صف عناوين (Headers) في السطر الأول.")
            return False
        row_values = [str(row_dict.get(h.strip().lower(), "")) for h in headers]
        worksheet.append_row(row_values, value_input_option="USER_ENTERED")
        load_sheet_safely.clear()
        return True
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"⚠️ الصفحة '{sheet_name}' مش موجودة. تأكد من اسم الـ Tab في الشيت.")
        return False
    except Exception as e:
        st.error(f"⚠️ فشل الحفظ في '{sheet_name}': {e}")
        return False


def update_attendance_status(record_date, player_id, new_status):
    """تعديل حالة حضور موجودة بالفعل (بدل ما تتضاف كصف جديد)."""
    try:
        sh = get_spreadsheet()
        worksheet = sh.worksheet("Attendance")
        headers = [h.strip().lower() for h in worksheet.row_values(1)]
        if not all(c in headers for c in ("date", "player_id", "status")):
            st.error("⚠️ صفحة Attendance ناقصها أعمدة أساسية (date / player_id / status).")
            return False
        date_col = headers.index("date")
        pid_col = headers.index("player_id")
        status_col = headers.index("status") + 1  # gspread أعمدة بتبدأ من 1
        all_rows = worksheet.get_all_values()[1:]
        for i, row in enumerate(all_rows, start=2):  # الصف 2 هو أول صف بيانات فعلي
            if len(row) > max(date_col, pid_col) and row[date_col] == str(record_date) and row[pid_col] == str(player_id):
                worksheet.update_cell(i, status_col, new_status)
                load_sheet_safely.clear()
                return True
        st.error("⚠️ لم يتم العثور على صف الحضور المطلوب تعديله.")
        return False
    except Exception as e:
        st.error(f"⚠️ فشل التعديل: {e}")
        return False


def clear_sheet_data(sheet_name):
    """مسح كل الصفوف ما عدا صف العناوين."""
    try:
        sh = get_spreadsheet()
        worksheet = sh.worksheet(sheet_name)
        if worksheet.row_count > 1:
            worksheet.batch_clear([f"A2:Z{worksheet.row_count}"])
        load_sheet_safely.clear()
        return True
    except Exception as e:
        st.error(f"⚠️ فشل المسح: {e}")
        return False


# =========================================================================
# 🔑 شاشة تسجيل الدخول
# =========================================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

df_users_init = pd.DataFrame([{
    "username": "admin",
    "password": "123",
    "full_name": "مدير النظام الرئيسي (كابتن كريم)",
    "role": "SuperAdmin",
    "assigned_teams": "الكل",
}])

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
                    if not df_users.empty and "username" in df_users.columns and "password" in df_users.columns:
                        user_check = df_users[
                            (df_users["username"].astype(str) == username_input)
                            & (df_users["password"].astype(str) == password_input)
                        ]
                        if not user_check.empty:
                            st.session_state.logged_in = True
                            st.session_state.user = user_check.iloc[0].to_dict()
                            st.rerun()
                        else:
                            st.error("اسم المستخدم أو كلمة المرور غير صحيحة")
                    else:
                        st.error("اسم المستخدم غير صحيح أو هناك مشكلة في الاتصال بشيت Users حالياً.")

        with st.expander("🔧 فحص الاتصال بالجوجل شيت (لو في مشكلة في الدخول أو البيانات)"):
            if st.button("اختبار الاتصال الآن"):
                try:
                    sh = get_spreadsheet()
                    tabs = [ws.title for ws in sh.worksheets()]
                    st.success("✅ الاتصال ناجح!")
                    st.write("الصفحات (Tabs) الموجودة في الشيت:", tabs)
                except Exception as e:
                    st.error(f"❌ فشل الاتصال: {e}")

else:
    user = st.session_state.user
    st.sidebar.title(f"👋 {user.get('full_name', 'مستخدم النادي')}")
    st.sidebar.info(f"المنصب: {user.get('role', 'Coach')}")

    if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()

    today_str = str(date.today())

    df_players = load_sheet_safely("Players")
    df_attendance = load_sheet_safely("Attendance")
    df_holidays = load_sheet_safely("Global_Holidays")
    df_excuses = load_sheet_safely("Excuses_Log")
    df_audit = load_sheet_safely("Audit_Log")

    # --- 1️⃣ لوحة تحكم المدرب (Coach) ---
    if user.get("role") == "Coach":
        st.header("📋 شاشة المدرب لتسجيل الحضور اليومي")
        st.info(f"📅 تاريخ اليوم التلقائي: {today_str}")

        teams_allowed = [t.strip() for t in str(user.get("assigned_teams", "")).split(",") if t.strip()]

        if not teams_allowed or df_players.empty:
            st.warning("لم يتم ربط أي فرق بحسابك، أو كشف اللاعبين فارغ في الجوجل شيت.")
        else:
            selected_team = st.selectbox("اختر الفريق المراد تسجيل حضوره الآن:", teams_allowed)

            is_holiday = False
            if not df_holidays.empty and "start_date" in df_holidays.columns:
                holiday_match = df_holidays[
                    (today_str >= df_holidays["start_date"].astype(str))
                    & (today_str <= df_holidays["end_date"].astype(str))
                    & ((df_holidays["target_team"] == selected_team) | (df_holidays["target_team"] == "كل الفرق"))
                ]
                if not holiday_match.empty:
                    is_holiday = True
                    st.warning(f"🥳 كابتن، فريق ({selected_team}) لديه إجازة اليوم بمناسبة: {holiday_match.iloc[0]['holiday_name']}. السيستم مغلق للراحة.")

            if not is_holiday:
                players_team = df_players[df_players["team_age"] == selected_team]

                already_submitted = False
                if not df_attendance.empty and not players_team.empty and "player_id" in df_attendance.columns:
                    p_ids = players_team["player_id"].astype(str).tolist()
                    dup_check = df_attendance[
                        (df_attendance["date"] == today_str) & (df_attendance["player_id"].astype(str).isin(p_ids))
                    ]
                    if not dup_check.empty:
                        already_submitted = True

                if already_submitted:
                    st.error("⚠️ تم تسجيل حضور هذا الفريق اليوم بالفعل! لا يمكنك الإدخال مجدداً.")
                elif players_team.empty:
                    st.info("لا يوجد لاعبين مسجلين لهذه المرحلة في الشيت حالياً.")
                else:
                    st.write("علّم على اللاعبين الحاضرين في تمرين اليوم:")
                    attendance_dict = {}

                    for _, p in players_team.iterrows():
                        col_name, col_status = st.columns([3, 1])
                        with col_name:
                            has_excuse = False
                            if not df_excuses.empty and "player_id" in df_excuses.columns:
                                exc_match = df_excuses[
                                    (df_excuses["player_id"].astype(str) == str(p["player_id"]))
                                    & (today_str >= df_excuses["start_date"].astype(str))
                                    & (today_str <= df_excuses["end_date"].astype(str))
                                ]
                                if not exc_match.empty:
                                    has_excuse = True
                                    reason_val = exc_match.iloc[0]["reason"]
                                    doc_val = exc_match.iloc[0]["document_link"]
                                    if pd.notna(doc_val) and str(doc_val).strip() != "":
                                        st.write(f"🔹 {p['player_name']} *(⚠️ إجازة رسمية: {reason_val} - [📄 عرض المستند]({doc_val}) )*")
                                    else:
                                        st.write(f"🔹 {p['player_name']} *(⚠️ إجازة رسمية: {reason_val} )*")
                            if not has_excuse:
                                st.write(f"🔹 {p['player_name']}")
                        with col_status:
                            is_present = st.checkbox("حاضر", key=f"p_{p['player_id']}")
                            attendance_dict[p["player_id"]] = "Present" if is_present else "Absent"

                    if st.button("💾 حفظ وإرسال التقرير للإدارة", type="primary"):
                        now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ok = True
                        for pid, status in attendance_dict.items():
                            row = {
                                "date": today_str,
                                "player_id": pid,
                                "status": status,
                                "excuse_reason": "",
                                "submitted_by": user.get("username", user.get("full_name", "")),
                                "timestamp": now_ts,
                            }
                            if not append_row_to_sheet("Attendance", row):
                                ok = False
                        if ok:
                            st.success("✔️ تم حفظ الكشف وإرساله للسحاب بنجاح!")
                            st.balloons()
                        else:
                            st.warning("⚠️ حصلت مشكلة في حفظ بعض الصفوف، راجع رسائل الخطأ بالأعلى.")

    # --- 2️⃣ لوحة تحكم الإداري (Admin) ---
    elif user.get("role") == "Admin":
        st.header("🛡️ لوحة تحكم ومراقبة الإداريين")
        admin_teams = [t.strip() for t in str(user.get("assigned_teams", "")).split(",") if t.strip()]

        if not admin_teams:
            st.warning("⚠️ لم يتم ربط أي فرق بحسابك الإداري حالياً. يرجى مراجعة رئيس الجهاز.")
        else:
            tab1, tab1_b, tab2, tab3 = st.tabs([
                "📁 تسجيل إجازة لاعب ومستندها",
                "🗓️ تسجيل إجازة فرقة (أسبوعية / جوية)",
                "🔄 مراجعة وتصحيح أخطاء الغياب",
                "📝 إدخال غياب يدوي (بديل للمدرب)",
            ])

            with tab1:
                st.subheader("تسجيل إجازة معتمدة بمستندات (مرضي / سفر / امتحانات)")
                if not df_players.empty:
                    players_allowed = df_players[df_players["team_age"].isin(admin_teams)]
                    if players_allowed.empty:
                        st.info("لا يوجد لاعبين في فرقك المخصصة حالياً.")
                    else:
                        selected_p = st.selectbox(
                            "اختر اللاعب:", players_allowed.to_dict("records"),
                            format_func=lambda x: f"{x['team_age']} - {x['player_name']}",
                        )
                        col_s, col_e = st.columns(2)
                        start_d = col_s.date_input("بداية الإجازة", date.today(), key="adm_s")
                        end_d = col_e.date_input("نهاية الإجازة", date.today(), key="adm_e")
                        exc_reason = st.selectbox("السبب:", ["إصابة", "سفر", "امتحانات"])
                        doc_link = st.text_input("رابط صور المستند أو الشهادة الطبية (من Google Drive):")

                        if st.button("اعتماد إجازة اللاعب ومستندها المرفوع"):
                            row = {
                                "player_id": selected_p["player_id"],
                                "start_date": str(start_d),
                                "end_date": str(end_d),
                                "reason": exc_reason,
                                "document_link": doc_link,
                                "registered_by": user.get("username", user.get("full_name", "")),
                            }
                            if append_row_to_sheet("Excuses_Log", row):
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
                        row = {
                            "holiday_name": h_name,
                            "start_date": str(h_start),
                            "end_date": str(h_end),
                            "target_team": target_team,
                            "registered_by": user.get("username", user.get("full_name", "")),
                        }
                        if append_row_to_sheet("Global_Holidays", row):
                            st.success(f"✔️ تم ربط إجازة ({h_name}) بـ [{target_team}] بنجاح!")
                    else:
                        st.warning("من فضلك اكتب سبب الإجازة أولاً.")

            with tab2:
                st.subheader("تعديل غياب أخطأ فيه مدرب (توثيق الرقابة)")
                t_date = st.date_input("اختر التاريخ", date.today())
                if not df_attendance.empty and "date" in df_attendance.columns and not df_players.empty:
                    df_attendance["player_id_str"] = df_attendance["player_id"].astype(str)
                    df_players["player_id_str"] = df_players["player_id"].astype(str)

                    merged_att = df_attendance.merge(df_players, on="player_id_str", how="inner")
                    filtered_records = merged_att[
                        (merged_att["date"] == str(t_date)) & (merged_att["team_age"].isin(admin_teams))
                    ]

                    if not filtered_records.empty:
                        st.dataframe(filtered_records[["team_age", "player_name", "status", "submitted_by"]], use_container_width=True)
                        to_edit = st.selectbox(
                            "اختر اللاعب للتعديل:", filtered_records.to_dict("records"),
                            format_func=lambda x: f"{x['team_age']} - {x['player_name']} ({x['status']})",
                        )
                        new_st = st.selectbox("الحالة الجديدة المعتمدة:", ["Present", "Absent", "Excused"])
                        if st.button("تحديث وتوثيق الحركة في كشف الرقابة"):
                            ok1 = update_attendance_status(t_date, to_edit["player_id"], new_st)
                            audit_row = {
                                "player_name": to_edit["player_name"],
                                "team_age": to_edit["team_age"],
                                "old_status": to_edit["status"],
                                "new_status": new_st,
                                "modified_by": user.get("username", user.get("full_name", "")),
                                "modification_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            }
                            ok2 = append_row_to_sheet("Audit_Log", audit_row)
                            if ok1 and ok2:
                                st.success("✔️ تم التعديل وتدوينه في سجل الرقابة!")
                    else:
                        st.warning("لا توجد بيانات حضور مسجلة لفرقك المخصصة في هذا التاريخ.")

            with tab3:
                st.subheader("تسجيل غياب وحضور يدوي بديل (نيابة عن المدرب)")
                p_date = st.date_input("تاريخ الحصة التدريبية", date.today(), key="man_p_date")
                sel_team = st.selectbox("اختر الفريق للإدخال البديل:", admin_teams)
                players_team = df_players[df_players["team_age"] == sel_team]

                if not players_team.empty:
                    st.write("حدد اللاعبين الحاضرين بناءً على الكشف الورقي:")
                    for _, p in players_team.iterrows():
                        st.checkbox(p["player_name"], key=f"man_{p['player_id']}")
                    if st.button("حفظ الكشف الإداري البديل"):
                        now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ok = True
                        for _, p in players_team.iterrows():
                            status = "Present" if st.session_state.get(f"man_{p['player_id']}") else "Absent"
                            row = {
                                "date": str(p_date),
                                "player_id": p["player_id"],
                                "status": status,
                                "excuse_reason": "",
                                "submitted_by": f"{user.get('username', '')} (إدخال بديل)",
                                "timestamp": now_ts,
                            }
                            if not append_row_to_sheet("Attendance", row):
                                ok = False
                        if ok:
                            st.success("✔️ تم حفظ الكشف البديل بنجاح في الجوجل شيت!")

    # --- 3️⃣ لوحة التحكم المطلقة (SuperAdmin) ---
    elif user.get("role") == "SuperAdmin":
        st.header("🏆 لوحة التحكم المطلقة لمدير النظام ورئيس الجهاز")

        with st.sidebar.expander("🔧 فحص الاتصال بالجوجل شيت"):
            if st.button("اختبار الاتصال الآن"):
                try:
                    sh = get_spreadsheet()
                    tabs = [ws.title for ws in sh.worksheets()]
                    st.success("✅ الاتصال ناجح!")
                    st.write(tabs)
                except Exception as e:
                    st.error(f"❌ {e}")

        menu = st.sidebar.radio("🗂️ اختر قسم التحكم الإداري الشامل:", [
            "📊 التقارير الختامية ونسب الحضور للموسم",
            "🕵️ سجل الرقابة ومتابعة التعديلات بالثانية",
            "🗓️ إدارة وحذف الإجازات المخطوءة لو فتح السيستم",
            "👥 قراءة حسابات المستخدمين",
            "🏃 قراءة قوائم اللاعبين من السحاب",
        ])

        if menu == "📊 التقارير الختامية ونسب الحضور للموسم":
            st.subheader("إحصائيات ونسب الحضور التراكمية")
            if not df_players.empty:
                teams_list = ["الكل"] + df_players["team_age"].unique().tolist()
                sel_t = st.selectbox("تصفية التقرير حسب الفريق:", teams_list)
                if not df_attendance.empty:
                    st.dataframe(df_attendance, use_container_width=True)
                    st.download_button(
                        "📥 تحميل التقرير الشامل كملف CSV للمكتب الفني",
                        df_attendance.to_csv(index=False).encode("utf-8-sig"),
                        "Full_Club_Report.csv", "text/csv", use_container_width=True,
                    )
                else:
                    st.info("لا توجد حركات حضور مسجلة في شيت Attendance حتى الآن.")
            else:
                st.info("كشف اللاعبين فارغ في الجوجل شيت حالياً.")

        elif menu == "🕵️ سجل الرقابة ومتابعة التعديلات بالثانية":
            st.subheader("🕵️ شاشة مراقبة حركات الإداريين والتعديلات الفورية")
            if not df_audit.empty:
                st.dataframe(df_audit, use_container_width=True)
            else:
                st.info("لم يقم أي إداري بتعديل أي غياب حتى الآن.")

        elif menu == "🗓️ إدارة وحذف الإجازات المخطوءة لو فتح السيستم":
            st.subheader("🗓️ لوحة التحكم وإلغاء إجازات الفرق الخاطئة")
            if not df_holidays.empty:
                st.dataframe(df_holidays, use_container_width=True)
                if st.button("🗑️ تصفير ومسح كل الإجازات المسجلة الآن"):
                    if clear_sheet_data("Global_Holidays"):
                        st.success("تم مسح السجلات وإتاحة النظام للفرق فوراً!")
                        st.rerun()
            else:
                st.info("لا توجد إجازات مسجلة حالياً.")

        elif menu == "👥 قراءة حسابات المستخدمين":
            st.subheader("👥 الحسابات الحالية للمدربين والإداريين:")
            df_users_sa = load_sheet_safely("Users")
            if not df_users_sa.empty:
                st.dataframe(df_users_sa, use_container_width=True)
                st.caption("💡 لتغيير كلمة مرور أو إضافة مدرب، عدّل صفحة Users في الشيت مباشرة.")
            else:
                st.dataframe(df_users_init, use_container_width=True)

        elif menu == "🏃 قراءة قوائم اللاعبين من السحاب":
            st.subheader("🏃 قائمة اللاعبين المسجلين بالنظام حالياً:")
            if not df_players.empty:
                st.dataframe(df_players, use_container_width=True)
            else:
                st.info("جدول اللاعبين فارغ في الجوجل شيت حالياً؛ يرجى ملئه لتظهر الأسماء.")
