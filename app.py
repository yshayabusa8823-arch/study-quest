import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, timedelta

st.set_page_config(
    page_title="Study Quest",
    page_icon="icon.png",
    layout="centered"
)

SHEET_NAME = "StudyQuestDB"

# =====================
# Google Sheets 接続
# =====================

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
    }


sheets = connect_sheets()
logs_sheet = sheets["logs"]
users_sheet = sheets["users"]
subjects_sheet = sheets["subjects"]


# =====================
# Sheets 読み書き
# =====================

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
        users_sheet.append_row([user_id, name, float(weekly_goal)])


def delete_log_by_sheet_row(sheet_row):
    logs_sheet.delete_rows(sheet_row)


# =====================
# 計算
# =====================

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


# =====================
# バッジ図鑑
# =====================

def get_badge_catalog(user_logs):
    badges = []

    hour_badges = [
        (1, "🌱", "はじめの一歩", "累計1時間勉強する"),
        (3, "🧃", "軽く始動", "累計3時間勉強する"),
        (5, "🐣", "助走開始", "累計5時間勉強する"),
        (10, "📚", "10時間突破", "累計10時間勉強する"),
        (20, "🧱", "土台づくり", "累計20時間勉強する"),
        (25, "🥉", "25時間突破", "累計25時間勉強する"),
        (50, "🏆", "50時間突破", "累計50時間勉強する"),
        (75, "🥈", "75時間突破", "累計75時間勉強する"),
        (100, "👑", "100時間突破", "累計100時間勉強する"),
        (150, "💪", "努力家", "累計150時間勉強する"),
        (200, "🔥", "継続の達人", "累計200時間勉強する"),
        (300, "💎", "300時間突破", "累計300時間勉強する"),
        (500, "🚀", "500時間突破", "累計500時間勉強する"),
        (1000, "🌌", "1000時間の境地", "累計1000時間勉強する"),
    ]

    for target, icon, title, desc in hour_badges:
        badges.append({
            "type": "累計時間",
            "icon": icon,
            "title": title,
            "desc": desc,
            "condition": "total_hours",
            "target": target
        })

    streak_badges = [
        (2, "🧩", "2日連続", "2日連続で記録する"),
        (3, "🔥", "継続の火", "3日連続で記録する"),
        (5, "🌿", "習慣の芽", "5日連続で記録する"),
        (7, "🗓️", "一週間継続", "7日連続で記録する"),
        (14, "⚔️", "二週間継続", "14日連続で記録する"),
        (30, "🏯", "習慣化成功", "30日連続で記録する"),
        (50, "🦁", "継続王", "50日連続で記録する"),
        (100, "👑", "継続皇帝", "100日連続で記録する"),
    ]

    for target, icon, title, desc in streak_badges:
        badges.append({
            "type": "連続記録",
            "icon": icon,
            "title": title,
            "desc": desc,
            "condition": "streak",
            "target": target
        })

    weekly_badges = [
        (1.0, "🎯", "週間目標達成", "今週の目標を達成する"),
        (1.2, "🚴", "目標超え", "週間目標の120%を達成する"),
        (1.5, "🦅", "大幅達成", "週間目標の150%を達成する"),
        (2.0, "🐉", "圧倒的達成", "週間目標の200%を達成する"),
    ]

    for rate, icon, title, desc in weekly_badges:
        badges.append({
            "type": "週間目標",
            "icon": icon,
            "title": title,
            "desc": desc,
            "condition": "weekly_rate",
            "target": rate
        })

    focus_badges = [
        (80, "🎧", "集中モード", "集中度80%以上を記録する"),
        (90, "⚡", "集中マスター", "集中度90%以上を記録する"),
        (100, "🧠", "完全集中", "集中度100%を記録する"),
    ]

    for target, icon, title, desc in focus_badges:
        badges.append({
            "type": "集中度",
            "icon": icon,
            "title": title,
            "desc": desc,
            "condition": "max_focus",
            "target": target
        })

    high_focus_count_badges = [
        (3, "🔎", "集中の再現", "集中度90%以上を3回記録する"),
        (5, "🔮", "集中の再現性", "集中度90%以上を5回記録する"),
        (10, "🧘", "集中の達人", "集中度90%以上を10回記録する"),
    ]

    for target, icon, title, desc in high_focus_count_badges:
        badges.append({
            "type": "集中回数",
            "icon": icon,
            "title": title,
            "desc": desc,
            "condition": "high_focus_count",
            "target": target
        })

    one_day_badges = [
        (2, "☕", "2時間クエスト", "1回で2時間以上勉強する"),
        (3, "⏳", "3時間クエスト", "1回で3時間以上勉強する"),
        (5, "🗻", "5時間クエスト", "1回で5時間以上勉強する"),
        (8, "🐉", "限界突破", "1回で8時間以上勉強する"),
    ]

    for target, icon, title, desc in one_day_badges:
        badges.append({
            "type": "一回の勉強",
            "icon": icon,
            "title": title,
            "desc": desc,
            "condition": "max_hours",
            "target": target
        })

    count_badges = [
        (3, "✍️", "記録初心者", "3回記録する"),
        (10, "📘", "記録習慣", "10回記録する"),
        (30, "📒", "ログ職人", "30回記録する"),
        (50, "🗂️", "記録マスター", "50回記録する"),
        (100, "🧾", "記録の鬼", "100回記録する"),
    ]

    for target, icon, title, desc in count_badges:
        badges.append({
            "type": "記録回数",
            "icon": icon,
            "title": title,
            "desc": desc,
            "condition": "log_count",
            "target": target
        })

    if not user_logs.empty:
        subjects = sorted(user_logs["subject"].dropna().unique())

        for subject in subjects:
            for target, icon, label in [
                (10, "📖", "10時間"),
                (30, "🎓", "30時間"),
                (50, "🏅", "50時間"),
                (100, "👑", "マスター"),
            ]:
                badges.append({
                    "type": "科目別",
                    "icon": icon,
                    "title": f"{subject} {label}",
                    "desc": f"{subject}を累計{target}時間勉強する",
                    "condition": "subject_hours",
                    "target": target,
                    "subject": subject
                })

    return badges


