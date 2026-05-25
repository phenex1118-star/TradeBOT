import streamlit as st
import pandas as pd

st.set_page_config(page_title="視覺模擬器", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #232946; color: #FFFFFE; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 迷你 K 圖 (Sparklines) 視覺模擬器")

# ==========================================
# 方案一：Streamlit 官方原生方案 (BarChartColumn)
# ==========================================
st.subheader("▶️ 方案一：官方原生方案 (單色量能)")
st.caption("優點：效能極高，與表格完美融合。 缺點：全系統統一單色，無法區分單日紅綠。")

# 建立假數據陣列
data_native = {
    "股票代碼": ["2330.TW", "2454.TW", "2317.TW"],
    "名稱": ["台積電", "聯發科", "鴻海"],
    "近5日成交量": [[120, 150, 90, 200, 310], [50, 45, 60, 55, 80], [200, 180, 220, 190, 250]]
}
df_native = pd.DataFrame(data_native)

# 使用 Streamlit 內建圖表渲染
st.dataframe(
    df_native,
    column_config={
        "近5日成交量": st.column_config.BarChartColumn(
            "近5日成交量 (單色)",
            width="medium",
            y_min=0,
            y_max=350
        )
    },
    hide_index=True,
    use_container_width=True
)

st.write("---")

# ==========================================
# 方案二：SVG 動態渲染法 (台股紅綠量能棒)
# ==========================================
st.subheader("▶️ 方案二：SVG 動態渲染法 (紅綠漲跌量)")
st.caption("優點：視覺極致完美，台股紅綠分明。 缺點：需捨棄原生 dataframe，改用 HTML 表格排版。")

# 這裡使用 HTML 搭配 CSS Flexbox 來完美模擬量能柱狀圖
# 台股邏輯：紅柱 = 收盤上漲，綠柱 = 收盤下跌
html_table = """
<table style="width:100%; text-align:left; color:#FFFFFE; border-collapse: collapse; font-family: sans-serif;">
  <tr style="border-bottom: 1px solid #444; background-color: #121629;">
    <th style="padding: 12px;">股票代碼</th>
    <th style="padding: 12px;">名稱</th>
    <th style="padding: 12px;">近5日紅綠量能棒</th>
  </tr>
  
  <tr style="border-bottom: 1px solid #444;">
    <td style="padding: 12px;">2330.TW</td>
    <td style="padding: 12px;">台積電</td>
    <td style="padding: 12px;">
      <div style="display: flex; align-items: flex-end; gap: 4px; height: 35px;">
        <div style="width: 12px; height: 40%; background-color: #00E676; border-radius: 2px;"></div> <div style="width: 12px; height: 50%; background-color: #FF3B30; border-radius: 2px;"></div> <div style="width: 12px; height: 30%; background-color: #00E676; border-radius: 2px;"></div> <div style="width: 12px; height: 65%; background-color: #FF3B30; border-radius: 2px;"></div> <div style="width: 12px; height: 100%; background-color: #FF3B30; border-radius: 2px;"></div> </div>
    </td>
  </tr>
  
  <tr style="border-bottom: 1px solid #444;">
    <td style="padding: 12px;">2454.TW</td>
    <td style="padding: 12px;">聯發科</td>
    <td style="padding: 12px;">
      <div style="display: flex; align-items: flex-end; gap: 4px; height: 35px;">
        <div style="width: 12px; height: 60%; background-color: #FF3B30; border-radius: 2px;"></div>
        <div style="width: 12px; height: 50%; background-color: #00E676; border-radius: 2px;"></div>
        <div style="width: 12px; height: 70%; background-color: #FF3B30; border-radius: 2px;"></div>
        <div style="width: 12px; height: 65%; background-color: #FF3B30; border-radius: 2px;"></div>
        <div style="width: 12px; height: 90%; background-color: #FF3B30; border-radius: 2px;"></div>
      </div>
    </td>
  </tr>
</table>
"""

st.markdown(html_table, unsafe_allow_html=True)
