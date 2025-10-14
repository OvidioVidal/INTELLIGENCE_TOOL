#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M&A Intelligence Analytics Dashboard
Interactive Streamlit dashboard for visualizing deal intelligence data.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from analytics_calculator import AnalyticsCalculator
import pandas as pd
from datetime import datetime, timedelta
import json
from pathlib import Path
from send_email import EmailSender

# Page configuration
st.set_page_config(
    page_title="M&A Intelligence Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .big-metric {
        font-size: 48px;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
    }
    .metric-label {
        font-size: 18px;
        color: #666;
        text-align: center;
        margin-bottom: 10px;
    }
    .section-header {
        font-size: 24px;
        font-weight: bold;
        margin-top: 30px;
        margin-bottom: 15px;
        border-bottom: 2px solid #1f77b4;
        padding-bottom: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize calculator
# Note: Removed caching to ensure latest extraction logic is always used
# If you need caching for performance, add a version parameter: @st.cache_resource(ttl=3600)
def get_calculator():
    return AnalyticsCalculator()

calc = get_calculator()


# Helper functions for email config
def load_email_config():
    """Load email configuration from JSON file."""
    config_file = Path("email_config.json")
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "recipients": [],
            "smtp": {
                "server": "smtp.gmail.com",
                "port": 587,
                "username": "",
                "password": "",
                "from_address": "",
                "use_tls": True
            }
        }

def save_email_config(config):
    """Save email configuration to JSON file."""
    config_file = Path("email_config.json")
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

# Initialize session state for email config
if 'email_config' not in st.session_state:
    st.session_state.email_config = load_email_config()

# Sidebar - Filters
st.sidebar.title("📊 Dashboard Filters")
st.sidebar.markdown("---")

# Date range selector
period_options = {
    "All Time": "all",
    "Year to Date": "ytd",
    "Current Month": "current_month",
    "Custom Range": "custom"
}

selected_period_label = st.sidebar.selectbox(
    "Time Period",
    options=list(period_options.keys()),
    index=0
)

period = period_options[selected_period_label]

# Custom date range inputs
if period == "custom":
    st.sidebar.markdown("### Custom Date Range")
    col1, col2 = st.sidebar.columns(2)

    default_start = datetime.now() - timedelta(days=90)
    default_end = datetime.now()

    start_date = col1.date_input("Start Date", value=default_start)
    end_date = col2.date_input("End Date", value=default_end)

    period = f"{start_date},{end_date}"

st.sidebar.markdown("---")

# Email Settings Section
st.sidebar.title("📧 Email Settings")

with st.sidebar.expander("Manage Recipients", expanded=False):
    st.markdown("### Current Recipients")

    # Display current recipients with delete buttons
    config = st.session_state.email_config
    recipients = config.get('recipients', [])

    if recipients:
        for idx, recipient in enumerate(recipients):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.text(recipient)
            with col2:
                if st.button("🗑️", key=f"del_{idx}"):
                    recipients.pop(idx)
                    config['recipients'] = recipients
                    save_email_config(config)
                    st.session_state.email_config = config
                    st.rerun()
    else:
        st.info("No recipients configured")

    # Add new recipient
    st.markdown("### Add Recipient")
    new_recipient = st.text_input("Email address", key="new_recipient")
    if st.button("➕ Add Recipient", use_container_width=True):
        if new_recipient and '@' in new_recipient:
            if new_recipient not in recipients:
                recipients.append(new_recipient)
                config['recipients'] = recipients
                save_email_config(config)
                st.session_state.email_config = config
                st.success(f"Added {new_recipient}")
                st.rerun()
            else:
                st.warning("Recipient already exists")
        else:
            st.error("Invalid email address")

