import streamlit as st
import pandas as pd
from datetime import date, timedelta
from pathlib import Path

st.set_page_config(
    page_title="Study Quest",
    page_icon="icon.png",
    layout="centered"
)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

LOG_FILE = DATA_DIR / "study_logs.csv"
USER_FILE = DATA_DIR / "users.csv"
SUBJECT_FILE = DATA_DIR / "subjects.csv"


def load_csv(path, columns):
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame(columns=columns)


def save_csv(df, path):
    df.to_csv(path, index=False)


def load_logs():
    return load_csv(LOG_FILE, ["user_id", "date", "subject", "hours", "focus", "memo"])


def load_users():
    return load_csv(USER_FILE, ["user_id", "name", "weekly_goal"])


def load_subjects():
    return load_csv(SUBJECT_FILE, ["user_id", "subject"])


def get_week_range(today):
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end


def calc_streak(user_logs):
    if user_logs.empty:
        return 0

    dates = sorted(pd.to_datetime(user_logs["date"]).dt.date.unique(), reverse=True)
    current = date.today()
    streak = 0

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


def get_badges(total_hours, streak, weekly_total, weekly_goal, user_logs):
    badges = []

    hour_badges = [
        (1, "🌱", "はじめの一歩", "最初の1時間を達成"),
        (5, "🐣", "助走開始", "総勉強時間5時間達成"),
        (10, "📚", "10時間突破", "総勉強時間10時間達成"),
        (25, "🥉", "25時間突破", "総勉強時間25時間達成"),
        (50, "🏆", "50時間突破", "総勉強時間50時間達成"),
        (75, "🥈", "75時間突破", "総勉強時間75時間達成"),
        (100, "👑", "100時間突破", "総勉強時間100時間達成"),
        (150, "💪", "努力家", "総勉強時間150時間達成"),
        (200, "🔥", "継続の達人", "総勉強時間200時間達成"),
        (300, "💎", "300時間突破", "総勉強時間300時間達成"),
        (500, "🚀", "500時間突破", "総勉強時間500時間達成"),
        (1000, "🌌", "1000時間の境地", "総勉強時間1000時間達成"),
    ]

    for target, icon, title, desc in hour_badges:
        if total_hours >= target:
            badges.append((icon, title, desc))

    streak_badges = [
        (2, "🧩", "2日連続", "2日連続で勉強"),
        (3, "🔥", "継続の火", "3日連続で勉強"),
        (7, "🗓️", "一週間継続", "7日連続で勉強"),
        (14, "⚔️", "二週間継続", "14日連続で勉強"),
        (30, "🏯", "習慣化成功", "30日連続で勉強"),
        (50, "🦁", "継続王", "50日連続で勉強"),
        (100, "👑", "継続皇帝", "100日連続で勉強"),
    ]

    for target, icon, title, desc in streak_badges:
        if streak >= target:
            badges.append((icon, title, desc))

    if weekly_total >= weekly_goal:
        badges.append(("🎯", "週間目標達成", "今週の目標時間を達成"))

    if weekly_total >= weekly_goal * 1.2:
        badges.append(("🚴", "目標超え", "週間目標の120%を達成"))

    if weekly_total >= weekly_goal * 1.5:
        badges.append(("🦅", "大幅達成", "週間目標の150%を達成"))

    if not user_logs.empty:
        log_count = len(user_logs)

        count_badges = [
            (3, "✍️", "記録初心者", "勉強記録3回達成"),
            (10, "📘", "記録習慣", "勉強記録10回達成"),
            (30, "📒", "ログ職人", "勉強記録30回達成"),
            (50, "🗂️", "記録マスター", "勉強記録50回達成"),
            (100, "🧾", "記録の鬼", "勉強記録100回達成"),
        ]

        for target, icon, title, desc in count_badges:
            if log_count >= target:
                badges.append((icon, title, desc))

        if user_logs["focus"].max() >= 90:
            badges.append(("⚡", "集中マスター", "集中度90以上を記録"))

        if user_logs["focus"].max() >= 100:
            badges.append(("🧠", "完全集中", "集中度100を記録"))

        high_focus_count = len(user_logs[user_logs["focus"] >= 90])

        if high_focus_count >= 5:
            badges.append(("🔮", "集中の再現性", "集中度90以上を5回記録"))

        if high_focus_count >= 10:
            badges.append(("🧘", "集中の達人", "集中度90以上を10回記録"))

        if user_logs["hours"].max() >= 3:
            badges.append(("⏳", "3時間クエスト", "1回で3時間以上勉強"))

        if user_logs["hours"].max() >= 5:
            badges.append(("🗻", "5時間クエスト", "1回で5時間以上勉強"))

        if user_logs["hours"].max() >= 8:
            badges.append(("🐉", "限界突破", "1回で8時間以上勉強"))

        subject_totals = user_logs.groupby("subject")["hours"].sum()

        for subject, hours in subject_totals.items():
            if hours >= 10:
                badges.append(("📖", f"{subject} 10時間", f"{subject}を10時間勉強"))
            if hours >= 30:
                badges.append(("🎓", f"{subject} 30時間", f"{subject}を30時間勉強"))
            if hours >= 50:
                badges.append(("🏅", f"{subject} 50時間", f"{subject}を50時間勉強"))
            if hours >= 100:
                badges.append(("👑", f"{subject} マスター", f"{subject}を100時間勉強"))

    return badges


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
.stat-card {
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
.quest-card {
    background: white;
    padding: 20px;
    border-radius: 26px;
    box-shadow: 0 12px 32px rgba(15,23,42,0.10);
    border: 1px solid #e5e7eb;
    margin-bottom: 18px;
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

default_users = {
    "syun": {"name": "しゅん", "weekly_goal": 25.0},
    "shiori": {"name": "しおり", "weekly_goal": 35.0},
}

default_subjects_map = {
    "syun": ["線形代数", "統計", "微分積分", "法律", "その他"],
    "shiori": ["民法", "憲法", "刑法", "民事訴訟法", "刑事訴訟法", "商法", "知的財産法", "その他"],
}


st.sidebar.title("⚙️ 設定")

user_id = st.sidebar.selectbox("ユーザーを選択", ["syun", "shiori"])

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
    users = users[users["user_id"] != user_id]
    new_user = pd.DataFrame([{
        "user_id": user_id,
        "name": edit_name,
        "weekly_goal": edit_weekly_goal
    }])
    users = pd.concat([users, new_user], ignore_index=True)
    save_csv(users, USER_FILE)
    st.sidebar.success("保存しました")
    st.rerun()


user_subjects = subjects_df[
    subjects_df["user_id"] == user_id
]["subject"].tolist()

if not user_subjects:
    user_subjects = default_subjects_map[user_id]

st.sidebar.divider()
st.sidebar.subheader("科目追加")

new_subject_sidebar = st.sidebar.text_input("追加したい科目")

if st.sidebar.button("科目を追加"):
    if new_subject_sidebar.strip():
        subject_name = new_subject_sidebar.strip()

        if subject_name in user_subjects:
            st.sidebar.warning("その科目は既にあります")
        else:
            new_row = pd.DataFrame([{
                "user_id": user_id,
                "subject": subject_name
            }])
            subjects_df = pd.concat([subjects_df, new_row], ignore_index=True)
            save_csv(subjects_df, SUBJECT_FILE)
            st.sidebar.success("科目を追加しました")
            st.rerun()
    else:
        st.sidebar.warning("科目名を入力してください")


today = date.today()
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

badges = get_badges(total_hours, streak, weekly_total, edit_weekly_goal, user_logs)


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

if badges:
    badge_html = ""
    for icon, title, desc in badges:
        badge_html += f'<span class="badge-pill">{icon} {title}</span>'
    st.markdown(badge_html, unsafe_allow_html=True)
else:
    st.write("まだバッジはありません。まずは1時間勉強してみよう。")


st.markdown('<div class="section-title">今日のクエスト</div>', unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="quest-card">', unsafe_allow_html=True)

    with st.form("study_form"):
        subject = st.selectbox("科目", user_subjects)

        hours = st.number_input("勉強時間", min_value=0.0, value=1.0, step=0.5)
        focus = st.slider("集中度", min_value=0, max_value=100, value=70)
        memo = st.text_area("メモ", placeholder="例：統計の仮説検定を復習した")

        submitted = st.form_submit_button("記録する")

        if submitted:
            old_level, _, _, _ = calc_level(total_hours)

            new_log = pd.DataFrame([{
                "user_id": user_id,
                "date": str(today),
                "subject": subject,
                "hours": hours,
                "focus": focus,
                "memo": memo
            }])

            logs = pd.concat([logs, new_log], ignore_index=True)
            save_csv(logs, LOG_FILE)

            new_level, _, _, _ = calc_level(total_hours + hours)

            if new_level > old_level:
                st.balloons()
                st.success(f"🎉 レベルアップ！ Lv.{new_level} になりました！")
            else:
                st.success("記録しました！ページを再読み込みすると反映されます。")

    st.markdown('</div>', unsafe_allow_html=True)


st.markdown('<div class="section-title">今週の記録</div>', unsafe_allow_html=True)

if week_logs.empty:
    st.write("今週の記録はまだありません。")
else:
    display_logs = week_logs[
        ["date", "subject", "hours", "focus", "memo"]
    ].sort_values("date", ascending=False)

    st.dataframe(display_logs, use_container_width=True)

    st.markdown('<div class="section-title">科目別勉強時間</div>', unsafe_allow_html=True)

    subject_summary = week_logs.groupby("subject")["hours"].sum().reset_index()
    st.bar_chart(subject_summary, x="subject", y="hours")

    st.markdown('<div class="section-title">記録を削除</div>', unsafe_allow_html=True)

    delete_options = []

    for idx, row in display_logs.iterrows():
        label = f"{row['date']} | {row['subject']} | {row['hours']}h | 集中{row['focus']}%"
        delete_options.append((idx, label))

    if delete_options:
        selected_delete = st.selectbox(
            "削除する記録を選択",
            delete_options,
            format_func=lambda x: x[1]
        )

        if st.button("この記録を削除"):
            delete_idx = selected_delete[0]
            logs = logs.drop(delete_idx)
            save_csv(logs, LOG_FILE)
            st.success("記録を削除しました")
            st.rerun()
