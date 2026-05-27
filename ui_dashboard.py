import streamlit as st
import json
import os
import yfinance as yf
import pandas as pd
import requests
import re

# ==========================================
# 0. 自動刷新套件安全載入檢查
# ==========================================
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

# ==========================================
# 1. 系統核心配置與 UI 切邊修復
# ==========================================
st.set_page_config(page_title="TradeBOT 策略完全體戰情室", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .block-container {
        padding-top: 3.5rem !important;
        padding-bottom: 1rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 100% !important;
    }
    .stApp { background-color: #121629; color: #FFFFFE; }
    div[data-testid="stSidebar"] { background-color: #161B33; }
    h1, h2, h3, h4 { color: #EEBBC3 !important; margin-top: 0rem !important; margin-bottom: 0.3rem !important; }
    .stExpander { border: 1px solid rgba(255, 215, 0, 0.3) !important; background-color: rgba(255, 255, 255, 0.02) !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 輕量化 JSON 大字典與存檔機制
# ==========================================
@st.cache_data(ttl=86400)
def load_local_stock_dict():
    json_path = "stock_dict.json"
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return {}

def get_clean_stock_name(stock_id):
    pure_code = stock_id.split('.')[0]
    local_dict = load_local_stock_dict()
    if pure_code in local_dict: return local_dict[pure_code]
    cache_key = f"name_cache_{pure_code}"
    if cache_key in st.session_state: return st.session_state[cache_key]
    try:
        ticker = yf.Ticker(stock_id)
        ch_name = ticker.info.get('shortName') or ticker.info.get('longName') or ticker.info.get('name')
        if ch_name:
            for suffix in ["Taiwan", "Stock", "Co.,Ltd.", "Co.", "Ltd."]:
                ch_name = ch_name.replace(suffix, "").strip()
            st.session_state[cache_key] = ch_name
            return ch_name
    except: pass
    return f"台股 {pure_code}"

# ==========================================
# 3. 記憶體初始化與 【URL 參數自動登入技術】
# ==========================================
DEFAULT_GROUP_DATA = {
    "custom_name": "", 
    "logic": "AND (嚴格：需同時符合所有啟用條件)",
    "spark_days": {"val": 5, "active": True},
    "price_ma": {"val": 20, "active": True},
    "volume_ma": {"val": 5, "active": True},
    "volume_min": {"val": 5, "active": False},
    "volume_burst": {"val": 2.5, "active": False}, 
    "volume_burst_days": {"val": 5, "active": True},
    "rsi": {"val": 75, "active": False},
    "min_volume": {"val": 500, "active": False},
    "sell_ma": {"val": 10, "active": False},
    "sell_trailing": {"val": 8.0, "active": False},
    "watch_list": []
}

if "user_cfg" not in st.session_state:
    st.session_state.user_cfg = {
        "tg_token": "", "tg_chat_id": "",
        "groups": {
            "群組一": json.loads(json.dumps(DEFAULT_GROUP_DATA)),
            "群組二": json.loads(json.dumps(DEFAULT_GROUP_DATA)),
            "群組三": json.loads(json.dumps(DEFAULT_GROUP_DATA))
        }
    }

# 【核心修復】透過網址列的 uid 參數，實現 100% 穩定的無密碼自動登入
if "uid" in st.query_params and not st.session_state.user_cfg["tg_token"]:
    uid = st.query_params["uid"]
    filename = f"userdata_{uid}.json"
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                st.session_state.user_cfg = json.load(f)
        except: pass

def save_user_config():
    chat_id = st.session_state.user_cfg.get("tg_chat_id")
    if chat_id:
        filename = f"userdata_{chat_id}.json"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(st.session_state.user_cfg, f, ensure_ascii=False)
        except: pass

for g_name, g_body in st.session_state.user_cfg["groups"].items():
    if "spark_days" not in g_body: g_body["spark_days"] = {"val": 5, "active": True}
    if "volume_burst_days" not in g_body: g_body["volume_burst_days"] = {"val": 5, "active": True}
    if "sell_ma" not in g_body: g_body["sell_ma"] = {"val": 10, "active": False}
    if "sell_trailing" not in g_body: g_body["sell_trailing"] = {"val": 8.0, "active": False}

if 'active_group' not in st.session_state: st.session_state.active_group = "群組一"
if 'skip_login' not in st.session_state: st.session_state.skip_login = False
if 'delete_confirm_target' not in st.session_state: st.session_state.delete_confirm_target = ""

user_cfg = st.session_state.user_cfg
active_group = st.session_state.active_group
grp_data = user_cfg["groups"][active_group]

def calculate_rsi(data, periods=14):
    close_delta = data['Close'].diff()
    up = close_delta.clip(lower=0)
    down = -1 * close_delta.clip(upper=0)
    ma_up = up.ewm(com=periods - 1, adjust=True, min_periods=periods).mean()
    ma_down = down.ewm(com=periods - 1, adjust=True, min_periods=periods).mean()
    return 100 - (100 / (1 + (ma_up / ma_down)))

def send_telegram_alert(token, chat_id, message):
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

# ==========================================
# 4. 漸進式登入頁面
# ==========================================
has_tg_credentials = bool(user_cfg["tg_token"] and user_cfg["tg_chat_id"])

if not has_tg_credentials and not st.session_state.skip_login:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("📈 策略工作站系統登入")
        st.write("請輸入您的 Telegram 通訊憑證。登入後將產生您的專屬網址，未來點擊網址即可自動登入。")
        temp_token = st.text_input("🤖 Telegram Bot Token", type="password")
        temp_chat_id = st.text_input("👤 Telegram Chat ID", type="password")
        
        input_error = False
        if temp_token or temp_chat_id:
            if re.search(r'[\u4e00-\u9fff]', temp_token) or re.search(r'[\u4e00-\u9fff]', temp_chat_id):
                st.error("⚠️ 憑證內含有中文字元，請重新檢查。")
                input_error = True
        
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("🔓 綁定並登入", type="primary", use_container_width=True) and temp_token and temp_chat_id and not input_error:
                # 將憑證寫入 Session 與存檔
                st.session_state.user_cfg["tg_token"] = temp_token
                st.session_state.user_cfg["tg_chat_id"] = temp_chat_id
                save_user_config()
                # 寫入專屬 URL 參數
                st.query_params["uid"] = temp_chat_id
                st.rerun()
        with c_btn2:
            if st.button("➡️ 略過 (僅看盤)", use_container_width=True):
                st.session_state.skip_login = True
                st.rerun()
        st.write("---")
        with st.expander("❓ 第一次使用？如何獲取 Telegram Token 與 ID？"):
            st.markdown(
"""<div style="background-color: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px;">
<p style="font-size: 16px; color: #EEBBC3; font-weight: bold; margin-bottom: 15px;">💡 只要 3 分鐘，建立您專屬的私密警報機器人：</p>
<div style="margin-bottom: 18px;">
<span style="color: #F8CA00; font-size: 18px; font-weight: bold;">步驟一：取得 Bot Token 🔑</span>
<div style="margin-left: 32px; margin-top: 6px; line-height: 1.6; color: #E0E0E0;">
1. 在 Telegram 搜尋列尋找 <code style="color:#F8CA00; background:rgba(0,0,0,0.3);">@BotFather</code> (帶有官方藍勾勾)。<br>
2. 點擊對話後，輸入 <code>/newbot</code> 建立新機器人。<br>
3. 幫您的機器人取個顯示名稱，以及使用者帳號 (必須以 <code>bot</code> 結尾)。<br>
4. 成功後，複製您的 <strong>Bot Token</strong> 到上方。
</div></div>
<div style="margin-bottom: 18px;">
<span style="color: #F8CA00; font-size: 18px; font-weight: bold;">步驟二：取得 Chat ID 👤</span>
<div style="margin-left: 32px; margin-top: 6px; line-height: 1.6; color: #E0E0E0;">
1. 在 Telegram 搜尋 <code style="color:#F8CA00; background:rgba(0,0,0,0.3);">@userinfobot</code>。<br>
2. 點擊 <code>Start</code>，取得 <code>Id</code> 後面的數字，即為 <strong>Chat ID</strong>。
</div></div>
<div style="margin-bottom: 5px;">
<span style="color: #F8CA00; font-size: 18px; font-weight: bold;">步驟三：啟動您的機器人 🚀</span>
<div style="margin-left: 32px; margin-top: 6px; line-height: 1.6; color: #E0E0E0;">
1. 在 Telegram 搜尋剛剛建立的機器人。<br>
2. 點擊 <code>Start</code> 即可完成連線！
</div></div></div>""", unsafe_allow_html=True)
    st.stop()

# ==========================================
# 5. 左側控制台 與 自動巡航啟動區
# ==========================================
st.sidebar.title("⚙️ 交易控制面板")

# 自動巡航模組 (強勢掛載)
if HAS_AUTOREFRESH:
    # interval=300000 為 5分鐘
    refresh_count = st_autorefresh(interval=300000, limit=None, key="strategy_autorefresh")
    st.sidebar.success(f"⏱️ 背景巡航啟動中 (已自動刷新 {refresh_count} 次)")
else:
    st.sidebar.error("⚠️ 缺少自動刷新套件 (請在 requirements.txt 加入 streamlit-autorefresh)")

if has_tg_credentials:
    st.sidebar.info(f"🟢 TG通訊：連線正常")
    if st.sidebar.button("🔒 登出 (清除個人憑證)", use_container_width=True):
        st.session_state.user_cfg["tg_token"], st.session_state.user_cfg["tg_chat_id"] = "", ""
        if "uid" in st.query_params:
            del st.query_params["uid"]
        st.session_state.skip_login = False
        st.rerun()
else:
    st.sidebar.warning("⚠️ TG通訊：未串接")
    if st.sidebar.button("🔐 重新串接 Telegram", use_container_width=True):
        st.session_state.skip_login = False
        st.rerun()

st.sidebar.write("---")
display_name = grp_data.get("custom_name") if grp_data.get("custom_name") else active_group
st.sidebar.subheader(f"🎯 參數調整 ({display_name})")
grp_data["logic"] = st.sidebar.selectbox("多重條件觸發規則", ["AND (嚴格：需同時符合)", "OR (寬鬆：符合任一即觸發)"], index=0 if "AND" in grp_data["logic"] else 1)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 視覺與顯示設定")
grp_data["spark_days"]["val"] = st.sidebar.slider("迷你紅綠量能 K 棒顯示天數", 3, 20, int(grp_data["spark_days"]["val"]), step=1, key="sld_spark")

def render_strategy_param(title, key_name, min_v, max_v, suffix="", step=1.0):
    c1, c2 = st.sidebar.columns([3, 1])
    with c1: grp_data[key_name]["val"] = st.slider(title, min_v, max_v, float(grp_data[key_name]["val"]), step=step, key=f"sld_{key_name}")
    with c2: grp_data[key_name]["active"] = st.toggle("啟用", value=grp_data[key_name]["active"], key=f"tg_{key_name}")
    st.sidebar.caption(f"數值: **{grp_data[key_name]['val']}{suffix}** | {'💡 已啟用' if grp_data[key_name]['active'] else '❌ 忽略'}")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🟢 買方進場與監控濾網")
render_strategy_param("價格突破均線", "price_ma", 5.0, 60.0, "天", step=1.0)
render_strategy_param("N日均量線(跌破均量)", "volume_ma", 3.0, 20.0, "天", step=1.0)
render_strategy_param("前N日窒息量(排除今天)", "volume_min", 3.0, 20.0, "天", step=1.0) 

st.sidebar.markdown("**🔥 爆量表態控制模組**")
c1, c2 = st.sidebar.columns([3, 1])
with c1:
    grp_data["volume_burst_days"]["val"] = st.slider("爆量對比基準天數", 5, 60, int(grp_data["volume_burst_days"]["val"]), step=1, key="sld_burst_days")
    grp_data["volume_burst"]["val"] = st.slider("當天爆量突破門檻", 1.5, 10.0, float(grp_data["volume_burst"]["val"]), step=0.5, key="sld_burst_mult")
with c2:
    st.write("")
    grp_data["volume_burst"]["active"] = st.toggle("啟用", value=grp_data["volume_burst"]["active"], key="tg_volume_burst")

render_strategy_param("RSI 熱度上限", "rsi", 40.0, 95.0, "波段", step=1.0)
render_strategy_param("5日最低均量門檻", "min_volume", 100.0, 5000.0, "張", step=100.0)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔴 賣方紀律與停損策略")
render_strategy_param("跌破短期生命線 (MA)", "sell_ma", 3.0, 20.0, "天", step=1.0)
render_strategy_param("近20日高點回檔 (Trailing)", "sell_trailing", 3.0, 20.0, "%", step=0.5)

st.sidebar.write("---")
st.sidebar.info("💡 系統已啟用雲端自動存檔，參數變更將綁定您的 TG 帳戶永久保存。")

# ==========================================
# 6. 右側主畫面與極速批次下載邏輯
# ==========================================
name1 = user_cfg["groups"]["群組一"].get("custom_name") or "群組一"
name2 = user_cfg["groups"]["群組二"].get("custom_name") or "群組二"
name3 = user_cfg["groups"]["群組三"].get("custom_name") or "群組三"

c_tab1, c_tab2, c_tab3 = st.columns(3)
if c_tab1.button(f"📂 【{name1}】", use_container_width=True, type="primary" if active_group == "群組一" else "secondary"):
    st.session_state.active_group, st.session_state.delete_confirm_target = "群組一", ""
    st.rerun()
if c_tab2.button(f"📂 【{name2}】", use_container_width=True, type="primary" if active_group == "群組二" else "secondary"):
    st.session_state.active_group, st.session_state.delete_confirm_target = "群組二", ""
    st.rerun()
if c_tab3.button(f"📂 【{name3}】", use_container_width=True, type="primary" if active_group == "群組三" else "secondary"):
    st.session_state.active_group, st.session_state.delete_confirm_target = "群組三", ""
    st.rerun()

st.write("---")
c_head, c_rename = st.columns([2, 1])
with c_head: st.header(f"📊 {display_name} - 即時快照")
with c_rename:
    new_name = st.text_input("✏️ 重新命名當前群組 (Enter存檔)", value=grp_data.get("custom_name", ""), placeholder="例如: 突破主攻艙")
    if new_name != grp_data.get("custom_name", ""):
        grp_data["custom_name"] = new_name
        st.rerun()

# 讓自動迴圈與按鈕共用刷新邏輯
with st.spinner("🚀 極速批次下載資料中，免疫 API 限流..."):
    summary_data = []
    triggered_stocks_for_tg = []
    watch_list = grp_data["watch_list"]
    
    if watch_list:
        try:
            tickers_str = " ".join(watch_list)
            batch_data = yf.download(tickers_str, period="1y", progress=False)
            
            for stock_id in watch_list:
                if len(watch_list) == 1:
                    df = batch_data.copy()
                else:
                    try:
                        df = pd.DataFrame({
                            'Open': batch_data['Open'][stock_id],
                            'High': batch_data['High'][stock_id],
                            'Low': batch_data['Low'][stock_id],
                            'Close': batch_data['Close'][stock_id],
                            'Volume': batch_data['Volume'][stock_id]
                        })
                    except KeyError: continue
                        
                df = df.dropna()
                if df.empty: continue
                
                ch_name = get_clean_stock_name(stock_id)
                latest = df.iloc[-1]
                prev_close = df.iloc[-2]['Close'] if len(df) > 1 else latest['Close']
                pct_change = ((latest['Close'] - prev_close) / prev_close) * 100
                
                ma_p_val = df['Close'].rolling(window=int(grp_data["price_ma"]["val"])).mean().iloc[-1]
                ma_v_val = df['Volume'].rolling(window=int(grp_data["volume_ma"]["val"])).mean().iloc[-1]
                burst_base_val = df['Volume'].rolling(window=int(grp_data["volume_burst_days"]["val"])).mean().iloc[-1]
                
                v_min_days = int(grp_data["volume_min"]["val"])
                history_df = df.iloc[:-1]
                vol_ndays_min = history_df['Volume'].tail(v_min_days).min() if len(history_df) >= v_min_days else 0
                
                df['RSI'] = calculate_rsi(df, 14)
                rsi_val = df['RSI'].iloc[-1]
                vol_5d_avg = df['Volume'].rolling(window=5).mean().iloc[-1]
                
                high_20d = df['High'].rolling(window=20).max().iloc[-1]
                ma_sell_val = df['Close'].rolling(window=int(grp_data["sell_ma"]["val"])).mean().iloc[-1]
                
                cond_p = (latest['Close'] > ma_p_val) if grp_data["price_ma"]["active"] else None
                cond_v_ma = (latest['Volume'] < ma_v_val) if grp_data["volume_ma"]["active"] else None
                cond_v_min = (latest['Volume'] <= vol_ndays_min) if grp_data["volume_min"]["active"] else None
                cond_v_burst = (latest['Volume'] > (burst_base_val * grp_data["volume_burst"]["val"])) if grp_data["volume_burst"]["active"] else None
                cond_rsi = (rsi_val < grp_data["rsi"]["val"]) if grp_data["rsi"]["active"] else None
                cond_minv = (vol_5d_avg > (grp_data["min_volume"]["val"] * 1000)) if grp_data["min_volume"]["active"] else None
                
                active_conditions = [c for c in [cond_p, cond_v_ma, cond_v_min, cond_v_burst, cond_rsi, cond_minv] if c is not None]
                if not active_conditions: is_triggered = False
                elif "AND" in grp_data["logic"]: is_triggered = all(active_conditions)
                else: is_triggered = any(active_conditions)
                
                cond_sell_ma = (latest['Close'] < ma_sell_val) if grp_data["sell_ma"]["active"] else False
                cond_sell_trail = (latest['Close'] < high_20d * (1 - grp_data["sell_trailing"]["val"]/100)) if grp_data["sell_trailing"]["active"] else False
                sell_warning = []
                if cond_sell_ma: sell_warning.append("🔴 破線")
                if cond_sell_trail: sell_warning.append("🔴 回檔")
                sell_status = "｜".join(sell_warning) if sell_warning else "✅ 安全"
                
                spark_days = int(grp_data["spark_days"]["val"])
                recent_df = df.tail(spark_days)
                spark_info = [{"volume": row['Volume'], "color": "#FF3B30" if row['Close'] >= row['Open'] else "#00E676"} for _, row in recent_df.iterrows()]
                
                summary_data.append({
                    "股票代碼": stock_id, "名稱(含ETF)": ch_name, "收盤價": f"${latest['Close']:.2f}",
                    "漲跌幅": f"{pct_change:+.2f}%",
                    "價MA": "✅" if cond_p == True else ("❌" if cond_p == False else "➖"),
                    "均量": "✅" if cond_v_ma == True else ("❌" if cond_v_ma == False else "➖"),
                    "窒息": "✅" if cond_v_min == True else ("❌" if cond_v_min == False else "➖"),
                    "爆量": "💥" if cond_v_burst == True else ("❌" if cond_v_burst == False else "➖"),
                    "綜合警報": "🔥 策略觸發" if is_triggered else "⚪ 靜止",
                    "出場警示": sell_status,
                    "sparkline_data": spark_info
                })
                
                if is_triggered:
                    detail_list = []
                    if grp_data["price_ma"]["active"]: detail_list.append(f"  ├ 價格突破均線：{'✅ 符合' if cond_p else '❌ 未突破'}")
                    if grp_data["volume_ma"]["active"]: detail_list.append(f"  ├ N日均量線萎縮：{'✅ 符合' if cond_v_ma else '❌ 偏高'}")
                    if grp_data["volume_min"]["active"]: detail_list.append(f"  ├ 前N日窒息量低：{'✅ 創低' if cond_v_min else '❌ 未創低'}")
                    if grp_data["volume_burst"]["active"]: detail_list.append(f"  ├ 當天爆量門檻：{'💥 爆量達標' if cond_v_burst else '❌ 未達標'}")
                    if grp_data["rsi"]["active"]: detail_list.append(f"  ├ RSI熱度上限：{'✅ 安全' if cond_rsi else '⚠️ 過熱'}")
                    if grp_data["min_volume"]["active"]: detail_list.append(f"  ├ 最低均量門檻：{'✅ 達標' if cond_minv else '❌ 未達標'}")
                    triggered_stocks_for_tg.append((stock_id.split('.')[0], ch_name, latest['Close'], rsi_val, detail_list))
                    
        except Exception as e:
            st.error(f"⚠️ 批量下載數據發生異常: {e}，請確認股票代碼是否正確。")
            
    if summary_data:
        show_days = int(grp_data["spark_days"]["val"])
        # 【核心修復】調整表格寬度與加入自適應 flexbox 排版，徹底消滅右側空白
        html_table = f"""<table style="width:100%; text-align:left; color:#FFFFFE; border-collapse: collapse; font-family: sans-serif; font-size:14px;">
<tr style="border-bottom: 2px solid rgba(255,215,0,0.4); background-color: #161B33; font-weight: bold;">
<th style="padding: 12px 8px;">代碼</th>
<th style="padding: 12px 8px;">名稱</th>
<th style="padding: 12px 8px;">現價</th>
<th style="padding: 12px 8px;">漲跌</th>
<th style="padding: 12px 8px; width: 140px;">近 {show_days} 日量能K棒</th>
<th style="padding: 12px 8px;">價MA/均量/窒息/爆量</th>
<th style="padding: 12px 8px;">出場防護警示</th>
<th style="padding: 12px 8px;">買進策略狀態</th>
</tr>"""
        for res in summary_data:
            spark_data = res["sparkline_data"]
            # 使用 flex: 1 讓 K 棒均勻填滿 140px 的欄位寬度
            sparkline_html = '<div style="display: flex; align-items: flex-end; gap: 2px; height: 32px; width: 100%; max-width: 130px; padding-top: 2px;">'
            if spark_data:
                max_vol = max([d["volume"] for d in spark_data]) or 1
                for day in spark_data:
                    h_pct = max(12, int((day["volume"] / max_vol) * 100))
                    sparkline_html += f'<div style="flex: 1; height: {h_pct}%; background-color: {day["color"]}; border-radius: 1px;" title="量: {day["volume"]:,}"></div>'
            else: sparkline_html += '<span style="color:#666; font-size:11px;">無數據</span>'
            sparkline_html += '</div>'
            
            c_color = "#FF3B30" if "+" in res["漲跌幅"] else ("#00E676" if "-" in res["漲跌幅"] else "#FFFFFE")
            s_style = "color: #F8CA00; font-weight: bold;" if "🔥" in res["綜合警報"] else "color: #A0A5C1;"
            w_style = "color: #FF3B30; font-weight: bold;" if "🔴" in res["出場警示"] else "color: #A0A5C1;"
            q_status = f"{res['價MA']}｜{res['均量']}｜{res['窒息']}｜{res['爆量']}"
            
            html_table += f"""<tr style="border-bottom: 1px solid rgba(255,255,255,0.08); background-color: rgba(255,255,255,0.01);">
<td style="padding: 10px 8px; font-weight: 600;">{res["股票代碼"]}</td>
<td style="padding: 10px 8px;">{res["名稱(含ETF)"]}</td>
<td style="padding: 10px 8px; font-weight: 600;">{res["收盤價"]}</td>
<td style="padding: 10px 8px; color: {c_color}; font-weight: bold;">{res["漲跌幅"]}</td>
<td style="padding: 10px 8px; vertical-align: middle;">{sparkline_html}</td>
<td style="padding: 10px 8px; font-size:12px; color:#A0A5C1;">{q_status}</td>
<td style="padding: 10px 8px; {w_style}">{res["出場警示"]}</td>
<td style="padding: 10px 8px; {s_style}">{res["綜合警報"]}</td>
</tr>"""
        html_table += "</table>"
        st.markdown(html_table, unsafe_allow_html=True)
        
        if triggered_stocks_for_tg and has_tg_credentials:
            for sid, name, price, rsi, details in triggered_stocks_for_tg:
                detail_str = "\n".join(details)
                tg_msg = f"🔔 *【雲端網頁觸發通報 - {display_name}】*\n━━━━━━━━━━━━━━━━\n📈 標的：`[{sid}] {name}`\n💰 當前收盤：`{price:.2f} 元`\n🔥 核心RSI值：`{rsi:.1f}`\n\n🛠️ 觸發篩選條件明細：\n{detail_str}\n━━━━━━━━━━━━━━━━"
                send_telegram_alert(user_cfg["tg_token"], user_cfg["tg_chat_id"], tg_msg)
    else: st.info("清單目前為空。")

# ==========================================
# 7. 標的管理模組
# ==========================================
st.write("---")
st.subheader(f"📋 {display_name} 標的管理")
c_add1, c_add2 = st.columns([3, 1])
with c_add1: 
    raw_stocks = st.text_input("輸入代碼 (支援批量，可用逗號或空格分隔)", placeholder="例如: 2330, 2317 0050", key="add_stock").strip()
with c_add2:
    st.write("") 
    if st.button("➕ 批次新增標的", use_container_width=True) and raw_stocks:
        new_tickers = [s.strip() for s in re.split(r'[\s,，]+', raw_stocks) if s.strip()]
        has_error = False
        for tk in new_tickers:
            if re.search(r'[\u4e00-\u9fff]', tk):
                has_error = True
            else:
                fmt_stock = f"{tk}.TW"
                if fmt_stock not in grp_data["watch_list"]:
                    grp_data["watch_list"].append(fmt_stock)
        
        if has_error:
            st.error("⚠️ 已過濾掉帶有中文的輸入。支援純代碼批次新增。")
        st.session_state.delete_confirm_target = ""
        st.rerun()

st.write("目前監控中：")
if grp_data["watch_list"]:
    cols = st.columns(min(len(grp_data["watch_list"]), 6))
    for idx, sid in enumerate(grp_data["watch_list"]):
        with cols[idx % 6]:
            is_warn = (st.session_state.delete_confirm_target == sid)
            lbl = f"⚠️ 確定刪除 {sid.split('.')[0]}？" if is_warn else f"{sid} ❌"
            if st.button(lbl, key=f"del_{sid}", use_container_width=True):
                if is_warn:
                    grp_data["watch_list"].remove(sid)
                    st.session_state.delete_confirm_target = ""
                    st.rerun()
                else:
                    st.session_state.delete_confirm_target = sid
                    st.rerun()

# 每次網頁互動時執行雲端存檔
if has_tg_credentials:
    save_user_config()
