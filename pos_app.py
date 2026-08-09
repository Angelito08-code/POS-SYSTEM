import streamlit as st
import streamlit.components.v1 as components
import psycopg2
import pandas as pd
import os
from datetime import datetime

# ---------------------------------------------------------
# DATABASE & SETTINGS FUNCTIONS (SUPABASE / POSTGRESQL)
# ---------------------------------------------------------
def get_db_connection():
    host = None
    database = None
    user = None
    password = None
    port = "5432"

    # 1. Subukang basahin mula sa Streamlit Secrets
    try:
        if "supabase" in st.secrets:
            db_config = st.secrets["supabase"]
            host = db_config.get("host")
            database = db_config.get("database")
            user = db_config.get("user")
            password = db_config.get("password")
            port = str(db_config.get("port", "5432"))
    except Exception:
        pass

    # 2. Fallback sa Render Environment Variables kung wala sa secrets
    if not host:
        host = os.environ.get("SUPABASE_HOST")
        database = os.environ.get("SUPABASE_DATABASE")
        user = os.environ.get("SUPABASE_USER")
        password = os.environ.get("SUPABASE_PASSWORD")
        port = os.environ.get("SUPABASE_PORT", "5432")

    # 3. Suriin kung kumpleto ang mga detalye
    if not host or not database or not user or not password:
        st.error("🚨 **Database Configuration Error:** Kulang o walang laman ang iyong Supabase Environment Variables sa Render dashboard!")
        st.info("Pumunta sa iyong **Render Dashboard > Environment** at siguraduhing naidagdag mo ang mga sumusunod:\n- `SUPABASE_HOST`\n- `SUPABASE_DATABASE`\n- `SUPABASE_USER`\n- `SUPABASE_PASSWORD`\n- `SUPABASE_PORT`")
        st.stop()

    conn = psycopg2.connect(
        host=host,
        database=database,
        user=user,
        password=password,
        port=port
    )
    return conn
