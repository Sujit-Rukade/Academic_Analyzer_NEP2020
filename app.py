
# from prompt_toolkit import prompt

import streamlit as st
import pandas as pd
import tempfile
import os
import json
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from result_parser import pdf_to_excel_wide
from rag_ingest import ingest_data_to_vector_db
from rag_agent import ask_rag_agent

# Page configuration
st.set_page_config(
    page_title="NEP Result Analysis System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Professional CSS styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    .main {
        padding: 2rem;
    }
    
    .header-container {
        background: linear-gradient(90deg, #1f4e79 0%, #2980b9 100%);
        color: white;
        padding: 2rem;
        border-radius: 8px;
        margin-bottom: 2rem;
        text-align: center;
    }
    
    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
        margin-bottom: 0.5rem;
    }
    
    .subtitle {
        font-size: 1.1rem;
        font-weight: 400;
        opacity: 0.9;
        margin: 0;
    }
    
    .section-header {
        background: #f8f9fa;
        border-left: 4px solid #2980b9;
        padding: 1rem 1.5rem;
        margin: 1.5rem 0;
        border-radius: 0 4px 4px 0;
    }
    
    .section-title {
        font-size: 1.3rem;
        font-weight: 600;
        color: #2c3e50;
        margin: 0;
    }
    
    .metric-container {
        background: white;
        border: 1px solid #e9ecef;
        border-radius: 6px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #2980b9;
        margin: 0;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #6c757d;
        font-weight: 500;
        margin-top: 0.5rem;
    }
    
    .success-box {
        background: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
        border-radius: 4px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .info-box {
        background: #d1ecf1;
        color: #0c5460;
        border: 1px solid #bee5eb;
        border-radius: 4px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .warning-box {
        background: #fff3cd;
        color: #856404;
        border: 1px solid #ffeaa7;
        border-radius: 4px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .error-box {
        background: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
        border-radius: 4px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .stButton > button {
        background: #2980b9;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 0.7rem 2rem;
        font-weight: 500;
        transition: background-color 0.3s ease;
    }
    
    .stButton > button:hover {
        background: #1f4e79;
    }
    
    .download-button {
        background: #27ae60 !important;
    }
    
    .download-button:hover {
        background: #2c3e50 !important;
    }
    
    .analysis-button {
        background: #8e44ad !important;
    }
    
    .analysis-button:hover {
        background: #6c3483 !important;
    }
    
    .reset-button {
        background: #e74c3c !important;
    }
    
    .reset-button:hover {
        background: #c0392b !important;
    }
    
    .backlog-student {
        background: #fff5f5;
        border-left: 4px solid #e53e3e;
        padding: 0.75rem;
        margin: 0.5rem 0;
        border-radius: 0 4px 4px 0;
    }
    
    .no-backlog-student {
        background: #f0fff4;
        border-left: 4px solid #38a169;
        padding: 0.75rem;
        margin: 0.5rem 0;
        border-radius: 0 4px 4px 0;
    }
    
    .subject-backlog {
        background: #fef5e7;
        border: 1px solid #f6cc3b;
        border-radius: 4px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

def create_analysis_charts(student_data, subject_data):
    """Create analysis charts from backlog data"""
    charts = {}
    
    # 1. Backlog Distribution Pie Chart
    backlog_counts = {"No Backlogs": 0, "With Backlogs": 0}
    backlog_distribution = {}
    
    for student_id, data in student_data.items():
        count = data['Count']
        if count == 0:
            backlog_counts["No Backlogs"] += 1
        else:
            backlog_counts["With Backlogs"] += 1
            if count not in backlog_distribution:
                backlog_distribution[count] = 0
            backlog_distribution[count] += 1
    
    fig_pie = px.pie(
        values=list(backlog_counts.values()), 
        names=list(backlog_counts.keys()),
        title="Overall Backlog Distribution",
        color_discrete_map={"No Backlogs": "#27ae60", "With Backlogs": "#e74c3c"}
    )
    fig_pie.update_layout(height=400)
    charts['pie'] = fig_pie
    
    # 2. Backlog Count Distribution Bar Chart
    if backlog_distribution:
        fig_bar = px.bar(
            x=list(backlog_distribution.keys()),
            y=list(backlog_distribution.values()),
            title="Distribution of Backlog Counts",
            labels={'x': 'Number of Backlogs', 'y': 'Number of Students'},
            color=list(backlog_distribution.values()),
            color_continuous_scale="Reds"
        )
        fig_bar.update_layout(height=400, showlegend=False)
        charts['bar'] = fig_bar
    
    # 3. Course-wise Backlog Analysis
    if subject_data:
        subjects = list(subject_data.keys())
        counts = [subject_data[sub]['Count'] for sub in subjects]
        
        fig_subjects = px.bar(
            x=counts,
            y=subjects,
            orientation='h',
            title="Course-wise Backlog Analysis",
            labels={'x': 'Number of Students', 'y': 'Courses'},
            color=counts,
            color_continuous_scale="Oranges"
        )
        fig_subjects.update_layout(height=max(400, len(subjects) * 50), showlegend=False)
        charts['subjects'] = fig_subjects
    
    return charts

def main():
    # Header
    st.markdown("""
    <div class="header-container">
        <h1 class="main-title">NEP Result Analysis System</h1>
        <p class="subtitle">Transform PDF Result Files into Comprehensive Excel Analytics</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'converted_df' not in st.session_state:
        st.session_state.converted_df = None
    if 'excel_buffer' not in st.session_state:
        st.session_state.excel_buffer = None
    if 'file_processed' not in st.session_state:
        st.session_state.file_processed = False
    if 'uploaded_filename' not in st.session_state:
        st.session_state.uploaded_filename = None
    if 'student_backlog_data' not in st.session_state:
        st.session_state.student_backlog_data = None
    if 'subject_backlog_data' not in st.session_state:
        st.session_state.subject_backlog_data = None
    if 'show_analysis' not in st.session_state:
        st.session_state.show_analysis = False
    if 'show_backlog_students' not in st.session_state:
        st.session_state.show_backlog_students = False
    
   
    uploaded_file = st.file_uploader(
        "Choose a PDF file containing student result data",
        type=['pdf'],
        help="Upload the PDF file that needs to be converted to Excel format."
    )
    
    if uploaded_file is not None:
        st.session_state.uploaded_filename = uploaded_file.name
        st.markdown(f'<div class="success-box">✅ File "{uploaded_file.name}" uploaded successfully!</div>', unsafe_allow_html=True)
        
        # Convert button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔄 Convert PDF to Excel", key="convert_btn", use_container_width=True):
                with st.spinner("🔄 Processing your PDF file... This may take a moment."):
                    try:
                        # Create temporary files
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
                            tmp_pdf.write(uploaded_file.getvalue())
                            tmp_pdf_path = tmp_pdf.name
                        
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_excel:
                            tmp_excel_path = tmp_excel.name
                        
                        # Create temporary JSON files
                        student_json_path = tempfile.mktemp(suffix='_students.json')
                        subject_json_path = tempfile.mktemp(suffix='_subjects.json')
                        
                        # Convert PDF to Excel using trial2.py function
                        pdf_to_excel_wide(tmp_pdf_path, tmp_excel_path, student_json_path, subject_json_path)
                        
                        # Read the converted Excel file
                        df = pd.read_excel(tmp_excel_path, engine='openpyxl')
                        
#                         from rag_ingest import ingest_data_to_vector_db
# from rag_agent import ask_rag_agent

# # ... inside the "Convert PDF to Excel" button logic in app.py ...
                        
#                         # Read the converted Excel file
#                         df = pd.read_excel(tmp_excel_path, engine='openpyxl')
                        
                        # Read JSON data for analysis
                        with open(student_json_path, 'r', encoding='utf-8') as f:
                            student_data = json.load(f)
                        with open(subject_json_path, 'r', encoding='utf-8') as f:
                            subject_data = json.load(f)
                            
                        # --- THE FIX: PASS THE DATAFRAME TO RAG ---
                        st.session_state.uploaded_filename = uploaded_file.name
                        ingest_data_to_vector_db(
                            st.session_state.uploaded_filename,
                            df,
                            student_backlog_data=student_data,
                            subject_backlog_data=subject_data,
                        )
                        # ------------------------------------------
                        
                        # Read JSON data for analysis
                        with open(student_json_path, 'r', encoding='utf-8') as f:
                            student_data = json.load(f)
                        with open(subject_json_path, 'r', encoding='utf-8') as f:
                            subject_data = json.load(f)
                        
                        # Store in session state
                        st.session_state.converted_df = df
                        st.session_state.student_backlog_data = student_data
                        st.session_state.subject_backlog_data = subject_data
                        st.session_state.file_processed = True
                        st.session_state.show_analysis = False
                        
                        # Create Excel buffer for download
                        excel_buffer = BytesIO()
                        df.to_excel(excel_buffer, index=False, engine='openpyxl')
                        excel_buffer.seek(0)
                        st.session_state.excel_buffer = excel_buffer
                        
                        # Clean up temporary files
                        for temp_file in [tmp_pdf_path, tmp_excel_path, student_json_path, subject_json_path]:
                            try:
                                os.unlink(temp_file)
                            except:
                                pass
                        
                        st.markdown('<div class="success-box">✅ Conversion completed successfully!</div>', unsafe_allow_html=True)
                        st.rerun()
                        
                    except Exception as e:
                        # st.markdown(f'<div class="error-box">❌ Error during conversion: {str(e)}</div>', unsafe_allow_html=True)
                        # st.error("Please ensure the PDF file follows the expected format and try again.")
                        import traceback
                        st.error("❌ Full Error:")
                        st.text(traceback.format_exc())
    
    # Preview and Analysis Section
    if st.session_state.file_processed and st.session_state.converted_df is not None:
        df = st.session_state.converted_df

        # Calculate metrics
        total_students = len(df)
        total_columns = len(df.columns)
        
        # Count unique course codes (prefix before first underscore)
        non_data_cols = {"SEAT NO", "Name", "Mother Name", "PRN", "SGPA"}
        course_cols = [col for col in df.columns if col not in non_data_cols]
        unique_courses = set()
        for col in course_cols:
            if '_' in col:
                unique_courses.add(col.split('_')[0])
        courses_found = len(unique_courses)
        
        # Calculate backlog statistics
        student_data = st.session_state.student_backlog_data
        total_backlogs = sum(data['Count'] for data in student_data.values())
        students_with_backlogs = len([data for data in student_data.values() if data['Count'] > 0])
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="metric-container">
                <div class="metric-value">{total_students}</div>
                <div class="metric-label">Total Students</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-container">
                <div class="metric-value">{courses_found}</div>
                <div class="metric-label">Courses Found</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-container">
                <div class="metric-value">{total_backlogs}</div>
                <div class="metric-label">Total Backlogs</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="metric-container">
                <div class="metric-value">{students_with_backlogs}</div>
                <div class="metric-label">Students with Backlogs</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(
                f"View {students_with_backlogs} students",
                key="view_backlog_students",
                use_container_width=True,
            ):
                st.session_state.show_backlog_students = True

        # Detailed list of students with backlogs (triggered by clicking above button)
        if st.session_state.show_backlog_students:
            backlog_students = []
            for seat_no, data in student_data.items():
                count = data.get("Count", 0)
                if count > 0:
                    backlog_students.append(
                        {
                            "SEAT NO": seat_no,
                            "Name": data.get("Name", ""),
                            "Backlog Count": count,
                            "Backlog Courses": ", ".join(data.get("Backlogs", [])),
                        }
                    )

            if backlog_students:
                backlog_df = (
                    pd.DataFrame(backlog_students)
                    .sort_values(by="Backlog Count", ascending=False)
                    .reset_index(drop=True)
                )
                backlog_df.index = range(1, len(backlog_df) + 1)
                st.markdown(
                    '<div class="section-header"><h3 class="section-title">📚 Students with Course Backlogs</h3></div>',
                    unsafe_allow_html=True,
                )
                try:
                    styler = backlog_df.style.set_properties(
                        subset=["Backlog Count"], **{"text-align": "left"}
                    ).set_properties(
                        subset=["Backlog Courses"],
                        **{"white-space": "normal", "word-break": "break-word"},
                    ).set_table_attributes('style="width: 100%; table-layout: fixed;"')
                    st.markdown(styler.to_html(), unsafe_allow_html=True)
                except Exception:
                    st.dataframe(backlog_df, use_container_width=True)

                # Course-wise backlog details: per course, list students having backlog
                subject_data = st.session_state.subject_backlog_data
                if subject_data:
                    subject_rows = []
                    for course_name, info in subject_data.items():
                        subject_rows.append(
                            {
                                "Course": course_name,
                                "Backlog Count": info.get("Count", 0),
                                "Students": ", ".join(info.get("Students", [])),
                            }
                        )

                    if subject_rows:
                        subject_df = (
                            pd.DataFrame(subject_rows)
                            .sort_values(by="Backlog Count", ascending=False)
                            .reset_index(drop=True)
                        )
                        subject_df.index = range(1, len(subject_df) + 1)
                        st.markdown(
                            '<div class="section-header"><h3 class="section-title">📚 Course-wise Backlogs</h3></div>',
                            unsafe_allow_html=True,
                        )
                        try:
                            subj_styler = subject_df.style.set_properties(
                                subset=["Backlog Count"], **{"text-align": "left"}
                            ).set_properties(
                                subset=["Students"],
                                **{"white-space": "normal", "word-break": "break-word"},
                            ).set_table_attributes('style="width: 100%; table-layout: fixed;"')
                            st.markdown(subj_styler.to_html(), unsafe_allow_html=True)
                        except Exception:
                            st.dataframe(subject_df, use_container_width=True)

                        # Per-subject: show list of students having backlog in the selected subject
                        subject_list = subject_df["Course"].tolist()
                        if subject_list:
                            selected_subject = st.selectbox(
                                "Select a course to see students having a backlog in it",
                                subject_list,
                                key="course_backlog_select",
                            )
                            if selected_subject:
                                students_in_subject = subject_data.get(
                                    selected_subject, {}
                                ).get("Students", [])
                                if students_in_subject:
                                    students_df = pd.DataFrame(
                                        {"Student Name": students_in_subject}
                                    )
                                    students_df.index = range(1, len(students_df) + 1)
                                    st.markdown(
                                        f'<div class="section-header"><h3 class="section-title">👨‍🎓 Students with backlog in: {selected_subject}</h3></div>',
                                        unsafe_allow_html=True,
                                    )
                                    st.dataframe(students_df, use_container_width=True)
            else:
                st.info("✅ Currently, no students have backlogs.")
        
        # Data Preview Section
        st.markdown('<div class="section-header"><h3 class="section-title">👀 Data Preview</h3></div>', unsafe_allow_html=True)
        st.markdown('<div class="info-box">📋 Review the converted data to ensure accuracy before downloading or analyzing.</div>', unsafe_allow_html=True)
        
        # Display dataframe
        st.dataframe(df.head(10), use_container_width=True, height=400)
        
        if len(df) > 10:
            st.info(f"📄 Showing first 10 rows out of {len(df)} total rows.")
        
        # Action Buttons
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.session_state.excel_buffer is not None:
                filename = f"NEP_Results_{st.session_state.uploaded_filename.replace('.pdf', '')}.xlsx"
                st.download_button(
                    label="💾 Download Excel",
                    data=st.session_state.excel_buffer.getvalue(),
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Download the converted Excel file",
                    use_container_width=True
                )
        
        with col2:
            if st.button("📊 Analyze Results", key="analyze_btn", use_container_width=True):
                st.session_state.show_analysis = True
                st.rerun()
        
        with col3:
            if st.button("🔄 Process Another File", key="reset_btn", use_container_width=True):
                # Clear session state
                for key in list(st.session_state.keys()):
                    if key.startswith(('converted_', 'excel_', 'file_', 'uploaded_', 'student_', 'subject_', 'show_')):
                        del st.session_state[key]
                st.rerun()
        
        # Analysis Section
        if st.session_state.show_analysis:
            st.markdown("---")
            st.markdown('<div class="section-header"><h2 class="section-title">📈 Result Analysis</h2></div>', unsafe_allow_html=True)

            # Overall Top 3 Toppers — use SGPA extracted directly from the PDF
            top3_df = None
            try:
                if "SGPA" in df.columns:
                    df_sgpa = df.copy()
                    df_sgpa["SGPA_num"] = pd.to_numeric(df_sgpa["SGPA"], errors="coerce")
                    valid = df_sgpa["SGPA_num"].notna()
                    if valid.any():
                        top3 = (
                            df_sgpa[valid]
                            .sort_values("SGPA_num", ascending=False)
                            .head(3)
                            .copy()
                        )
                        top3.insert(0, "Rank", range(1, len(top3) + 1))
                        cols_to_show = [c for c in ["Rank", "Name", "SEAT NO", "PRN", "SGPA"] if c in top3.columns]
                        top3_df = top3[cols_to_show].reset_index(drop=True)
                else:
                    # Fallback: compute GPA from CP / CRD columns
                    cp_cols  = [c for c in df.columns if c.endswith("_CP")]
                    crd_cols = [c for c in df.columns if c.endswith("_CRD")]
                    if cp_cols and crd_cols:
                        df_cp = df.copy()
                        df_cp[cp_cols + crd_cols] = df_cp[cp_cols + crd_cols].apply(pd.to_numeric, errors="coerce")
                        df_cp["Total_CP"]  = df_cp[cp_cols].sum(axis=1, skipna=True)
                        df_cp["Total_CRD"] = df_cp[crd_cols].sum(axis=1, skipna=True)
                        valid = df_cp["Total_CRD"] > 0
                        if valid.any():
                            df_cp.loc[valid, "GPA"] = df_cp.loc[valid, "Total_CP"] / df_cp.loc[valid, "Total_CRD"]
                            top3 = df_cp[valid].sort_values("GPA", ascending=False).head(3).copy()
                            top3.insert(0, "Rank", range(1, len(top3) + 1))
                            cols_to_show = [c for c in ["Rank", "Name", "SEAT NO", "PRN", "GPA"] if c in top3.columns]
                            top3_df = top3[cols_to_show].reset_index(drop=True)
            except Exception:
                top3_df = None

            if top3_df is not None and len(top3_df) > 0:
                st.markdown(
                    '<div class="section-header"><h3 class="section-title">🏆 Overall Top 3 Toppers</h3></div>',
                    unsafe_allow_html=True,
                )
                st.dataframe(top3_df, use_container_width=True)
            
            # Create and display charts
            if st.session_state.student_backlog_data and st.session_state.subject_backlog_data:
                charts = create_analysis_charts(st.session_state.student_backlog_data, st.session_state.subject_backlog_data)
                
                # Display charts
                col1, col2 = st.columns(2)
                
                with col1:
                    if 'pie' in charts:
                        st.plotly_chart(charts['pie'], use_container_width=True)
                
                with col2:
                    if 'bar' in charts:
                        st.plotly_chart(charts['bar'], use_container_width=True)
                
                if 'subjects' in charts:
                    st.plotly_chart(charts['subjects'], use_container_width=True)
                
            else:
                st.info("📊 No backlog data available for analysis.")
                
        if st.session_state.show_analysis:
            st.markdown("---")
            st.markdown('<div class="section-header"><h2 class="section-title">🤖 AI Assistant</h2></div>', unsafe_allow_html=True)
            
            # Initialize chat history
            if "messages" not in st.session_state:
                
                st.session_state.messages = []

            # Display chat messages
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            # Chat Input Box
            if prompt := st.chat_input("Ask about the results... (e.g., 'Which subject has the most backlogs?')"):
                # Add user message
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                # Add AI response
                with st.chat_message("assistant"):
                    with st.spinner("Analyzing student data..."):
                        try:
                            conversion_context = {
                                "subjectBacklogData": st.session_state.subject_backlog_data,
                                "studentBacklogData": st.session_state.student_backlog_data,
                            }
                            response = ask_rag_agent(
                                prompt,
                                st.session_state.uploaded_filename,
                                conversion_context,
                            )
                            st.markdown(response)
                            
                            # Only save to chat history if the call was successful
                            st.session_state.messages.append({"role": "assistant", "content": response})

                        except Exception as e:
                            error_msg = str(e)
                            st.warning(error_msg)
                            if "503" in error_msg:
                                st.warning("⚠️ Google's AI servers are currently experiencing peak global traffic. Please wait 15 seconds and try again.")
                            elif "429" in error_msg:
                                st.warning("⏳ We are analyzing data too quickly! Please wait 60 seconds for the speed limit to reset.")
                            else:
                                st.error("🚨 An unexpected error occurred. Please try asking a slightly different question.")
                                print(f"Backend Error: {error_msg}")

if __name__ == "__main__":
    main()