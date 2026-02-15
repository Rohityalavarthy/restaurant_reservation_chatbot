"""
GoodFoods AI Reservation Assistant
Main Streamlit Application
"""

import streamlit as st
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.conversation_manager import ConversationManager
from config.settings import settings

st.set_page_config(
    page_title=settings.APP_TITLE,
    page_icon=settings.APP_ICON,
    layout="centered",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stChatMessage {
        padding: 1rem;
        border-radius: 0.5rem;
    }
    .main-header {
        text-align: center;
        padding: 1rem 0;
        background: linear-gradient(135deg, #20808D 0%, #13343B 100%);
        color: white;
        border-radius: 0.5rem;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

if "conversation_manager" not in st.session_state:
    try:
        st.session_state.conversation_manager = ConversationManager()
    except ValueError as e:
        st.error(f"❌ Configuration Error: {e}")
        st.info("Please set TOGETHER_API_KEY in your .env file")
        st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []
    welcome = """👋 Welcome to GoodFoods! I'm your reservation assistant.

I can help you:
- 📅 Book tables at 50 locations across India
- ❌ Cancel bookings
- 📍 Get location information

Try: "Book a table for 4 tonight at 9pm in Juhu"
"""
    st.session_state.messages.append({"role": "assistant", "content": welcome})

st.markdown('<div class="main-header"><h1>🍝 GoodFoods AI Assistant</h1><p>Book tables across 50 locations in seconds</p></div>', unsafe_allow_html=True)

chat_container = st.container()

with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

if prompt := st.chat_input("Type your message..."):
    with st.chat_message("user"):
        st.markdown(prompt)
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("assistant"):
        with st.spinner("🤔 Thinking..."):
            try:
                response = st.session_state.conversation_manager.process_message(prompt)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
                
            except Exception as e:
                error_msg = f"❌ Sorry, I encountered an error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

with st.sidebar:
    st.header("About GoodFoods")
    
    st.markdown("""
    **GoodFoods** is a cult-favorite Italian fast-casual chain born in Mumbai's Bandra neighborhood, 
    now operating 50 locations across India's tier-1 cities.
    
    **Legendary for:** Our tiramisu cake 🍰 - consistently ranked among the world's top 10 desserts!
    """)
    
    st.divider()
    
    st.header("Quick Commands")
    
    st.markdown("""
    **New Booking:**
    - "Table for 4 tomorrow 8pm in Bandra"
    
    **Modify:**
    - "Change my time to 7:30pm"
    
    **Cancel:**
    - "Cancel my reservation"
    """)
    
    st.divider()
    
    st.header("System Stats")
    
    try:
        from utils.database import load_restaurants, load_reservations
        restaurants = load_restaurants()
        reservations = load_reservations()
        active_reservations = [r for r in reservations if r.get("status") == "confirmed"]
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("🏪 Locations", len(restaurants))
        with col2:
            st.metric("📅 Active Bookings", len(active_reservations))
            
    except Exception:
        pass
    
    st.divider()
    
    if st.button("🔄 Clear Conversation", use_container_width=True):
        st.session_state.conversation_manager.reset()
        st.session_state.messages = []
        st.rerun()
    
    st.caption(f"Powered by {settings.MODEL_NAME}")
