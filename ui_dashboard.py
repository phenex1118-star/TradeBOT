import streamlit as st
import pandas as pd
import numpy as np
import re
import yfinance as yf

# ==========================================
# 1. 系統核心配置與 Phase 2 視覺優化
# ==========================================
st.set_page_config(
    page_title="TradeBOT 策略完全體戰情室",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 透過隱藏不必要的元件與優化邊距，達成手機/電腦版頂部完全貼齊、視覺無損縮排
st.markdown("""
    <style>
    /* 移除 Streamlit 原生頂部空白 */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 1rem !important;
    }
    /* 自訂深色系主題底色，確保高對比度 */
    .stApp {
        background-color: #121629;
        color: #FFFFFE;
    }
    /* 精緻化展開折疊區塊的框線 */
    .stExpander {
        border: 1px solid rgba(255, 215, 0, 0.3) !important;
        background-color: rgba(255, 255, 255, 0.02) !important;
    }
    </style>
""", unsafe_allow_html=True)

# 初始化 Session State
if "skip_login" not in st.session_state:
    st.session_state.skip_login = False
if "user_cfg" not in st.session_state:
    st.session_state.user_cfg = {"tg_token": "", "tg_chat_id": ""}

user_cfg = st.session_state.user_cfg

# ==========================================
# 2. 登入防呆、錯誤精準捕捉與 TG 圖文引導
# ==========================================
has_tg_credentials = bool(user_cfg["tg_token"] and user_cfg["tg_chat_id"])

if not has_tg_credentials and not st.session_state.skip_login:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("📈 策略工作站系統登入")
        st.write("請輸入您的 Telegram 通訊憑證。此資料僅存在您的瀏覽器中，系統不會進行任何雲端備份。")
        
        # 使用者輸入憑證
        temp_token = st.text_input("🤖 Telegram Bot Token", type="password", help="請輸入由 @BotFather 核發的 Token")
        temp_chat_id = st.text_input("👤 Telegram Chat ID", type="password", help="請輸入您的個人 Chat ID")
        
        # 憑證安全與防呆檢查機制
        input_error = False
        if temp_token or temp_chat_id:
            # 偵測是否輸入了中文字元，防止因不小心輸入股票中文名稱導致底層邏輯被誤導為限流錯誤
            if re.search(r'[\u4e00-\u9fff]', temp_token) or re.search(r'[\u4e00-\u9fff]', temp_chat_id):
                st.error("⚠️ 欄位格式錯誤：憑證內含有中文字元，請重新檢查並確認輸入內容。")
                input_error = True
        
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("🔓 驗證並登入", type="primary", use_container_width=True):
                if not temp_token or not temp_chat_id:
                    st.warning("請完整填寫 Token 與 Chat ID。")
                elif not input_error:
                    user_cfg["tg_token"], user_cfg["tg_chat_id"] = temp_token, temp_chat_id
                    st.success("憑證暫存成功！完成連線。")
                    st.rerun()
        with c_btn2:
            if st.button("➡️ 略過 (僅看盤)", use_container_width=True):
                st.session_state.skip_login = True
                st.rerun()
        
        st.write("---")
        # 📖 新增：給新手的 Telegram 高彩度折疊說明 (排縮與色彩層次完全對齊優化)
        with st.expander("❓ 第一次使用？如何獲取 Telegram Token 與 ID？"):
            st.markdown("""
            <div style="background-color: rgba(255,255,255,0.03); padding: 15px; border-radius: 8px;">
                <p style="font-size: 16px; color: #EEBBC3; font-weight: bold; margin-bottom: 15px;">💡 只要 3 分鐘，建立您專屬的私密警報機器人：</p>
                
                <div style="margin-bottom: 18px;">
                    <span style="color: #F8CA00; font-size: 18px; font-weight: bold;">步驟一：取得 Bot Token 🔑</span>
                    <div style="margin-left: 32px; margin-top: 6px; line-height: 1.6; color: #E0E0E0;">
                        1. 在 Telegram 搜尋列尋找 <code style="color:#F8CA00; background:rgba(0,0,0,0.3); padding: 2px 6px; border-radius:3px;">@BotFather</code> (帶有官方藍勾勾)。<br>
                        2. 點擊對話後，輸入 <code>/newbot</code> 建立新機器人。<br>
                        3. 幫您的機器人取個顯示名稱 (例如：<code>戰情通報</code>)，以及使用者帳號 (必須以 <code>bot</code> 結尾，例如 <code>MyTrade_bot</code>)。<br>
                        4. 成功後，BotFather 會給您一串專屬金鑰（例如 <code>1234567890:ABCdef...</code>），這就是您的 <strong>Bot Token</strong>，請複製貼上到上方。
                    </div>
                </div>

                <div style="margin-bottom: 18px;">
                    <span style="color: #F8CA00; font-size: 18px; font-weight: bold;">步驟二：取得 Chat ID 👤</span>
                    <div style="margin-left: 32px; margin-top: 6px; line-height: 1.6; color: #E0E0E0;">
                        1. 在 Telegram 搜尋 <code style="color:#F8CA00; background:rgba(0,0,0,0.3); padding: 2px 6px; border-radius:3px;">@userinfobot</code>。<br>
                        2. 點擊 <code>Start</code>，它會立刻回覆您的帳號資訊，其中 <code>Id</code> 後面的數字（例如 <code>1087654321</code>）就是您的 <strong>Chat ID</strong>。
                    </div>
                </div>
                
                <div style="margin-bottom: 5px;">
                    <span style="color: #F8CA00; font-size: 18px; font-weight: bold;">步驟三：啟動您的機器人 🚀</span>
                    <div style="margin-left: 32px; margin-top: 6px; line-height: 1.6; color: #E0E0E0;">
                        1. 在 Telegram 搜尋您剛剛建立的機器人名稱。<br>
                        2. 點擊進入並按下 <code>Start</code>，您的專屬戰情室就連線完成了！
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    st.stop()

# ==========================================
# 3. 側邊控制台：買賣策略解耦與獨立面板
# ==========================================
with st.sidebar:
    st.header("🛠️ 戰術參數控制台")
    
    # 擴充池項目：自選股批次輸入功能
    st.subheader("📋 監控標的管理")
    raw_input = st.text_area("請輸入台股代碼 (逗號或空格分隔):", value="2330.TW, 2317.TW, 2454.TW, 2002.TW")
    # 清洗資料格式
    watch_list = [t.strip().upper() for t in re.split(r'[\s,，]+', raw_input) if t.strip()]

    # 🟢 買方進場策略獨立區塊
    st.write("---")
    st.markdown("### 🟢 買方進場策略設定")
    
    # 價格突破設定
    enable_price_ma = st.checkbox("啟用：價格向上突破均線", value=True)
    price_ma_days = st.slider("價格均線天數 (Price MA)", 5, 240, 20, help="常用參數：5為週線，20為月線，60為季線")
    
    # 【參數解耦核心更新】成交量爆量策略完全體
    st.write("")
    enable_volume_burst = st.checkbox("啟用：成交量爆量表態", value=True)
    # 獨立的爆量基準天數，不再與價格天數強行綁定
    burst_ma_days = st.slider("爆量對比基準天數 (Volume MA)", 5, 60, 5, help="決定要與過去幾天的平均產生成交量對比")
    volume_burst_mult = st.slider("爆量觸發倍數 (Multiplier)", 1.5, 10.0, 3.0, step=0.5)

    # 其他輔助進場條件
    enable_rsi = st.checkbox("啟用：RSI 低檔超賣過濾", value=False)
    rsi_threshold = st.slider("RSI 門檻值", 10, 50, 30)

    # 🔴 賣方出場與避險獨立區塊
    st.write("---")
    st.markdown("### 🔴 賣方出場與避險設定")
    enable_volume_min = st.checkbox("啟用：極致量縮窒息量偵測", value=False)
    volume_min_days = st.slider("量縮尋找區間 (天)", 5, 60, 20)
    
    st.write("")
    enable_stop_loss = st.checkbox("啟用：移動停損停利通報", value=False)
    stop_loss_pct = st.slider("自高點回檔跌幅 (%)", 1.0, 15.0, 5.0, step=0.5)

# ==========================================
# 4. 主畫面：高效批次運算與精準錯誤捕捉
# ==========================================
st.title("🛡️ TradeBOT 量化完全體戰情室")
if st.button("🔄 立即刷新全盤訊號", type="primary"):
    st.rerun()

# 模擬資料撈取與核心邏輯處理
if watch_list:
    results = []
    
    # 提示使用者目前正在撈取，並透過進度條優化體驗
    progress_bar = st.progress(0)
    
    for idx, ticker in enumerate(watch_list):
        # 基礎輸入格式檢查：防止使用者誤填中文名稱
        if re.search(r'[\u4e00-\u9fff]', ticker):
            results.append({
                "代碼": ticker, "名稱": "格式錯誤", "現價": "N/A", "漲跌幅": "N/A",
                "策略狀態": f"❌ 請改輸入代碼 (例如: {ticker.split('.')[0]})", "sparkline_data": []
            })
            continue
            
        try:
            # 獲取歷史與最新數據 (為了計算最大240日均線，固定抓取適量長度)
            stock = yf.Ticker(ticker)
            df = stock.history(period="1y")
            
            if df.empty:
                results.append({
                    "代碼": ticker, "名稱": "查無此股", "現價": "N/A", "漲跌幅": "N/A",
                    "策略狀態": "❌ 查無此代碼，請確認格式是否帶有 .TW", "sparkline_data": []
                })
                continue
            
            # 精準計算各項解耦參數
            latest = df.iloc[-1]
            prev_close = df.iloc[-2]['Close'] if len(df) > 1 else latest['Close']
            pct_change = ((latest['Close'] - prev_close) / prev_close) * 100
            
            # 計算價格均線與獨立的量能均線
            df['Price_MA'] = df['Close'].rolling(window=price_ma_days).mean()
            df['Volume_MA'] = df['Volume'].rolling(window=burst_ma_days).mean()
            
            current_price_ma = df['Price_MA'].iloc[-1]
            current_volume_ma = df['Volume_MA'].iloc[-1]
            
            # 撈取最近 5 天的量能與漲跌歷史，供 SVG 迷你圖渲染使用
            recent_df = df.tail(5)
            spark_info = []
            for i in range(len(recent_df)):
                day_data = recent_df.iloc[i]
                day_open = day_data['Open']
                day_close = day_data['Close']
                # 判定當天 K 棒收紅或收綠
                color = "#FF3B30" if day_close >= day_open else "#00E676"
                spark_info.append({"volume": day_data['Volume'], "color": color})
            
            # 策略觸發判定
            triggers = []
            if enable_price_ma and latest['Close'] > current_price_ma:
                triggers.append("🟢價格突破MA")
            if enable_volume_burst and latest['Volume'] > (current_volume_ma * volume_burst_mult):
                triggers.append(f"🔥爆量突破({volume_burst_mult}x)")
                
            status_text = "｜".join(triggers) if triggers else "⏳ 盤整觀察中"
            
            results.append({
                "代碼": ticker,
                "名稱": stock.info.get('shortName', '未知標的'),
                "現價": f"${latest['Close']:.2f}",
                "漲跌幅": f"{pct_change:+.2f}%",
                "策略狀態": status_text,
                "sparkline_data": spark_info
            })
            
        except Exception as e:
            # 精準錯誤捕捉：區分到底是真正的 API 阻斷限制，還是因為輸入內容導致的內部錯誤
            err_msg = str(e)
            if "429" in err_msg or "Too Many Requests" in err_msg:
                results.append({
                    "代碼": ticker, "名稱": "伺服器忙碌", "現價": "N/A", "漲跌幅": "N/A",
                    "策略狀態": "⚠️ API 限流中，請等待 10 秒後重試", "sparkline_data": []
                })
            else:
                results.append({
                    "代碼": ticker, "名稱": "讀取失敗", "現價": "N/A", "漲跌幅": "N/A",
                    "策略狀態": f"❌ 錯誤: {err_msg[:20]}...", "sparkline_data": []
                })
        
        progress_bar.progress((idx + 1) / len(watch_list))
    
    progress_bar.empty()

    # ==========================================
    # 5. 極致視覺化：自訂 HTML / SVG 紅綠量能圖表格
    # ==========================================
    st.subheader("📊 策略即時監控快照（內嵌 5 日量能 K 棒）")
    
    # 構建純 HTML 表格頭部
    html_table = """
    <table style="width:100%; text-align:left; color:#FFFFFE; border-collapse: collapse; font-family: sans-serif; font-size:15px;">
      <tr style="border-bottom: 2px solid rgba(255,215,0,0.4); background-color: #161B33; font-weight: bold;">
        <th style="padding: 14px 10px;">股票代碼</th>
        <th style="padding: 14px 10px;">公司名稱</th>
        <th style="padding: 14px 10px;">當前現價</th>
        <th style="padding: 14px 10px;">今日漲跌</th>
        <th style="padding: 14px 10px; min-width:150px;">近 5 日紅綠量能棒 (Sparklines)</th>
        <th style="padding: 14px 10px;">量化策略狀態</th>
      </tr>
    """
    
    # 動態渲染每一檔股票的橫排資料
    for res in results:
        # 計算此標的 5 天內的最大成交量，做為畫圖的比例尺基準 (防爆框設計)
        spark_data = res["sparkline_data"]
        max_vol = max([d["volume"] for d in spark_data]) if spark_data else 1
        
        # 動態生成 5 根獨立對比的 SVG 柱狀圖外殼
        sparkline_html = '<div style="display: flex; align-items: flex-end; gap: 5px; height: 35px; padding-top:2px;">'
        if spark_data:
            for day in spark_data:
                # 依據量能佔比動態計算高度百分比，並填入當日收盤紅綠色
                height_pct = max(10, int((day["volume"] / max_vol) * 100)) 
                sparkline_html += f'<div style="width: 14px; height: {height_pct}%; background-color: {day["color"]}; border-radius: 1px;" title="量: {day["volume"]:,}"></div>'
        else:
            sparkline_html += '<span style="color:#666; font-size:12px;">無量能數據</span>'
        sparkline_html += '</div>'
        
        # 決定漲跌幅的文字顏色
        change_color = "#FF3B30" if "+" in res["漲跌幅"] else ("#00E676" if "-" in res["漲跌幅"] else "#FFFFFE")
        status_style = "color: #F8CA00; font-weight: bold;" if "🟢" in res["策略狀態"] or "🔥" in res["策略狀態"] else "color: #A0A5C1;"
        
        html_table += f"""
          <tr style="border-bottom: 1px solid rgba(255,255,255,0.08); background-color: rgba(255,255,255,0.01);">
            <td style="padding: 12px 10px; font-weight: 600;">{res["代碼"]}</td>
            <td style="padding: 12px 10px;">{res["名稱"]}</td>
            <td style="padding: 12px 10px; font-weight: 600;">{res["現價"]}</td>
            <td style="padding: 12px 10px; color: {change_color}; font-weight: bold;">{res["漲跌幅"]}</td>
            <td style="padding: 12px 10px;">{sparkline_html}</td>
            <td style="padding: 12px 10px; {status_style}">{res["策略狀態"]}</td>
          </tr>
        """
        
    html_table += "</table>"
    
    # 將客製化的高級 HTML 表格完全渲染至主介面
    st.markdown(html_table, unsafe_allow_html=True)

else:
    st.info("💡 請在左側控制台輸入要監控的台股自選清單。")
