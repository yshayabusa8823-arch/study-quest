import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(
    page_title="Study Quest",
    page_icon="icon.png",
    layout="centered"
)

SHEET_NAME = "StudyQuestDB"
JST = ZoneInfo("Asia/Tokyo")

if "notice_message" not in st.session_state:
    st.session_state.notice_message = None

if "notice_type" not in st.session_state:
    st.session_state.notice_type = "success"


@st.cache_resource
def connect_sheets():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scope
    )

    client = gspread.authorize(creds)
    spreadsheet = client.open(SHEET_NAME)

    return {
        "logs": spreadsheet.worksheet("logs"),
        "users": spreadsheet.worksheet("users"),
        "subjects": spreadsheet.worksheet("subjects"),
        "active_sessions": spreadsheet.worksheet("active_sessions"),
    }


sheets = connect_sheets()
logs_sheet = sheets["logs"]
users_sheet = sheets["users"]
subjects_sheet = sheets["subjects"]
sessions_sheet = sheets["active_sessions"]


def load_sheet(sheet, columns):
    records = sheet.get_all_records()

    if not records:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(records)

    for col in columns:
        if col not in df.columns:
            df[col] = ""

    return df[columns]


def load_logs():
    df = load_sheet(
        logs_sheet,
        ["user_id", "date", "subject", "hours", "focus", "memo"]
    )

    if not df.empty:
        df["hours"] = pd.to_numeric(df["hours"], errors="coerce").fillna(0)
        df["focus"] = pd.to_numeric(df["focus"], errors="coerce").fillna(0)

    return df


def load_users():
    df = load_sheet(
        users_sheet,
        ["user_id", "name", "weekly_goal"]
    )

    if not df.empty:
        df["weekly_goal"] = pd.to_numeric(
            df["weekly_goal"],
            errors="coerce"
        ).fillna(25)

    return df


def load_subjects():
    return load_sheet(
        subjects_sheet,
        ["user_id", "subject"]
    )


def load_sessions():
    return load_sheet(
        sessions_sheet,
        ["user_id", "subject", "start_time", "focus", "memo"]
    )


def append_log(user_id, log_date, subject, hours, focus, memo):
    logs_sheet.append_row([
        user_id,
        str(log_date),
        subject,
        float(hours),
        int(focus),
        memo
    ])


def append_subject(user_id, subject):
    subjects_sheet.append_row([user_id, subject])


def start_session(user_id, subject, focus, memo):
    sessions_sheet.append_row([
        user_id,
        subject,
        datetime.now(JST).isoformat(timespec="seconds"),
        int(focus),
        memo
    ])


def delete_session_by_sheet_row(sheet_row):
    sessions_sheet.delete_rows(sheet_row)


def delete_log_by_sheet_row(sheet_row):
    logs_sheet.delete_rows(sheet_row)


def upsert_user(user_id, name, weekly_goal):
    users = load_users()
    target_row = None

    for i, row in users.iterrows():
        if row["user_id"] == user_id:
            target_row = i + 2
            break

    if target_row:
        users_sheet.update(
            f"A{target_row}:C{target_row}",
            [[user_id, name, float(weekly_goal)]]
        )
    else:
        users_sheet.append_row([
            user_id,
            name,
            float(weekly_goal)
        ])


def get_week_range(today):
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end


def calc_streak(user_logs):
    if user_logs.empty:
        return 0

    dates = sorted(
        pd.to_datetime(user_logs["date"]).dt.date.unique(),
        reverse=True
    )

    today_jst = datetime.now(JST).date()

    if today_jst not in dates:
        today_jst = today_jst - timedelta(days=1)

    streak = 0
    current = today_jst

    while current in dates:
        streak += 1
        current -= timedelta(days=1)

    return streak


