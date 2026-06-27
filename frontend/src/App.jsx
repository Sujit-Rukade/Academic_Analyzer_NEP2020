import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import Plot from "react-plotly.js";
import AiAdvisor from "./AiAdvisor";

const API_BASE = "http://127.0.0.1:8000";
const NEP_MAPPING_OPTIONS = [
  { id: "none", label: "None" },
  { id: "nep2020", label: "NEP 2020 Vertical Mapping" },
];

const NEP_VERTICAL_RULES = [
  {
    vertical: "STEM and Innovation",
    keywords: [
      "data structures",
      "algorithms",
      "programming",
      "c programming",
      "physics",
      "electronics",
      "mechanics",
      "network",
      "circuit",
      "quantum",
      "calculus",
      "algebra",
      "engineering",
      "lab",
    ],
  },
  {
    vertical: "Multidisciplinary and Holistic Education",
    keywords: [
      "language",
      "german",
      "human values",
      "professional development",
      "career readiness",
      "community engagement",
      "project",
      "seminar",
    ],
  },
  {
    vertical: "Skill Development and Employability",
    keywords: [
      "skill",
      "practical",
      "oral",
      "project",
      "workshop",
      "industry",
      "career",
      "development",
    ],
  },
];

function normalizeCourseLabel(courseName = "") {
  return String(courseName)
    .replace(/\((theory|practical|skill)\)/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

function mapToNepVertical(courseName = "") {
  const clean = normalizeCourseLabel(courseName).toLowerCase();
  for (const rule of NEP_VERTICAL_RULES) {
    if (rule.keywords.some((keyword) => clean.includes(keyword))) {
      return rule.vertical;
    }
  }
  return "Other / General";
}

function App() {
  const [uploadedFile, setUploadedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [convertedData, setConvertedData] = useState(null);
  const [activePage, setActivePage] = useState("home");
  const [selectedSubject, setSelectedSubject] = useState("");
  const [historyItems, setHistoryItems] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [historyActionId, setHistoryActionId] = useState("");
  const [analysisMappingMode, setAnalysisMappingMode] = useState("none");

  const studentBacklogData = convertedData?.studentBacklogData || {};
  const subjectBacklogData = convertedData?.subjectBacklogData || {};
  const chartsData = convertedData?.chartsData || {};

  const backlogStudents = useMemo(() => {
    const rows = [];
    Object.entries(studentBacklogData).forEach(([seatNo, data]) => {
      if ((data?.Count || 0) > 0) {
        rows.push({
          seatNo,
          name: data?.Name || "",
          backlogCount: data?.Count || 0,
          backlogCourses: (data?.Backlogs || []).join(", "),
        });
      }
    });
    return rows.sort((a, b) => b.backlogCount - a.backlogCount);
  }, [studentBacklogData]);

  const subjectRows = useMemo(() => {
    const rows = Object.entries(subjectBacklogData).map(([course, info]) => ({
      course,
      backlogCount: info?.Count || 0,
      students: (info?.Students || []).join(", "),
      studentsArr: info?.Students || [],
    }));
    return rows.sort((a, b) => b.backlogCount - a.backlogCount);
  }, [subjectBacklogData]);

  const selectedSubjectStudents =
    subjectBacklogData?.[selectedSubject]?.Students || [];

  const subjectChartEntries = useMemo(() => {
    return subjectRows
      .filter((row) => (row?.backlogCount || 0) > 0)
      .map((row) => [row.course, row.backlogCount])
      .sort((a, b) => b[1] - a[1])
      .slice(0, 20);
  }, [subjectRows]);

  const nepSummaryRows = useMemo(() => {
    const items = subjectRows.map((row) => {
      const mappedVertical = mapToNepVertical(row.course);
      return {
        course: normalizeCourseLabel(row.course),
        vertical: mappedVertical,
        backlogCount: row.backlogCount || 0,
      };
    });

    const summaryMap = new Map();
    items.forEach((item) => {
      if (!summaryMap.has(item.vertical)) {
        summaryMap.set(item.vertical, {
          vertical: item.vertical,
          courseCount: 0,
          totalBacklogs: 0,
        });
      }
      const current = summaryMap.get(item.vertical);
      current.courseCount += 1;
      current.totalBacklogs += item.backlogCount;
    });

    return Array.from(summaryMap.values()).sort(
      (a, b) => b.totalBacklogs - a.totalBacklogs
    );
  }, [subjectRows]);

  const nepMappedCourseRows = useMemo(() => {
    return subjectRows
      .map((row) => ({
        course: normalizeCourseLabel(row.course),
        mappedVertical: mapToNepVertical(row.course),
        backlogCount: row.backlogCount || 0,
      }))
      .sort((a, b) => b.backlogCount - a.backlogCount);
  }, [subjectRows]);

  const onUpload = (e) => {
    const file = e.target.files?.[0];
    setUploadedFile(file || null);
    setError("");
  };

  const onConvert = async () => {
    if (!uploadedFile) {
      setError("Please choose a PDF file first.");
      return;
    }
    setLoading(true);
    setError("");
    setActivePage("home");
    setSelectedSubject("");

    try {
      const formData = new FormData();
      formData.append("file", uploadedFile);
      const response = await axios.post(`${API_BASE}/api/convert`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setConvertedData(response.data);
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          "Conversion failed. Please verify PDF format and try again."
      );
    } finally {
      setLoading(false);
    }
  };

  const onDownload = () => {
    if (!convertedData?.fileId) return;
    window.open(`${API_BASE}/api/download/${convertedData.fileId}`, "_blank");
  };

  const onReset = () => {
    setUploadedFile(null);
    setLoading(false);
    setError("");
    setConvertedData(null);
    setActivePage("home");
    setSelectedSubject("");
    setAnalysisMappingMode("none");
    const input = document.getElementById("pdf-input");
    if (input) input.value = "";
  };

  const loadHistory = async () => {
    setHistoryLoading(true);
    setHistoryError("");
    try {
      const response = await axios.get(`${API_BASE}/api/conversions`, {
        params: { limit: 50 },
      });
      setHistoryItems(response.data?.items || []);
    } catch (err) {
      setHistoryError(
        err?.response?.data?.detail || "Unable to load conversion history."
      );
    } finally {
      setHistoryLoading(false);
    }
  };

  const onOpenHistoryItem = async (fileId) => {
    setHistoryActionId(fileId);
    setError("");
    try {
      const response = await axios.get(`${API_BASE}/api/conversions/${fileId}`);
      setConvertedData(response.data);
      setSelectedSubject("");
      setActivePage("home");
    } catch (err) {
      setError(
        err?.response?.data?.detail || "Unable to open selected history item."
      );
    } finally {
      setHistoryActionId("");
    }
  };

  const onDownloadHistoryItem = (fileId) => {
    window.open(`${API_BASE}/api/download/${fileId}`, "_blank");
  };

  useEffect(() => {
    if (activePage === "history") {
      loadHistory();
    }
  }, [activePage]);

  const metrics = convertedData?.metrics;
  const previewRows = convertedData?.dataframe?.previewRows || [];
  const totalRows = convertedData?.dataframe?.totalRows || 0;
  const previewColumns = convertedData?.dataframe?.columns || [];

  const hasData = Boolean(convertedData);

  return (
    <div className="app-shell">
      <header className="header-container">
        <h1 className="main-title">NEP Result Analysis System</h1>
        <p className="subtitle">
          Transform PDF Result Files into Comprehensive Excel Analytics
        </p>
      </header>

      <nav className="page-nav">
        <button
          className={`nav-btn ${activePage === "home" ? "nav-btn-active" : ""}`}
          onClick={() => setActivePage("home")}
        >
          Home
        </button>
        <button
          className={`nav-btn ${activePage === "backlogs" ? "nav-btn-active" : ""}`}
          onClick={() => setActivePage("backlogs")}
          disabled={!hasData}
        >
          Backlogs
        </button>
        <button
          className={`nav-btn ${activePage === "analysis" ? "nav-btn-active" : ""}`}
          onClick={() => setActivePage("analysis")}
          disabled={!hasData}
        >
          Analysis
        </button>
        <button
          className={`nav-btn ${activePage === "advisor" ? "nav-btn-active" : ""}`}
          onClick={() => setActivePage("advisor")}
          disabled={!hasData}
        >
          AI Advisor
        </button>
        <button
          className={`nav-btn ${activePage === "history" ? "nav-btn-active" : ""}`}
          onClick={() => setActivePage("history")}
        >
          History
        </button>
      </nav>

      {activePage === "home" && (
        <>
          <div className="upload-card">
            <label htmlFor="pdf-input" className="upload-label">
              Choose a PDF file containing student result data
            </label>
            <input id="pdf-input" type="file" accept=".pdf" onChange={onUpload} />
            {uploadedFile && (
              <div className="success-box">
                File "{uploadedFile.name}" uploaded successfully!
              </div>
            )}
            {error && <div className="error-box">{error}</div>}

            <button className="primary-btn" onClick={onConvert} disabled={loading}>
              {loading ? "Processing..." : "Convert PDF to Excel"}
            </button>
          </div>

          {hasData && (
            <>
              <section className="metrics-grid">
                <MetricCard value={metrics?.totalStudents} label="Total Students" />
                <MetricCard value={metrics?.coursesFound} label="Courses Found" />
                <MetricCard value={metrics?.totalBacklogs} label="Total Backlogs" />
                <MetricCard
                  value={metrics?.studentsWithBacklogs}
                  label="Students with Backlogs"
                />
              </section>

              <div className="actions-grid">
                <button className="btn-green" onClick={onDownload}>
                  Download Excel
                </button>
                <button className="btn-purple" onClick={() => setActivePage("backlogs")}>
                  View Backlogs
                </button>
                <button className="btn-purple" onClick={() => setActivePage("analysis")}>
                  Analyze Results
                </button>
                <button className="btn-purple" onClick={() => setActivePage("advisor")}>
                  Ask AI Advisor
                </button>
                <button className="btn-red" onClick={onReset}>
                  Process Another File
                </button>
              </div>

              <SectionTitle title="Data Preview" />
              <div className="info-box">
                Review the converted data to ensure accuracy before downloading or analyzing.
              </div>
              <SimpleTable
                columns={previewColumns}
                rows={previewRows.map((row) => previewColumns.map((col) => row[col] ?? ""))}
              />
              {totalRows > 10 && (
                <div className="info-box">
                  Showing first 10 rows out of {totalRows} total rows.
                </div>
              )}
            </>
          )}
        </>
      )}

      {activePage === "backlogs" && (
        <>
          {!hasData ? (
            <div className="info-box">No converted data found. Please upload and convert first.</div>
          ) : (
            <>
              <SectionTitle title="Students with Course Backlogs" />
              {backlogStudents.length === 0 ? (
                <div className="info-box">Currently, no students have backlogs.</div>
              ) : (
                <SimpleTable
                  columns={["#", "SEAT NO", "Name", "Backlog Count", "Backlog Courses"]}
                  wrapText
                  variant="backlogStudents"
                  rows={backlogStudents.map((row, idx) => [
                    idx + 1,
                    row.seatNo,
                    row.name,
                    row.backlogCount,
                    row.backlogCourses,
                  ])}
                />
              )}

              {subjectRows.length > 0 && (
                <>
                  <SectionTitle title="Course-wise Backlogs" />
                  <SimpleTable
                    columns={["#", "Course", "Backlog Count", "Students"]}
                    wrapText
                    variant="subjectBacklogs"
                    rows={subjectRows.map((row, idx) => [
                      idx + 1,
                      row.course,
                      row.backlogCount,
                      row.students,
                    ])}
                  />

                  <div className="subject-picker">
                    <label>Select a course to see students having a backlog in it</label>
                    <select
                      value={selectedSubject}
                      onChange={(e) => setSelectedSubject(e.target.value)}
                    >
                      <option value="">Select course</option>
                      {subjectRows.map((row) => (
                        <option key={row.course} value={row.course}>
                          {row.course}
                        </option>
                      ))}
                    </select>
                  </div>

                  {selectedSubject && (
                    <>
                      <SectionTitle title={`Students with backlog in: ${selectedSubject}`} />
                      <SimpleTable
                        columns={["#", "Student Name"]}
                        wrapText
                        variant="subjectStudents"
                        rows={selectedSubjectStudents.map((name, idx) => [idx + 1, name])}
                      />
                    </>
                  )}
                </>
              )}
            </>
          )}
        </>
      )}

      {activePage === "analysis" && (
        <>
          {!hasData ? (
            <div className="info-box">No converted data found. Please upload and convert first.</div>
          ) : (
            <>
              <SectionTitle title="Result Analysis" />
              <div className="mapping-control">
                <label htmlFor="mapping-mode-select">Analysis Mapping Option</label>
                <select
                  id="mapping-mode-select"
                  value={analysisMappingMode}
                  onChange={(e) => setAnalysisMappingMode(e.target.value)}
                >
                  {NEP_MAPPING_OPTIONS.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              {convertedData?.top3?.length > 0 && (
                <>
                  <SectionTitle title="Overall Top 3 Toppers" />
                  <SimpleTable
                    columns={Object.keys(convertedData.top3[0] || {})}
                    rows={convertedData.top3.map((r) => Object.values(r))}
                  />
                </>
              )}

              <div className="chart-grid">
                <Plot
                  data={[
                    {
                      type: "pie",
                      labels: Object.keys(chartsData?.backlogCounts || {}),
                      values: Object.values(chartsData?.backlogCounts || {}),
                      marker: {
                        colors: ["#156cbf", "#76b9ea"],
                      },
                      textinfo: "percent",
                      hovertemplate: "label=%{label}<br>value=%{value}<extra></extra>",
                    },
                  ]}
                  layout={{
                    title: "Overall Backlog Distribution",
                    height: 400,
                    margin: { l: 20, r: 20, t: 50, b: 20 },
                    legend: { orientation: "v", x: 0.95, y: 0.95 },
                    template: "plotly_white",
                  }}
                  config={{ responsive: true, displayModeBar: true, displaylogo: false }}
                  useResizeHandler
                  style={{ width: "100%", height: "100%" }}
                  className="chart-card"
                />

                <Plot
                  data={[
                    {
                      type: "bar",
                      x: Object.keys(chartsData?.backlogDistribution || {}),
                      y: Object.values(chartsData?.backlogDistribution || {}),
                      marker: {
                        color: Object.values(chartsData?.backlogDistribution || {}),
                        colorscale: "Reds",
                        showscale: true,
                        colorbar: { title: "color" },
                      },
                      hovertemplate:
                        "Number of Backlogs=%{x}<br>Number of Students=%{y}<br>color=%{y}<extra></extra>",
                    },
                  ]}
                  layout={{
                    title: "Distribution of Backlog Counts",
                    xaxis: { title: "Number of Backlogs" },
                    yaxis: { title: "Number of Students" },
                    height: 400,
                    margin: { l: 50, r: 20, t: 50, b: 50 },
                    showlegend: false,
                    template: "plotly_white",
                  }}
                  config={{ responsive: true, displayModeBar: true, displaylogo: false }}
                  useResizeHandler
                  style={{ width: "100%", height: "100%" }}
                  className="chart-card"
                />
              </div>

              {subjectChartEntries.length > 0 ? (
                <div className="subject-chart-wrap">
                  <Plot
                    data={[
                      {
                        type: "bar",
                        x: subjectChartEntries.map((item) => item[1]),
                        y: subjectChartEntries.map((item) => item[0]),
                        orientation: "h",
                        marker: {
                          color: subjectChartEntries.map((item) => item[1]),
                          colorscale: "Oranges",
                          showscale: true,
                          colorbar: { title: "color" },
                        },
                        hovertemplate:
                          "Subjects=%{y}<br>Number of Students=%{x}<br>color=%{x}<extra></extra>",
                      },
                    ]}
                    layout={{
                      title: "Subject-wise Backlog Analysis",
                      xaxis: { title: "Number of Students" },
                      yaxis: { title: "Subjects", automargin: true },
                      margin: { l: 320, r: 20, t: 60, b: 50 },
                      height: Math.max(420, subjectChartEntries.length * 55),
                      showlegend: false,
                      template: "plotly_white",
                    }}
                    config={{ responsive: true, displayModeBar: true, displaylogo: false }}
                    useResizeHandler
                    style={{ width: "100%", height: "100%" }}
                    className="chart-card"
                  />
                </div>
              ) : (
                <div className="info-box">
                  No subject-wise backlog data available for charting.
                </div>
              )}

              {analysisMappingMode === "nep2020" && (
                <>
                  <SectionTitle title="NEP 2020 Vertical Mapping Summary" />
                  {nepSummaryRows.length > 0 ? (
                    <>
                      <SimpleTable
                        columns={["#", "NEP 2020 Vertical", "Courses Mapped", "Total Backlogs"]}
                        wrapText
                        variant="nepSummary"
                        rows={nepSummaryRows.map((row, idx) => [
                          idx + 1,
                          row.vertical,
                          row.courseCount,
                          row.totalBacklogs,
                        ])}
                      />
                      <div className="nep-chart-wrap">
                        <Plot
                          data={[
                            {
                              type: "bar",
                              x: nepSummaryRows.map((item) => item.totalBacklogs),
                              y: nepSummaryRows.map((item) => item.vertical),
                              orientation: "h",
                              marker: {
                                color: nepSummaryRows.map((item) => item.totalBacklogs),
                                colorscale: "Blues",
                                showscale: true,
                                colorbar: { title: "Backlogs" },
                              },
                            },
                          ]}
                          layout={{
                            title: "Backlogs by NEP 2020 Vertical",
                            xaxis: { title: "Total Backlogs" },
                            yaxis: { title: "NEP 2020 Vertical", automargin: true },
                            height: Math.max(320, nepSummaryRows.length * 68),
                            margin: { l: 220, r: 20, t: 60, b: 50 },
                            showlegend: false,
                            template: "plotly_white",
                          }}
                          config={{ responsive: true, displayModeBar: true, displaylogo: false }}
                          useResizeHandler
                          style={{ width: "100%", height: "100%" }}
                          className="chart-card"
                        />
                      </div>
                    </>
                  ) : (
                    <div className="info-box">
                      No subject data available for NEP 2020 mapping.
                    </div>
                  )}

                  <SectionTitle title="Course to NEP 2020 Vertical Mapping" />
                  <SimpleTable
                    columns={["#", "Course", "Mapped NEP 2020 Vertical", "Backlog Count"]}
                    wrapText
                    variant="nepCourses"
                    rows={nepMappedCourseRows.map((row, idx) => [
                      idx + 1,
                      row.course,
                      row.mappedVertical,
                      row.backlogCount,
                    ])}
                  />
                </>
              )}
            </>
          )}
        </>
      )}

      {activePage === "advisor" && (
        <>
          {!hasData ? (
            <div className="info-box">
              No converted data found. Please upload and convert a PDF first.
            </div>
          ) : (
            <AiAdvisor
              fileId={convertedData.fileId}
              fileName={convertedData.uploadedFilename}
              apiBase={API_BASE}
            />
          )}
        </>
      )}

      {activePage === "history" && (
        <>
          <SectionTitle title="Conversion History" />
          {historyError && <div className="error-box">{historyError}</div>}
          {historyLoading ? (
            <div className="info-box">Loading history...</div>
          ) : historyItems.length === 0 ? (
            <div className="info-box">No previous conversions found.</div>
          ) : (
            <div className="table-wrap history-wrap">
              <table className="history-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>File Name</th>
                    <th>Total Students</th>
                    <th>Courses Found</th>
                    <th>Total Backlogs</th>
                    <th>Students With Backlogs</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {historyItems.map((item, idx) => (
                    <tr key={item.fileId}>
                      <td>{idx + 1}</td>
                      <td>{item.uploadedFilename}</td>
                      <td>{item.metrics?.totalStudents ?? 0}</td>
                      <td>{item.metrics?.coursesFound ?? 0}</td>
                      <td>{item.metrics?.totalBacklogs ?? 0}</td>
                      <td>{item.metrics?.studentsWithBacklogs ?? 0}</td>
                      <td>
                        <div className="history-actions">
                          <button
                            className="btn-purple history-btn"
                            onClick={() => onOpenHistoryItem(item.fileId)}
                            disabled={historyActionId === item.fileId}
                          >
                            {historyActionId === item.fileId ? "Opening..." : "Open"}
                          </button>
                          <button
                            className="btn-green history-btn"
                            onClick={() => onDownloadHistoryItem(item.fileId)}
                          >
                            Download
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function MetricCard({ value, label }) {
  return (
    <div className="metric-container">
      <div className="metric-value">{value ?? 0}</div>
      <div className="metric-label">{label}</div>
    </div>
  );
}

function SectionTitle({ title }) {
  return (
    <div className="section-header">
      <h3 className="section-title">{title}</h3>
    </div>
  );
}

function SimpleTable({ columns, rows, wrapText = false, variant = "" }) {
  if (!columns?.length) return null;
  return (
    <div
      className={`table-wrap ${wrapText ? "wrap-text" : ""} ${
        variant ? `variant-${variant}` : ""
      }`}
    >
      <table>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows?.length ? (
            rows.map((row, idx) => (
              <tr key={`r-${idx}`}>
                {row.map((cell, cIdx) => (
                  <td key={`c-${idx}-${cIdx}`}>{String(cell ?? "")}</td>
                ))}
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={columns.length}>No data available.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default App;
