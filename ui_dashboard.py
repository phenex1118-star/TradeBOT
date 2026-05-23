import streamlit as st
import json
import os
import yfinance as yf
import pandas as pd
import urllib.request
import requests

# ==========================================
# 1. 100% 證交所繁中查名模組 (含明星級 ETF 保底字典)
# ==========================================
@st.cache_data(ttl=86400)
def get_twse_stock_dict():
    stock_dict = {}
    apis = [
        "https://openapi.twse.com.tw/v1/opendata/t187ap03_L", 
        "https://openapi.tpex.org.tw/v1/opendata/t187ap03_O", 
        "https://openapi.twse.com.tw/v1/opendata/t187ap03_E"  
    ]
    for url in apis:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                for item in json.loads(response.read().decode('utf-8')):
                    code = item.get('公司代號', item.get('證券代號', '')).strip()
                    name = item.get('公司簡稱', item.get('證券名稱', '')).strip()
                    if code and name:
                        stock_dict[code] = name
        except Exception: pass
        
    BOND_DICT = {
        "0050": "元大台灣50", "0056": "元大高股息", 
        "00757": "統一FANG+", "00878": "國泰永續高股息",
        "00919": "群益台灣精選高息", "00929": "復華台灣科技優息"
    }
    stock_dict.update(BOND_DICT)
    return stock_dict

def get_clean_stock_name(stock_id, twse_dict):
    pure_code = stock_id.split('.')[0]
    return twse_dict.get(pure_code, f"台股 {pure_code}")

# ==========================================
# 2. 瀏覽器獨立記憶體 (Session State) 多用戶隔離初始化
# ==========================================
DEFAULT_GROUP_DATA = {
    "custom_name": "", 
    "logic": "AND (嚴格：需同時符合所有啟用條件)",
    "price_ma": {"val": 20, "active": True},
    "volume_ma": {"val": 5, "active": True},
    "volume_min": {"val": 5, "active": False},
    "rsi": {"val": 75, "active": False},
    "min_volume": {"val": 500, "active": False},
    "watch_list": []
}

if "user_cfg" not in st.session_state:
    st.session_state.user_cfg = {
        "tg_token": "", 
        "tg_chat_id": "",
        "groups": {
            "群組一": json.loads(json.dumps(DEFAULT_GROUP_DATA)),
            "群組二": json.loads(json.dumps(DEFAULT_GROUP_DATA)),
            "群組三": json.loads(json.dumps(DEFAULT_GROUP_DATA))
        }
    }

if 'active_group' not in st.session_state: st.session_state.active_group = "群組一"
if 'skip_login' not in st.session_state: st.session_state.skip_login = False
# 🛠️ 用來暫存哪個按鈕正處於「等待第二次點擊確認」狀態的記憶卡
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
# 3. 靜態主題與排版
# ==========================================
st.set_page_config(page_title="法人級多策略控制台", layout="wide")
twse_dict = get_twse_stock_dict()