def calc_level(total_hours):
    level = int(total_hours // 10) + 1
    next_level_total = level * 10
    current_level_total = (level - 1) * 10
    progress_in_level = total_hours - current_level_total
    required_for_level = next_level_total - current_level_total

    return level, progress_in_level, required_for_level, next_level_total


def badge(icon, title, earned, note):
    return {
        "icon": icon,
        "title": title,
        "earned": earned,
        "note": note
    }


def get_badge_status(total_hours, streak, weekly_total, weekly_goal, user_logs):
    all_badges = []

    hour_badges = [
        (1, "🌱", "はじめの一歩"),
        (5, "🐣", "助走開始"),
        (10, "📚", "10時間突破"),
        (25, "🥉", "25時間突破"),
        (50, "🏆", "50時間突破"),
        (75, "🥈", "75時間突破"),
        (100, "👑", "100時間突破"),
        (150, "💪", "努力家"),
        (200, "🔥", "継続の達人"),
        (300, "💎", "300時間突破"),
        (500, "🚀", "500時間突破"),
        (1000, "🌌", "1000時間の境地"),
    ]

    for target, icon, title in hour_badges:
        earned = total_hours >= target
        remain = max(target - total_hours, 0)
        note = "獲得済み" if earned else f"あと {remain:.1f}h"
        all_badges.append(badge(icon, title, earned, note))

    streak_badges = [
        (2, "🧩", "2日連続"),
        (3, "🔥", "継続の火"),
        (7, "🗓️", "一週間継続"),
        (14, "⚔️", "二週間継続"),
        (30, "🏯", "習慣化成功"),
        (50, "🦁", "継続王"),
        (100, "👑", "継続皇帝"),
    ]

    for target, icon, title in streak_badges:
        earned = streak >= target
        remain = max(target - streak, 0)
        note = "獲得済み" if earned else f"あと {remain}日"
        all_badges.append(badge(icon, title, earned, note))

    weekly_badges = [
        (1.0, "🎯", "週間目標達成"),
        (1.2, "🚴", "目標超え"),
        (1.5, "🦅", "大幅達成"),
    ]

    for rate, icon, title in weekly_badges:
        target = weekly_goal * rate
        earned = weekly_total >= target
        remain = max(target - weekly_total, 0)
        note = "獲得済み" if earned else f"あと {remain:.1f}h"
        all_badges.append(badge(icon, title, earned, note))

    if user_logs.empty:
        log_count = 0
        max_focus = 0
        high_focus_count = 0
        max_hours = 0
        subject_totals = pd.Series(dtype=float)
    else:
        log_count = len(user_logs)
        max_focus = user_logs["focus"].max()
        high_focus_count = len(user_logs[user_logs["focus"] >= 90])
        max_hours = user_logs["hours"].max()
        subject_totals = user_logs.groupby("subject")["hours"].sum()

    count_badges = [
        (3, "✍️", "記録初心者"),
        (10, "📘", "記録習慣"),
        (30, "📒", "ログ職人"),
        (50, "🗂️", "記録マスター"),
        (100, "🧾", "記録の鬼"),
    ]

    for target, icon, title in count_badges:
        earned = log_count >= target
        remain = max(target - log_count, 0)
        note = "獲得済み" if earned else f"あと {remain}回"
        all_badges.append(badge(icon, title, earned, note))

    focus_badges = [
        (max_focus >= 90, "⚡", "集中マスター", "集中度90以上"),
        (max_focus >= 100, "🧠", "完全集中", "集中度100"),
        (high_focus_count >= 5, "🔮", "集中の再現性", f"あと {max(5 - high_focus_count, 0)}回"),
        (high_focus_count >= 10, "🧘", "集中の達人", f"あと {max(10 - high_focus_count, 0)}回"),
    ]

    for earned, icon, title, locked_note in focus_badges:
        note = "獲得済み" if earned else locked_note
        all_badges.append(badge(icon, title, earned, note))

    long_badges = [
        (3, "⏳", "3時間クエスト"),
        (5, "🗻", "5時間クエスト"),
        (8, "🐉", "限界突破"),
    ]

    for target, icon, title in long_badges:
        earned = max_hours >= target
        remain = max(target - max_hours, 0)
        note = "獲得済み" if earned else f"1回であと {remain:.1f}h"
        all_badges.append(badge(icon, title, earned, note))

    for subject, hours in subject_totals.items():
        subject_badges = [
            (10, "📖", f"{subject} 10時間"),
            (30, "🎓", f"{subject} 30時間"),
            (50, "🏅", f"{subject} 50時間"),
            (100, "👑", f"{subject} マスター"),
        ]

        for target, icon, title in subject_badges:
            earned = hours >= target
            remain = max(target - hours, 0)
            note = "獲得済み" if earned else f"あと {remain:.1f}h"
            all_badges.append(badge(icon, title, earned, note))

    earned_badges = [b for b in all_badges if b["earned"]]
    locked_badges = [b for b in all_badges if not b["earned"]]

    return earned_badges, locked_badges


st.markdown("""
<style>
.block-container {
    padding-top: 1rem;
    padding-left: 1rem;
    padding-right: 1rem;
    max-width: 760px;
}
.hero {
    background: linear-gradient(135deg, #111827, #4f46e5, #ec4899);
    padding: 26px;
    border-radius: 30px;
    color: white;
    margin-bottom: 20px;
    box-shadow: 0 18px 40px rgba(79,70,229,0.25);
}
.hero h1 {
    font-size: 42px;
    line-height: 1.05;
    margin-bottom: 14px;
}
.hero h3 {
    font-size: 24px;
    line-height: 1.3;
}
.mission-card {
    background: linear-gradient(135deg, #fff7ed, #ffedd5);
    padding: 20px;
    border-radius: 24px;
    border: 1px solid #fed7aa;
    margin-bottom: 18px;
    font-size: 18px;
}
.stat-card, .quest-card {
    background: white;
    padding: 18px;
    border-radius: 24px;
    box-shadow: 0 10px 28px rgba(15,23,42,0.08);
    border: 1px solid #eef2f7;
    margin-bottom: 12px;
}
.stat-label {
    color: #64748b;
    font-size: 14px;
    margin-bottom: 6px;
}
.stat-number {
    color: #111827;
    font-size: 32px;
    font-weight: 900;
}
.badge-pill {
    display: inline-block;
    background: #f1f5f9;
    padding: 10px 14px;
    border-radius: 999px;
    margin: 5px 4px;
    font-weight: 700;
    font-size: 14px;
}
.locked-badge-pill {
    display: inline-block;
    background: #f8fafc;
    color: #94a3b8;
    border: 1px dashed #cbd5e1;
    padding: 10px 14px;
    border-radius: 999px;
    margin: 5px 4px;
    font-weight: 700;
    font-size: 14px;
    opacity: 0.58;
}
.locked-note {
    font-size: 11px;
    font-weight: 600;
    margin-left: 4px;
}
.section-title {
    font-size: 28px;
    font-weight: 900;
    margin-top: 24px;
    margin-bottom: 12px;
}
</style>
""", unsafe_allow_html=True)


users = load_users()
logs = load_logs()
subjects_df = load_subjects()
sessions_df = load_sessions()

default_users = {
    "syun": {"name": "しゅん", "weekly_goal": 25.0},
    "shiori": {"name": "しおり", "weekly_goal": 35.0},
}

default_subjects_map = {
    "syun": ["線形代数", "統計", "微分積分", "法律", "その他"],
    "shiori": [
        "民法",
        "憲法",
        "刑法",
        "民事訴訟法",
        "刑事訴訟法",
        "商法",
        "知的財産法",
        "その他"
    ],
}


st.sidebar.title("⚙️ 設定")

if st.sidebar.button("🔄 更新"):
    st.rerun()

user_options = ["syun", "shiori"]

query_user = st.query_params.get("user", "syun")

if query_user not in user_options:
    query_user = "syun"

default_index = user_options.index(query_user)

user_id = st.sidebar.selectbox(
    "ユーザーを選択",
    user_options,
    index=default_index
)

st.query_params["user"] = user_id

user_data = users[users["user_id"] == user_id]

if user_data.empty:
    name = default_users[user_id]["name"]
    weekly_goal = default_users[user_id]["weekly_goal"]
else:
    name = user_data.iloc[0]["name"]
    weekly_goal = float(user_data.iloc[0]["weekly_goal"])

st.sidebar.divider()
st.sidebar.subheader("プロフィール編集")

edit_name = st.sidebar.text_input("表示名", value=name)

edit_weekly_goal = st.sidebar.number_input(
    "1週間の目標勉強時間",
    min_value=1.0,
    value=float(weekly_goal),
    step=0.5
)

if st.sidebar.button("プロフィールを保存"):
    upsert_user(user_id, edit_name, edit_weekly_goal)
    st.session_state.notice_message = "プロフィールを保存しました"
    st.session_state.notice_type = "success"
    st.rerun()


default_subjects = default_subjects_map[user_id]

added_subjects = subjects_df[
    subjects_df["user_id"] == user_id
]["subject"].dropna().astype(str).tolist()

user_subjects = []

for subject in default_subjects + added_subjects:
    subject = subject.strip()
    if subject and subject not in user_subjects:
        user_subjects.append(subject)

st.sidebar.divider()
st.sidebar.subheader("科目追加")

new_subject_sidebar = st.sidebar.text_input("追加したい科目")

if st.sidebar.button("科目を追加"):
    if new_subject_sidebar.strip():
        subject_name = new_subject_sidebar.strip()

        if subject_name in user_subjects:
            st.sidebar.warning("その科目は既にあります")
        else:
            append_subject(user_id, subject_name)
            st.session_state.notice_message = "科目を追加しました"
            st.session_state.notice_type = "success"
            st.rerun()
    else:
        st.sidebar.warning("科目名を入力してください")


today = datetime.now(JST).date()
week_start, week_end = get_week_range(today)

user_logs = logs[logs["user_id"] == user_id].copy()

if not user_logs.empty:
    user_logs["date_dt"] = pd.to_datetime(user_logs["date"]).dt.date
    week_logs = user_logs[
        (user_logs["date_dt"] >= week_start) &
        (user_logs["date_dt"] <= week_end)
    ]
else:
    week_logs = pd.DataFrame()

weekly_total = week_logs["hours"].sum() if not week_logs.empty else 0
total_hours = user_logs["hours"].sum() if not user_logs.empty else 0
remaining = max(edit_weekly_goal - weekly_total, 0)
achievement = min((weekly_total / edit_weekly_goal) * 100, 100)

streak = calc_streak(user_logs)

level, progress_in_level, required_for_level, next_level_total = calc_level(total_hours)
level_progress = progress_in_level / required_for_level
remaining_for_level = next_level_total - total_hours

earned_badges, locked_badges = get_badge_status(
    total_hours,
    streak,
    weekly_total,
    edit_weekly_goal,
    user_logs
)

if remaining == 0:
    mission_text = "🎉 今週の目標達成！今日は復習か軽めの積み上げでOK。"
elif streak == 0:
    mission_text = "🔥 まずは30分だけ記録しよう。ゼロにしないのが勝ち。"
elif achievement >= 70:
    mission_text = "⚔️ あと少し。今日は1時間だけでも積めばかなり強い。"
else:
    mission_text = f"📚 今週の残りは {remaining:.1f}h。今日は1.0hを目標にしよう。"


st.markdown(f"""
<div class="hero">
    <h1>🧭 Study<br>Quest</h1>
    <h3>{edit_name} の学習ダッシュボード</h3>
    <p>今日の積み上げが、未来の自分を作る。</p>
</div>
""", unsafe_allow_html=True)

if st.session_state.notice_message:
    if "レベルアップ" in st.session_state.notice_message:
        st.balloons()

    if st.session_state.notice_type == "success":
        st.success(st.session_state.notice_message)
    elif st.session_state.notice_type == "warning":
        st.warning(st.session_state.notice_message)
    else:
        st.info(st.session_state.notice_message)

    st.session_state.notice_message = None

st.markdown(f"""
<div class="mission-card">
    <b>今日のミッション</b><br>
    {mission_text}
</div>
""", unsafe_allow_html=True)


col1, col2 = st.columns(2)

with col1:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-label">今週</div>
        <div class="stat-number">{weekly_total:.1f}h</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-label">残り</div>
        <div class="stat-number">{remaining:.1f}h</div>
    </div>
    """, unsafe_allow_html=True)

col3, col4 = st.columns(2)

with col3:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-label">連続</div>
        <div class="stat-number">{streak}日</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-label">レベル</div>
        <div class="stat-number">Lv.{level}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown(f"""
<div class="stat-card">
    <div class="stat-label">総勉強時間</div>
    <div class="stat-number">{total_hours:.1f}h</div>
</div>
""", unsafe_allow_html=True)


st.markdown('<div class="section-title">進捗</div>', unsafe_allow_html=True)

st.write("今週の達成率")
st.progress(achievement / 100)
st.write(f"{achievement:.1f}% 達成")

st.write("レベル進捗")
st.progress(level_progress)
st.write(f"あと {remaining_for_level:.1f} 時間で Lv.{level + 1}")


st.markdown('<div class="section-title">獲得バッジ</div>', unsafe_allow_html=True)

if earned_badges:
    badge_html = ""
    for b in earned_badges:
        badge_html += f'<span class="badge-pill">{b["icon"]} {b["title"]}</span>'

    st.markdown(badge_html, unsafe_allow_html=True)
else:
    st.write("まだバッジはありません。まずは1時間勉強してみよう。")


st.markdown('<div class="section-title">未獲得バッジ</div>', unsafe_allow_html=True)

if locked_badges:
    locked_html = ""
    for b in locked_badges:
        locked_html += (
            f'<span class="locked-badge-pill">'
            f'🔒 {b["icon"]} {b["title"]}'
            f'<span class="locked-note">({b["note"]})</span>'
            f'</span>'
        )

    st.markdown(locked_html, unsafe_allow_html=True)
else:
    st.success("全バッジ獲得済み！すごすぎる。")


st.markdown('<div class="section-title">タイマー学習</div>', unsafe_allow_html=True)

active_user_sessions = sessions_df[sessions_df["user_id"] == user_id].copy()

if active_user_sessions.empty:
    with st.form("timer_start_form"):
        timer_subject = st.selectbox(
            "タイマー科目",
            user_subjects,
            key="timer_subject"
        )

        timer_focus = st.slider(
            "予定集中度",
            min_value=0,
            max_value=100,
            value=70,
            key="timer_focus"
        )

        timer_memo = st.text_area(
            "タイマーメモ",
            placeholder="例：民法の復習を開始",
            key="timer_memo"
        )

        start_submitted = st.form_submit_button("▶️ 勉強開始")

        if start_submitted:
            start_session(user_id, timer_subject, timer_focus, timer_memo)
            st.session_state.notice_message = "タイマーを開始しました"
            st.session_state.notice_type = "success"
            st.rerun()

else:
    session_row = active_user_sessions.iloc[0]
    session_index = active_user_sessions.index[0]
    sheet_row = session_index + 2

    start_time = datetime.fromisoformat(str(session_row["start_time"]))

    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=JST)

    elapsed = datetime.now(JST) - start_time
    elapsed_minutes = int(elapsed.total_seconds() // 60)
    elapsed_hours = round(elapsed.total_seconds() / 3600, 2)

    st.info(
        f"⏱️ 勉強中：{session_row['subject']} / "
        f"開始 {start_time.strftime('%H:%M')} / "
        f"経過 約{elapsed_minutes}分"
    )

    col_end, col_cancel = st.columns(2)

    with col_end:
        if st.button("⏹️ 終了して記録"):
            if elapsed_hours <= 0:
                st.warning("記録できる時間が短すぎます")
            else:
                old_level, _, _, _ = calc_level(total_hours)

                append_log(
                    user_id,
                    datetime.now(JST).date(),
                    session_row["subject"],
                    elapsed_hours,
                    int(session_row["focus"]),
                    session_row["memo"]
                )

                delete_session_by_sheet_row(sheet_row)

                new_level, _, _, _ = calc_level(total_hours + elapsed_hours)

                if new_level > old_level:
                    st.session_state.notice_message = f"🎉 レベルアップ！ Lv.{new_level} になりました！"
                else:
                    st.session_state.notice_message = f"{elapsed_hours:.2f}時間を記録しました"

                st.session_state.notice_type = "success"
                st.rerun()

    with col_cancel:
        if st.button("🗑️ タイマーを取り消す"):
            delete_session_by_sheet_row(sheet_row)
            st.session_state.notice_message = "タイマーを取り消しました"
            st.session_state.notice_type = "success"
            st.rerun()


st.markdown('<div class="section-title">手動で記録</div>', unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="quest-card">', unsafe_allow_html=True)

    with st.form("study_form"):
        subject = st.selectbox("科目", user_subjects)

        hours = st.number_input(
            "勉強時間",
            min_value=0.0,
            value=1.0,
            step=0.5
        )

        focus = st.slider(
            "集中度",
            min_value=0,
            max_value=100,
            value=70
        )

        memo = st.text_area(
            "メモ",
            placeholder="例：統計の仮説検定を復習した"
        )

        submitted = st.form_submit_button("記録する")

        if submitted:
            old_level, _, _, _ = calc_level(total_hours)

            append_log(
                user_id,
                today,
                subject,
                hours,
                focus,
                memo
            )

            new_level, _, _, _ = calc_level(total_hours + hours)

            if new_level > old_level:
                st.session_state.notice_message = f"🎉 レベルアップ！ Lv.{new_level} になりました！"
            else:
                st.session_state.notice_message = "記録しました！"

            st.session_state.notice_type = "success"
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


st.markdown('<div class="section-title">今週の記録</div>', unsafe_allow_html=True)

if week_logs.empty:
    st.write("今週の記録はまだありません。")
else:
    display_logs = week_logs[
        ["date", "subject", "hours", "focus", "memo"]
    ].copy()

    display_logs = display_logs.sort_values("date", ascending=False)

    st.dataframe(display_logs, use_container_width=True)

    st.markdown('<div class="section-title">科目別勉強時間</div>', unsafe_allow_html=True)

    subject_summary = week_logs.groupby("subject")["hours"].sum().reset_index()

    st.bar_chart(
        subject_summary,
        x="subject",
        y="hours"
    )

    st.markdown('<div class="section-title">記録を削除</div>', unsafe_allow_html=True)

    user_week_logs = logs[logs["user_id"] == user_id].copy()

    user_week_logs["date_dt"] = pd.to_datetime(
        user_week_logs["date"]
    ).dt.date

    user_week_logs = user_week_logs[
        (user_week_logs["date_dt"] >= week_start) &
        (user_week_logs["date_dt"] <= week_end)
    ]

    delete_options = []

    for idx, row in user_week_logs.iterrows():
        sheet_row = idx + 2
        label = (
            f"{row['date']} | "
            f"{row['subject']} | "
            f"{row['hours']}h | "
            f"集中{row['focus']}%"
        )

        delete_options.append((sheet_row, label))

    if delete_options:
        selected_delete = st.selectbox(
            "削除する記録を選択",
            delete_options,
            format_func=lambda x: x[1]
        )

        if st.button("この記録を削除"):
            delete_log_by_sheet_row(selected_delete[0])
            st.session_state.notice_message = "記録を削除しました"
            st.session_state.notice_type = "success"
            st.rerun()
