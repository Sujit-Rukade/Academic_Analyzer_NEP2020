import { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const SUGGESTED_PROMPTS = [
  "Which subject has the most backlogs?",
  "Who are the top 3 students by SGPA?",
  "List students with more than 2 backlogs",
  "Summarize overall class performance",
  "Which courses have zero backlogs?",
];

export default function AiAdvisor({ fileId, fileName, apiBase }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [indexState, setIndexState] = useState("checking");
  const [indexError, setIndexError] = useState("");
  const [ragConfigured, setRagConfigured] = useState(true);
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const ensureIndexed = useCallback(async () => {
    if (!fileId) return;

    setIndexState("checking");
    setIndexError("");

    try {
      const statusRes = await axios.get(`${apiBase}/api/rag/status/${fileId}`);
      setRagConfigured(statusRes.data?.configured !== false);

      if (statusRes.data?.indexed) {
        setIndexState("ready");
        return;
      }

      setIndexState("indexing");
      const ingestRes = await axios.post(`${apiBase}/api/rag/ingest/${fileId}`);
      if (ingestRes.data?.indexed) {
        setIndexState("ready");
      } else {
        setIndexState("error");
        setIndexError(ingestRes.data?.error || "Failed to prepare data for AI queries.");
      }
    } catch (err) {
      setIndexState("error");
      setIndexError(
        err?.response?.data?.detail || "Unable to prepare result data for the AI advisor."
      );
    }
  }, [apiBase, fileId]);

  useEffect(() => {
    setMessages([]);
    setInput("");
    setLoading(false);
    ensureIndexed();
  }, [fileId, ensureIndexed]);

  const sendQuestion = async (question) => {
    const trimmed = question.trim();
    if (!trimmed || loading || indexState !== "ready") return;

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
    setLoading(true);

    try {
      const response = await axios.post(`${apiBase}/api/rag/ask`, {
        fileId,
        question: trimmed,
      });
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: response.data?.answer || "No response received." },
      ]);
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        "An unexpected error occurred. Please try a slightly different question.";
      setMessages((prev) => [...prev, { role: "assistant", content: detail, isError: true }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const onSubmit = (e) => {
    e.preventDefault();
    sendQuestion(input);
  };

  const onPromptClick = (prompt) => {
    if (loading || indexState !== "ready") return;
    sendQuestion(prompt);
  };

  const onClearChat = () => {
    setMessages([]);
    setInput("");
  };

  const isReady = indexState === "ready" && ragConfigured;
  const showConfigWarning = !ragConfigured;

  return (
    <div className="ai-advisor">
      <div className="ai-advisor-header">
        <div>
          <h3 className="ai-advisor-title">AI Academic Advisor</h3>
          <p className="ai-advisor-subtitle">
            Ask natural-language questions about{" "}
            <span className="ai-file-name">{fileName || "this result file"}</span>. Answers are
            grounded in your uploaded result data.
          </p>
        </div>
        <div className="ai-advisor-actions">
          <span className={`ai-status-badge ai-status-${indexState}`}>
            {indexState === "checking" && "Checking index..."}
            {indexState === "indexing" && "Indexing results..."}
            {indexState === "ready" && "Ready for questions"}
            {indexState === "error" && "Index unavailable"}
          </span>
          {messages.length > 0 && (
            <button type="button" className="ai-clear-btn" onClick={onClearChat}>
              Clear chat
            </button>
          )}
        </div>
      </div>

      {showConfigWarning && (
        <div className="error-box">
          AI advisor is not configured on the server. Add <code>GOOGLE_API_KEY</code> to your{" "}
          <code>.env</code> file and restart the backend.
        </div>
      )}

      {indexState === "error" && indexError && (
        <div className="error-box">
          {indexError}
          <button type="button" className="ai-retry-btn" onClick={ensureIndexed}>
            Retry indexing
          </button>
        </div>
      )}

      <div className="ai-suggested-prompts">
        <span className="ai-suggested-label">Suggested questions</span>
        <div className="ai-prompt-chips">
          {SUGGESTED_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              type="button"
              className="ai-prompt-chip"
              onClick={() => onPromptClick(prompt)}
              disabled={!isReady || loading}
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>

      <div className="ai-chat-panel">
        <div className="ai-chat-messages">
          {messages.length === 0 && !loading && (
            <div className="ai-empty-state">
              <div className="ai-empty-icon">🎓</div>
              <h4>Start a conversation</h4>
              <p>
                Ask about backlogs, toppers, subject performance, or individual student records.
                Pick a suggested question above or type your own below.
              </p>
            </div>
          )}

          {messages.map((message, idx) => (
            <div
              key={`msg-${idx}`}
              className={`ai-message ai-message-${message.role} ${
                message.isError ? "ai-message-error" : ""
              }`}
            >
              <div className="ai-message-avatar">
                {message.role === "user" ? "You" : "AI"}
              </div>
              <div className="ai-message-body">
                {message.role === "assistant" && !message.isError ? (
                  <div className="chat-markdown">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {message.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <p>{message.content}</p>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="ai-message ai-message-assistant">
              <div className="ai-message-avatar">AI</div>
              <div className="ai-message-body">
                <div className="ai-typing">
                  <span />
                  <span />
                  <span />
                  Analyzing student data...
                </div>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <form className="ai-chat-input-row" onSubmit={onSubmit}>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              isReady
                ? "Ask about the results... (e.g., 'Which subject has the most backlogs?')"
                : "Waiting for result data to be indexed..."
            }
            disabled={!isReady || loading}
          />
          <button type="submit" className="primary-btn ai-send-btn" disabled={!isReady || loading}>
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