def is_badge_unlocked(
    badge,
    total_hours,
    streak,
    weekly_total,
    weekly_goal,
    user_logs
):
    condition = badge["condition"]

    if condition == "total_hours":
        return total_hours >= badge["target"]

    if condition == "streak":
        return streak >= badge["target"]

    if condition == "weekly_rate":
        return weekly_total >= weekly_goal * badge["target"]

    if user_logs.empty:
        return False

    if condition == "max_focus":
        return user_logs["focus"].max() >= badge["target"]

    if condition == "high_focus_count":
        return len(user_logs[user_logs["focus"] >= 90]) >= badge["target"]

    if condition == "max_hours":
        return user_logs["hours"].max() >= badge["target"]

    if condition == "log_count":
        return len(user_logs) >= badge["target"]

    if condition == "subject_hours":
        subject = badge.get("subject")
        subject_total = user_logs[user_logs["subject"] == subject]["hours"].sum()
        return subject_total >= badge["target"]

    return False


# =====================
# CSS
# =====================

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

.section-title {
    font-size: 28px;
    font-weight: 900;
    margin-top: 24px;
    margin-bottom: 12px;
}

.badge-card {
    background: white;
    border-radius: 22px;
    padding: 16px;
    margin-bottom: 12px;
    box-shadow: 0 8px 22px rgba(15,23,42,0.07);
    border: 1px solid #dbeafe;
}

.badge-card-locked {
    background: #f8fafc;
    border-radius: 22px;
    padding: 16px;
    margin-bottom: 12px;
    border: 1px solid #e5e7eb;
    opacity: 0.42;
}

.badge-icon {
    font-size: 30px;
    margin-bottom: 4px;
}

.badge-title {
    font-size: 16px;
    font-weight: 900;
    color: #111827;
}

.badge-type {
    font-size: 12px;
    color: #64748b;
    margin-top: 3px;
}

.badge-desc {
    font-size: 13px;
    color: #475569;
    margin-top: 8px;
}

.log-card {
    background: white;
    padding: 16px;
    border-radius: 20px;
    margin-bottom: 12px;
    border: 1px solid #e5e7eb;
    box-shadow: 0 8px 20px rgba(15,23,42,0.06);
}

.log-date {
    color: #64748b;
    font-size: 13px;
    margin-bottom: 4px;
}

.log-main {
    font-size: 18px;
    font-weight: 900;
    color: #111827;
}

.log-sub {
    color: #475569;
    font-size: 14px;
    margin-top: 5px;
}