with st.sidebar.expander("SMTP Configuration", expanded=False):
    smtp_config = config.get('smtp', {})

    from_addr = st.text_input("From Address", value=smtp_config.get('from_address', ''))
    smtp_server = st.text_input("SMTP Server", value=smtp_config.get('server', 'smtp.gmail.com'))
    smtp_port = st.number_input("Port", value=smtp_config.get('port', 587), min_value=1, max_value=65535)
    smtp_user = st.text_input("Username", value=smtp_config.get('username', ''))
    smtp_pass = st.text_input("Password", value=smtp_config.get('password', ''), type="password")
    use_tls = st.checkbox("Use TLS", value=smtp_config.get('use_tls', True))

    if st.button("💾 Save SMTP Settings", use_container_width=True):
        smtp_config['from_address'] = from_addr
        smtp_config['server'] = smtp_server
        smtp_config['port'] = smtp_port
        smtp_config['username'] = smtp_user
        smtp_config['password'] = smtp_pass
        smtp_config['use_tls'] = use_tls
        config['smtp'] = smtp_config
        save_email_config(config)
        st.session_state.email_config = config
        st.success("SMTP settings saved!")

st.sidebar.markdown("---")

# Send Email Button
if st.sidebar.button("📨 Send Filtered Email", use_container_width=True, type="primary"):
    if not recipients:
        st.sidebar.error("No recipients configured!")
    elif not smtp_config.get('from_address'):
        st.sidebar.error("From address not configured!")
    else:
        with st.sidebar:
            with st.spinner("Sending email..."):
                try:
                    sender = EmailSender()
                    success = sender.send_from_config(filter_sectors=True)
                    if success:
                        st.success(f"✓ Email sent to {len(recipients)} recipient(s)!")
                    else:
                        st.error("Failed to send email. Check configuration.")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

st.sidebar.markdown("---")

# Refresh button
if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    st.cache_resource.clear()
    st.cache_data.clear()
    st.rerun()


# Main Dashboard
st.title("📊 M&A Intelligence Analytics Dashboard")
st.markdown(f"**Period:** {selected_period_label}")
st.markdown("---")

# Manual Email Section
st.markdown("## ✉️ Manual Email Composer")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### Paste Email Content")
    st.markdown("Enter subject and paste your raw email content:")

    # Subject field
    email_subject = st.text_input(
        label="Email Subject",
        placeholder="e.g., M&A Intelligence Weekly - January 2025",
        key="email_subject"
    )

    manual_email_input = st.text_area(
        label="Raw Email Input",
        height=250,
        placeholder="Paste your email content here...",
        key="manual_email_input",
        label_visibility="collapsed"
    )

    if st.button("🔄 Format Email", use_container_width=True, type="primary"):
        if not email_subject.strip():
            st.warning("Please enter an email subject first")
        elif not manual_email_input.strip():
            st.warning("Please paste email content first")
        else:
            # Save to input file and trigger pipeline
            with open('input_email.txt', 'w', encoding='utf-8') as f:
                f.write(manual_email_input)

            # Save subject for database import
            st.session_state.pending_email_subject = email_subject.strip()

            st.success("Email content saved! Processing...")

            # Trigger the pipeline
            try:
                import Input_mail_to_json
                import json_to_db
                import output_mail_composer

                # Step 1: Parse email
                Input_mail_to_json.main()

                # Step 2: Import to DB with subject
                # Modify the email metadata with subject from form
                with open('grouped.json', 'r', encoding='utf-8') as f:
                    grouped_data = json.load(f)

                # Add email metadata with subject
                email_metadata = {
                    "subject": st.session_state.pending_email_subject,
                    "timestamp": datetime.now().isoformat(),
                    "parsed_date": datetime.now().strftime("%Y-%m-%d")
                }

                # Import to database
                json_to_db.import_data(grouped_data, email_metadata)

                # Step 3: Compose output
                composer = output_mail_composer.EmailComposer()
                email_content = composer.compose_email()

                # Store in session state
                st.session_state.formatted_email = email_content

                st.success("✓ Email formatted and saved to database!")
                st.rerun()
            except Exception as e:
                st.error(f"Error processing email: {str(e)}")

