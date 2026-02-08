import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from app.core.data import get_lv_prices_15min, transform_for_pro_chart
from app.core.analysis import daily_average
from app.ui.locales import LANG_DATA

def run_ui():
    # 1. Настройка страницы (БЕЗ скрытия хедера, чтобы кнопка не пропадала)
    st.set_page_config(page_title="Energy Terminal", layout="wide")
    
    # 2. "Благородный" CSS: только для кнопок и скрытия футера
    st.markdown("""
        <style>
        /* Минималистичные кнопки-ссылки */
        .stButton > button {
            border: none !important;
            background: transparent !important;
            color: #888 !important;
            font-size: 14px !important;
            font-weight: 500 !important;
            padding: 0px !important;
            width: auto !important;
            min-width: 35px !important;
            white-space: nowrap !important;
        }
        .stButton > button:hover {
            color: #29b5e8 !important;
            background: transparent !important;
        }
        /* Скрываем только футер */
        footer {visibility: hidden;}
        /* Убираем красный декор в углу */
        [data-testid="stDecoration"] {display:none;}
        </style>
        """, unsafe_allow_html=True)

    # --- SIDEBAR: Control Panel ---
    with st.sidebar:
        st.title(":material/settings: Control Panel")

        # Переключатель языка (те самые благородные кнопки)
        if "lang" not in st.session_state: 
            st.session_state.lang = "en"
            
        # Увеличили пропорции колонок (0.15 вместо 0.1), чтобы текст не ломался
        l1, l2, _ = st.columns([0.15, 0.15, 0.7])
        with l1:
            if st.button("EN"): 
                st.session_state.lang = "en"
                st.rerun()
        with l2:
            if st.button("LV"): 
                st.session_state.lang = "lv"
                st.rerun()

        L = LANG_DATA[st.session_state.lang]
        st.divider()

        # Навигация
        page = st.radio(L['nav_label'], [L['nav_mon'], L['nav_plan']], index=0)

        # Переменные для планировщика
        target_price, power_kw = 0.15, 10.0
        if page == L['nav_plan']:
            st.divider()
            st.subheader(L['settings_header'])
            target_price = st.slider(L['threshold_label'], 0.0, 0.40, 0.15, step=0.01)
            power_kw = st.number_input(L['power_label'], min_value=0.0, value=10.0, step=1.0)

        st.divider()
        if st.button(L['btn'], icon=":material/sync:", type="primary", use_container_width=True):
            st.session_state.df = get_lv_prices_15min()
            st.rerun()

    # 3. АВТОЗАГРУЗКА ДАННЫХ
    if "df" not in st.session_state:
        st.session_state.df = get_lv_prices_15min()

    # 4. ОСНОВНОЙ КОНТЕНТ
    if "df" in st.session_state:
        df = st.session_state.df
        today_cols = [c for c in df.columns if "Today" in c]
        avg_price = daily_average(df[["Hour"] + today_cols])

        if page == L['nav_mon']:
            st.title(f":material/bolt: {L['title']}")
            c1, c2 = st.columns(2)
            c1.metric(L['avg_tod'], f"{avg_price:.4f} {L['unit']}")
            
            tom_cols = [c for c in df.columns if "Tomorrow" in c]
            if tom_cols:
                avg_tom = daily_average(df[["Hour"] + tom_cols])
                c2.metric(L['avg_tom'], f"{avg_tom:.4f} {L['unit']}", 
                          delta=f"{(avg_tom - avg_price):.4f}", delta_color="inverse")

            chart_data = transform_for_pro_chart(df)
            show_tom = st.toggle(L['tog'], value=False)
            plot_df = chart_data[chart_data['Day'] == "Today"]
            if show_tom and not chart_data[chart_data['Day'] == "Tomorrow"].empty:
                plot_df = chart_data
            
            st.line_chart(plot_df.set_index("Time")["Price"], color="#29b5e8")

            with st.expander(L['grid'], icon=":material/table_chart:"):
                st.dataframe(df, use_container_width=True)

        else:
            st.title(f":material/calculate: {L['plan_title']}")
            full_data = transform_for_pro_chart(df)
            cheap_windows = full_data[full_data['Price'] <= target_price].copy()

            if not cheap_windows.empty:
                cheap_windows = cheap_windows.sort_values('Time')
                blocks = []
                start_t = cheap_windows.iloc[0]['Time']
                prev_t = start_t
                for i in range(1, len(cheap_windows)):
                    curr_t = cheap_windows.iloc[i]['Time']
                    if curr_t - prev_t > timedelta(minutes=15):
                        blocks.append((start_t, prev_t, cheap_windows.iloc[i - 1]['Price']))
                        start_t = curr_t
                    prev_t = curr_t
                blocks.append((start_t, prev_t, cheap_windows.iloc[-1]['Price']))

                for start, end, price in blocks:
                    duration = (end - start).seconds / 3600 + 0.25
                    savings = (avg_price - price) * power_kw * duration
                    with st.container(border=True):
                        c_t, c_m = st.columns([0.4, 0.6])
                        time_str = f"{start.strftime('%H:%M')} - {(end + timedelta(minutes=15)).strftime('%H:%M')}"
                        c_t.subheader(f":material/schedule: {time_str}")
                        c_t.caption(f"{price:.4f} {L['unit']}")
                        if savings > 0:
                            c_m.success(f"{L['potential_savings']} **{savings:.2f} €**")
    else:
        st.info("Loading energy data...")