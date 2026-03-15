import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import random
import re
import json
from datetime import date, datetime, timedelta
import calendar
import os

try:
    from streamlit_calendar import calendar as st_calendar
    HAS_STREAMLIT_CALENDAR = True
except ImportError:
    HAS_STREAMLIT_CALENDAR = False

try:
    from streamlit_option_menu import option_menu
    HAS_OPTION_MENU = True
except ImportError:
    HAS_OPTION_MENU = False

# ページ設定（タブレット向け）
st.set_page_config(
    page_title="未来塾 生徒用アプリ",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

CSV_PATH = "users.csv"
PLANS_PATH = "plans.csv"
CONTENT_PATH = "content.csv"
NEWS_PATH = "news.csv"
MATERIALS_PATH = "materials.csv"
ADMIN_OPTION = "👨‍🏫 管理者"
ADMIN_PASSWORD = "admin"  # 本番では環境変数などに変更を推奨

COL_LAST_LOGIN = "last_login_date"  # 気分チェック（ボーナス）済みの日付
COL_LAST_VISIT = "last_visit_date"  # ストリーク用・最終訪問日
COL_STREAK = "streak"
COL_RECENT_LOGINS = "recent_login_dates"  # 直近7日分 "YYYY-MM-DD,..."
GACHA_COST = 50
TASK_POINTS = 5  # タスク完了ごとのポイント（今日の予定で未使用・互換のため残す）
TASK_TOGGLE_POINTS = 10  # チェックボックスで完了にした時 +10pt、外した時 -10pt

# ページ名
PAGE_HOME = "home"
PAGE_STUDY = "study"
PAGE_TEST = "test"
PAGE_GACHA = "gacha"
PAGE_SCHEDULE = "schedule"
PAGE_PLAN = "plan"

# ナビゲーション用：メニュー表示名とページ定数の対応
NAV_OPTIONS = ["ホーム", "📅 今日の学習", "計画確認", "小テスト", "ガチャ"]
NAV_ICONS = ["house", "journal-check", "map", "pencil-square", "gift"]
OPTION_TO_PAGE = {
    "ホーム": PAGE_HOME, "📅 今日の学習": PAGE_SCHEDULE, "計画確認": PAGE_PLAN,
    "小テスト": PAGE_TEST, "ガチャ": PAGE_GACHA,
}
PAGE_TO_OPTION = {
    PAGE_HOME: "ホーム", PAGE_SCHEDULE: "📅 今日の学習", PAGE_PLAN: "計画確認",
    PAGE_STUDY: "📅 今日の学習", PAGE_TEST: "小テスト", PAGE_GACHA: "ガチャ",
}

# users.csv を読み込み（列が古い場合は streak / last_visit_date / recent_login_dates を追加）
@st.cache_data
def load_users():
    df = pd.read_csv(CSV_PATH, encoding="utf-8")
    if COL_LAST_LOGIN not in df.columns:
        df[COL_LAST_LOGIN] = ""
    if COL_STREAK not in df.columns:
        df[COL_STREAK] = 0
    if COL_LAST_VISIT not in df.columns:
        df[COL_LAST_VISIT] = ""
    if COL_RECENT_LOGINS not in df.columns:
        df[COL_RECENT_LOGINS] = ""
    df.to_csv(CSV_PATH, index=False, encoding="utf-8")
    return df

def save_users(df):
    df.to_csv(CSV_PATH, index=False, encoding="utf-8")
    st.cache_data.clear()

def today_str():
    return date.today().isoformat()

def this_month_str():
    return date.today().strftime("%Y-%m")

# plans.csv を読み込み（無ければダミーデータで作成）
def load_plans():
    if not os.path.exists(PLANS_PATH):
        dummy = pd.DataFrame([
            ["田中太郎", "〇〇中学合格！", "図形マスター", "図形の基礎問題を5問解く", today_str(), 0, "", "", ""],
        ], columns=["ユーザー名", "大計画", "中計画", "小計画タスク", "日付", "完了フラグ", "video_url", "material_id", "page_range"])
        dummy.to_csv(PLANS_PATH, index=False, encoding="utf-8")
        return dummy
    df = pd.read_csv(PLANS_PATH, encoding="utf-8")
    updated = False
    for col, default in [("video_url", ""), ("material_id", ""), ("page_range", "")]:
        if col not in df.columns:
            df[col] = default
            updated = True
    if updated:
        df.to_csv(PLANS_PATH, index=False, encoding="utf-8")
    return df

def save_plans(df):
    df.to_csv(PLANS_PATH, index=False, encoding="utf-8")


def load_content():
    if not os.path.exists(CONTENT_PATH):
        pd.DataFrame(columns=["教科", "種別", "タイトル", "URL"]).to_csv(CONTENT_PATH, index=False, encoding="utf-8")
    return pd.read_csv(CONTENT_PATH, encoding="utf-8")

def save_content(df):
    df.to_csv(CONTENT_PATH, index=False, encoding="utf-8")

def load_news():
    if not os.path.exists(NEWS_PATH):
        pd.DataFrame(columns=["メッセージ", "作成日", "target_user"]).to_csv(NEWS_PATH, index=False, encoding="utf-8")
        return pd.read_csv(NEWS_PATH, encoding="utf-8")
    df = pd.read_csv(NEWS_PATH, encoding="utf-8")
    if "target_user" not in df.columns:
        df["target_user"] = "全員"
        df.to_csv(NEWS_PATH, index=False, encoding="utf-8")
    return df

def save_news(df):
    df.to_csv(NEWS_PATH, index=False, encoding="utf-8")


def load_materials():
    if not os.path.exists(MATERIALS_PATH):
        pd.DataFrame(columns=["ID", "教科", "教材名", "出版社", "対象学年", "目次データ"]).to_csv(MATERIALS_PATH, index=False, encoding="utf-8")
    return pd.read_csv(MATERIALS_PATH, encoding="utf-8")


def save_materials(df):
    df.to_csv(MATERIALS_PATH, index=False, encoding="utf-8")


# ---------- 計画用：標準ダイアログ（@st.dialog） ----------
@st.dialog("タスクの編集")
def edit_task_dialog(plan_idx):
    df = load_plans()
    df["日付"] = df["日付"].astype(str).str[:10]
    if plan_idx not in df.index:
        st.warning("タスクが見つかりません。")
        return
    row = df.loc[plan_idx]
    st.caption(f"科目（中計画）：{row['中計画']}　ステータス：{'完了' if int(row['完了フラグ']) == 1 else '未完了'}")
    try:
        current_d = datetime.strptime(str(row["日付"])[:10], "%Y-%m-%d").date()
    except Exception:
        current_d = date.today()
    new_date = st.date_input("日付", value=current_d, key="dialog_edit_date")
    new_task_name = st.text_input("タスク名", value=str(row["小計画タスク"]), key="dialog_edit_task")
    col_s, col_d, col_c = st.columns(3)
    with col_s:
        if st.button("保存（更新）", key="dialog_edit_save"):
            if new_task_name.strip():
                df.loc[plan_idx, "小計画タスク"] = new_task_name.strip()
            df.loc[plan_idx, "日付"] = new_date.isoformat()
            save_plans(df)
            st.rerun()
    with col_d:
        if st.button("削除", key="dialog_edit_delete"):
            df = df.drop(index=plan_idx)
            save_plans(df)
            st.rerun()
    with col_c:
        if st.button("キャンセル", key="dialog_edit_cancel"):
            st.rerun()


@st.dialog("新規タスク追加")
def add_task_dialog(mid_plan, selected_user):
    df = load_plans()
    user_rows = df[df["ユーザー名"] == selected_user]
    big_plan = user_rows["大計画"].iloc[0] if len(user_rows) > 0 else ""
    st.markdown(f"**中計画：** {mid_plan}")
    new_task_name = st.text_input("何をするか（タスク名）", key="dialog_add_task")
    new_task_date = st.date_input("いつやるか（日付）", value=date.today(), key="dialog_add_date")
    col_a, col_c = st.columns(2)
    with col_a:
        if st.button("追加する", key="dialog_add_submit"):
            if new_task_name and new_task_name.strip():
                new_row = pd.DataFrame([{
                    "ユーザー名": selected_user,
                    "大計画": big_plan,
                    "中計画": mid_plan,
                    "小計画タスク": new_task_name.strip(),
                    "日付": new_task_date.isoformat(),
                    "完了フラグ": 0,
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                save_plans(df)
                st.rerun()
            else:
                st.warning("タスク名を入力してください。")
    with col_c:
        if st.button("キャンセル", key="dialog_add_cancel"):
            st.rerun()


# 例として使用するURL（実際の運用では差し替えてください）
YOUTUBE_EMBED_URL = "https://www.youtube.com/embed/dQw4w9WgXcQ"
GOOGLE_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScVVn3qGYn48oxTzGLOE0iPzFqYjvQnLexample/viewform"

# ---------- セッション状態：現在のページ ----------
if "page" not in st.session_state:
    st.session_state.page = PAGE_HOME
if "toast_shown" not in st.session_state:
    st.session_state.toast_shown = False

# ---------- 共通：ユーザーデータ読み込み ----------
df = load_users()
df_plans = load_plans()

# サイドバー：ユーザー選択（管理者オプション付き）
st.sidebar.title("👤 ユーザー選択")
st.sidebar.markdown("---")
user_names = df["ユーザー名"].tolist()
options = user_names + [ADMIN_OPTION]
selected_user = st.sidebar.selectbox(
    "名前を選んでください",
    options=options,
    index=0
)

# 管理者選択時：パスワード入力と管理画面へ
if selected_user == ADMIN_OPTION:
    if "admin_ok" not in st.session_state:
        st.session_state.admin_ok = False
    pwd = st.sidebar.text_input("パスワード", type="password", key="admin_pwd")
    if st.sidebar.button("ログイン", key="admin_login") and pwd == ADMIN_PASSWORD:
        st.session_state.admin_ok = True
        st.rerun()
    if not st.session_state.admin_ok:
        st.info("👨‍🏫 管理者を選択しました。パスワードを入力してログインしてください。")
        st.stop()
    # 以下：管理画面を表示して終了
    st.title("👨‍🏫 管理者画面")
    tab_dash, tab_content, tab_materials, tab_news = st.tabs(["📊 生徒の進捗一覧", "📎 教材管理", "📚 教材マスター", "📢 お知らせ管理"])

    with tab_dash:
        st.subheader("生徒の進捗ダッシュボード")
        df_u = load_users()
        dash = df_u[["ユーザー名", "現在ポイント", COL_STREAK, COL_LAST_VISIT]].copy()
        dash.columns = ["生徒名", "ポイント", "連続ログイン日数", "最終ログイン日"]
        dash["最終ログイン日"] = dash["最終ログイン日"].fillna("").astype(str)
        cutoff = (date.today() - timedelta(days=3)).isoformat()
        def highlight_old(row):
            v = str(row["最終ログイン日"]).strip()
            if not v or v == "nan":
                return ["background-color: #ffcccc"] * len(row)
            if v < cutoff:
                return ["background-color: #ffcccc"] * len(row)
            return [""] * len(row)
        st.dataframe(dash.style.apply(highlight_old, axis=1), use_container_width=True, hide_index=True)
        st.caption("※ 赤背景＝最終ログインが3日以上前（要注意）")

    with tab_content:
        st.subheader("教材（動画・小テスト）URL 管理")
        df_c = load_content()
        if "教科" not in df_c.columns:
            df_c = pd.DataFrame(columns=["教科", "種別", "タイトル", "URL"])
            save_content(df_c)
        for subject in ["国語", "算数", "理科", "社会"]:
            with st.expander(f"📚 {subject}", expanded=True):
                sub = df_c[df_c["教科"] == subject] if len(df_c) else pd.DataFrame()
                for idx, row in sub.iterrows():
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        url_preview = (row.get("URL") or "")[:60] + ("..." if len(row.get("URL") or "") > 60 else "")
                        st.markdown(f"**{row.get('タイトル', '')}**（{row.get('種別', '')}）　{url_preview}")
                    with c2:
                        if st.button("削除", key=f"content_del_{subject}_{idx}"):
                            df_c = load_content()
                            df_c = df_c.drop(index=idx)
                            save_content(df_c)
                            st.rerun()
                        if st.button("編集", key=f"content_edit_{subject}_{idx}"):
                            st.session_state[f"content_editing_{subject}"] = idx
                            st.rerun()
                adding = st.session_state.get(f"content_adding_{subject}")
                editing_idx = st.session_state.get(f"content_editing_{subject}")
                show_form = adding or (editing_idx is not None)
                if show_form:
                    df_c = load_content()
                    if editing_idx is not None and editing_idx in df_c.index:
                        row = df_c.loc[editing_idx]
                        default_tit = row.get("タイトル", "")
                        default_typ = row.get("種別", "動画")
                        if default_typ == "フォーム":
                            default_typ = "小テスト"
                        default_url = row.get("URL", "")
                    else:
                        default_tit = default_url = ""
                        default_typ = "動画"
                    form_suffix = f"edit_{editing_idx}" if editing_idx is not None else "new"
                    tit = st.text_input("タイトル", value=default_tit, key=f"ctitle_{subject}_{form_suffix}")
                    typ = st.selectbox("種別", ["動画", "小テスト"], index=0 if default_typ == "動画" else 1, key=f"ctype_{subject}_{form_suffix}")
                    url_label = "小テストURL" if typ == "小テスト" else "動画URL"
                    url = st.text_input(url_label, value=default_url, key=f"curl_{subject}_{form_suffix}")
                    if st.button("保存", key=f"csave_{subject}") and tit and url:
                        df_c = load_content()
                        if editing_idx is not None and editing_idx in df_c.index:
                            df_c.at[editing_idx, "タイトル"] = tit
                            df_c.at[editing_idx, "種別"] = typ
                            df_c.at[editing_idx, "URL"] = url
                        else:
                            df_c = pd.concat([df_c, pd.DataFrame([{"教科": subject, "種別": typ, "タイトル": tit, "URL": url}])], ignore_index=True)
                        save_content(df_c)
                        st.session_state[f"content_adding_{subject}"] = False
                        st.session_state[f"content_editing_{subject}"] = None
                        st.rerun()
                    if st.button("キャンセル", key=f"ccancel_{subject}"):
                        st.session_state[f"content_adding_{subject}"] = False
                        st.session_state[f"content_editing_{subject}"] = None
                        st.rerun()
                if not show_form and st.button(f"➕ 追加", key=f"content_add_{subject}"):
                    st.session_state[f"content_adding_{subject}"] = True
                    st.rerun()

    with tab_materials:
        st.subheader("📚 教材マスター登録")
        if "materials_toc_draft" not in st.session_state:
            st.session_state.materials_toc_draft = []
        # 基本情報
        st.markdown("**教材の基本情報**")
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            mat_kyouka = st.selectbox("教科", ["国語", "算数", "理科", "社会"], key="mat_kyouka")
            mat_name = st.text_input("教材名", key="mat_name")
        with col_m2:
            mat_pub = st.text_input("出版社", key="mat_pub")
            mat_grade = st.text_input("対象学年（例: 中1・小5）", key="mat_grade")
        st.markdown("---")
        st.markdown("**目次・単元の登録**")
        col_t1, col_t2, col_t3 = st.columns([2, 2, 1])
        with col_t1:
            toc_unit = st.text_input("単元名", key="toc_unit")
        with col_t2:
            toc_pages = st.text_input("ページ範囲（例: P.10-15）", key="toc_pages")
        with col_t3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ 追加", key="toc_add_btn") and toc_unit.strip():
                st.session_state.materials_toc_draft.append({"単元名": toc_unit.strip(), "ページ範囲": toc_pages.strip() or "-"})
                st.rerun()
        if st.session_state.materials_toc_draft:
            st.markdown("**一時保存中の目次**")
            for i, item in enumerate(st.session_state.materials_toc_draft):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"- **{item['単元名']}** … {item['ページ範囲']}")
                with c2:
                    if st.button("削除", key=f"toc_del_{i}"):
                        st.session_state.materials_toc_draft.pop(i)
                        st.rerun()
            if st.button("教材を保存", type="primary", key="mat_save_btn"):
                if not mat_name.strip():
                    st.warning("教材名を入力してください。")
                else:
                    df_m = load_materials()
                    try:
                        new_id = int(df_m["ID"].dropna().max()) + 1 if len(df_m) else 1
                    except (ValueError, TypeError):
                        new_id = 1
                    toc_json = json.dumps(st.session_state.materials_toc_draft, ensure_ascii=False)
                    new_row = pd.DataFrame([{"ID": new_id, "教科": mat_kyouka, "教材名": mat_name.strip(), "出版社": mat_pub.strip(), "対象学年": mat_grade.strip(), "目次データ": toc_json}])
                    df_m = pd.concat([df_m, new_row], ignore_index=True)
                    save_materials(df_m)
                    st.session_state.materials_toc_draft = []
                    st.success("教材を保存しました。")
                    st.rerun()
        else:
            st.caption("単元名とページ範囲を入力して「追加」を押すと、ここに目次が溜まります。最後に「教材を保存」で materials.csv に書き込みます。")
        st.markdown("---")
        st.subheader("登録済み教材一覧")
        df_m = load_materials()
        if len(df_m) == 0:
            st.info("まだ教材が登録されていません。")
        else:
            df_display = df_m[["ID", "教科", "教材名", "出版社", "対象学年"]].copy()
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            st.markdown("**詳細（目次）を表示**")
            mat_options = [f"ID{row['ID']} {row['教材名']}（{row['教科']}）" for _, row in df_m.iterrows()]
            sel_idx = st.selectbox("教材を選択", range(len(mat_options)), format_func=lambda i: mat_options[i], key="mat_sel_detail")
            if sel_idx is not None and 0 <= sel_idx < len(df_m):
                toc_str = df_m.iloc[sel_idx].get("目次データ", "[]")
                try:
                    toc_list = json.loads(toc_str) if isinstance(toc_str, str) else toc_str
                except Exception:
                    toc_list = []
                if toc_list:
                    for item in toc_list:
                        st.markdown(f"- **{item.get('単元名', '')}** … {item.get('ページ範囲', '')}")
                else:
                    st.caption("目次データはありません。")

    with tab_news:
        st.subheader("お知らせメッセージ（ホームに表示）")
        df_n = load_news()
        user_names = load_users()["ユーザー名"].tolist()
        for idx, row in df_n.iterrows():
            c1, c2 = st.columns([4, 1])
            with c1:
                target = row.get("target_user", "全員")
                st.markdown(f"- **[{target}]** {row.get('メッセージ', '')}")
            with c2:
                if st.button("削除", key=f"news_del_{idx}"):
                    df_n = df_n.drop(index=idx)
                    save_news(df_n)
                    st.rerun()
        if st.button("➕ お知らせを追加", key="news_add_btn"):
            st.session_state["news_adding"] = True
        if st.session_state.get("news_adding"):
            msg = st.text_area("メッセージ", key="new_news_msg")
            target_options = ["全員"] + user_names
            target_user = st.selectbox("対象（全員 / 生徒名）", options=target_options, key="news_target_user")
            if st.button("登録", key="news_save_btn") and msg.strip():
                df_n = load_news()
                df_n = pd.concat([df_n, pd.DataFrame([{"メッセージ": msg.strip(), "作成日": today_str(), "target_user": target_user}])], ignore_index=True)
                save_news(df_n)
                st.session_state["news_adding"] = False
                st.rerun()
            if st.button("キャンセル", key="news_cancel_btn"):
                st.session_state["news_adding"] = False
                st.rerun()

    st.stop()

# 通常の生徒として続行（管理者でない）
user_row = df[df["ユーザー名"] == selected_user]
current_points = int(user_row["現在ポイント"].values[0])
last_login = str(user_row[COL_LAST_LOGIN].values[0]) if pd.notna(user_row[COL_LAST_LOGIN].values[0]) else ""
today = today_str()
this_month = this_month_str()

# ストリーク用（ホームで更新するためここでは読み取りのみ）
def _get_val(row, col, default=""):
    v = row[col].values[0]
    return v if pd.notna(v) and str(v).strip() else default

streak = int(user_row[COL_STREAK].values[0]) if COL_STREAK in df.columns and pd.notna(user_row[COL_STREAK].values[0]) else 0
last_visit = _get_val(user_row, COL_LAST_VISIT, "") if COL_LAST_VISIT in df.columns else ""
recent_login_dates = _get_val(user_row, COL_RECENT_LOGINS, "") if COL_RECENT_LOGINS in df.columns else ""

# ---------- 水平メニューバー（streamlit-option-menu） ----------
if HAS_OPTION_MENU:
    current_option = PAGE_TO_OPTION.get(st.session_state.page, "ホーム")
    default_index = NAV_OPTIONS.index(current_option) if current_option in NAV_OPTIONS else 0
    selected = option_menu(
        menu_title=None,
        options=NAV_OPTIONS,
        icons=NAV_ICONS,
        default_index=default_index,
        orientation="horizontal",
        styles={
            "container": {"padding": "0.25rem 0", "background-color": "#f5f5f5"},
            "icon": {"color": "#ff9800", "font-size": "1.2rem"},
            "nav-link": {"font-size": "1rem", "text-align": "center", "--hover-color": "#e3f2fd"},
            "nav-link-selected": {"background-color": "#007bff"},
        },
    )
    if selected and OPTION_TO_PAGE.get(selected) != st.session_state.page:
        st.session_state.page = OPTION_TO_PAGE[selected]
        st.rerun()
else:
    # ライブラリ未導入時：シンプルなボタンで遷移
    cur_opt = PAGE_TO_OPTION.get(st.session_state.page, "ホーム")
    idx = NAV_OPTIONS.index(cur_opt) if cur_opt in NAV_OPTIONS else 0
    sel = st.radio("メニュー", NAV_OPTIONS, index=idx, horizontal=True, label_visibility="collapsed")
    if sel and OPTION_TO_PAGE.get(sel) != st.session_state.page:
        st.session_state.page = OPTION_TO_PAGE[sel]
        st.rerun()

# ---------- 共通：画面右上に小さく挨拶・ポイント表示 ----------
st.markdown("""
<style>
    .header-right { text-align: right; font-size: 1rem; color: #555; margin-bottom: 0.5rem; }
    .mood-btn button { font-size: 1.6rem !important; padding: 1rem !important; min-height: 3.5rem !important; }
    .learning-card { background: #fff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); padding: 1.5rem; margin: 1rem 0; border: 1px solid #e0e0e0; }
    .test-link-card { display: block; background: linear-gradient(135deg, #1f77b4 0%, #2ca02c 100%); color: white !important; text-align: center; padding: 1.5rem 2rem; border-radius: 12px; font-size: 1.5rem; font-weight: bold; text-decoration: none; box-shadow: 0 4px 12px rgba(0,0,0,0.15); margin: 1rem 0; transition: transform 0.2s, box-shadow 0.2s; }
    .test-link-card:hover { transform: scale(1.02); box-shadow: 0 6px 16px rgba(0,0,0,0.2); color: white !important; }
    .gacha-result-box { text-align: center; padding: 2rem; margin: 2rem 0; border-radius: 16px; font-size: 2rem; font-weight: bold; box-shadow: 0 6px 20px rgba(0,0,0,0.15); }
    .gacha-result-urare { background: linear-gradient(135deg, #ffd700 0%, #ff8c00 100%); color: #333; }
    .gacha-result-super { background: linear-gradient(135deg, #c0c0c0 0%, #a0a0a0 100%); color: #222; }
    .gacha-result-normal { background: linear-gradient(135deg, #87ceeb 0%, #6bb6e0 100%); color: #222; }
    .point-shortage { color: #d32f2f !important; font-size: 1.8rem !important; font-weight: bold !important; }
    .plan-big { font-size: 2rem; font-weight: bold; color: #1f77b4; margin: 1rem 0; padding: 1rem; background: #e3f2fd; border-radius: 12px; }
    .plan-mid { font-size: 1.5rem; font-weight: bold; color: #2e7d32; margin: 0.8rem 0; padding: 0.8rem; background: #e8f5e9; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

_, header_col = st.columns([3, 1])
with header_col:
    st.markdown(f'<p class="header-right">こんにちは、{selected_user}さん！　現在のポイント：<strong>{current_points}pt</strong></p>', unsafe_allow_html=True)

# ホーム画面のときだけトーストで挨拶（1回だけ）
if st.session_state.page == PAGE_HOME and not st.session_state.toast_shown:
    st.toast(f"こんにちは、{selected_user}さん！")
    st.session_state.toast_shown = True

# ---------- ホームに戻るボタン（予定・計画などナビにないページ用） ----------
def render_back_home():
    if st.button("🏠 ホームに戻る", use_container_width=False):
        st.session_state.page = PAGE_HOME
        st.rerun()

if st.session_state.page != PAGE_HOME:
    render_back_home()
    st.markdown("---")

# ========== ホーム画面 ==========
if st.session_state.page == PAGE_HOME:
    # 訪問日更新（ストリーク用）：今日まだ訪問していなければ更新
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    if last_visit != today:
        new_streak = (streak + 1) if (last_visit == yesterday) else 1
        dates_list = [today] + [d.strip() for d in recent_login_dates.split(",") if d.strip()]
        cutoff = (date.today() - timedelta(days=6)).isoformat()
        dates_list = [d for d in dates_list if d >= cutoff][:7]
        new_recent = ",".join(dates_list)
        df.loc[df["ユーザー名"] == selected_user, COL_STREAK] = new_streak
        df.loc[df["ユーザー名"] == selected_user, COL_LAST_VISIT] = today
        df.loc[df["ユーザー名"] == selected_user, COL_RECENT_LOGINS] = new_recent
        save_users(df)
        streak = new_streak
        recent_login_dates = new_recent

    st.markdown("## ホーム")

    # お知らせ（news.csv）：自分宛て or 全員宛てのみ表示・目立つ表示
    df_news = load_news()
    if "target_user" not in df_news.columns:
        df_news["target_user"] = "全員"
    df_news_mine = df_news[(df_news["target_user"] == "全員") | (df_news["target_user"] == selected_user)]
    if len(df_news_mine) > 0:
        with st.container():
            st.markdown("### 📢 お知らせ")
            for _, row in df_news_mine.iterrows():
                st.warning("⚠️ " + row.get("メッセージ", ""), icon="📢")
            st.markdown("---")

    # 連続記録（Streak）の可視化（ワクワクヒートマップ）
    st.markdown(
        f'<p style="font-size: 2rem; font-weight: bold; color: #e65100;">🔥 連続 {streak}日目！</p>',
        unsafe_allow_html=True,
    )
    recent_set = set(d.strip() for d in recent_login_dates.split(",") if d.strip())
    today_iso = date.today().isoformat()
    weekdays_ja = ["月", "火", "水", "木", "金", "土", "日"]
    # 直近7日分の日付・達成有無・曜日
    day_infos = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        is_today = d == today_iso
        achieved = d in recent_set
        if achieved:
            icon = "🔥"
            label = "今日" if is_today else d[5:].replace("-", "/")
            css_class = "streak-cell achieved"
        elif is_today:
            icon = "✨"
            label = "今日"
            css_class = "streak-cell today-empty"
        else:
            icon = "⚪"
            label = d[5:].replace("-", "/")
            css_class = "streak-cell empty"
        wd = date.fromisoformat(d).weekday()
        day_infos.append({"date": d, "icon": icon, "label": label, "css": css_class, "weekday": weekdays_ja[wd]})
    st.markdown("""
    <style>
    .streak-cell { text-align: center; padding: 0.5rem; border-radius: 12px; font-size: 1rem; }
    .streak-cell.achieved { background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%); color: #fff; font-size: 1.8rem; font-weight: bold; box-shadow: 0 4px 12px rgba(245,124,0,0.4); }
    .streak-cell.today-empty { background: #fff8e1; color: #f9a825; font-size: 1.2rem; }
    .streak-cell.empty { color: #9e9e9e; }
    </style>
    """, unsafe_allow_html=True)
    st.markdown("**直近7日間**")
    cols = st.columns(7)
    for idx, col in enumerate(cols):
        with col:
            info = day_infos[idx]
            st.markdown(
                f'<div class="{info["css"]}"><span style="display:block; font-size: inherit;">{info["icon"]}</span><span style="display:block; font-size: 0.85rem; margin-top: 0.2rem;">{info["label"]}</span></div>',
                unsafe_allow_html=True,
            )
    cols_w = st.columns(7)
    for idx, col in enumerate(cols_w):
        with col:
            st.markdown(f'<p style="text-align: center; font-size: 0.9rem; color: #666; margin-top: -0.3rem;">{day_infos[idx]["weekday"]}</p>', unsafe_allow_html=True)
    st.caption("🔥＝達成済み　⚪＝未達成　✨＝今日（まだならログインして炎を灯そう！）")
    st.markdown("")

    # 今日の気分チェック（last_login_date が今日なら表示しない／登録済みのみ）
    if last_login == today:
        st.markdown("### 今日の気分　登録済み")
        st.caption("今日の気分チェックは完了しています。")
    else:
        st.markdown("### 今日の気分は？")
        st.markdown("")
        st.markdown('<div class="mood-btn">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            btn_genki = st.button("元気！", use_container_width=True, type="primary")
        with c2:
            btn_futsuu = st.button("ふつう", use_container_width=True)
        with c3:
            btn_nemui = st.button("眠い...", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        bonus_gotten = False
        if btn_genki or btn_futsuu or btn_nemui:
            current_points += 10
            df.loc[df["ユーザー名"] == selected_user, "現在ポイント"] = current_points
            df.loc[df["ユーザー名"] == selected_user, COL_LAST_LOGIN] = today
            save_users(df)
            bonus_gotten = True
        if bonus_gotten:
            st.success("🎉 ログインボーナスゲット！")

# ========== 今日の学習（タスク一覧＆実行） ==========
elif st.session_state.page == PAGE_SCHEDULE:
    st.markdown("## 📅 今日の学習")
    st.markdown("")

    df_plans = load_plans()
    df_plans["日付"] = df_plans["日付"].astype(str).str[:10]
    today_plans = df_plans[(df_plans["ユーザー名"] == selected_user) & (df_plans["日付"] == today)]

    def subject_from_mid(mid):
        s = str(mid).strip()
        m = re.match(r"^\[(.*?)\]", s)
        return m.group(1).strip() if m else s

    df_materials = load_materials() if os.path.exists(MATERIALS_PATH) else pd.DataFrame()

    if today_plans.empty:
        st.info("今日の学習タスクはありません。")
    else:
        for idx, row in today_plans.iterrows():
            done = int(row["完了フラグ"]) == 1
            status_icon = "✅" if done else "⬜"
            subject = subject_from_mid(row.get("中計画", ""))
            task_name = str(row.get("小計画タスク", ""))
            header_label = f"{status_icon} {subject} : {task_name}"

            with st.expander(header_label, expanded=not done):
                # 教材情報（material_id があれば）
                mat_id = row.get("material_id")
                if pd.notna(mat_id) and str(mat_id).strip() and len(df_materials):
                    try:
                        mid_int = int(float(mat_id))
                        mat_row = df_materials[df_materials["ID"].astype(int) == mid_int]
                        if not mat_row.empty:
                            mat_name = mat_row.iloc[0].get("教材名", "")
                            page_range = str(row.get("page_range", "")).strip() or ""
                            if page_range:
                                st.markdown(f"📖 **使用教材:** {mat_name} P.{page_range}")
                            else:
                                st.markdown(f"📖 **使用教材:** {mat_name}")
                    except (ValueError, TypeError):
                        pass
                # 動画（video_url があれば）
                video_url = row.get("video_url")
                if pd.notna(video_url) and str(video_url).strip():
                    st.video(str(video_url).strip())
                # ストップウォッチ（開始/終了記録・任意）
                if f"task_start_{idx}" not in st.session_state:
                    st.session_state[f"task_start_{idx}"] = None
                col_sw1, col_sw2, _ = st.columns([1, 1, 2])
                with col_sw1:
                    if st.button("⏱ 開始", key=f"sw_start_{idx}"):
                        st.session_state[f"task_start_{idx}"] = datetime.now().strftime("%H:%M")
                        st.rerun()
                with col_sw2:
                    if st.button("⏹ 終了", key=f"sw_end_{idx}"):
                        st.session_state[f"task_start_{idx}"] = None
                        st.rerun()
                if st.session_state.get(f"task_start_{idx}"):
                    st.caption(f"開始: {st.session_state[f'task_start_{idx}']}")
                # 完了アクション
                if not done:
                    if st.button("✅ 完了！", type="primary", key=f"task_done_{idx}"):
                        df_plans = load_plans()
                        df_plans["日付"] = df_plans["日付"].astype(str).str[:10]
                        df_plans.loc[idx, "完了フラグ"] = 1
                        new_pt = max(0, current_points + TASK_TOGGLE_POINTS)
                        df = load_users()
                        df.loc[df["ユーザー名"] == selected_user, "現在ポイント"] = new_pt
                        save_plans(df_plans)
                        save_users(df)
                        st.balloons()
                        st.rerun()
                else:
                    st.success("このタスクは完了しています。")

# ========== 計画確認ページ ==========
elif st.session_state.page == PAGE_PLAN:
    st.markdown("## 🗺️ 計画確認")
    st.markdown("")

    df_plans = load_plans()
    df_plans["日付"] = df_plans["日付"].astype(str).str[:10]
    user_plans = df_plans[df_plans["ユーザー名"] == selected_user].copy()
    month_plans = user_plans[user_plans["日付"].str.startswith(this_month, na=False)].copy()

    # カレンダー用イベント（ユーザーの全タスクを表示）
    calendar_events = []
    for idx, row in user_plans.iterrows():
        done = int(row["完了フラグ"]) == 1
        status_ja = "完了" if done else "未完了"
        calendar_events.append({
            "id": str(idx),
            "title": str(row["小計画タスク"])[:30],
            "start": str(row["日付"])[:10],
            "end": str(row["日付"])[:10],
            "allDay": True,
            "extendedProps": {
                "subject": str(row["中計画"]),
                "status": status_ja,
                "plan_idx": int(idx) if isinstance(idx, (int, float)) else idx,
            },
        })

    if user_plans.empty:
        st.info("計画データがありません。")
    else:
        big_plan = user_plans["大計画"].iloc[0]
        # 中計画から [科目] 目標 形式をパース
        def parse_mid(mid):
            s = str(mid).strip()
            m = re.match(r"^\[(.*?)\]\s*(.*)$", s)
            if m:
                return m.group(1).strip(), m.group(2).strip()
            return s, s

        # 存在する月を抽出（無ければ 2026年3〜6月を固定）
        month_list = sorted(user_plans["日付"].astype(str).str[:7].unique().tolist())
        if not month_list:
            month_list = ["2026-03", "2026-04", "2026-05", "2026-06"]
        SUBJECTS = ["国語", "算数", "理科", "社会"]

        with st.expander("🎯 目標を確認・編集する（クリックで開閉）", expanded=False):
            new_big = st.text_input("大計画", value=str(big_plan), key="plan_input_big")
            st.markdown("**月ごと・科目ごとの目標**")
            tab_labels = [f"{m[:4]}年{int(m[5:7])}月" for m in month_list]
            month_tabs = st.tabs(tab_labels)

            for i, month_str in enumerate(month_list):
                with month_tabs[i]:
                    month_data = user_plans[user_plans["日付"].astype(str).str[:7] == month_str]
                    subject_goals = {}
                    for mid in month_data["中計画"].dropna().unique():
                        subj, goal = parse_mid(mid)
                        if subj and subj not in subject_goals:
                            subject_goals[subj] = goal
                    new_goals = {}
                    for subj in SUBJECTS:
                        new_goals[subj] = st.text_input(
                            f"{subj}の目標",
                            value=subject_goals.get(subj, ""),
                            key=f"plan_goal_{month_str}_{subj}",
                        )
                    month_label = f"{int(month_str[5:7])}月"
                    if st.button(f"💾 {month_label}の目標を保存", key=f"plan_save_{month_str}"):
                        df = load_plans()
                        df["日付"] = df["日付"].astype(str).str[:10]
                        df.loc[df["ユーザー名"] == selected_user, "大計画"] = new_big
                        for subj in SUBJECTS:
                            new_goal = str(new_goals.get(subj, "")).strip()
                            mask = (
                                (df["ユーザー名"] == selected_user)
                                & (df["日付"].str[:7] == month_str)
                                & (df["中計画"].astype(str).str.strip().str.startswith(f"[{subj}]"))
                            )
                            df.loc[mask, "中計画"] = f"[{subj}] {new_goal}"
                        save_plans(df)
                        st.success(f"{month_label}の目標を保存しました。")
                        st.rerun()

        total = len(month_plans)
        done_count = (month_plans["完了フラグ"].astype(int) == 1).sum() if total else 0
        st.progress(done_count / total if total else 0)
        st.caption(f"達成状況：{int(done_count)} / {int(total)} タスク")
        st.markdown("")

        # タブ：カレンダー / タスクリスト（タブレットで見やすく）
        tab_cal, tab_list = st.tabs(["📅 カレンダー", "📝 タスクリスト"])

        with tab_cal:
            st.markdown("#### 📆 カレンダー（タスクをクリックで編集）")
            if HAS_STREAMLIT_CALENDAR:
                calendar_options = {
                    "editable": False,
                    "selectable": True,
                    "initialView": "dayGridMonth",
                    "headerToolbar": {"left": "today prev,next", "center": "title", "right": ""},
                    "initialDate": this_month + "-01",
                }
                cal_result = st_calendar(
                    events=calendar_events,
                    options=calendar_options,
                    key="plan-calendar",
                )
                if cal_result and cal_result.get("callback") == "eventClick":
                    ev = cal_result.get("eventClick", {}).get("event", {})
                    ext = ev.get("extendedProps") or {}
                    plan_idx = ext.get("plan_idx")
                    if plan_idx is not None:
                        edit_task_dialog(plan_idx)
            else:
                year, month = date.today().year, date.today().month
                days_in_month = calendar.monthrange(year, month)[1]
                plan_dates = month_plans["日付"].astype(str).str[:10]
                count_by_date = plan_dates.value_counts()
                rows = []
                for d in range(1, days_in_month + 1):
                    d_str = f"{year}-{month:02d}-{d:02d}"
                    wd = date(year, month, d).weekday()
                    weekday_ja = ["月", "火", "水", "木", "金", "土", "日"][wd]
                    n = int(count_by_date.get(d_str, 0))
                    rows.append({"日付": d_str, "曜日": weekday_ja, "タスク数": n})
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                if not HAS_STREAMLIT_CALENDAR:
                    st.caption("※ streamlit-calendar をインストールすると月表示カレンダーが使えます。")

        with tab_list:
            st.markdown("#### 📝 今月のタスク（科目ごと）")
            if month_plans.empty:
                st.caption("今月のタスクはありません。")
            else:
                mid_groups = month_plans.groupby("中計画", sort=False)
                for mid_plan, group in mid_groups:
                    tasks_sorted = group.sort_values("日付")
                    label = f"{mid_plan}（{len(tasks_sorted)}件）"
                    with st.expander(label, expanded=True):
                        for idx, row in tasks_sorted.iterrows():
                            done = int(row["完了フラグ"]) == 1
                            c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
                            with c1:
                                checked = st.checkbox(
                                    row["小計画タスク"],
                                    value=done,
                                    key=f"planlist_cb_{idx}",
                                )
                                if checked != done:
                                    df_plans.loc[idx, "完了フラグ"] = 1 if checked else 0
                                    delta = TASK_TOGGLE_POINTS if checked else -TASK_TOGGLE_POINTS
                                    new_pt = max(0, current_points + delta)
                                    df.loc[df["ユーザー名"] == selected_user, "現在ポイント"] = new_pt
                                    save_plans(df_plans)
                                    save_users(df)
                                    st.rerun()
                            with c2:
                                st.caption(row["日付"])
                            with c3:
                                if st.button("📅 日付変更", key=f"chdate_{idx}"):
                                    edit_task_dialog(idx)
                        if st.button("➕ 新しいタスクを追加", key=f"add_{hash(mid_plan) % 10**8}"):
                            add_task_dialog(mid_plan, selected_user)

# ========== 勉強画面 ==========
# ========== 小テスト画面 ==========
elif st.session_state.page == PAGE_TEST:
    st.markdown("## ✍️ 小テスト")
    st.markdown("")
    st.markdown("以下のボタンから小テストを開いてください。")
    st.markdown("")
    st.markdown(
        f'<a href="{GOOGLE_FORM_URL}" target="_blank" rel="noopener noreferrer" class="test-link-card">✍️ 小テストを開く</a>',
        unsafe_allow_html=True
    )

# ========== ガチャ画面 ==========
elif st.session_state.page == PAGE_GACHA:
    st.markdown("## 🎁 お楽しみガチャ")
    st.markdown("")
    st.markdown(f"現在のポイント：**{current_points}pt**（1回 50pt）")
    st.markdown("")

    btn_gacha = st.button("ガチャを引く（50pt消費）", use_container_width=True, type="primary")

    if btn_gacha:
        if current_points < GACHA_COST:
            st.markdown('<p class="point-shortage">ポイントが足りないよ！</p>', unsafe_allow_html=True)
        else:
            current_points -= GACHA_COST
            df.loc[df["ユーザー名"] == selected_user, "現在ポイント"] = current_points
            save_users(df)

            r = random.random()
            if r < 0.05:
                prize_text = "【激レア】先生とのお喋り券チケット！🎉"
                result_class = "gacha-result-urare"
            elif r < 0.20:
                prize_text = "【スーパーレア】宿題1回パス券！✨"
                result_class = "gacha-result-super"
            else:
                prize_text = "【ノーマル】すごい！明日も頑張ろう！👍"
                result_class = "gacha-result-normal"

            st.markdown(
                f'<div class="gacha-result-box {result_class}">{prize_text}</div>',
                unsafe_allow_html=True
            )