with col2:
    st.markdown("### Formatted Output")
    st.markdown("Copy this formatted version:")

    if 'formatted_email' in st.session_state and st.session_state.formatted_email:
        formatted_output = st.text_area(
            label="Formatted Email Output",
            value=st.session_state.formatted_email,
            height=300,
            key="formatted_email_output",
            label_visibility="collapsed"
        )

        # Buttons row
        col_a, col_b = st.columns(2)

        with col_a:
            # Copy button using clipboard (experimental feature)
            if st.button("📋 Copy to Clipboard", use_container_width=True, type="secondary"):
                # Use st.write with javascript to copy to clipboard
                st.write("✓ Copied to clipboard!")
                # Use experimental clipboard API
                try:
                    import pyperclip
                    pyperclip.copy(st.session_state.formatted_email)
                except ImportError:
                    # Fallback: show instructions
                    st.info("Select the text above and press Ctrl+C (or Cmd+C on Mac) to copy")

        with col_b:
            # Download button for formatted email
            st.download_button(
                label="📥 Download File",
                data=st.session_state.formatted_email,
                file_name=f"formatted_email_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True
            )
    else:
        st.info("Formatted email will appear here after processing")

st.markdown("---")

# Key Metrics Row
st.markdown("## 🎯 Key Metrics")

# Check if database has data
try:
    total_all = calc.get_total_deals('all')
    has_data = total_all > 0
except Exception as e:
    has_data = False
    total_all = 0

if not has_data:
    st.info("📭 No data in the database yet. Use the Manual Email Composer above to import your first email!")
else:
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total Deals (All Time)",
            value=f"{total_all:,}",
            delta=None
        )

    with col2:
        total_mtd = calc.get_total_deals('current_month')
        st.metric(
            label="Deals This Month",
            value=f"{total_mtd:,}",
            delta=None
        )

    with col3:
        total_ytd = calc.get_total_deals('ytd')
        st.metric(
            label="Deals Year-to-Date",
            value=f"{total_ytd:,}",
            delta=None
        )

    with col4:
        sectors_df = calc.get_deals_by_sector(period)
        total_sectors = len(sectors_df)
        st.metric(
            label="Active Sectors",
            value=f"{total_sectors}",
            delta=None
        )

st.markdown("---")