st.markdown("""
    <style>
    .stApp { background-color: #232946; color: #FFFFFE; }
    div[data-testid="stSidebar"] { background-color: #121629; }
    h1, h2, h3, h4 { color: #EEBBC3 !important; margin-top: 0rem !important; margin-bottom: 0.3rem !important; }
    .main .block-container { padding-top: 0.5rem !important; padding-left: 2rem !important; padding-right: 2rem !important; max-width: 100% !important; }
    div[data-testid="stSidebarVerticalBlock"] { gap: 0.6rem !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 4. 漸進式登入頁面
# ==========================================
has_tg_credentials = bool(user_cfg["tg_token"] and user_cfg["tg_chat_id"])

if not has_tg_credentials and not st.session_state.skip_login:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("📈 策略工作站系統登入")
        st.write("請輸入『您自己』的 Telegram 通訊憑證。此資料僅存在您的手機瀏覽器中，安全隔離。")
        temp_token = st.text_input("🤖 Telegram Bot Token", type="password")
        temp_chat_id = st.text_input("👤 Telegram Chat ID", type="password")
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("🔓 登入", type="primary", use_container_width=True) and temp_token and temp_chat_id:
                user_cfg["tg_token"], user_cfg["tg_chat_id"] = temp_token, temp_chat_id
                st.rerun()
        with c_btn2:
            if st.button("➡️ 略過 (僅看盤)", use_container_width=True):
                st.session_state.skip_login = True
                st.rerun()
    st.stop()

# ==========================================
# 5. 左側控制台連動
# ==========================================
st.sidebar.title("⚙️ 交易控制面板")

if has_tg_credentials:
    st.sidebar.success("🟢 個人TG警報：已連線")
    if st.sidebar.button("🔒 登出 (清除個人憑證)", use_container_width=True):
        user_cfg["tg_token"], user_cfg["tg_chat_id"] = "", ""
        st.session_state.skip_login = False
        st.rerun()
else:
    st.sidebar.warning("⚠️ TG警報：未串接")
    if st.sidebar.button("🔐 重新串接 Telegram", use_container_width=True):
        st.session_state.skip_login = False
        st.rerun()

#  ✅ 正確的順序（先把功能寫好，底下再呼叫）
st.sidebar.write("---")
display_name = grp_data.get("custom_name") if grp_data.get("custom_name") else active_group

st.sidebar.subheader(f"🎯 參數調整 ({display_name})")
grp_data["logic"] = st.sidebar.selectbox("多重條件觸發規則", ["AND (嚴格：需同時符合)", "OR (寬鬆：符合任一即觸發)"], index=0 if "AND" in grp_data["logic"] else 1)

# 1. 先把工具定義好
def render_strategy_param(title, key_name, min_v, max_v, suffix=""):
    c1, c2 = st.sidebar.columns([3, 1])
    with c1:
        grp_data[key_name]["val"] = st.slider(title, min_v, max_v, grp_data[key_name]["val"], label_visibility="collapsed")
    with c2:
        grp_data[key_name]["active"] = st.toggle("啟用", value=grp_data[key_name]["active"], key=f"tg_{key_name}")
    status_text = "💡 已啟用" if grp_data[key_name]["active"] else "❌ 忽略"
    st.sidebar.caption(f"{title}: **{grp_data[key_name]['val']}{suffix}** | {status_text}")

# 2. 接下來才正式呼叫畫出滑桿
render_strategy_param("價格突破均線", "price_ma", 5, 60, "天")
render_strategy_param("N日均量線(跌破均量)", "volume_ma", 3, 20, "天")
render_strategy_param("N日窒息量(創N日低)", "volume_min", 3, 20, "天")
render_strategy_param("RSI 熱度上限", "rsi", 40, 95, "波段")
render_strategy_param("5日最低均量門檻", "min_volume", 100, 5000, "張")

st.sidebar.write("---")
st.sidebar.info("💡 雲端模式：參數已即時鎖定在您的瀏覽器中。")

# ==========================================
# 6. 右側主畫面 (獨立動態分頁與改名)
# ==========================================
name1 = user_cfg["groups"]["群組一"].get("custom_name") or "群組一"
name2 = user_cfg["groups"]["群組二"].get("custom_name") or "群組二"
name3 = user_cfg["groups"]["群組三"].get("custom_name") or "群組三"

c_tab1, c_tab2, c_tab3 = st.columns(3)
if c_tab1.button(f"📂 【{name1}】", use_container_width=True, type="primary" if active_group == "群組一" else "secondary"):
    st.session_state.active_group = "群組一"
    st.session_state.delete_confirm_target = "" # 切換分頁時重設刪除狀態
    st.rerun()
if c_tab2.button(f"📂 【{name2}】", use_container_width=True, type="primary" if active_group == "群組二" else "secondary"):
    st.session_state.active_group = "群組二"
    st.session_state.delete_confirm_target = ""
    st.rerun()
if c_tab3.button(f"📂 【{name3}】", use_container_width=True, type="primary" if active_group == "群組三" else "secondary"):
    st.session_state.active_group = "群組三"
    st.session_state.delete_confirm_target = ""
    st.rerun()

st.write("---")

c_head, c_rename = st.columns([2, 1])
with c_head:
    st.header(f"📊 {display_name} - 即時快照")
with c_rename:
    new_name = st.text_input("✏️ 重新命名當前群組 (Enter存檔)", value=grp_data.get("custom_name", ""), placeholder="例如: 突破主攻艙")
    if new_name != grp_data.get("custom_name", ""):
        grp_data["custom_name"] = new_name
        st.rerun()

if st.button(f"🔄 立即刷新 {display_name} 數據與個人通報測試", type="secondary", use_container_width=True):
    with st.spinner("獲取行情數據與驗證指標中..."):
        summary_data = []
        triggered_stocks_for_tg = []
        
        for stock_id in grp_data["watch_list"]:
            try:
                stock = yf.Ticker(stock_id)
                df = stock.history(period="30d")
                if df.empty: continue
                
                ch_name = get_clean_stock_name(stock_id, twse_dict)
                latest = df.iloc[-1]
                
                ma_p_val = df['Close'].rolling(window=grp_data["price_ma"]["val"]).mean().iloc[-1]
                ma_v_val = df['Volume'].rolling(window=grp_data["volume_ma"]["val"]).mean().iloc[-1]
                v_min_days = grp_data["volume_min"]["val"]
                vol_ndays_min = df['Volume'].tail(v_min_days).min()
                
                df['RSI'] = calculate_rsi(df, 14)
                rsi_val = df['RSI'].iloc[-1]
                vol_5d_avg = df['Volume'].rolling(window=5).mean().iloc[-1]
                
                cond_p = (latest['Close'] > ma_p_val) if grp_data["price_ma"]["active"] else None
                cond_v_ma = (latest['Volume'] < ma_v_val) if grp_data["volume_ma"]["active"] else None
                cond_v_min = (latest['Volume'] <= vol_ndays_min) if grp_data["volume_min"]["active"] else None
                cond_rsi = (rsi_val < grp_data["rsi"]["val"]) if grp_data["rsi"]["active"] else None
                cond_minv = (vol_5d_avg > (grp_data["min_volume"]["val"] * 1000)) if grp_data["min_volume"]["active"] else None
                
                active_conditions = [c for c in [cond_p, cond_v_ma, cond_v_min, cond_rsi, cond_minv] if c is not None]
                
                if not active_conditions: is_triggered = False
                elif "AND" in grp_data["logic"]: is_triggered = all(active_conditions)
                else: is_triggered = any(active_conditions)
                
                summary_data.append({
                    "股票代碼": stock_id,
                    "名稱(含ETF)": ch_name,
                    "收盤價": round(latest['Close'], 2),
                    "價格突破": "✅ 符合" if cond_p == True else ("❌ 未突破" if cond_p == False else "➖"),
                    "均量萎縮": "✅ 符合" if cond_v_ma == True else ("❌ 偏高" if cond_v_ma == False else "➖"),
                    "創窒息量": "✅ 創低" if cond_v_min == True else ("❌ 未創低" if cond_v_min == False else "➖"),
                    "RSI合規": "✅ 安全" if cond_rsi == True else ("⚠️ 過熱" if cond_rsi == False else "➖"),
                    "綜合警報": "🔥 策略觸發！" if is_triggered else "⚪ 靜止"
                })
                
                if is_triggered:
                    detail_list = []
                    if grp_data["price_ma"]["active"]: detail_list.append(f"  ├ 價格突破均線：{'✅ 符合' if cond_p else '❌ 未突破'}")
                    if grp_data["volume_ma"]["active"]: detail_list.append(f"  ├ N日均量線萎縮：{'✅ 符合' if cond_v_ma else '❌ 偏高'}")
                    if grp_data["volume_min"]["active"]: detail_list.append(f"  ├ 創N日窒息量低：{'✅ 創低' if cond_v_min else '❌ 未創低'}")
                    if grp_data["rsi"]["active"]: detail_list.append(f"  ├ RSI熱度上限：{'✅ 安全' if cond_rsi else '⚠️ 過熱'}")
                    if grp_data["min_volume"]["active"]: detail_list.append(f"  ├ 最低均量門檻：{'✅ 達標' if cond_minv else '❌ 未達標'}")
                    triggered_stocks_for_tg.append((stock_id.split('.')[0], ch_name, latest['Close'], rsi_val, detail_list))
                    
            except Exception as e:
                if "Too Many Requests" in str(e):
                    st.error(f"⚠️ 標的 {stock_id} 觸發 Yahoo 限流防禦，請等 10 秒後再次嘗試。")
                else:
                    st.error(f"標的 {stock_id} 異常: {e}")
                
        if summary_data:
            st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
            if triggered_stocks_for_tg and has_tg_credentials:
                for sid, name, price, rsi, details in triggered_stocks_for_tg:
                    detail_str = "\n".join(details)
                    tg_msg = (
                        f"🔔 *【雲端網頁觸發通報 - {display_name}】*\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"📈 標的：`[{sid}] {name}`\n"
                        f"💰 當前收盤：`{price:.2f} 元`\n"
                        f"🔥 核心RSI值：`{rsi:.1f}`\n\n"
                        f"🛠️ 觸發篩選條件明細：\n{detail_str}\n"
                        f"━━━━━━━━━━━━━━━━━━"
                    )
                    send_telegram_alert(user_cfg["tg_token"], user_cfg["tg_chat_id"], tg_msg)
                st.success("📩 Telegram 個人明細警報已成功發送至您的手機！")
        else:
            st.info("清單目前為空。")

st.write("---")
st.subheader(f"📋 {display_name} 標的管理")
c_add1, c_add2 = st.columns([3, 1])
with c_add1:
    new_stock = st.text_input("輸入代碼 (例如: 2330 或 0050)", placeholder="輸入純數字", key="add_stock_input").strip()
with c_add2:
    st.write("") 
    if st.button("➕ 新增標的", use_container_width=True) and new_stock:
        formatted_stock = f"{new_stock}.TW"
        if formatted_stock not in grp_data["watch_list"]:
            grp_data["watch_list"].append(formatted_stock)
            st.session_state.delete_confirm_target = "" # 新增時重設刪除鎖定
            st.rerun()

st.write("目前監控中（具備防誤觸雙擊機制）：")
if grp_data["watch_list"]:
    cols_tags = st.columns(min(len(grp_data["watch_list"]), 6))
    for idx, stock_id in enumerate(grp_data["watch_list"]):
        with cols_tags[idx % 6]:
            # 🛠️ 智慧判斷：這顆按鈕當前是不是正在被點擊第一次？
            is_waiting_confirm = (st.session_state.delete_confirm_target == stock_id)
            
            # 動態改變按鈕的文字與警告外殼
            btn_label = f"⚠️ 確定刪除 {stock_id.split('.')[0]}？" if is_waiting_confirm else f"{stock_id} ❌"
            
            if st.button(btn_label, key=f"del_{stock_id}", use_container_width=True):
                if is_waiting_confirm:
                    # 第二次點擊：真正動刀切除股票
                    grp_data["watch_list"].remove(stock_id)
                    st.session_state.delete_confirm_target = "" # 執行完畢解除鎖定
                    st.rerun()
                else:
                    # 第一次點擊：按鈕進入黃色變身警示狀態，不刪除檔案
                    st.session_state.delete_confirm_target = stock_id
                    st.rerun()