.log-memo {
    background: #f8fafc;
    padding: 10px;
    border-radius: 12px;
    margin-top: 10px;
    color: #334155;
    font-size: 14px;
}
</style>
""", unsafe_allow_html=True)


# =====================
# 初期データ
# =====================

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


# =====================
# サイドバー
# =====================

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
    upsert_user(user_id, edit_name, edit_weekly_goal)
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
            append_subject(user_id, subject_name)
            st.sidebar.success("科目を追加しました")
            st.rerun()
    else:
        st.sidebar.warning("科目名を入力してください")


# =====================
# データ計算
# =====================

today = date.today()
week_start, week_end = get_week_range(today)

user_logs = logs[logs["user_id"] == user_id].copy()

if not user_logs.empty:
    user_logs["date_dt"] = pd.to_datetime(user_logs["date"]).dt.date
    week_logs = user_logs[
        (user_logs["date_dt"] >= week_start) &
        (user_logs["date_dt"] <= week_end)
    ].copy()
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

badge_catalog = get_badge_catalog(user_logs)

unlocked_badges = [
    badge for badge in badge_catalog
    if is_badge_unlocked(
        badge,
        total_hours,
        streak,
        weekly_total,
        edit_weekly_goal,
        user_logs
    )
]

if remaining == 0:
    mission_text = "🎉 今週の目標達成！今日は復習か軽めの積み上げでOK。"
elif streak == 0:
    mission_text = "🔥 まずは30分だけ記録しよう。ゼロにしないのが勝ち。"
elif achievement >= 70:
    mission_text = "⚔️ あと少し。今日は1時間だけでも積めばかなり強い。"
else:
    mission_text = f"📚 今週の残りは {remaining:.1f}h。今日は1.0hを目標にしよう。"


# =====================
# メイン画面
# =====================

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


# =====================
# 獲得済みバッジ
# =====================

st.markdown('<div class="section-title">獲得バッジ</div>', unsafe_allow_html=True)

if unlocked_badges:
    cols = st.columns(2)

    for i, badge in enumerate(unlocked_badges[:8]):
        with cols[i % 2]:
            st.markdown(f"""
            <div class="badge-card">
                <div class="badge-icon">{badge["icon"]}</div>
                <div class="badge-title">{badge["title"]}</div>
                <div class="badge-type">{badge["type"]}</div>
            </div>
            """, unsafe_allow_html=True)

    if len(unlocked_badges) > 8:
        st.caption(f"ほか {len(unlocked_badges) - 8} 個のバッジを獲得済み")
else:
    st.write("まだバッジはありません。まずは1時間勉強してみよう。")


# =====================
# 今日のクエスト
# =====================

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

            append_log(user_id, today, subject, hours, focus, memo)

            new_level, _, _, _ = calc_level(total_hours + hours)

            if new_level > old_level:
                st.balloons()
                st.success(f"🎉 レベルアップ！ Lv.{new_level} になりました！")
            else:
                st.success("記録しました！")

            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# =====================
# 今週の記録カード
# =====================

st.markdown('<div class="section-title">今週の記録</div>', unsafe_allow_html=True)

if week_logs.empty:
    st.write("今週の記録はまだありません。")
else:
    display_logs = week_logs[
        ["date", "subject", "hours", "focus", "memo"]
    ].copy()

    display_logs = display_logs.sort_values("date", ascending=False)

    for _, row in display_logs.iterrows():
        memo_text = row["memo"] if str(row["memo"]).strip() else "メモなし"

        st.markdown(f"""
        <div class="log-card">
            <div class="log-date">{row["date"]}</div>
            <div class="log-main">{row["subject"]}　{float(row["hours"]):.1f}h</div>
            <div class="log-sub">集中度 {int(row["focus"])}%</div>
            <div class="log-memo">{memo_text}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">科目別勉強時間</div>', unsafe_allow_html=True)

    subject_summary = week_logs.groupby("subject")["hours"].sum().reset_index()

    for _, row in subject_summary.iterrows():
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">{row["subject"]}</div>
            <div class="stat-number">{float(row["hours"]):.1f}h</div>
        </div>
        """, unsafe_allow_html=True)


# =====================
# バッジ図鑑
# =====================

st.markdown('<div class="section-title">バッジ図鑑</div>', unsafe_allow_html=True)

badge_filter = st.selectbox(
    "表示するバッジ",
    ["すべて", "未獲得のみ", "獲得済みのみ"]
)

cols = st.columns(2)

visible_index = 0

for badge in badge_catalog:
    unlocked = is_badge_unlocked(
        badge,
        total_hours,
        streak,
        weekly_total,
        edit_weekly_goal,
        user_logs
    )

    if badge_filter == "未獲得のみ" and unlocked:
        continue

    if badge_filter == "獲得済みのみ" and not unlocked:
        continue

    card_class = "badge-card" if unlocked else "badge-card-locked"
    status = "獲得済み" if unlocked else "未獲得"

    with cols[visible_index % 2]:
        st.markdown(f"""
        <div class="{card_class}">
            <div class="badge-icon">{badge["icon"]}</div>
            <div class="badge-title">{badge["title"]}</div>
            <div class="badge-type">{badge["type"]}｜{status}</div>
            <div class="badge-desc">{badge["desc"]}</div>
        </div>
        """, unsafe_allow_html=True)

    visible_index += 1


# =====================
# 記録削除
# =====================

st.markdown('<div class="section-title">記録を削除</div>', unsafe_allow_html=True)

if week_logs.empty:
    st.write("削除できる今週の記録はありません。")
else:
    user_week_logs = logs[logs["user_id"] == user_id].copy()
    user_week_logs["date_dt"] = pd.to_datetime(user_week_logs["date"]).dt.date
    user_week_logs = user_week_logs[
        (user_week_logs["date_dt"] >= week_start) &
        (user_week_logs["date_dt"] <= week_end)
    ]

    delete_options = []

    for idx, row in user_week_logs.iterrows():
        sheet_row = idx + 2
        label = f"{row['date']} | {row['subject']} | {row['hours']}h | 集中{row['focus']}%"
        delete_options.append((sheet_row, label))

    if delete_options:
        selected_delete = st.selectbox(
            "削除する記録を選択",
            delete_options,
            format_func=lambda x: x[1]
        )

        confirm_delete = st.checkbox("本当に削除する")

        if st.button("この記録を削除"):
            if confirm_delete:
                delete_log_by_sheet_row(selected_delete[0])
                st.success("記録を削除しました")
                st.rerun()
            else:
                st.warning("削除するにはチェックを入れてください")