# Sector Analysis Section
if has_data:
    st.markdown("## 📈 Sector Analysis")

    # Get sector data
    sectors_df = calc.get_deals_by_sector(period)

    if not sectors_df.empty:
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("### Deals by Sector")

            # Bar chart
            fig_bar = px.bar(
                sectors_df,
                x='sector',
                y='deal_count',
                title=f'Deal Count by Sector ({selected_period_label})',
                labels={'sector': 'Sector', 'deal_count': 'Number of Deals'},
                color='deal_count',
                color_continuous_scale='Blues'
            )
            fig_bar.update_layout(
                xaxis_tickangle=-45,
                height=500,
                showlegend=False
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with col2:
            st.markdown("### Sector Distribution")

            # Pie chart
            fig_pie = px.pie(
                sectors_df,
                values='deal_count',
                names='sector',
                title='Sector Share (%)',
                hole=0.4
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(height=500)
            st.plotly_chart(fig_pie, use_container_width=True)

        # Sector table with average deals per month
        st.markdown("### Sector Metrics Table")
        avg_deals_df = calc.get_average_deals_per_sector(period)

        # Format the dataframe for display
        avg_deals_df_display = avg_deals_df.copy()
        avg_deals_df_display.columns = ['Sector', 'Total Deals', 'Avg Deals/Month']
        avg_deals_df_display.index = range(1, len(avg_deals_df_display) + 1)

        st.dataframe(
            avg_deals_df_display,
            use_container_width=True,
            height=400
        )

    else:
        st.info("No sector data available for the selected period.")

    st.markdown("---")

    # Monthly Trend Section
    st.markdown("## 📅 Monthly Trends")

    monthly_trend = calc.get_sector_monthly_trend(months=12)

    if not monthly_trend.empty:
        # Line chart showing trends
        fig_trend = px.line(
            monthly_trend,
            x='month',
            y='deal_count',
            color='sector',
            title='Deal Volume Trends by Sector (Last 12 Months)',
            labels={'month': 'Month', 'deal_count': 'Number of Deals', 'sector': 'Sector'},
            markers=True
        )
        fig_trend.update_layout(
            height=500,
            hovermode='x unified'
        )
        st.plotly_chart(fig_trend, use_container_width=True)

        # Pivot table view
        with st.expander("📊 View Monthly Data Table"):
            pivot_table = monthly_trend.pivot(index='month', columns='sector', values='deal_count').fillna(0)
            pivot_table = pivot_table.astype(int)
            st.dataframe(pivot_table, use_container_width=True)

    else:
        st.info("No monthly trend data available.")

    st.markdown("---")

    # PE Firms Section
    st.markdown("## 🏢 Most Active PE Firms")

    top_firms = calc.get_top_pe_firms(limit=20, period=period)

    if not top_firms.empty:
        col1, col2 = st.columns([3, 2])

        with col1:
            st.markdown("### Top 20 PE Firms by Deal Count")

            # Bar chart
            fig_firms = px.bar(
                top_firms.head(20),
                x='deal_count',
                y='firm_name',
                orientation='h',
                title=f'Most Active PE Firms ({selected_period_label})',
                labels={'firm_name': 'PE Firm', 'deal_count': 'Number of Deals'},
                color='deal_count',
                color_continuous_scale='Viridis'
            )
            fig_firms.update_layout(
                height=600,
                yaxis={'categoryorder': 'total ascending'}
            )
            st.plotly_chart(fig_firms, use_container_width=True)

        with col2:
            st.markdown("### Ranking Table")

            # Formatted table
            top_firms_display = top_firms.copy()
            top_firms_display.index = range(1, len(top_firms_display) + 1)
            top_firms_display.columns = ['PE Firm', 'Deal Count']

            st.dataframe(
                top_firms_display,
                use_container_width=True,
                height=600
            )

    else:
        st.info("No PE firm data available for the selected period.")

    st.markdown("---")

    # Deal Quality Section
    st.markdown("## ⭐ Deal Quality & Geography")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Deals by Grade")
        deals_by_grade = calc.get_deals_by_grade(period)

        if not deals_by_grade.empty:
            fig_grade = px.pie(
                deals_by_grade,
                values='deal_count',
                names='grade',
                title='Deal Distribution by Grade',
                color_discrete_sequence=px.colors.sequential.RdBu
            )
            fig_grade.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_grade, use_container_width=True)

            # Table
            deals_by_grade_display = deals_by_grade.copy()
            deals_by_grade_display.columns = ['Grade', 'Count']
            st.dataframe(deals_by_grade_display, use_container_width=True)
        else:
            st.info("No grade data available.")

    with col2:
        st.markdown("### Geographic Breakdown")
        geo_breakdown = calc.get_geographic_breakdown(period)

        if not geo_breakdown.empty:
            fig_geo = px.bar(
                geo_breakdown,
                x='region',
                y='deal_count',
                title='Deals by Region',
                labels={'region': 'Region', 'deal_count': 'Number of Deals'},
                color='deal_count',
                color_continuous_scale='Greens'
            )
            st.plotly_chart(fig_geo, use_container_width=True)

            # Table
            geo_breakdown_display = geo_breakdown.copy()
            geo_breakdown_display.columns = ['Region', 'Count']
            st.dataframe(geo_breakdown_display, use_container_width=True)
        else:
            st.info("No geographic data available.")

    st.markdown("---")

    # Export Section
    st.markdown("## 💾 Export Data")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Export sector data
        if st.button("📥 Export Sector Data (CSV)", use_container_width=True):
            csv = sectors_df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"sector_data_{selected_period_label.lower().replace(' ', '_')}.csv",
                mime="text/csv",
                use_container_width=True
            )

    with col2:
        # Export PE firms data
        if st.button("📥 Export PE Firms (CSV)", use_container_width=True):
            csv = top_firms.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"pe_firms_{selected_period_label.lower().replace(' ', '_')}.csv",
                mime="text/csv",
                use_container_width=True
            )

    with col3:
        # Export monthly trend
        if st.button("📥 Export Monthly Trend (CSV)", use_container_width=True):
            csv = monthly_trend.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"monthly_trend_{selected_period_label.lower().replace(' ', '_')}.csv",
                mime="text/csv",
                use_container_width=True
            )

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; padding: 20px;'>
        <p>M&A Intelligence Analytics Dashboard</p>
        <p>Data updated from intelligence.db | Last refresh: {}</p>
    </div>
    """.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    unsafe_allow_html=True
)
