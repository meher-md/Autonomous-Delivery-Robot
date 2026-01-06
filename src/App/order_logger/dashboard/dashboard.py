import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import os
from datetime import datetime

# Page Config
st.set_page_config(
    page_title="Delivery Bot Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
CSV_FILE = os.path.expanduser("~/ws/delivery_log.csv")
REFRESH_RATE = 5  # seconds

# Title with Style
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    h1 {
        color: #ff4b4b;
    }
    .stMetric {
        background-color: #262730;
        padding: 10px;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar Filters
st.sidebar.header("Filters")

# --- Branding (Sidebar) ---
# Display HTI Logo (Reverted to Original)
if os.path.exists("hti_logo.jpg"):
    st.sidebar.image("hti_logo.jpg", width=150)
    
st.sidebar.markdown("**Higher Technological Institute**")
st.sidebar.markdown("*10th of Ramadan City*")
st.sidebar.markdown("---")

# Main Page Branding (Robot Logo)
col_logo, col_title = st.columns([1, 4])
with col_logo:
    # Use Processed Dashboard Logo (Original Colors + Transparent)
    if os.path.exists("robot_logo_dashboard.png"):
        st.image("robot_logo_dashboard.png", width=180)
    elif os.path.exists("robot_logo_inverted.png"):
        st.image("robot_logo_inverted.png", width=180)
    elif os.path.exists("robot_logo_white.png"):
        st.image("robot_logo_white.png", width=180)
    elif os.path.exists("robot_logo_black.png"):
        st.image("robot_logo_black.png", width=180)
    else:
        st.write("🤖")

with col_title:
    st.title("Autonomous Delivery Dashboard")
    st.markdown("Real-time monitoring of delivery missions.")

# Date Filter
today = datetime.now().date()

@st.cache_data(ttl=5)
def load_data():
    if not os.path.exists(CSV_FILE):
        return pd.DataFrame()
    try:
        df = pd.read_csv(CSV_FILE)
        # Parse Dates
        df['Date_Full'] = pd.to_datetime(df['Date_Full'], errors='coerce').dt.date
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

# Main Loop placeholder for auto-refresh
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

df = load_data()

if df.empty:
    st.warning("⚠️ No data found. Waiting for first delivery...")
    st.stop()

# Apply Filters
st.sidebar.subheader("📅 Time Period")
filter_option = st.sidebar.radio(
    "Select Range:",
    ["All Time", "Today", "Last 7 Days", "Last 30 Days", "Last Year", "Custom Range"]
)

filtered_df = df.copy()
today_date = datetime.now().date()

# Convert Date_Full to datetime for comparison if not already
filtered_df['Date_Full'] = pd.to_datetime(filtered_df['Date_Full']).dt.date

if filter_option == "Today":
    filtered_df = filtered_df[filtered_df['Date_Full'] == today_date]
elif filter_option == "Last 7 Days":
    start_date = today_date - pd.Timedelta(days=7)
    filtered_df = filtered_df[filtered_df['Date_Full'] >= start_date]
elif filter_option == "Last 30 Days":
    start_date = today_date - pd.Timedelta(days=30)
    filtered_df = filtered_df[filtered_df['Date_Full'] >= start_date]
elif filter_option == "Last Year":
    start_date = today_date - pd.Timedelta(days=365)
    filtered_df = filtered_df[filtered_df['Date_Full'] >= start_date]
elif filter_option == "Custom Range":
    min_date = filtered_df['Date_Full'].min()
    max_date = filtered_df['Date_Full'].max()
    date_range = st.sidebar.date_input("Select Date Range", [min_date, max_date])
    if len(date_range) == 2:
        start_d, end_d = date_range
        filtered_df = filtered_df[
            (filtered_df['Date_Full'] >= start_d) & 
            (filtered_df['Date_Full'] <= end_d)
        ]
# "All Time" does nothing (keeps all)

# Status Filter
status_options = ["All"] + list(df['Order_Final_Status'].unique())
selected_status = st.sidebar.selectbox("Filter Status", status_options)

if selected_status != "All":
    filtered_df = filtered_df[filtered_df['Order_Final_Status'] == selected_status]

# --- KPIs ---
kp1, kp2, kp3, kp4 = st.columns(4)

total_orders = len(filtered_df)
delivered_count = len(filtered_df[filtered_df['Order_Final_Status'] == 'Delivered'])
success_rate = (delivered_count / total_orders * 100) if total_orders > 0 else 0

# Most Popular Location
if not filtered_df.empty:
    top_loc = filtered_df['Target_Location'].value_counts().idxmax()
else:
    top_loc = "N/A"

# Avg Trip Duration
avg_duration = 0.0
if not filtered_df.empty and 'Trip_Duration_Min' in filtered_df.columns:
    # Ensure numeric
    durs = pd.to_numeric(filtered_df['Trip_Duration_Min'], errors='coerce')
    avg_duration = durs.mean()
    if pd.isna(avg_duration): avg_duration = 0.0

kp1.metric("📦 Total Orders", total_orders)
kp2.metric("✅ Success Rate", f"{success_rate:.1f}%")
kp3.metric("📍 Top Destination", top_loc)
kp4.metric("🕒 Avg Trip Duration", f"{avg_duration:.1f} min")

st.divider()

# --- Charts ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📊 Orders Over Time")
    if not filtered_df.empty:
        # Group by Hour? Or just linear index if same day
        # Let's count per Location
        loc_counts = filtered_df['Target_Location'].value_counts().reset_index()
        loc_counts.columns = ['Location', 'Count']
        
        fig_bar = px.bar(loc_counts, x='Location', y='Count', color='Location', 
                         title="Orders by Destination", template="plotly_dark")
        st.plotly_chart(fig_bar, key="bar_chart")

with col2:
    st.subheader("📉 Order Status")
    if not filtered_df.empty:
        status_counts = filtered_df['Order_Final_Status'].value_counts()
        fig_pie = px.pie(values=status_counts.values, names=status_counts.index, 
                         title="Delivery Outcome", hole=0.4, template="plotly_dark")
        # Text inside = percent only
        fig_pie.update_traces(textposition='inside', textinfo='percent')
        # Legend (Label) = bottom center "under the ball"
        fig_pie.update_layout(
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.2,
                xanchor="center",
                x=0.5
            )
        )
        st.plotly_chart(fig_pie, key="pie_chart")

# --- Hourly Traffic Analysis (New Professional Feature) ---
st.subheader("🕒 Busy Hours Analysis")
if not filtered_df.empty:
    # Extract Hour safely
    # Time_Arrival format is HH:MM:SS
    def get_hour(t_str):
        try:
            return int(str(t_str).split(':')[0])
        except:
            return 0
            
    hours = filtered_df['Time_Arrival'].apply(get_hour)
    hour_counts = hours.value_counts().sort_index().reset_index()
    hour_counts.columns = ['Hour', 'Orders']
    
    fig_line = px.area(hour_counts, x='Hour', y='Orders', 
                       title="Order Volume by Hour of Day", 
                       template="plotly_dark", markers=True)
    fig_line.update_xaxes(tickmode='linear', dtick=1)
    st.plotly_chart(fig_line, key="hourly_chart")

# --- Recent Log Table (Styled) ---
st.subheader("📋 Recent Activity Log")

def highlight_status(val):
    color = '#28a745' if val == 'Delivered' else '#dc3545'
    return f'color: {color}; font-weight: bold;'

# Display with Pandas Styler
st.dataframe(
    filtered_df[['Time_Arrival', 'Order_ID', 'Target_Location', 'Order_Final_Status', 'Date_Full']]
    .sort_values(by='Time_Arrival', ascending=False)
    .style.map(highlight_status, subset=['Order_Final_Status']),
    hide_index=True
)

# --- Download Buttons (Sidebar) ---
st.sidebar.markdown("---")

# CSV Download
csv_data = filtered_df.to_csv(index=False).encode('utf-8')
st.sidebar.download_button(
    label="📥 Download CSV (Excel)",
    data=csv_data,
    file_name="delivery_report.csv",
    mime="text/csv"
)

# PDF Generation (Professional)
from fpdf import FPDF
import tempfile

# PDF Generation (Professional)
from fpdf import FPDF
import tempfile
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg') # Non-interactive backend

class PDFReport(FPDF):
    def header(self):
        # Logos for PDF
        # We enforce a smaller height/width to ensure they fit above the line.
        
        if os.path.exists("hti_logo.jpg"):
            self.image("hti_logo.jpg", 10, 5, 25) # Left Logo (Smaller, Y=5)
            
        # Use Robot Logo (Dashboard or Original)
        if os.path.exists("robot_logo_dashboard.png"):
             self.image("robot_logo_dashboard.png", 175, 5, 25)
        elif os.path.exists("robot_logo_orig.png"):
             self.image("robot_logo_orig.png", 175, 5, 25)
        elif os.path.exists("robot_logo_black.png"): # Fallback
            self.image("robot_logo_black.png", 175, 5, 25)

        # Title
        self.set_y(10) # Align Title with logos
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Autonomous Delivery Report', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(0, 5, 'Higher Technological Institute', 0, 1, 'C')
        
        # Line break
        self.ln(15) 
        self.set_draw_color(0, 80, 180) # Blue line
        self.set_line_width(1)
        # Draw line at Y=35
        self.line(10, 35, 200, 35)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Page {self.page_no()} - Generated by Delivery Bot Dashboard', 0, 0, 'C')

def create_pdf_charts(df):
    """Generates temporary chart images for PDF"""
    chart_paths = {}
    
    # 1. Pie Chart (Success vs Failed)
    if not df.empty:
        status_counts = df['Order_Final_Status'].value_counts()
        fig1, ax1 = plt.subplots(figsize=(5, 4))
        # Use simple colors
        colors = ['#28a745', '#dc3545', '#ffc107', '#17a2b8'] # Green, Red, Yellow, Cyan
        wedges, texts, autotexts = ax1.pie(status_counts, labels=status_counts.index, autopct='%1.1f%%', startangle=90, colors=colors)
        ax1.axis('equal')
        plt.title("Delivery Success Rate")
        
        # Save
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            plt.savefig(tmp.name, bbox_inches='tight')
            chart_paths['pie'] = tmp.name
        plt.close(fig1)

    # 2. Bar Chart (Orders by Location)
    if not df.empty:
        loc_counts = df['Target_Location'].value_counts()
        fig2, ax2 = plt.subplots(figsize=(6, 4))
        ax2.bar(loc_counts.index, loc_counts.values, color='#007bff')
        plt.title("Orders by Destination")
        plt.xlabel("Location")
        plt.ylabel("Count")
        
        # Save
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            plt.savefig(tmp.name, bbox_inches='tight')
            chart_paths['bar'] = tmp.name
        plt.close(fig2)
        
    return chart_paths

def generate_pdf(dataframe, period_name):
    pdf = PDFReport()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # --- 1. Report Info ---
    pdf.set_y(40) # Start below header
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(0)
    pdf.cell(0, 8, f"Period: {period_name}", 0, 1)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 0, 1)
    
    # --- 2. KPI Cards (Executive Summary) ---
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Executive Summary", 0, 1)
    
    # Calculations
    total = len(dataframe)
    delivered = len(dataframe[dataframe['Order_Final_Status'] == 'Delivered'])
    success_pct = (delivered / total * 100) if total > 0 else 0
    
    # Avg Trip Duration (Mock logic if real data missing, but let's try to parse 'Trip_Duration_Min')
    avg_dur = 0.0
    if not dataframe.empty and 'Trip_Duration_Min' in dataframe.columns:
         # Clean data: convert to numeric, coerce errors
         dems = pd.to_numeric(dataframe['Trip_Duration_Min'], errors='coerce')
         avg_dur = dems.mean()
         if pd.isna(avg_dur): avg_dur = 0.0
            
    # Draw 3 Cards
    # Y Position
    card_y = pdf.get_y() + 2
    card_w = 60
    card_h = 25
    gap = 5
    
    # Card 1: Total
    pdf.set_fill_color(240, 245, 255) # Light Blue
    pdf.rect(10, card_y, card_w, card_h, 'F')
    pdf.set_xy(10, card_y + 5)
    pdf.set_font("Arial", '', 10)
    pdf.cell(card_w, 5, "Total Missions", 0, 2, 'C')
    pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(0, 80, 180)
    pdf.cell(card_w, 10, f"{total}", 0, 0, 'C')
    
    # Card 2: Success
    pdf.set_fill_color(240, 255, 240) # Light Green
    pdf.rect(10 + card_w + gap, card_y, card_w, card_h, 'F')
    pdf.set_xy(10 + card_w + gap, card_y + 5)
    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(0)
    pdf.cell(card_w, 5, "Success Rate", 0, 2, 'C')
    pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(40, 167, 69)
    pdf.cell(card_w, 10, f"{success_pct:.1f}%", 0, 0, 'C')

    # Card 3: Avg Time
    pdf.set_fill_color(255, 250, 240) # Light Orange
    pdf.rect(10 + 2*(card_w + gap), card_y, card_w, card_h, 'F')
    pdf.set_xy(10 + 2*(card_w + gap), card_y + 5)
    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(0)
    pdf.cell(card_w, 5, "Avg Trip Duration", 0, 2, 'C')
    pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(255, 140, 0)
    pdf.cell(card_w, 10, f"{avg_dur:.1f} min", 0, 0, 'C')
    
    pdf.set_y(card_y + card_h + 10)
    
    # --- 3. Charts Section ---
    pdf.set_font("Arial", 'B', 14)
    pdf.set_text_color(0)
    pdf.cell(0, 10, "Analytics", 0, 1)
    
    # Generate Charts
    charts = create_pdf_charts(dataframe)
    
    # Embed Charts side-by-side
    start_y_charts = pdf.get_y()
    if 'pie' in charts:
        pdf.image(charts['pie'], x=15, y=start_y_charts, w=80)
    if 'bar' in charts:
        pdf.image(charts['bar'], x=110, y=start_y_charts, w=85)
        
    pdf.set_y(start_y_charts + 70) # Move down past charts
    
    # --- 4. Detailed Logs (Enhanced Table) ---
    pdf.set_font("Arial", 'B', 14)
    pdf.set_text_color(0, 50, 100)
    pdf.cell(0, 10, "Mission Logs (Recent 50)", 0, 1)
    pdf.ln(2)
    
    # Table Header
    # Cols: Date (25), Time (20), ID (30), Loc (30), Journey (20), Verification (40), Status (25) = 190 total
    pdf.set_font("Arial", 'B', 8) # Slightly smaller font for more cols
    pdf.set_fill_color(50, 50, 50) # Dark Gray Header
    pdf.set_text_color(255)
    
    cols = [
        ("Date", 25), ("Time", 20), ("Order ID", 30), ("Location", 30), 
        ("Journey", 20), ("Verification", 40), ("Status", 25)
    ]
    
    for col_name, width in cols:
        pdf.cell(width, 8, col_name, 1, 0, 'C', True)
    pdf.ln()
    
    # Table Rows
    pdf.set_font("Arial", '', 8)
    pdf.set_text_color(0)
    
    subset = dataframe.head(50)
    
    fill = False
    for index, row in subset.iterrows():
        # Alternating colors
        pdf.set_fill_color(240, 240, 240)
        
        date_str = str(row.get('Date_Full', 'N/A'))
        t_arr = str(row.get('Time_Arrival', 'N/A'))
        oid = str(row.get('Order_ID', 'N/A'))[:6] + ".." # Shorten ID further
        loc = str(row.get('Target_Location', 'N/A'))
        # Truncate location if too long
        if len(loc) > 12: loc = loc[:10] + ".."
            
        dur = str(row.get('Trip_Duration_Min', '0.0')) + "m"
        
        # Verify Logic
        qr_stat = str(row.get('QR_Scan_Status', ''))
        gest_stat = str(row.get('Client_Gesture_Status', ''))
        verify_txt = "N/A"
        
        if "Verified" in qr_stat:
            # Check for Like/Thumb
            if "Thumb" in gest_stat or "Like" in gest_stat:
                # Note: Standard FPDF fonts don't support emojis, using text to allow PDF generation.
                verify_txt = "QR + Like" 
            else:
                verify_txt = "QR"
        elif "Failed" in qr_stat:
             verify_txt = "Failed"
        
        status = str(row.get('Order_Final_Status', 'N/A'))
        
        # Row Cells
        pdf.cell(cols[0][1], 7, date_str, 1, 0, 'C', fill)
        pdf.cell(cols[1][1], 7, t_arr, 1, 0, 'C', fill)
        pdf.cell(cols[2][1], 7, oid, 1, 0, 'C', fill)
        pdf.cell(cols[3][1], 7, loc, 1, 0, 'C', fill)
        pdf.cell(cols[4][1], 7, dur, 1, 0, 'C', fill)
        pdf.cell(cols[5][1], 7, verify_txt, 1, 0, 'C', fill)
        
        # Color status
        if status == 'Delivered':
            pdf.set_text_color(0, 150, 0)
            pdf.set_font("Arial", 'B', 8)
        else:
            pdf.set_text_color(200, 0, 0)
            pdf.set_font("Arial", 'B', 8)
            
        pdf.cell(cols[6][1], 7, status, 1, 1, 'C', fill)
        
        # Reset font/color for next row
        pdf.set_text_color(0)
        pdf.set_font("Arial", '', 8)
        fill = not fill
        
    # Clean up charts
    for p in charts.values():
        if os.path.exists(p):
            os.remove(p)
            
    return pdf

# PDF Button
if st.sidebar.button("📄 Generate PDF Report"):
    with st.spinner("Generating PDF..."):
        try:
            # Generate PDF object
            pdf = generate_pdf(filtered_df, filter_option)
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                pdf.output(tmp_file.name)
                tmp_path = tmp_file.name
                
            # Read back binary
            with open(tmp_path, "rb") as f:
                pdf_bytes = f.read()
                
            st.sidebar.success("PDF Generated!")
            st.sidebar.download_button(
                label="⬇️ Download PDF",
                data=pdf_bytes,
                file_name=f"Report_{filter_option.replace(' ', '_')}.pdf",
                mime="application/pdf"
            )
            os.remove(tmp_path)
            
        except Exception as e:
            st.sidebar.error(f"Failed to generate PDF: {e}")

# Auto-Refresh Logic (Experimental)
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

# Auto Refresh using sleep loop in older Streamlit versions or st.empty?
# Streamlit reruns script on interaction. For auto-refresh we rely on user or st.autorefresh component (not installed).
# We can use a simple sleep loop if running as a dedicated dashboard, but standard way is manual refresh or st.rerun
